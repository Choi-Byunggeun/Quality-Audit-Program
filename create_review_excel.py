import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

plan_path = r'c:\Users\twayair\Desktop\동재\심사 프로그램\2027년 정비부문 품질심사 계획표 (R.0).xlsx'
master_path = r'c:\Users\twayair\Desktop\동재\심사 프로그램\(Master) 정비본부 품질심사 실시이력(2026.11.09).xlsm'
out_path = r'c:\Users\twayair\Desktop\동재\심사 프로그램\2027년_품질심사대상_계약및정비지원_검토요청서.xlsx'

wb_plan = openpyxl.load_workbook(plan_path, data_only=True)
ws_imp = wb_plan['2027년 계획표 (개선양식)']
ws_std = wb_plan['2027년 계획표 (기존표준양식)']

# Extract rows 18..64 (47 items: 해외 운항지점 30 + 주요 정비작업 업체 17) + rows 65..67 (정비 협력업체 3)
items_2027 = []
curr_b = '내부'
curr_c = ''
curr_d = ''
curr_e = ''
curr_g = ''

for r in range(6, 68):
    b_val = ws_imp.cell(r, 2).value
    c_val = ws_imp.cell(r, 3).value
    d_val = ws_imp.cell(r, 4).value
    e_val = ws_imp.cell(r, 5).value
    f_val = ws_imp.cell(r, 6).value
    g_val = ws_imp.cell(r, 7).value
    h_val = ws_imp.cell(r, 8).value  # 심사방식 in 개선양식
    prev_val = ws_imp.cell(r, 24).value  # 이전 수행일자 in 개선양식

    if b_val:
        curr_b = str(b_val).strip()
    if c_val:
        curr_c = str(c_val).replace('\n', ' ').strip()
    if d_val:
        curr_d = str(d_val).replace('\n', ' ').strip()
    if e_val:
        curr_e = str(e_val).replace('\n', ' ').strip()
    if g_val:
        curr_g = str(g_val).replace('\n', ' ').strip()

    if r >= 18:
        # Find planned month (cols 12..23 in 개선양식 correspond to Jan..Dec)
        months = []
        for m in range(1, 13):
            v = ws_imp.cell(r, 11 + m).value
            if v is not None and str(v).strip() != '':
                months.append(f'{m}월')
        plan_month_str = ', '.join(months) if months else '-'
        f_clean = str(f_val).replace('\n', ' ').strip() if f_val else ''
        items_2027.append({
            'row_no': r,
            'inout': curr_b,
            'cat_c': curr_c,
            'cat_d': curr_d,
            'country_e': curr_e,
            'target_f': f_clean,
            'check_g': curr_g,
            'audit_type': str(h_val).strip() if h_val else '',
            'plan_month': plan_month_str,
            'prev_date': str(prev_val).strip() if prev_val else '-'
        })

# Also read Master file for Sheet 2 (All Overseas Stations & External MROs including 2026/2028/비운항)
wb_master = openpyxl.load_workbook(master_path, data_only=True)
ws_m = wb_master['수행실적']

master_items = []
m_cat = ''
for r in range(18, 122):
    a_val = ws_m.cell(r, 1).value
    b_val = ws_m.cell(r, 2).value
    c_val = ws_m.cell(r, 3).value
    d_val = ws_m.cell(r, 4).value
    e_val = ws_m.cell(r, 5).value
    if a_val:
        m_cat = str(a_val).replace('\n', ' ').strip()
    if not c_val:
        continue
    # Check if header row
    if str(c_val).strip() in ('Station', '업체명', '공항'):
        continue
    country = str(b_val).strip() if b_val else ''
    target = str(c_val).replace('\n', ' ').strip()
    cycle = str(d_val).strip() if d_val else ''
    op_status = str(e_val).strip() if e_val else ''
    y2025_type = ws_m.cell(r, 19).value
    y2025_date = ws_m.cell(r, 20).value
    y2026_type = ws_m.cell(r, 21).value
    y2026_date = ws_m.cell(r, 22).value
    y2027_type = ws_m.cell(r, 23).value
    y2028_type = ws_m.cell(r, 25).value

    def fmt_hist(t, d):
        t_s = str(t).strip() if t else ''
        d_s = str(d).strip() if d else ''
        if d_s and d_s != 'None':
            return f'{d_s} ({t_s})' if t_s else d_s
        return t_s if t_s else '-'

    master_items.append({
        'm_row': r,
        'm_cat': m_cat,
        'country': country,
        'target': target,
        'cycle': f'{cycle}년' if cycle in ('1', '2') else cycle,
        'op_status': op_status,
        'h2025': fmt_hist(y2025_type, y2025_date),
        'h2026': fmt_hist(y2026_type, y2026_date),
        'p2027': str(y2027_type).strip() if y2027_type else '-',
        'p2028': str(y2028_type).strip() if y2028_type else '-',
    })

