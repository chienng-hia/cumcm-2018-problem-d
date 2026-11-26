import json
import zipfile
import xml.sax.saxutils as saxutils

def write_xlsx(sheets, out_path):
    """
    Write multiple sheets to a valid .xlsx file using pure Python stdlib.
    sheets: list of (sheet_name, rows), where rows is list of lists of values.
    """
    shared_strings = []
    ss_map = {}

    def get_ss_idx(s):
        if s not in ss_map:
            ss_map[s] = len(shared_strings)
            shared_strings.append(s)
        return ss_map[s]

    def col_letter(idx):
        res = ''
        idx += 1
        while idx > 0:
            idx, rem = divmod(idx - 1, 26)
            res = chr(65 + rem) + res
        return res

    sheet_xmls = []
    for name, rows in sheets:
        lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
        lines.append('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">')
        lines.append('<sheetData>')
        for r_idx, row in enumerate(rows, start=1):
            lines.append(f'<row r="{r_idx}">')
            for c_idx, val in enumerate(row):
                ref = f"{col_letter(c_idx)}{r_idx}"
                if isinstance(val, (int, float)):
                    lines.append(f'<c r="{ref}"><v>{val}</v></c>')
                else:
                    s_idx = get_ss_idx(str(val))
                    lines.append(f'<c r="{ref}" t="s"><v>{s_idx}</v></c>')
            lines.append('</row>')
        lines.append('</sheetData>')
        lines.append('</worksheet>')
        sheet_xmls.append('\n'.join(lines))

    # Build sharedStrings.xml
    ss_lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    ss_lines.append(f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(shared_strings)}" uniqueCount="{len(shared_strings)}">')
    for s in shared_strings:
        ss_lines.append(f'<si><t>{saxutils.escape(s)}</t></si>')
    ss_lines.append('</sst>')
    ss_xml = '\n'.join(ss_lines)

    # [Content_Types].xml
    ct_lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    ct_lines.append('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">')
    ct_lines.append('<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>')
    ct_lines.append('<Default Extension="xml" ContentType="application/xml"/>')
    ct_lines.append('<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>')
    ct_lines.append('<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>')
    for i in range(1, len(sheets) + 1):
        ct_lines.append(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
    ct_lines.append('</Types>')
    ct_xml = '\n'.join(ct_lines)

    # _rels/.rels
    rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>'''

    # xl/workbook.xml
    wb_lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    wb_lines.append('<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">')
    wb_lines.append('<sheets>')
    for i, (name, _) in enumerate(sheets, start=1):
        wb_lines.append(f'<sheet name="{saxutils.escape(name)}" sheetId="{i}" r:id="rId{i}"/>')
    wb_lines.append('</sheets>')
    wb_lines.append('</workbook>')
    wb_xml = '\n'.join(wb_lines)

    # xl/_rels/workbook.xml.rels
    wb_rels_lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    wb_rels_lines.append('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">')
    for i in range(1, len(sheets) + 1):
        wb_rels_lines.append(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>')
    wb_rels_lines.append(f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>')
    wb_rels_lines.append('</Relationships>')
    wb_rels_xml = '\n'.join(wb_rels_lines)

    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', ct_xml)
        z.writestr('_rels/.rels', rels_xml)
        z.writestr('xl/workbook.xml', wb_xml)
        z.writestr('xl/_rels/workbook.xml.rels', wb_rels_xml)
        z.writestr('xl/sharedStrings.xml', ss_xml)
        for i, s_xml in enumerate(sheet_xmls, start=1):
            z.writestr(f'xl/worksheets/sheet{i}.xml', s_xml)


def main():
    with open('/home/tc-zhoubin/code/lab02/final_solution.json') as f:
        data = json.load(f)
    seq = data['seq']
    lines = data['lines']

    sheet_names = ['9月17日', '9月18日', '9月19日', '9月20日', '9月21日', '9月22日', '9月23日']
    header = ['装配顺序', '品牌', '配置', '动力', '驱动', '颜色', '喷涂线']

    sheets = []
    for d_idx, s_name in enumerate(sheet_names):
        rows = [header]
        for k in range(460):
            idx = d_idx * 460 + k
            c = seq[idx]
            rows.append([
                k + 1,
                c['brand'],
                c['config'],
                c['power'],
                c['drive'],
                c['color'],
                lines[idx]
            ])
        sheets.append((s_name, rows))

    out_path = '/home/tc-zhoubin/code/lab02/schedule.xlsx'
    write_xlsx(sheets, out_path)
    print(f"Successfully exported {out_path} with {len(sheets)} sheets.")

if __name__ == '__main__':
    main()
