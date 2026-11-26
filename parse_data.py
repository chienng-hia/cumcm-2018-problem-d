import zipfile
import xml.etree.ElementTree as ET
import re
import json
from collections import defaultdict

EXCEL_DATES = {
    '43360': '2018-09-17',
    '43361': '2018-09-18',
    '43362': '2018-09-19',
    '43363': '2018-09-20',
    '43364': '2018-09-21',
    '43365': '2018-09-22',
    '43366': '2018-09-23',
}

def col_to_idx(col_str):
    res = 0
    for ch in col_str:
        res = res * 26 + (ord(ch) - ord('A') + 1)
    return res - 1

def parse_appendix(xlsx_path):
    with zipfile.ZipFile(xlsx_path) as z:
        ns = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            ss_xml = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in ss_xml.findall('.//main:si', ns):
                shared.append(''.join(t.text or '' for t in si.findall('.//main:t', ns)))
        sheet1 = ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
        grid = {}
        for r in sheet1.findall('.//main:row', ns):
            r_idx = int(r.attrib['r'])
            row_dict = {}
            for c in r.findall('main:c', ns):
                ref = c.attrib['r']
                col_str = re.match(r'[A-Z]+', ref).group(0)
                c_idx = col_to_idx(col_str)
                t = c.attrib.get('t')
                v = c.find('main:v', ns)
                val = v.text if v is not None else ''
                if t == 's' and val != '':
                    val = shared[int(val)]
                if val != '':
                    row_dict[c_idx] = val
            if row_dict:
                grid[r_idx] = row_dict

    # Find date blocks
    max_r = max(grid.keys())
    days_data = {}
    
    # Locate rows where col 0 is in EXCEL_DATES
    date_rows = sorted([r for r, d in grid.items() if d.get(0) in EXCEL_DATES])
    for idx, start_r in enumerate(date_rows):
        date_str = EXCEL_DATES[grid[start_r][0]]
        end_r = date_rows[idx + 1] - 1 if idx + 1 < len(date_rows) else max_r
        
        # Two side-by-side tables: A1 (cols 0..6) and A2 (cols 8..15)
        # Let's parse each side independently
        day_items = []
        for brand, col_start, col_end in [('A1', 0, 7), ('A2', 8, 16)]:
            # Row start_r + 1 has power headers ('汽油', '柴油')
            # Row start_r + 2 has '颜色', B1, B2, ...
            power_row = grid.get(start_r + 1, {})
            cfg_row = grid.get(start_r + 2, {})
            
            # Determine column -> (power, config)
            col_meta = {}
            cur_power = None
            for c in range(col_start + 1, col_end):
                if c in power_row and power_row[c] in ('汽油', '柴油'):
                    cur_power = power_row[c]
                if c in cfg_row and cfg_row[c].startswith('B'):
                    assert cur_power is not None, f"Missing power at {date_str} {brand} col {c}"
                    col_meta[c] = (cur_power, cfg_row[c])
            
            cur_drive = None
            total_check = 0
            for r in range(start_r + 3, end_r + 1):
                row = grid.get(r, {})
                first = row.get(col_start, '')
                if not first:
                    continue
                if first in ('两驱', '四驱'):
                    cur_drive = first
                elif first == '总计':
                    expected = int(row[max(c for c in row if col_start < c < col_end)])
                    assert total_check == expected, f"Mismatch {date_str} {brand}: {total_check} != {expected}"
                    break
                else:
                    color = first
                    assert cur_drive is not None
                    for c, (power, cfg) in col_meta.items():
                        if c in row:
                            cnt = int(row[c])
                            if cnt > 0:
                                day_items.append({
                                    'brand': brand,
                                    'config': cfg,
                                    'power': power,
                                    'drive': cur_drive,
                                    'color': color,
                                    'count': cnt
                                })
                                total_check += cnt
        days_data[date_str] = day_items
    return days_data

if __name__ == '__main__':
    path = '/home/tc-zhoubin/code/lab02/2018-D-Chinese/CUMCM-2018-Problem-D-Chinese-Appendix.xlsx'
    data = parse_appendix(path)
    for d, items in sorted(data.items()):
        tot = sum(x['count'] for x in items)
        a1 = sum(x['count'] for x in items if x['brand'] == 'A1')
        a2 = sum(x['count'] for x in items if x['brand'] == 'A2')
        four_wd = sum(x['count'] for x in items if x['drive'] == '四驱')
        diesel = sum(x['count'] for x in items if x['power'] == '柴油')
        by_color = defaultdict(int)
        for x in items:
            by_color[x['color']] += x['count']
        print(f"{d}: total={tot}, A1={a1}, A2={a2}, 4WD={four_wd}, diesel={diesel}, colors={dict(by_color)}")