# Create output workbook
wb_out = openpyxl.Workbook()

# Styles
font_title = Font(name='맑은 고딕', size=15, bold=True, color='FFFFFF')
font_sub = Font(name='맑은 고딕', size=10, bold=False, color='1F3864')
font_sec = Font(name='맑은 고딕', size=11, bold=True, color='1F3864')
font_hdr = Font(name='맑은 고딕', size=10, bold=True, color='FFFFFF')
font_hdr_rev = Font(name='맑은 고딕', size=10, bold=True, color='7F6000')
font_data = Font(name='맑은 고딕', size=10, bold=False, color='000000')
font_data_bold = Font(name='맑은 고딕', size=10, bold=True, color='000000')
font_direct = Font(name='맑은 고딕', size=10, bold=True, color='1F4E79')
font_indirect = Font(name='맑은 고딕', size=10, bold=True, color='833C0C')
font_kpi_lbl = Font(name='맑은 고딕', size=9, bold=True, color='333333')
font_kpi_val = Font(name='맑은 고딕', size=12, bold=True, color='1F4E79')

fill_title = PatternFill('solid', fgColor='1F3864')
fill_guide = PatternFill('solid', fgColor='EDF2F8')
fill_hdr_base = PatternFill('solid', fgColor='2F5597')
fill_hdr_rev = PatternFill('solid', fgColor='FFD966')
fill_sec_overseas = PatternFill('solid', fgColor='D9E1F2')
fill_sec_mro = PatternFill('solid', fgColor='E2EFDA')
fill_sec_sub = PatternFill('solid', fgColor='FCE4D6')
fill_zebra = PatternFill('solid', fgColor='F9FAFC')
fill_white = PatternFill('solid', fgColor='FFFFFF')
fill_input = PatternFill('solid', fgColor='FFFDF0')
fill_direct = PatternFill('solid', fgColor='DDEBF7')
fill_indirect = PatternFill('solid', fgColor='FFF2CC')
fill_kpi_hdr = PatternFill('solid', fgColor='D9E1F2')

thin_side = Side(style='thin', color='BFBFBF')
med_navy = Side(style='medium', color='1F3864')
double_bottom = Side(style='double', color='1F3864')

border_data = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
border_hdr = Border(left=thin_side, right=thin_side, top=med_navy, bottom=double_bottom)
border_input = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

align_center = Alignment(horizontal='center', vertical='center', wrap_text=True)
align_left = Alignment(horizontal='left', vertical='center', wrap_text=True)
align_right = Alignment(horizontal='right', vertical='center', wrap_text=True)

# ==============================================================================
# SHEET 1: 2027년 계획표 기준 검토 요청서 (해외 운항지점 30 + 주요 정비작업 업체 17)
# ==============================================================================
ws1 = wb_out.active
ws1.title = '1_2027년계획대상_계약검토(47개)'
ws1.views.sheetView[0].showGridLines = True

# Title Banner
ws1.merge_cells('A1:N1')
ws1['A1'] = '2027년 정비부문 품질심사 대상 (해외 운항지점 · 주요 정비작업 업체) 계약 및 정비지원 현황 검토 요청서'
ws1['A1'].font = font_title
ws1['A1'].fill = fill_title
ws1['A1'].alignment = align_center
ws1.row_dimensions[1].height = 34

# Guide Box
ws1.merge_cells('A2:N2')
ws1['A2'] = (
    '※ [작성 안내] 본 자료는 「2027년 정비부문 품질심사 계획표 (R.0)」 C열의 [해외 운항지점(30곳)] 및 [주요 정비작업 업체(17곳)]에 대해 현재 계약 유지 및 실제 정비지원 여부를 확인하기 위한 검토 양식입니다.\n'
    '   우측 노란색 음영 컬럼(J열~N열)에 드롭다운 선택 또는 의견을 기재하여 회신해 주시기 바랍니다. (계약 해지·비운항·업체 변경 시 2027년 품질심사 계획에서 조정/제외 반영 예정)'
)
ws1['A2'].font = font_sub
ws1['A2'].fill = fill_guide
ws1['A2'].alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
ws1.row_dimensions[2].height = 34

