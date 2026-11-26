import random
import math
import time
from collections import defaultdict
from parse_data import parse_appendix
from solver import (
    BLACK_NEIGHBORS, NON_BLACK_ALLOWED, PAINT_C1_ONLY, PAINT_C2_ONLY,
    is_color_adj_valid, build_cars_by_day, assign_paint_lines_dp, evaluate_sequence
)

# Encode attributes as integers for fast SA
COLORS = ['黑', '白', '蓝', '黄', '红', '银', '棕', '灰', '金']
C_MAP = {c: i for i, c in enumerate(COLORS)}
BLK_ID = C_MAP['黑']
GOLD_ID = C_MAP['金']
YR_IDS = {C_MAP['黄'], C_MAP['红']}

# Precompute 9x9 adjacency matrix: ADJ_OK[c1][c2] -> bool
ADJ_OK = [[False] * 9 for _ in range(9)]
for c1_s in COLORS:
    for c2_s in COLORS:
        ADJ_OK[C_MAP[c1_s]][C_MAP[c2_s]] = is_color_adj_valid(c1_s, c2_s)


def construct_better_initial(day_cars):
    """
    Construct initial 28 segments (14 shifts x 2 brands) such that:
    - Every shift has [A1 | A2]
    - Inside A1: [NB_start (~12) | Black_1 (~65) | NB_mid (~35) | Black_2_A1]
    - Inside A2: [Black_2_A2 | NB_end (~15-30)]
    This guarantees Black_2 spans A1->A2, and NB_end + next NB_start >= 20!
    """
    shifts = []
    for d_idx, cars in enumerate(day_cars):
        a1_all = [c for c in cars if c['brand'] == 'A1']
        a2_all = [c for c in cars if c['brand'] == 'A2']
        n_a1_day = (len(a1_all) + 1) // 2
        n_a2_day = len(a2_all) // 2

        def split_balanced(lst, n_first):
            lst_sorted = sorted(lst, key=lambda x: (x['color'], x['drive'], x['power'], x['config']))
            first, second = [], []
            for i, c in enumerate(lst_sorted):
                if i % 2 == 0 and len(first) < n_first:
                    first.append(c)
                elif len(second) < len(lst) - n_first:
                    second.append(c)
                else:
                    first.append(c)
            return first, second

        a1_day, a1_night = split_balanced(a1_all, n_a1_day)
        a2_day, a2_night = split_balanced(a2_all, n_a2_day)
        shifts.append((a1_day, a2_day))
        shifts.append((a1_night, a2_night))

    segments = []  # 28 lists of car dicts
    for s_idx, (a1, a2) in enumerate(shifts):
        a1_blk = [c for c in a1 if c['color'] == '黑']
        a1_nb = [c for c in a1 if c['color'] != '黑']
        a2_blk = [c for c in a2 if c['color'] == '黑']
        a2_nb = [c for c in a2 if c['color'] != '黑']

        # Put ~15 white/non-black at start of A1 so previous shift's A2_nb + this >= 20
        a1_whites = [c for c in a1_nb if c['color'] == '白']
        a1_other_nb = [c for c in a1_nb if c['color'] != '白']
        n_start = min(15, len(a1_whites))
        nb_start = a1_whites[:n_start]
        nb_mid = a1_whites[n_start:] + a1_other_nb

        tot_blk = len(a1_blk) + len(a2_blk)
        b1_len = min(tot_blk // 2, len(a1_blk))
        b1 = a1_blk[:b1_len]
        b2_a1 = a1_blk[b1_len:]

        segments.append(nb_start + b1 + nb_mid + b2_a1)
        segments.append(a2_blk + a2_nb)

    return segments


def compute_full_cost(flat_cars):
    """
    Fast integer-based cost function on flat list of tuples:
    (color_id, config_id, is_4wd, is_diesel, brand_id)
    Returns (hard_viol_cost, soft_cost, details_dict)
    """
    N = len(flat_cars)
    c_adj_viol = 0
    gold_fb = 0
    cfg_sw = 0

    blk_len_viol = 0
    blk_gap_viol = 0
    blk_run = 0
    last_blk_end = -1000

    fwd_consec = 0
    fwd_lt5 = 0
    fwd_5_9 = 0
    fwd_run = 0
    last_fwd_end = -1000

    dsl_consec = 0
    dsl_lt5 = 0
    dsl_5_9 = 0
    dsl_run = 0
    last_dsl_end = -1000

    color_sw = 0  # assembly line color switches (proxy for keeping colors grouped)

    for i in range(N):
        col, cfg, fwd, dsl, br = flat_cars[i]

        if i > 0:
            pcol, pcfg, _, _, pbr = flat_cars[i - 1]
            if not ADJ_OK[pcol][col]:
                c_adj_viol += 1
            if br == pbr and cfg != pcfg:
                cfg_sw += 1
            if col != pcol:
                color_sw += 1

        if col == GOLD_ID:
            ok_yr = False
            if i > 0 and flat_cars[i - 1][0] in YR_IDS:
                ok_yr = True
            elif i + 1 < N and flat_cars[i + 1][0] in YR_IDS:
                ok_yr = True
            if not ok_yr:
                gold_fb += 1

        # Black
        if col == BLK_ID:
            if blk_run == 0 and last_blk_end >= 0:
                gap = i - last_blk_end - 1
                if gap < 20:
                    blk_gap_viol += (20 - gap)
            blk_run += 1
        else:
            if blk_run > 0:
                if blk_run < 50:
                    blk_len_viol += (50 - blk_run)
                elif blk_run > 70:
                    blk_len_viol += (blk_run - 70)
                last_blk_end = i - 1
                blk_run = 0

        # 4WD
        if fwd:
            if fwd_run == 0 and last_fwd_end >= 0:
                gap = i - last_fwd_end - 1
                if gap < 5:
                    fwd_lt5 += (5 - gap)
                elif gap < 10:
                    fwd_5_9 += (10 - gap)
            fwd_run += 1
            if fwd_run > 2:
                fwd_consec += 1
        else:
            if fwd_run > 0:
                last_fwd_end = i - 1
                fwd_run = 0

        # Diesel
        if dsl:
            if dsl_run == 0 and last_dsl_end >= 0:
                gap = i - last_dsl_end - 1
                if gap < 5:
                    dsl_lt5 += (5 - gap)
                elif gap < 10:
                    dsl_5_9 += (10 - gap)
            dsl_run += 1
            if dsl_run > 2:
                dsl_consec += 1
        else:
            if dsl_run > 0:
                last_dsl_end = i - 1
                dsl_run = 0

    if blk_run > 0:
        if blk_run < 50:
            blk_len_viol += (50 - blk_run)
        elif blk_run > 70:
            blk_len_viol += (blk_run - 70)

    hard = (
        c_adj_viol * 50000
        + blk_len_viol * 10000
        + blk_gap_viol * 10000
        + fwd_consec * 20000
        + fwd_lt5 * 10000
        + dsl_consec * 20000
        + dsl_lt5 * 10000
    )
    soft = (
        fwd_5_9 * 500
        + dsl_5_9 * 500
        + gold_fb * 200
        + cfg_sw * 10
        + color_sw * 5
    )
    return hard + soft, {
        'c_adj': c_adj_viol,
        'blk_len': blk_len_viol,
        'blk_gap': blk_gap_viol,
        'fwd_consec': fwd_consec,
        'fwd_lt5': fwd_lt5,
        'fwd_5_9': fwd_5_9,
        'dsl_consec': dsl_consec,
        'dsl_lt5': dsl_lt5,
        'dsl_5_9': dsl_5_9,
        'gold_fb': gold_fb,
        'cfg_sw': cfg_sw,
        'color_sw': color_sw,
    }


def run_sa(segments, max_seconds=15.0, seed=42):
    rng = random.Random(seed)
    # Build flat list and segment offsets
    # Keep original car dicts in parallel
    seg_dicts = [list(s) for s in segments]
    seg_tuples = []
    for s in seg_dicts:
        seg_tuples.append([
            (C_MAP[c['color']], int(c['config'][1:]), 1 if c['drive'] == '四驱' else 0,
             1 if c['power'] == '柴油' else 0, 0 if c['brand'] == 'A1' else 1)
            for c in s
        ])

    def flatten():
        res = []
        for st in seg_tuples:
            res.extend(st)
        return res

    flat = flatten()
    cur_cost, cur_det = compute_full_cost(flat)
    best_cost = cur_cost
    best_det = dict(cur_det)
    best_dicts = [list(s) for s in seg_dicts]

    print(f"Start cost={cur_cost}, det={cur_det}")

    t_start = time.time()
    temp = 2000.0
    temp_end = 1.0
    iters = 0

    while True:
        elapsed = time.time() - t_start
        if elapsed >= max_seconds:
            break
        frac = elapsed / max_seconds
        temp = 2000.0 * ((temp_end / 2000.0) ** frac)

        iters += 1
        move_type = rng.random()

        if move_type < 0.65:
            # Swap two cars in same segment
            k = rng.randrange(28)
            st = seg_tuples[k]
            sd = seg_dicts[k]
            n = len(st)
            if n < 2:
                continue
            i = rng.randrange(n)
            j = rng.randrange(n)
            if i == j or st[i] == st[j]:
                continue
            st[i], st[j] = st[j], st[i]
            sd[i], sd[j] = sd[j], sd[i]

            nflat = flatten()
            ncost, ndet = compute_full_cost(nflat)
            delta = ncost - cur_cost
            if delta <= 0 or rng.random() < math.exp(-delta / temp):
                cur_cost, cur_det = ncost, ndet
                if cur_cost < best_cost:
                    best_cost = cur_cost
                    best_det = dict(cur_det)
                    best_dicts = [list(s) for s in seg_dicts]
            else:
                st[i], st[j] = st[j], st[i]
                sd[i], sd[j] = sd[j], sd[i]

        elif move_type < 0.85:
            # Relocate single car within same segment
            k = rng.randrange(28)
            st = seg_tuples[k]
            sd = seg_dicts[k]
            n = len(st)
            if n < 3:
                continue
            i = rng.randrange(n)
            j = rng.randrange(n)
            if i == j:
                continue
            t_item = st.pop(i)
            d_item = sd.pop(i)
            st.insert(j, t_item)
            sd.insert(j, d_item)

            nflat = flatten()
            ncost, ndet = compute_full_cost(nflat)
            delta = ncost - cur_cost
            if delta <= 0 or rng.random() < math.exp(-delta / temp):
                cur_cost, cur_det = ncost, ndet
                if cur_cost < best_cost:
                    best_cost = cur_cost
                    best_det = dict(cur_det)
                    best_dicts = [list(s) for s in seg_dicts]
            else:
                st.pop(j)
                sd.pop(j)
                st.insert(i, t_item)
                sd.insert(i, d_item)

        else:
            # Swap between Day and Night shift of same day and same brand
            d = rng.randrange(7)
            b = rng.randrange(2)
            k1 = 4 * d + b
            k2 = 4 * d + 2 + b
            st1, sd1 = seg_tuples[k1], seg_dicts[k1]
            st2, sd2 = seg_tuples[k2], seg_dicts[k2]
            i = rng.randrange(len(st1))
            j = rng.randrange(len(st2))
            if st1[i] == st2[j]:
                continue
            st1[i], st2[j] = st2[j], st1[i]
            sd1[i], sd2[j] = sd2[j], sd1[i]

            nflat = flatten()
            ncost, ndet = compute_full_cost(nflat)
            delta = ncost - cur_cost
            if delta <= 0 or rng.random() < math.exp(-delta / temp):
                cur_cost, cur_det = ncost, ndet
                if cur_cost < best_cost:
                    best_cost = cur_cost
                    best_det = dict(cur_det)
                    best_dicts = [list(s) for s in seg_dicts]
            else:
                st1[i], st2[j] = st2[j], st1[i]
                sd1[i], sd2[j] = sd2[j], sd1[i]

    print(f"SA finished {iters} iters in {max_seconds:.1f}s: best_cost={best_cost}, det={best_det}")
    res = []
    for s in best_dicts:
        res.extend(s)
    return res


if __name__ == '__main__':
    data = parse_appendix('/home/tc-zhoubin/code/lab02/2018-D-Chinese/CUMCM-2018-Problem-D-Chinese-Appendix.xlsx')
    days, day_cars = build_cars_by_day(data)
    segs = construct_better_initial(day_cars)
    best_seq = run_sa(segs, max_seconds=10.0, seed=42)
    lines, dp_val = assign_paint_lines_dp(best_seq)
    m = evaluate_sequence(best_seq, lines)
    print("\nFinal full evaluation:")
    for k, v in m.items():
        print(f"  {k}: {v}")
