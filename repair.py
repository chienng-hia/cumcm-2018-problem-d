from parse_data import parse_appendix
from solver import (
    build_cars_by_day, is_color_adj_valid, assign_paint_lines_dp, evaluate_sequence
)

COLORS = ['黑', '白', '蓝', '黄', '红', '银', '棕', '灰', '金']

def load_best_order(path, day_cars):
    # Reconstruct segments from best_order.txt
    # Map (day, id) -> car dict
    rows = [list(map(int, line.split())) for line in open(path)]
    # Group into 28 segments based on (day, shift, brand)
    segs = []
    cur_seg = []
    cur_day = rows[0][0]
    cur_br = rows[0][2]
    # Note: within each day, order of brands is A1(day), A2(day), A1(night), A2(night)
    for r in rows:
        d, cid, br, cfg, dsl, fwd, col = r
        if d != cur_day or br != cur_br:
            segs.append(cur_seg)
            cur_seg = []
            cur_day = d
            cur_br = br
        c = dict(day_cars[d][cid])
        cur_seg.append(c)
    if cur_seg:
        segs.append(cur_seg)
    assert len(segs) == 28, f"Expected 28 segments, got {len(segs)}"
    return segs


def hard_score(seq):
    m = evaluate_sequence(seq, lines=None)
    hard = (
        m['color_adj_viol'] * 100
        + m['blk_len_viol'] * 100
        + m['blk_gap_viol'] * 100
        + m['4wd_consec_viol'] * 100
        + m['4wd_gap_lt5'] * 100
        + m['diesel_consec_viol'] * 100
        + m['diesel_gap_lt5'] * 100
    )
    soft = (
        m['4wd_gap_5_9'] * 10
        + m['diesel_gap_5_9'] * 10
        + m['gold_fallback'] * 5
    )
    return hard, soft, m


def flatten(segs):
    res = []
    for s in segs:
        res.extend(s)
    return res