# KPI Summary Row (Rows 4~5)
kpi_specs = [
    ('A4:B4', 'A5:B5', '검토 요청 총계', '=COUNTA(F8:F54)&"개 업체/지점"'),
    ('C4:D4', 'C5:D5', '① 해외 운항지점 (운항정비)', '=COUNTIF(C8:C54,"해외 운항지점")&"개 지점"'),
    ('E4:F4', 'E5:F5', '② 주요 정비작업 업체 (중정비/엔진)', '=COUNTIF(C8:C54,"주요 정비작업 업체")&"개 업체"'),
    ('G4:H4', 'G5:H5', '계약 유지 (정상)', '=COUNTIF(J8:J54,"계약유지")&"건"'),
    ('I4:J4', 'I5:J5', '계약종료 / 미지원 (변동)', '=(COUNTIF(J8:J54,"계약종료(해지)")+COUNTIF(K8:K54,"미지원(비운항/중단)"))&"건"'),
    ('K4:L4', 'K5:L5', '검토 완료율', '=TEXT(COUNTA(J8:J54)/COUNTA(F8:F54),"0.0%")&" ("&COUNTA(J8:J54)&"/"&COUNTA(F8:F54)&")"'),
    ('M4:N4', 'M5:N5', '미검토 (작성 대기)', '=(COUNTA(F8:F54)-COUNTA(J8:J54))&"건"'),
]
ws1.row_dimensions[3].height = 6
ws1.row_dimensions[4].height = 20
ws1.row_dimensions[5].height = 24
ws1.row_dimensions[6].height = 8

for hdr_rng, val_rng, lbl, formula in kpi_specs:
    ws1.merge_cells(hdr_rng)
    ws1.merge_cells(val_rng)
    top_cell = ws1[hdr_rng.split(':')[0]]
    bot_cell = ws1[val_rng.split(':')[0]]
    top_cell.value = lbl
    top_cell.font = font_kpi_lbl
    top_cell.fill = fill_kpi_hdr
    top_cell.alignment = align_center
    bot_cell.value = formula
    bot_cell.font = font_kpi_val
    bot_cell.fill = fill_white
    bot_cell.alignment = align_center
    for rng in (hdr_rng, val_rng):
        c1, c2 = rng.split(':')
        col1, row1 = openpyxl.utils.coordinate_to_tuple(c1)
        col2, row2 = openpyxl.utils.coordinate_to_tuple(c2)
        for rr in range(row1, row2 + 1):
            for cc in range(col1, col2 + 1):
                ws1.cell(rr, cc).border = border_data

# Table Headers (Row 7)
headers_s1 = [
    '연번',
    '계획표\n행번호',
    '심사 항목\n(계획표 C열)',
    '세부 분야\n(계획표 D열)',
    '구분\n(내부/외부)',
    '국가/지역\n(계획표 E열)',
    '점검대상 (지점 / 정비업체명)\n(계획표 F열)',
    '2027년 계획\n(방식 / 예정월)',
    '직전 심사이력\n(수행일자)',
    '[검토1] 현재 계약 유지 여부\n(드롭다운 선택)',
    '[검토2] 현재 정비지원 여부\n(드롭다운 선택)',
    '[검토3] 2027년 심사대상 유지 의견\n(드롭다운 선택)',
    '계약변동 / 취항중단 / 업체변경 상세사유\n(변경 업체명 또는 계약종료일 기재)',
    '검토부서 / 담당자\n(확인자 성명)'
]
ws1.row_dimensions[7].height = 32
for idx, h_text in enumerate(headers_s1, start=1):
    cell = ws1.cell(7, idx, h_text)
    if idx >= 10:
        cell.font = font_hdr_rev
        cell.fill = fill_hdr_rev
    else:
        cell.font = font_hdr
        cell.fill = fill_hdr_base
    cell.alignment = align_center
    cell.border = border_hdr

# Populate 47 core items (rows 18..64 of plan)
core_47 = [it for it in items_2027 if it['row_no'] <= 64]
sub_3 = [it for it in items_2027 if it['row_no'] >= 65]

