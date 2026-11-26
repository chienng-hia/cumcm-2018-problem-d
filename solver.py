import random
import math
import time
from collections import Counter, defaultdict
from parse_data import parse_appendix

# Color adjacency rules on assembly line (excluding Black-to-Black and Black boundary)
# Black boundary: Black <-> {白, 棕, 灰, 银}
BLACK_NEIGHBORS = {'白', '棕', '灰', '银'}

NON_BLACK_ALLOWED = {
    '白': {'白', '蓝', '棕'},
    '蓝': {'白'},
    '黄': {'银', '灰', '棕', '金'},
    '红': {'银', '灰', '棕', '金'},
    '金': {'黄', '红', '灰', '棕', '银'},  # 黄/红 preferred, 灰/棕/银 fallback
    '灰': {'灰', '银', '黄', '红', '金'},
    '银': {'银', '灰', '黄', '红', '金'},
    '棕': {'棕', '白', '黄', '红', '金'},
}

PAINT_C1_ONLY = {'蓝', '黄', '红'}
PAINT_C2_ONLY = {'金'}


def is_color_adj_valid(c1, c2):
    if c1 == '黑' and c2 == '黑':
        return True
    if c1 == '黑':
        return c2 in BLACK_NEIGHBORS
    if c2 == '黑':
        return c1 in BLACK_NEIGHBORS
    return c2 in NON_BLACK_ALLOWED[c1]


def build_cars_by_day(data):
    """Expand aggregated counts into individual car dicts per day."""
    days = sorted(data.keys())
    day_cars = []
    for d_idx, d in enumerate(days):
        cars = []
        for item in data[d]:
            for _ in range(item['count']):
                cars.append({
                    'day': d_idx,
                    'date': d,
                    'brand': item['brand'],
                    'config': item['config'],
                    'power': item['power'],
                    'drive': item['drive'],
                    'color': item['color'],
                })
        day_cars.append(cars)
    return days, day_cars