def repair_segments(segs):
    seq = flatten(segs)
    h, s, m = hard_score(seq)
    print(f"Before repair: hard={h}, soft={s}, m={m}")

    # Compute segment offsets
    for it in range(20):
        if h == 0 and s == 0:
            break
        improved = False
        # Find positions with violations
        seq = flatten(segs)
        N = len(seq)
        bad_segs = set()

        # Find bad positions
        offsets = []
        pos = 0
        for k, seg in enumerate(segs):
            offsets.append((pos, pos + len(seg)))
            pos += len(seg)

        def seg_of(idx):
            for k, (a, b) in enumerate(offsets):
                if a <= idx < b:
                    return k
            return 0

        for i in range(N - 1):
            if not is_color_adj_valid(seq[i]['color'], seq[i + 1]['color']):
                bad_segs.add(seg_of(i))
                bad_segs.add(seg_of(i + 1))

        # 4WD and Diesel violations
        for attr in ('drive', 'power'):
            val = '四驱' if attr == 'drive' else '柴油'
            run = 0
            last_end = None
            for i, c in enumerate(seq):
                if c[attr] == val:
                    if run == 0 and last_end is not None and (i - last_end - 1) < 10:
                        bad_segs.add(seg_of(i))
                        bad_segs.add(seg_of(last_end))
                    run += 1
                    if run > 2:
                        bad_segs.add(seg_of(i))
                else:
                    if run > 0:
                        last_end = i - 1
                        run = 0

        if not bad_segs:
            break

        # Only try moving/swapping cars near violations, or into/out of bad positions!
        # Find exact bad indices
        bad_indices = set()
        for i in range(N - 1):
            if not is_color_adj_valid(seq[i]['color'], seq[i + 1]['color']):
                bad_indices.add(i)
                bad_indices.add(i + 1)
        for attr in ('drive', 'power'):
            val = '四驱' if attr == 'drive' else '柴油'
            run = 0
            last_end = None
            for i, c in enumerate(seq):
                if c[attr] == val:
                    if run == 0 and last_end is not None and (i - last_end - 1) < 10:
                        bad_indices.add(i)
                        bad_indices.add(last_end)
                    run += 1
                    if run > 2:
                        bad_indices.add(i - 2)
                        bad_indices.add(i - 1)
                        bad_indices.add(i)
                else:
                    if run > 0:
                        last_end = i - 1
                        run = 0

        # Prioritize hard violations first!
        # Group bad_indices by segment
        color_bad_segs = {}
        for i in range(N - 1):
            if not is_color_adj_valid(seq[i]['color'], seq[i + 1]['color']):
                k = seg_of(i)
                color_bad_segs.setdefault(k, set()).add(i - offsets[k][0])
                k2 = seg_of(i + 1)
                color_bad_segs.setdefault(k2, set()).add(i + 1 - offsets[k2][0])

        seg_bad = {}
        for idx in sorted(bad_indices):
            k = seg_of(idx)
            seg_bad.setdefault(k, []).append(idx - offsets[k][0])

        for k, local_idxs in seg_bad.items():
            n = len(segs[k])
            # 1) Relocate each bad car to any position in seg k
            for i in local_idxs:
                c_item = segs[k].pop(i)
                for j in range(n):
                    if i == j:
                        continue
                    segs[k].insert(j, c_item)
                    nh, ns, nm = hard_score(flatten(segs))
                    if (nh, ns) < (h, s):
                        h, s, m = nh, ns, nm
                        improved = True
                        print(f"  Relocate in seg {k} ({i}->{j}): hard={h}, soft={s}")
                        break
                    segs[k].pop(j)
                if improved:
                    break
                segs[k].insert(i, c_item)
            if improved:
                break

            # 1b) Try block relocate ONLY on color_bad_segs
            if not improved and k in color_bad_segs:
                for i_bad in sorted(color_bad_segs[k]):
                    for start in range(max(0, i_bad - 10), i_bad + 1):
                        for L in range(2, min(14, n - start)):
                            if not (start <= i_bad < start + L):
                                continue
                            blk = segs[k][start:start + L]
                            del segs[k][start:start + L]
                            for j in range(len(segs[k]) + 1):
                                if j == start:
                                    continue
                                if j > 0 and not is_color_adj_valid(segs[k][j - 1]['color'], blk[0]['color']):
                                    continue
                                if j < len(segs[k]) and not is_color_adj_valid(blk[-1]['color'], segs[k][j]['color']):
                                    continue
                                segs[k][j:j] = blk
                                nh, ns, nm = hard_score(flatten(segs))
                                if (nh, ns) < (h, s):
                                    h, s, m = nh, ns, nm
                                    improved = True
                                    print(f"  Block relocate in seg {k} ({start}:{start+L}->{j}): hard={h}, soft={s}")
                                    break
                                del segs[k][j:j + L]
                            if improved:
                                break
                            segs[k][start:start] = blk
                        if improved:
                            break
                    if improved:
                        break
            if improved:
                break

            # 2) Swap each bad car with any car in partner segment
            d = k // 4
            b = k % 2
            k2 = (4 * d + 2 + b) if (k % 4 < 2) else (4 * d + b)
            for i in local_idxs:
                for j in range(len(segs[k2])):
                    if segs[k][i] == segs[k2][j]:
                        continue
                    segs[k][i], segs[k2][j] = segs[k2][j], segs[k][i]
                    nh, ns, nm = hard_score(flatten(segs))
                    if (nh, ns) < (h, s):
                        h, s, m = nh, ns, nm
                        improved = True
                        print(f"  Cross-swap seg {k}[{i}] <-> seg {k2}[{j}]: hard={h}, soft={s}")
                        break
                    segs[k][i], segs[k2][j] = segs[k2][j], segs[k][i]
                if improved:
                    break
            if improved:
                break

        if not improved:
            print("No more single-move improvements found.")
            break

    seq = flatten(segs)
    lines, dp_val = assign_paint_lines_dp(seq)
    m = evaluate_sequence(seq, lines)
    print("\nAfter repair full evaluation:")
    for k, v in m.items():
        print(f"  {k}: {v}")

    import json
    with open('/home/tc-zhoubin/code/lab02/final_solution.json', 'w') as f:
        json.dump({'seq': seq, 'lines': lines}, f, ensure_ascii=False)
    print("Saved final_solution.json")
    return segs, seq, lines


if __name__ == '__main__':
    data = parse_appendix('/home/tc-zhoubin/code/lab02/2018-D-Chinese/CUMCM-2018-Problem-D-Chinese-Appendix.xlsx')
    days, day_cars = build_cars_by_day(data)
    segs = load_best_order('/home/tc-zhoubin/code/lab02/best_order.txt', day_cars)
    repair_segments(segs)