curr_row = 8
for idx, it in enumerate(core_47, start=1):
    ws1.row_dimensions[curr_row].height = 24
    is_even = (idx % 2 == 0)
    row_fill = fill_zebra if is_even else fill_white

    c_cat = '주요 정비작업 업체' if '주요' in it['cat_c'] else it['cat_c']
    plan_info = f"{it['audit_type']} ({it['plan_month']})"

    row_vals = [
        idx,
        f"R{it['row_no']}",
        c_cat,
        it['cat_d'],
        it['inout'],
        it['country_e'],
        it['target_f'],
        plan_info,
        it['prev_date'],
        None,  # J: 계약 유지 여부
        None,  # K: 정비지원 여부
        None,  # L: 2027 심사대상 유지 의견
        None,  # M: 사유/비고
        None,  # N: 담당자
    ]

    for c_i, val in enumerate(row_vals, start=1):
        cell = ws1.cell(curr_row, c_i, val)
        cell.border = border_data
        if c_i in (1, 2, 4, 5, 6, 8, 9):
            cell.alignment = align_center
        elif c_i == 3:
            cell.alignment = align_center
        else:
            cell.alignment = align_left

        # Styling by column
        if c_i == 3:
            cell.fill = fill_sec_overseas if c_cat == '해외 운항지점' else fill_sec_mro
            cell.font = font_data_bold
        elif c_i == 7:
            cell.fill = row_fill
            cell.font = font_data_bold
        elif c_i == 8:
            if '직접' in it['audit_type']:
                cell.fill = fill_direct
                cell.font = font_direct
            else:
                cell.fill = fill_indirect
                cell.font = font_indirect
        elif c_i >= 10:
            cell.fill = fill_input
            cell.font = font_data
            if c_i in (10, 11, 12, 14):
                cell.alignment = align_center
        else:
            cell.fill = row_fill
            cell.font = font_data

    curr_row += 1

# Optional Reference Section at bottom of Sheet 1: 정비 협력업체 (3곳, C65:C67)
curr_row += 1
ws1.merge_cells(start_row=curr_row, start_column=1, end_row=curr_row, end_column=14)
sec_cell = ws1.cell(curr_row, 1, '▼ [참고] 계획표 C열 기타 외부업체: 정비 협력업체 (도급 / W·T) — 3개 업체 (필요 시 함께 검토)')
sec_cell.font = font_sec
sec_cell.fill = fill_sec_sub
sec_cell.alignment = align_left
ws1.row_dimensions[curr_row].height = 24
curr_row += 1

for s_idx, it in enumerate(sub_3, start=1):
    ws1.row_dimensions[curr_row].height = 24
    plan_info = f"{it['audit_type']} ({it['plan_month']})"
    row_vals = [
        f'참고{s_idx}',
        f"R{it['row_no']}",
        it['cat_c'],
        it['cat_d'],
        it['inout'],
        it['country_e'],
        it['target_f'],
        plan_info,
        it['prev_date'],
        None,
        None,
        None,
        None,
        None,
    ]
    for c_i, val in enumerate(row_vals, start=1):
        cell = ws1.cell(curr_row, c_i, val)
        cell.border = border_data
        cell.font = font_data
        cell.fill = fill_input if c_i >= 10 else fill_white
        if c_i in (1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 14):
            cell.alignment = align_center
        else:
            cell.alignment = align_left
        if c_i == 7:
            cell.font = font_data_bold
    curr_row += 1

# Add Dropdown Data Validations for Sheet 1 (Rows 8 to curr_row-1)
dv_contract = DataValidation(type='list', formula1='"계약유지,계약종료(해지),계약변경진행중,확인필요"', allow_blank=True)
dv_support = DataValidation(type='list', formula1='"정상지원중,미지원(비운항/중단),타업체로변경,확인필요"', allow_blank=True)
dv_audit = DataValidation(type='list', formula1='"2027년 심사유지,2027년 심사제외요청,일정조정필요,확인필요"', allow_blank=True)

ws1.add_data_validation(dv_contract)
ws1.add_data_validation(dv_support)
ws1.add_data_validation(dv_audit)

dv_contract.add(f'J8:J{curr_row-1}')
dv_support.add(f'K8:K{curr_row-1}')
dv_audit.add(f'L8:L{curr_row-1}')

# Set Column Widths & Freeze Panes for Sheet 1
col_widths_s1 = [7, 9, 18, 14, 9, 14, 34, 16, 18, 19, 19, 19, 34, 16]
for c_i, w in enumerate(col_widths_s1, start=1):
    ws1.column_dimensions[get_column_letter(c_i)].width = w

ws1.freeze_panes = 'A8'
ws1.auto_filter.ref = f'A7:N54'


# ==============================================================================
# SHEET 2: Master 파일 전체 해외지점·외부정비업체 통합 검토 (2026년/2028년/비운항 포함)
# ==============================================================================
ws2 = wb_out.create_sheet(title='2_마스터전체업체_통합검토(참고)')
ws2.views.sheetView[0].showGridLines = True

