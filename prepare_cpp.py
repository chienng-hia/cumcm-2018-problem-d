from parse_data import parse_appendix
from solver import build_cars_by_day

COLORS = ['黑', '白', '蓝', '黄', '红', '银', '棕', '灰', '金']
C_MAP = {c: i for i, c in enumerate(COLORS)}

data = parse_appendix('/home/tc-zhoubin/code/lab02/2018-D-Chinese/CUMCM-2018-Problem-D-Chinese-Appendix.xlsx')
days, day_cars = build_cars_by_day(data)

with open('/home/tc-zhoubin/code/lab02/cars_input.txt', 'w') as f:
    f.write(f"{len(days)}\n")
    for d_idx, cars in enumerate(day_cars):
        f.write(f"{d_idx} {days[d_idx]} {len(cars)}\n")
        for c_idx, c in enumerate(cars):
            br = 0 if c['brand'] == 'A1' else 1
            cfg = int(c['config'][1:]) - 1  # 0..5
            pwr = 1 if c['power'] == '柴油' else 0
            drv = 1 if c['drive'] == '四驱' else 0
            col = C_MAP[c['color']]
            f.write(f"{br} {cfg} {pwr} {drv} {col}\n")
print("Wrote cars_input.txt")
