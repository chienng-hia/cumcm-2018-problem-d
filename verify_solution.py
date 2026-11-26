import json
from collections import Counter
from parse_data import parse_appendix
from solver import is_color_adj_valid, PAINT_C1_ONLY, PAINT_C2_ONLY, evaluate_sequence

def verify_all(sol_path, appendix_path):
    with open(sol_path) as f:
        data_sol = json.load(f)
    seq = data_sol['seq']
    lines = data_sol['lines']

    assert len(seq) == 3220, f"Expected 3220 cars, got {len(seq)}"
    assert len(lines) == 3220, f"Expected 3220 lines, got {len(lines)}"

    # 1. Verify exact inventory per day against Appendix
    appendix = parse_appendix(appendix_path)
    days = sorted(appendix.keys())
    assert len(days) == 7

    for d_idx, date_str in enumerate(days):
        expected_counts = Counter()
        for item in appendix[date_str]:
            key = (item['brand'], item['config'], item['power'], item['drive'], item['color'])
            expected_counts[key] += item['count']

        day_seq = seq[d_idx * 460 : (d_idx + 1) * 460]
        actual_counts = Counter()
        for c in day_seq:
            assert c['date'] == date_str
            key = (c['brand'], c['config'], c['power'], c['drive'], c['color'])
            actual_counts[key] += 1

        assert actual_counts == expected_counts, f"Inventory mismatch on {date_str}"

        # 2. Verify Day/Night shift brand order & half-day split
        tot_a1 = sum(v for k, v in expected_counts.items() if k[0] == 'A1')
        tot_a2 = sum(v for k, v in expected_counts.items() if k[0] == 'A2')

        for shift_idx, s_name in [(0, 'Day'), (1, 'Night')]:
            sh = day_seq[shift_idx * 230 : (shift_idx + 1) * 230]
            seen_a2 = False
            n_a1 = 0
            n_a2 = 0
            for c in sh:
                if c['brand'] == 'A1':
                    assert not seen_a2, f"{date_str} {s_name}: A1 appeared after A2!"
                    n_a1 += 1
                else:
                    seen_a2 = True
                    n_a2 += 1
            assert abs(n_a1 - tot_a1 / 2) <= 0.5, f"{date_str} {s_name}: A1 count {n_a1} vs {tot_a1}/2"
            assert abs(n_a2 - tot_a2 / 2) <= 0.5, f"{date_str} {s_name}: A2 count {n_a2} vs {tot_a2}/2"

    # 3. Verify paint line assignments
    for i, (c, ln) in enumerate(zip(seq, lines)):
        assert ln in ('C1', 'C2')
        if c['color'] in PAINT_C1_ONLY:
            assert ln == 'C1', f"Pos {i}: {c['color']} must be C1, got {ln}"
        if c['color'] in PAINT_C2_ONLY:
            assert ln == 'C2', f"Pos {i}: {c['color']} must be C2, got {ln}"

    # 4. Full constraint evaluation
    m = evaluate_sequence(seq, lines)
    print("=== INDEPENDENT VERIFICATION PASSED ===")
    print("Inventory (all 7 days, 3220 cars): EXACT MATCH")
    print("Shift structure (14 shifts, A1->A2, half-day split): PASS")
    print("Paint line restrictions (蓝/黄/红->C1, 金->C2): PASS")
    print("\nConstraint & Objective Summary:")
    for k, v in m.items():
        print(f"  {k}: {v}")

    # Paint line load balance
    c1_cnt = sum(1 for x in lines if x == 'C1')
    c2_cnt = sum(1 for x in lines if x == 'C2')
    print(f"\nPaint line volume: C1={c1_cnt}, C2={c2_cnt}")

if __name__ == '__main__':
    verify_all(
        '/home/tc-zhoubin/code/lab02/final_solution.json',
        '/home/tc-zhoubin/code/lab02/2018-D-Chinese/CUMCM-2018-Problem-D-Chinese-Appendix.xlsx'
    )