ws2.merge_cells('A1:N1')
ws2['A1'] = '[통합 참고용] Master 파일 전체 해외지점 및 외주 정비업체 현황 (2026년 완료 · 2027년 계획 · 2028년 도래 · 비운항 전체 포함)'
ws2['A1'].font = font_title
ws2['A1'].fill = fill_title
ws2['A1'].alignment = align_center
ws2.row_dimensions[1].height = 34

ws2.merge_cells('A2:N2')
ws2['A2'] = (
    '※ [참고 안내] 1번 시트(2027년 심사 계획 47개 대상) 외에도, 2년 주기에 따라 2026년에 심사를 완료하여 2028년에 도래하는 업체 및 현재 [비운항]으로 분류된 지점까지 Master 파일의 전체 외주/해외 대상을 수록한 시트입니다.\n'
    '   비운항 지점의 재취항 여부나 2028년 도래 업체의 조기 계약 해지 여부 등을 함께 크로스체크하실 때 활용하시기 바랍니다.'
)
ws2['A2'].font = font_sub
ws2['A2'].fill = fill_guide
ws2['A2'].alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
ws2.row_dimensions[2].height = 34

headers_s2 = [
    '연번',
    'Master\n행번호',
    'Master 분류\n(A열)',
    '국가/지역\n(B열)',
    '점검대상 (Station / 업체명)\n(C열)',
    '심사주기\n(D열)',
    'Master 운항상태\n(E열)',
    '2025년 실적',
    '2026년 실적/계획',
    '2027년 계획',
    '2028년 계획',
    '[검토] 현재 계약 상태',
    '[검토] 현재 정비지원 상태',
    '비고 (변동사항 기재)'
]
ws2.row_dimensions[4].height = 30
for idx, h_text in enumerate(headers_s2, start=1):
    cell = ws2.cell(4, idx, h_text)
    if idx >= 12:
        cell.font = font_hdr_rev
        cell.fill = fill_hdr_rev
    else:
        cell.font = font_hdr
        cell.fill = fill_hdr_base
    cell.alignment = align_center
    cell.border = border_hdr

r2 = 5
for idx, mit in enumerate(master_items, start=1):
    ws2.row_dimensions[r2].height = 22
    is_non_op = (mit['op_status'] == '비운항')
    row_fill = PatternFill('solid', fgColor='F2F2F2') if is_non_op else (fill_zebra if idx % 2 == 0 else fill_white)

    vals = [
        idx,
        f"R{mit['m_row']}",
        mit['m_cat'],
        mit['country'],
        mit['target'],
        mit['cycle'],
        mit['op_status'],
        mit['h2025'],
        mit['h2026'],
        mit['p2027'],
        mit['p2028'],
        None,
        None,
        None
    ]
    for c_i, val in enumerate(vals, start=1):
        cell = ws2.cell(r2, c_i, val)
        cell.border = border_data
        cell.fill = fill_input if c_i >= 12 else row_fill
        cell.font = font_data_bold if c_i == 5 else font_data
        if c_i in (5, 14):
            cell.alignment = align_left
        else:
            cell.alignment = align_center
        if c_i == 7 and is_non_op:
            cell.font = Font(name='맑은 고딕', size=10, bold=True, color='C00000')
        if c_i == 10 and val in ('●', '◎'):
            cell.fill = fill_direct if val == '●' else fill_indirect
            cell.font = font_direct if val == '●' else font_indirect
    r2 += 1

dv_contract2 = DataValidation(type='list', formula1='"계약유지,계약종료(해지),계약변경진행중,확인필요"', allow_blank=True)
dv_support2 = DataValidation(type='list', formula1='"정상지원중,미지원(비운항/중단),재취항예정,타업체로변경,확인필요"', allow_blank=True)
ws2.add_data_validation(dv_contract2)
ws2.add_data_validation(dv_support2)
dv_contract2.add(f'L5:L{r2-1}')
dv_support2.add(f'M5:M{r2-1}')

col_widths_s2 = [7, 9, 18, 14, 34, 10, 14, 20, 20, 12, 12, 18, 18, 30]
for c_i, w in enumerate(col_widths_s2, start=1):
    ws2.column_dimensions[get_column_letter(c_i)].width = w

ws2.freeze_panes = 'A5'
ws2.auto_filter.ref = f'A4:N{r2-1}'

wb_out.save(out_path)
print(f'Successfully created: {out_path}')
print(f'Sheet 1 core items: {len(core_47)}, sub items: {len(sub_3)}')
print(f'Sheet 2 master items: {len(master_items)}')