def construct_initial_sequence(day_cars, rng):
    """
    Construct an initial 3220-car sequence respecting:
    - Day/Night shift brand counts (A1 then A2)
    - Black batches of 50-70 with >=20 gap
    - Valid color adjacency within non-Black blocks
    - 4WD and Diesel spaced out
    """
    shifts = []  # 14 shifts, each is (a1_list, a2_list)

    for d_idx, cars in enumerate(day_cars):
        a1_all = [c for c in cars if c['brand'] == 'A1']
        a2_all = [c for c in cars if c['brand'] == 'A2']
        # Split into day & night
        n_a1_day = (len(a1_all) + 1) // 2  # 184 on day 6, exact half on days 0..5
        n_a2_day = len(a2_all) // 2        # 46 on day 6, exact half on days 0..5

        # Stratified split by (color, drive, power, config) so day/night are balanced
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

    # Helper to order a non-Black block satisfying color adjacency and config grouping
    def order_non_black(nb_cars):
        if not nb_cars:
            return []
        by_color = defaultdict(list)
        for c in nb_cars:
            by_color[c['color']].append(c)
        for col in by_color:
            by_color[col].sort(key=lambda x: (x['config'], x['drive'], x['power']))

        # Build valid color sequence:
        # 1) Start with 白 (and interleave 蓝 inside 白: 白-蓝-白-蓝-白...)
        # 2) Then 棕 (can border 白 and 黄/红/金/灰/银? Wait: 棕 cannot border 灰/银!
        #    棕 can border 白, 黄, 红, 金! And 黄/红/金 can border 灰/银!
        #    So: 白/蓝 -> 棕 -> (黄/红/金 interleaved with 灰/银/棕) -> 灰/银 -> 白?
        #    Wait: 灰/银 CANNOT border 黑? Yes they can! And 白/棕 can border 黑!
        #    Wait: 灰/银 CANNOT border 白! So 白 -> 棕 -> 黄/红 -> 灰/银 works!
        seq = []

        # Put 白 and 蓝 first
        whites = by_color['白']
        blues = by_color['蓝']
        if blues:
            # Need at least len(blues)+1 whites if possible, or place blues between whites
            w_idx = 0
            if w_idx < len(whites):
                seq.append(whites[w_idx]); w_idx += 1
            for b in blues:
                seq.append(b)
                if w_idx < len(whites):
                    seq.append(whites[w_idx]); w_idx += 1
            while w_idx < len(whites):
                seq.append(whites[w_idx]); w_idx += 1
        else:
            seq.extend(whites)

        # Put 棕 next (borders 白 on left, and can border 黄/红/金 or 黑 on right)
        browns = by_color['棕']
        # Keep some browns if needed to interleave 黄/红/金
        yr = by_color['黄'] + by_color['红']
        golds = by_color['金']
        grays = by_color['灰'] + by_color['银']

        # Interleave 金 with 黄/红 first, then remaining 黄/红 with 灰/银/棕
        interleaved = []
        # How many separators (灰/银/棕) do we need?
        # Each 黄/红/金 needs to alternate with 灰/银/棕 or (金 with 黄/红).
        # Simple pattern: [棕...] -> [黄/红 - 金 - 黄/红 - 金 ...] -> [灰/银 - 黄/红 - 灰/银 ...] -> [剩余 灰/银]
        yr_idx = 0
        g_idx = 0
        gs_idx = 0
        b_idx = 0

        # Use browns before starting yr/gold
        # Leave 1 brown if needed? Usually grays >= yr
        seq.extend(browns)

        while yr_idx < len(yr) or g_idx < len(golds):
            if yr_idx < len(yr):
                # Before placing yr, if last in seq is yr/gold/white/blue/black, need separator
                if not seq or seq[-1]['color'] not in {'银', '灰', '棕', '金'}:
                    if gs_idx < len(grays):
                        seq.append(grays[gs_idx]); gs_idx += 1
                seq.append(yr[yr_idx]); yr_idx += 1
            if g_idx < len(golds):
                # 金 prefers 黄/红, fallback 灰/银/棕
                if seq and seq[-1]['color'] in {'黄', '红', '灰', '银', '棕'}:
                    seq.append(golds[g_idx]); g_idx += 1
                else:
                    if gs_idx < len(grays):
                        seq.append(grays[gs_idx]); gs_idx += 1
                    seq.append(golds[g_idx]); g_idx += 1
            else:
                # Next is yr, so add a gray/silver separator
                if yr_idx < len(yr) and gs_idx < len(grays):
                    seq.append(grays[gs_idx]); gs_idx += 1

        # Append remaining grays/silvers (can border 黑 at the end!)
        if gs_idx < len(grays):
            # If last is 白 or 蓝, grays cannot directly follow 白!
            # (Already handled if browns or yr/gold came after 白, unless browns=yr=gold=0)
            seq.extend(grays[gs_idx:])

        return seq

    # Arrange each shift:
    # A1: [Black_1 (~65)] + [NonBlack_A1] + [Black_2_A1 (rest of A1 Black)]
    # A2: [Black_2_A2 (all of A2 Black)] + [NonBlack_A2]
    # Let's check Black_2 size = len(Black_2_A1) + len(Black_2_A2):
    # Since total Black in shift is ~127..139, if Black_1 = total_Black_in_shift // 2 (~64..69),
    # then Black_2 = total_Black_in_shift - Black_1 (~63..70), both in [50, 70]!
    full_seq = []
    for s_idx, (a1, a2) in enumerate(shifts):
        a1_blk = [c for c in a1 if c['color'] == '黑']
        a1_nb = [c for c in a1 if c['color'] != '黑']
        a2_blk = [c for c in a2 if c['color'] == '黑']
        a2_nb = [c for c in a2 if c['color'] != '黑']

        tot_blk = len(a1_blk) + len(a2_blk)
        b1_len = tot_blk // 2
        # Ensure b1_len <= len(a1_blk)
        b1_len = min(b1_len, len(a1_blk))

        a1_blk.sort(key=lambda x: (x['config'], x['drive'], x['power']))
        a2_blk.sort(key=lambda x: (x['config'], x['drive'], x['power']))

        b1 = a1_blk[:b1_len]
        b2_a1 = a1_blk[b1_len:]
        nb1 = order_non_black(a1_nb)
        nb2 = order_non_black(a2_nb)

        shift_seq = b1 + nb1 + b2_a1 + a2_blk + nb2
        full_seq.extend(shift_seq)

    return full_seq


def assign_paint_lines_dp(seq):
    """
    Given assembly sequence `seq` of length N, find optimal paint line assignment (C1/C2)
    using DP to minimize:
    - Black <-> non-Black switches (high cost = 100)
    - Other color switches (cost = 10)
    - Slight load balance tie-breaker
    """
    N = len(seq)
    # State: (last_c1_color, last_c2_color) - wait, state space is 9*9 = 81!
    # 81 * 3220 = 260,820 operations -> runs in < 0.2s in Python!
    COLORS = ['黑', '白', '蓝', '黄', '红', '银', '棕', '灰', '金']
    C_IDX = {c: i for i, c in enumerate(COLORS)}
    BLK = C_IDX['黑']

    INF = 10**12
    # dp[c1][c2] = min cost
    dp = [[INF] * 9 for _ in range(9)]
    # Initialize at car 0
    c0 = C_IDX[seq[0]['color']]
    back = []

    # Start with dummy "none" by just paying 0 for first car on each line?
    # Better: use 10 states (0..8 = color, 9 = empty)
    dp = [[INF] * 10 for _ in range(10)]
    dp[9][9] = 0

    for t in range(N):
        col = seq[t]['color']
        ci = C_IDX[col]
        can_c1 = col not in PAINT_C2_ONLY
        can_c2 = col not in PAINT_C1_ONLY

        ndp = [[INF] * 10 for _ in range(10)]
        nbk = [[None] * 10 for _ in range(10)]

        for c1 in range(10):
            row = dp[c1]
            for c2 in range(10):
                val = row[c2]
                if val >= INF:
                    continue
                if can_c1:
                    cost = 0
                    if c1 != 9 and c1 != ci:
                        cost = 100 if (c1 == BLK or ci == BLK) else 10
                    nv = val + cost
                    if nv < ndp[ci][c2]:
                        ndp[ci][c2] = nv
                        nbk[ci][c2] = (1, c1, c2)
                if can_c2:
                    cost = 0
                    if c2 != 9 and c2 != ci:
                        cost = 100 if (c2 == BLK or ci == BLK) else 10
                    nv = val + cost
                    if nv < ndp[c1][ci]:
                        ndp[c1][ci] = nv
                        nbk[c1][ci] = (2, c1, c2)
        dp = ndp
        back.append(nbk)

    # Backtrack
    best_val = INF
    best_state = None
    for c1 in range(10):
        for c2 in range(10):
            if dp[c1][c2] < best_val:
                best_val = dp[c1][c2]
                best_state = (c1, c2)

    lines = [None] * N
    c1, c2 = best_state
    for t in range(N - 1, -1, -1):
        choice, pc1, pc2 = back[t][c1][c2]
        lines[t] = 'C1' if choice == 1 else 'C2'
        c1, c2 = pc1, pc2

    return lines, best_val


def evaluate_sequence(seq, lines=None):
    """Full exact evaluation of all constraints and objectives."""
    N = len(seq)
    metrics = {
        '4wd_consec_viol': 0,
        '4wd_gap_lt5': 0,
        '4wd_gap_5_9': 0,
        'diesel_consec_viol': 0,
        'diesel_gap_lt5': 0,
        'diesel_gap_5_9': 0,
        'blk_len_viol': 0,
        'blk_gap_viol': 0,
        'color_adj_viol': 0,
        'gold_fallback': 0,
        'config_switches': 0,
        'paint_blk_switches': 0,
        'paint_other_switches': 0,
        'paint_color_runs_extra': 0,
    }

    # 1. 4WD and Diesel
    def check_attr(attr_key, target_val, consec_key, lt5_key, g59_key):
        run = 0
        last_batch_end = None
        for i, c in enumerate(seq):
            if c[attr_key] == target_val:
                if run == 0 and last_batch_end is not None:
                    gap = i - last_batch_end - 1
                    if gap < 5:
                        metrics[lt5_key] += 1
                    elif gap < 10:
                        metrics[g59_key] += 1
                run += 1
                if run > 2:
                    metrics[consec_key] += 1
            else:
                if run > 0:
                    last_batch_end = i - 1
                    run = 0

    check_attr('drive', '四驱', '4wd_consec_viol', '4wd_gap_lt5', '4wd_gap_5_9')
    check_attr('power', '柴油', 'diesel_consec_viol', 'diesel_gap_lt5', 'diesel_gap_5_9')

    # 2. Black batches
    blk_run = 0
    last_blk_end = None
    for i, c in enumerate(seq):
        if c['color'] == '黑':
            if blk_run == 0 and last_blk_end is not None:
                gap = i - last_blk_end - 1
                if gap < 20:
                    metrics['blk_gap_viol'] += 1
            blk_run += 1
        else:
            if blk_run > 0:
                if not (50 <= blk_run <= 70):
                    metrics['blk_len_viol'] += 1
                last_blk_end = i - 1
                blk_run = 0
    if blk_run > 0 and not (50 <= blk_run <= 70):
        metrics['blk_len_viol'] += 1

    # 3. Color adjacency & Gold preference & Config switches
    for i in range(N - 1):
        c1, c2 = seq[i]['color'], seq[i + 1]['color']
        if not is_color_adj_valid(c1, c2):
            metrics['color_adj_viol'] += 1
        if seq[i]['brand'] == seq[i + 1]['brand'] and seq[i]['config'] != seq[i + 1]['config']:
            metrics['config_switches'] += 1

    for i, c in enumerate(seq):
        if c['color'] == '金':
            has_yr = False
            if i > 0 and seq[i - 1]['color'] in {'黄', '红'}:
                has_yr = True
            if i + 1 < N and seq[i + 1]['color'] in {'黄', '红'}:
                has_yr = True
            if not has_yr:
                metrics['gold_fallback'] += 1

    # 4. Paint lines
    if lines is not None:
        for line_name in ('C1', 'C2'):
            prev = None
            seen_non_bw = set()
            for i, c in enumerate(seq):
                if lines[i] != line_name:
                    continue
                col = c['color']
                if prev is not None and prev != col:
                    if prev == '黑' or col == '黑':
                        metrics['paint_blk_switches'] += 1
                    else:
                        metrics['paint_other_switches'] += 1
                    if col not in ('黑', '白') and col in seen_non_bw:
                        metrics['paint_color_runs_extra'] += 1
                if col not in ('黑', '白'):
                    seen_non_bw.add(col)
                prev = col

    return metrics


if __name__ == '__main__':
    t0 = time.time()
    data = parse_appendix('/home/tc-zhoubin/code/lab02/2018-D-Chinese/CUMCM-2018-Problem-D-Chinese-Appendix.xlsx')
    days, day_cars = build_cars_by_day(data)
    rng = random.Random(42)
    seq = construct_initial_sequence(day_cars, rng)
    lines, dp_val = assign_paint_lines_dp(seq)
    m = evaluate_sequence(seq, lines)
    print(f"Initial construction in {time.time() - t0:.2f}s:")
    for k, v in m.items():
        print(f"  {k}: {v}")
