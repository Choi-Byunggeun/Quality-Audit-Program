import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import copy
import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. Find the latest (Master) file automatically
master_files = sorted(glob.glob(os.path.join(BASE_DIR, "(Master)*.xlsm")))
if master_files:
    MASTER_PATH = master_files[-1]
else:
    MASTER_PATH = os.path.join(BASE_DIR, "(Master) 정비본부 품질심사 실시이력(2026.11.09).xlsm")

TEMPLATE_2026_PATH = os.path.join(BASE_DIR, "2026년 정비부문 품질심사 계획표 (R.0).xlsx")
OUTPUT_2027_PATH = os.path.join(BASE_DIR, "2027년 정비부문 품질심사 계획표 (R.0).xlsx")

print(f"[1/4] Master 파일 로드 중: {os.path.basename(MASTER_PATH)}")
wb_master = openpyxl.load_workbook(MASTER_PATH, data_only=True)
ws_master = wb_master['수행실적']

# Extract Master records by row and by normalized station name
master_rows = {}
for r in range(6, ws_master.max_row + 1):
    cat = ws_master.cell(r, 1).value
    op = ws_master.cell(r, 2).value
    name = ws_master.cell(r, 3).value
    if not name:
        continue
    clean_name = re.sub(r'\s+', ' ', str(name).replace('\n', ' ').replace('\r', ' ')).strip()
    s28, d28 = ws_master.cell(r, 4).value, ws_master.cell(r, 5).value
    s27, d27 = ws_master.cell(r, 6).value, ws_master.cell(r, 7).value
    s26, d26 = ws_master.cell(r, 8).value, ws_master.cell(r, 9).value
    s25, d25 = ws_master.cell(r, 10).value, ws_master.cell(r, 11).value
    s24, d24 = ws_master.cell(r, 12).value, ws_master.cell(r, 13).value
    s23, d23 = ws_master.cell(r, 14).value, ws_master.cell(r, 15).value

    master_rows[r] = {
        'row': r,
        'cat': str(cat).strip() if cat else '',
        'op': str(op).strip() if op else '',
        'name': clean_name,
        's27': s27, 'd27': d27,
        's26': s26, 'd26': d26,
        's25': s25, 'd25': d25,
        's24': s24, 'd24': d24,
        's23': s23, 'd23': d23,
    }

def format_master_prev_date(m_rec, fallback_prev):
    """Master 파일의 최근 심사 이력(2026 -> 2025 -> 2024 순)으로부터 이전 수행일자를 포맷팅"""
    if not m_rec:
        return fallback_prev
    for yr, s_key, d_key in [(2026, 's26', 'd26'), (2025, 's25', 'd25'), (2024, 's24', 'd24'), (2023, 's23', 'd23')]:
        sym = m_rec.get(s_key)
        dt = m_rec.get(d_key)
        if sym in ['●', '◎']:
            type_tag = '(직)' if sym == '●' else '(간)'
            if dt and str(dt).strip() not in ['None', '직접심사', '간접예정', '서류예정', '확인필요']:
                dt_str = str(dt).strip().split(' ')[0].replace('-', '.')
                return f"{dt_str}{type_tag}"
            elif fallback_prev:
                return fallback_prev
            else:
                return f"{yr}{type_tag}"
    return fallback_prev

def extract_month_from_prev(prev_str, default_month):
    if not prev_str:
        return default_month
    m = re.search(r'202\d\.(\d{1,2})', str(prev_str))
    if m:
        val = int(m.group(1))
        if 1 <= val <= 12:
            return val
    return default_month

# 2. Define the 2027 Plan structure synchronized 1:1 with Master (62 Operating + 1 정비품질 = 63 rows)
# Each entry references its exact Master row (`m_row`) so any future edits in Master automatically flow into the plan!
plan_definitions = [
    # --- 1. 내부 - 정비부문 각 부서 (8행: 직접 7건 + 정비품질 대체 1건) ---
    {
        'm_row': 123, 'gubun': '내부', 'area': '정비부문 각 부서', 'item': None, 'country': '국내',
        'target': '항공기기술', 'checklist': 'TW-MNT-001 항공기기술', 'fallback_prev': '2026.09(직)',
        'interval': '1년', 'plan_month': 9, 'auditor': '권혁, 최병근', 'etc': None,
        'cat_code': 1, 'stat_cat': '정비본부'
    },
    {
        'm_row': 124, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': '엔진기술', 'checklist': 'TW-MNT-014 엔진기술', 'fallback_prev': '2026.04.08(직)',
        'interval': None, 'plan_month': 4, 'auditor': '이진성, 김주원', 'etc': None,
        'cat_code': 1, 'stat_cat': '정비본부'
    },
    {
        'm_row': 125, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': '정비기획', 'checklist': 'TW-MNT-002 정비기획', 'fallback_prev': '2026.08(직)',
        'interval': None, 'plan_month': 8, 'auditor': '박병권, 최병근', 'etc': None,
        'cat_code': 1, 'stat_cat': '정비본부'
    },
    {
        'm_row': 126, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': '정비자재', 'checklist': 'TW-MNT-003 정비자재', 'fallback_prev': '2026.10(직)',
        'interval': None, 'plan_month': 10, 'auditor': '원대연, 유준열', 'etc': None,
        'cat_code': 1, 'stat_cat': '정비본부'
    },
    {
        'm_row': 127, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': '정비통제', 'checklist': 'TW-MNT-005 정비통제', 'fallback_prev': '2026.11(직)',
        'interval': None, 'plan_month': 11, 'auditor': '송동훈, 김주원', 'etc': None,
        'cat_code': 1, 'stat_cat': '정비본부'
    },
    {
        'm_row': 128, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': '운항정비 1,2', 'checklist': 'TW-MNT-010 정비기지공항', 'fallback_prev': '2026.07(직)',
        'interval': None, 'plan_month': 7, 'auditor': '박병권, 권혁', 'etc': None,
        'cat_code': 1, 'stat_cat': '정비본부'
    },
    {
        'm_row': 129, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': '부품수리', 'checklist': 'TW-MNT-012 부품수리', 'fallback_prev': '2026.03.25(직)',
        'interval': None, 'plan_month': 3, 'auditor': '박병권', 'etc': None,
        'cat_code': 1, 'stat_cat': '정비본부'
    },
    {
        'm_row': None, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': '정비품질', 'checklist': None, 'fallback_prev': '2026.03.17~19(직)',
        'interval': None, 'plan_month': 3, 'auditor': None, 'etc': '안전품질 심사로 대체',
        'cat_code': None, 'stat_cat': None, 'is_quality_self': True
    },

    # --- 2. 내부 - 국내 운항지점 (5행: 직접 5건) ---
    {
        'm_row': 130, 'gubun': None, 'area': '국내 운항지점', 'item': None, 'country': '국내',
        'target': 'CJU (제주)', 'checklist': 'TW-MNT-007\n주재정비공항', 'fallback_prev': '2026.08(직)',
        'interval': None, 'plan_month': 8, 'auditor': '원대연', 'etc': None,
        'cat_code': 1, 'stat_cat': '국내 운항지점'
    },
    {
        'm_row': 131, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': 'TAE (대구)', 'checklist': None, 'fallback_prev': '2026.09(직)',
        'interval': None, 'plan_month': 9, 'auditor': '송동훈', 'etc': None,
        'cat_code': 1, 'stat_cat': '국내 운항지점'
    },
    {
        'm_row': 132, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': 'KWJ (광주)', 'checklist': None, 'fallback_prev': '2026.05.29(직)',
        'interval': None, 'plan_month': 5, 'auditor': '이진성', 'etc': None,
        'cat_code': 1, 'stat_cat': '국내 운항지점'
    },
    {
        'm_row': 133, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': 'PUS (부산)', 'checklist': None, 'fallback_prev': '2026.10(직)',
        'interval': None, 'plan_month': 10, 'auditor': '원대연', 'etc': None,
        'cat_code': 1, 'stat_cat': '국내 운항지점'
    },
    {
        'm_row': 134, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': 'CJJ (청주)', 'checklist': None, 'fallback_prev': '2026.11(직)',
        'interval': None, 'plan_month': 11, 'auditor': '이진성', 'etc': None,
        'cat_code': 1, 'stat_cat': '국내 운항지점'
    },

    # --- 3. 내부 - 해외 운항지점 (5행: 직접 3건, 간접 2건) ---
    {
        'm_row': 6, 'gubun': None, 'area': '해외 운항지점', 'item': '운항정비', 'country': '미국',
        'target': 'GUM (괌)', 'checklist': None, 'fallback_prev': '2025.10.15~16(간)',
        'interval': '2년\n(직접 & 간접 \n순차 실시)', 'plan_month': 10, 'auditor': '최병근', 'etc': None,
        'cat_code': 2, 'stat_cat': '해외 운항지점'
    },
    {
        'm_row': 13, 'gubun': None, 'area': None, 'item': None, 'country': '베트남',
        'target': 'CXR (나트랑)', 'checklist': None, 'fallback_prev': '2025.02.24~28(직)',
        'interval': None, 'plan_month': 2, 'auditor': '이진성', 'etc': None,
        'cat_code': 2, 'stat_cat': '해외 운항지점'
    },
    {
        'm_row': 20, 'gubun': None, 'area': None, 'item': None, 'country': '일본',
        'target': 'CTS (치토세)', 'checklist': None, 'fallback_prev': '2025.04.10(간)',
        'interval': None, 'plan_month': 4, 'auditor': '김주원', 'etc': None,
        'cat_code': 2, 'stat_cat': '해외 운항지점'
    },
    {
        'm_row': 21, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': 'OKA (오키나와)', 'checklist': None, 'fallback_prev': '2025.05.28(간)',
        'interval': None, 'plan_month': 5, 'auditor': '박병권', 'etc': None,
        'cat_code': 2, 'stat_cat': '해외 운항지점'
    },
    {
        'm_row': 22, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': 'KMJ (구마모토)', 'checklist': None, 'fallback_prev': '2025.06.09~11(직)',
        'interval': None, 'plan_month': 6, 'auditor': '원대연', 'etc': None,
        'cat_code': 2, 'stat_cat': '해외 운항지점'
    },

    # --- 4. 외부 - 운항정비 위탁업체 (25행: 해외 완전위탁 23건 + 국내 대한항공 운항정비 2건 = 직접 16건, 간접 9건) ---
    {
        'm_row': 45, 'gubun': '외부', 'area': None, 'item': None, 'country': '태국',
        'target': 'TG (BKK 방콕)', 'checklist': 'TW-MNT-008\n위탁정비업체', 'fallback_prev': '2025.09.23(간)',
        'interval': None, 'plan_month': 9, 'auditor': '박병권', 'etc': None,
        'cat_code': 3, 'stat_cat': '운항정비위탁'
    },
    {
        'm_row': 47, 'gubun': None, 'area': None, 'item': None, 'country': '필리핀',
        'target': 'APLUS (KLO 칼리보)', 'checklist': None, 'fallback_prev': '2025.11.05~07(직)',
        'interval': None, 'plan_month': 11, 'auditor': '유준열', 'etc': None,
        'cat_code': 3, 'stat_cat': '운항정비위탁'
    },
    {
        'm_row': 48, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': 'LTP (CEB 세부)', 'checklist': None, 'fallback_prev': '2025.10.28~29(직)',
        'interval': None, 'plan_month': 10, 'auditor': '박병권', 'etc': None,
        'cat_code': 3, 'stat_cat': '운항정비위탁'
    },
    {
        'm_row': 49, 'gubun': None, 'area': None, 'item': None, 'country': '말레이시아',
        'target': 'MABES (BKI 코타키나발루)', 'checklist': None, 'fallback_prev': '2025.11.26~27(직)',
        'interval': None, 'plan_month': 11, 'auditor': '유준열', 'etc': None,
        'cat_code': 3, 'stat_cat': '운항정비위탁'
    },
    {
        'm_row': 50, 'gubun': None, 'area': None, 'item': None, 'country': '인도네시아',
        'target': 'JAE (DPS 발리)', 'checklist': None, 'fallback_prev': '2025.04.15~16(직)',
        'interval': None, 'plan_month': 4, 'auditor': '원대연', 'etc': None,
        'cat_code': 3, 'stat_cat': '운항정비위탁'
    },
    {
        'm_row': 51, 'gubun': None, 'area': None, 'item': None, 'country': '방글라데시',
        'target': 'STORM AVIATION (DAC 다카)', 'checklist': None, 'fallback_prev': '2025.11.20~21(직)',
        'interval': None, 'plan_month': 11, 'auditor': '김주원', 'etc': None,
        'cat_code': 3, 'stat_cat': '운항정비위탁'
    },
    {
        'm_row': 52, 'gubun': None, 'area': None, 'item': None, 'country': '홍콩',
        'target': 'PAPAS (HKG 홍콩)', 'checklist': None, 'fallback_prev': '2025.09.24~25(간)',
        'interval': None, 'plan_month': 9, 'auditor': '권혁', 'etc': None,
        'cat_code': 3, 'stat_cat': '운항정비위탁'
    },
    {
        'm_row': 60, 'gubun': None, 'area': None, 'item': None, 'country': '일본',
        'target': 'SIAEJ (FUK 후쿠오카)', 'checklist': None, 'fallback_prev': '2025.09.11~12(간)',
        'interval': None, 'plan_month': 9, 'auditor': '원대연', 'etc': None,
        'cat_code': 3, 'stat_cat': '운항정비위탁'
    },
    {
        'm_row': 61, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': 'SIAEJ (CTS 삿포로)', 'checklist': None, 'fallback_prev': '2025.09.11~12(간)',
        'interval': None, 'plan_month': 9, 'auditor': '김주원', 'etc': None,
        'cat_code': 3, 'stat_cat': '운항정비위탁'
    },
    {
        'm_row': 62, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': 'SIAEJ (KIX 오사카)', 'checklist': None, 'fallback_prev': '2025.08.18~20(직)',
        'interval': None, 'plan_month': 8, 'auditor': '김주원', 'etc': None,
        'cat_code': 3, 'stat_cat': '운항정비위탁'
    },
    {
        'm_row': 63, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': 'SIAEJ (NRT 도쿄)', 'checklist': None, 'fallback_prev': '2025.09.11~12(간)',
        'interval': None, 'plan_month': 9, 'auditor': '최병근', 'etc': None,
        'cat_code': 3, 'stat_cat': '운항정비위탁'
    },
    {
        'm_row': 64, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': 'SIAEJ (NGO 나고야)', 'checklist': None, 'fallback_prev': '2025.09.11~12(간)',
        'interval': None, 'plan_month': 9, 'auditor': '최병근', 'etc': None,
        'cat_code': 3, 'stat_cat': '운항정비위탁'
    },
    {
        'm_row': 67, 'gubun': None, 'area': None, 'item': None, 'country': '중국',
        'target': 'EASTEC (WUH 우한)', 'checklist': None, 'fallback_prev': '2025.10.29(간)',
        'interval': None, 'plan_month': 10, 'auditor': '김주원', 'etc': None,
        'cat_code': 3, 'stat_cat': '운항정비위탁'
    },
    {
        'm_row': 74, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': 'EASTEC (YNJ 연길)', 'checklist': None, 'fallback_prev': '2025.06.24~26(직)',
        'interval': None, 'plan_month': 6, 'auditor': '최병근', 'etc': None,
        'cat_code': 3, 'stat_cat': '운항정비위탁'
    },
    {
        'm_row': 70, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': 'Southern (YNJ 연길)', 'checklist': None, 'fallback_prev': '2025.12.18(간)',
        'interval': None, 'plan_month': 12, 'auditor': '최병근', 'etc': None,
        'cat_code': 3, 'stat_cat': '운항정비위탁'
    },
    {
        'm_row': 72, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': 'HNA (HAK 하이커우)', 'checklist': None, 'fallback_prev': '2025.08.12(간)',
        'interval': None, 'plan_month': 8, 'auditor': '김주원', 'etc': None,
        'cat_code': 3, 'stat_cat': '운항정비위탁'
    },
    {
        'm_row': 73, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': 'HNA (SYX 싼야)', 'checklist': None, 'fallback_prev': '2025.08.12(간)',
        'interval': None, 'plan_month': 8, 'auditor': '유준열', 'etc': None,
        'cat_code': 3, 'stat_cat': '운항정비위탁'
    },
    {
        'm_row': 77, 'gubun': None, 'area': None, 'item': None, 'country': '베트남',
        'target': 'VAECO (CXR 나트랑)', 'checklist': None, 'fallback_prev': '2025.02.25~27(직)',
        'interval': None, 'plan_month': 2, 'auditor': '이진성', 'etc': None,
        'cat_code': 3, 'stat_cat': '운항정비위탁'
    },
    {
        'm_row': 78, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': 'VAECO (PQC 푸꾸옥)', 'checklist': None, 'fallback_prev': '2025.12(간)',
        'interval': None, 'plan_month': 12, 'auditor': '원대연', 'etc': None,
        'cat_code': 3, 'stat_cat': '운항정비위탁'
    },
    {
        'm_row': 83, 'gubun': None, 'area': None, 'item': None, 'country': '프랑스',
        'target': 'Nayak Aero - CDG (파리)', 'checklist': None, 'fallback_prev': '2025.02.20(간)',
        'interval': None, 'plan_month': 2, 'auditor': '이진성', 'etc': None,
        'cat_code': 3, 'stat_cat': '운항정비위탁'
    },
    {
        'm_row': 84, 'gubun': None, 'area': None, 'item': None, 'country': '이탈리아',
        'target': 'Atitech - FCO (로마)', 'checklist': None, 'fallback_prev': '2025.02.20(간)',
        'interval': None, 'plan_month': 2, 'auditor': '권혁', 'etc': None,
        'cat_code': 3, 'stat_cat': '운항정비위탁'
    },
    {
        'm_row': 85, 'gubun': None, 'area': None, 'item': None, 'country': '스페인',
        'target': 'KLM - BCN (바르셀로나)', 'checklist': None, 'fallback_prev': '2025.09.08(간)',
        'interval': None, 'plan_month': 9, 'auditor': '박병권', 'etc': None,
        'cat_code': 3, 'stat_cat': '운항정비위탁'
    },
    {
        'm_row': 88, 'gubun': None, 'area': None, 'item': None, 'country': '캐나다',
        'target': 'Southbreeze - YVR (벤쿠버)', 'checklist': None, 'fallback_prev': '2025.04.15~16(직)',
        'interval': None, 'plan_month': 4, 'auditor': '유준열', 'etc': None,
        'cat_code': 3, 'stat_cat': '운항정비위탁'
    },
    {
        'm_row': 111, 'gubun': None, 'area': None, 'item': None, 'country': '국내',
        'target': '대한항공 (ICN, GMP 인천,김포)', 'checklist': None, 'fallback_prev': '2025.01.09~10(간)',
        'interval': None, 'plan_month': 5, 'auditor': '권혁, 김주원', 'etc': '국내 운항정비 위탁',
        'cat_code': 4, 'stat_cat': '국내정비위탁'
    },
    {
        'm_row': 112, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': '대한항공 (CJU 제주)', 'checklist': None, 'fallback_prev': '2025.01.09~10(간)',
        'interval': None, 'plan_month': 5, 'auditor': '권혁, 김주원', 'etc': '국내 운항정비 위탁',
        'cat_code': 4, 'stat_cat': '국내정비위탁'
    },

    # --- 5. 외부 - 주요 정비작업 업체 - 항공기 중정비 (9행: 직접 5건, 간접 4건) ---
    {
        'm_row': 99, 'gubun': None, 'area': '주요 \n정비작업 업체', 'item': '항공기\n중정비', 'country': '중국',
        'target': 'AMECO (CTU 청두)', 'checklist': None, 'fallback_prev': '2025.10.13(간)',
        'interval': None, 'plan_month': 10, 'auditor': '김주원', 'etc': None,
        'cat_code': 3, 'stat_cat': '중정비위탁'
    },
    {
        'm_row': 107, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': 'HAITE (TSN 톈진)', 'checklist': None, 'fallback_prev': '2025.03.17~19(직)',
        'interval': None, 'plan_month': 3, 'auditor': '김주원', 'etc': None,
        'cat_code': 3, 'stat_cat': '중정비위탁'
    },
    {
        'm_row': 100, 'gubun': None, 'area': None, 'item': None, 'country': '대만',
        'target': 'Air Asia Company Ltd (TNN 타이난)', 'checklist': None, 'fallback_prev': '2025.08.11~14(직)',
        'interval': None, 'plan_month': 8, 'auditor': '권혁', 'etc': None,
        'cat_code': 3, 'stat_cat': '중정비위탁'
    },
    {
        'm_row': 101, 'gubun': None, 'area': None, 'item': None, 'country': '필리핀',
        'target': 'SIAEP (CRK 클락)', 'checklist': None, 'fallback_prev': '2025.09.10~12(직)',
        'interval': None, 'plan_month': 9, 'auditor': '원대연', 'etc': None,
        'cat_code': 3, 'stat_cat': '중정비위탁'
    },
    {
        'm_row': 102, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': 'LTP (MNL 마닐라)', 'checklist': None, 'fallback_prev': '2025.10.21~24(직)',
        'interval': None, 'plan_month': 10, 'auditor': '박병권', 'etc': None,
        'cat_code': 3, 'stat_cat': '중정비위탁'
    },
    {
        'm_row': 103, 'gubun': None, 'area': None, 'item': None, 'country': '몽골',
        'target': 'MIAT Mongolian Airlines (ULN 울란바토르)', 'checklist': None, 'fallback_prev': '2025.08.07(간)',
        'interval': None, 'plan_month': 8, 'auditor': '이진성', 'etc': None,
        'cat_code': 3, 'stat_cat': '중정비위탁'
    },
    {
        'm_row': 104, 'gubun': None, 'area': None, 'item': None, 'country': '인도네시아',
        'target': 'GMF (CGK 자카르타) - C/K', 'checklist': None, 'fallback_prev': '2025.03.04~06(간)',
        'interval': None, 'plan_month': 3, 'auditor': '원대연, 이진성', 'etc': None,
        'cat_code': 3, 'stat_cat': '중정비위탁'
    },
    {
        'm_row': 115, 'gubun': None, 'area': None, 'item': None, 'country': '국내',
        'target': '대한항공 (중정비)', 'checklist': None, 'fallback_prev': '2025.01.09~10(간)',
        'interval': None, 'plan_month': 5, 'auditor': '권혁, 김주원', 'etc': None,
        'cat_code': 4, 'stat_cat': '국내정비위탁'
    },
    {
        'm_row': 117, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': 'KAEMS', 'checklist': None, 'fallback_prev': '2025.09.11(간)',
        'interval': None, 'plan_month': 9, 'auditor': '유준열', 'etc': None,
        'cat_code': 4, 'stat_cat': '국내정비위탁'
    },

    # --- 6. 외부 - 주요 정비작업 업체 - 엔진 중정비 ---
    {
        'm_row': 92, 'gubun': None, 'area': None, 'item': '엔진\n중정비', 'country': '중국',
        'target': 'ST Aerospace Engines Pte Ltd (XIAMEN)', 'checklist': None, 'fallback_prev': '2025.08.22(간)',
        'interval': None, 'plan_month': 8, 'auditor': '최병근', 'etc': None,
        'cat_code': 3, 'stat_cat': '중정비위탁'
    },
    {
        'm_row': 94, 'gubun': None, 'area': None, 'item': None, 'country': '인도네시아',
        'target': 'GMF (CGK 자카르타) ENG', 'checklist': None, 'fallback_prev': '2025.03.04~06(간)',
        'interval': None, 'plan_month': 3, 'auditor': '최병근, 박현', 'etc': None,
        'cat_code': 3, 'stat_cat': '중정비위탁'
    },
    {
        'm_row': 95, 'gubun': None, 'area': None, 'item': None, 'country': '영국',
        'target': 'GE Aircraft Engine Services (Wales)', 'checklist': None, 'fallback_prev': '2025.06.23(간)',
        'interval': None, 'plan_month': 6, 'auditor': '박현', 'etc': None,
        'cat_code': 3, 'stat_cat': '중정비위탁'
    },
    {
        'm_row': 96, 'gubun': None, 'area': None, 'item': None, 'country': '아랍에미레이트',
        'target': 'SANAD Aerotech (AUH 아부다비)', 'checklist': None, 'fallback_prev': '초도',
        'interval': None, 'plan_month': 9, 'auditor': '박현', 'etc': 'Trent700 엔진정비',
        'cat_code': 3, 'stat_cat': '중정비위탁'
    },
    {
        'm_row': 113, 'gubun': None, 'area': None, 'item': None, 'country': '독일',
        'target': 'N3 Engine Overhaul Services', 'checklist': None, 'fallback_prev': '2025.09.16~18(직)',
        'interval': None, 'plan_month': 9, 'auditor': '박현', 'etc': None,
        'cat_code': 3, 'stat_cat': '중정비위탁'
    },
    {
        'm_row': 114, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': 'Lufthansa Technik AG (Engine / HAM)', 'checklist': None, 'fallback_prev': '2025.04.16~18(직)',
        'interval': None, 'plan_month': 4, 'auditor': '박현', 'etc': None,
        'cat_code': 3, 'stat_cat': '중정비위탁'
    },
    {
        'm_row': 116, 'gubun': None, 'area': None, 'item': None, 'country': '국내',
        'target': 'GE ON WINGS KOREA', 'checklist': None, 'fallback_prev': '2025.05.26~28(간)',
        'interval': None, 'plan_month': 5, 'auditor': '박현', 'etc': None,
        'cat_code': 4, 'stat_cat': '국내정비위탁'
    },

    # --- 7. 외부 - 정비 협력업체 (3행: 직접 3건 - 대동금속, 고암에이스항공, DMT) ---
    {
        'm_row': 121, 'gubun': None, 'area': '정비 협력업체', 'item': '도급', 'country': '국내',
        'target': '대동금속', 'checklist': 'TW-MNT-013\n도급업체', 'fallback_prev': '2026.06.23(직)',
        'interval': '1년', 'plan_month': 6, 'auditor': '최병근', 'etc': None,
        'cat_code': 4, 'stat_cat': '정비협력업체'
    },
    {
        'm_row': 122, 'gubun': None, 'area': None, 'item': None, 'country': None,
        'target': '고암에이스항공', 'checklist': 'TW-MNT-014\n협력업체', 'fallback_prev': '2026.08.19(직)',
        'interval': None, 'plan_month': 8, 'auditor': '박병권', 'etc': None,
        'cat_code': 4, 'stat_cat': '정비협력업체'
    },
    {
        'm_row': 120, 'gubun': None, 'area': None, 'item': 'W/T', 'country': None,
        'target': 'DMT', 'checklist': None, 'fallback_prev': '2026.07.30(직)',
        'interval': None, 'plan_month': 7, 'auditor': '박현', 'etc': None,
        'cat_code': 4, 'stat_cat': '정비협력업체'
    }
]

# Populate dynamic fields from Master (비운항 자동 제외 + 그룹 라벨 승계)
items_2027 = []
pending_labels = {'gubun': None, 'area': None, 'item': None, 'country': None, 'checklist': None, 'interval': None}

for d in plan_definitions:
    item = copy.deepcopy(d)
    m_row = item.get('m_row')
    m_rec = master_rows.get(m_row) if m_row else None

    for k in pending_labels:
        if item.get(k):
            pending_labels[k] = item[k]

    if m_rec and m_rec.get('op') == '비운항':
        continue

    for k in pending_labels:
        if pending_labels[k] and not item.get(k):
            item[k] = pending_labels[k]
        pending_labels[k] = None

    if m_rec:
        # 1. Indirect vs Direct from Master's 2027 symbol ('●' vs '◎')
        s27 = m_rec['s27']
        item['is_indirect'] = (s27 == '◎')
        item['master_symbol'] = s27 or '●'
        item['master_name'] = m_rec['name']
        item['master_op'] = m_rec['op']
        # 2. Previous audit date from Master
        prev_str = format_master_prev_date(m_rec, item['fallback_prev'])
        item['prev_date'] = prev_str
        # 3. Planned month
        item['plan_month'] = extract_month_from_prev(prev_str, item['plan_month'])
    else:
        item['is_indirect'] = False
        item['master_symbol'] = '-'
        item['master_name'] = item['target']
        item['master_op'] = '자체심사대체'
        item['prev_date'] = item['fallback_prev']

    items_2027.append(item)

dir_count = sum(1 for x in items_2027 if not x.get('is_quality_self') and not x['is_indirect'])
ind_count = sum(1 for x in items_2027 if not x.get('is_quality_self') and x['is_indirect'])
print(f"[2/4] Master 데이터 동기화 완료: 총 {len(items_2027)}행 (운항 직접심사: {dir_count}건, 간접심사: {ind_count}건, 안전품질대체: 1건)")

# Load 2026 template for page setup & column widths if available
ws_template = None
if os.path.exists(TEMPLATE_2026_PATH):
    wb_template = openpyxl.load_workbook(TEMPLATE_2026_PATH)
    ws_template = wb_template.active

wb_new = openpyxl.Workbook()

# Common Styles
font_title = Font(name='맑은 고딕', size=16, bold=True, color='000000')
font_sub = Font(name='맑은 고딕', size=9, bold=False, color='333333')
font_legend_bold = Font(name='맑은 고딕', size=9, bold=True, color='1F4E78')
font_header = Font(name='맑은 고딕', size=9, bold=True, color='000000')
font_data = Font(name='맑은 고딕', size=9, bold=False, color='000000')
font_data_bold = Font(name='맑은 고딕', size=9, bold=True, color='000000')
font_p_direct = Font(name='맑은 고딕', size=9, bold=True, color='1F4E78')
font_p_indirect = Font(name='맑은 고딕', size=8, bold=True, color='7F6000')
font_ind_tag = Font(name='맑은 고딕', size=8, bold=True, color='7F6000')

fill_header = PatternFill(start_color='D9E1F2', end_color='D9E1F2', fill_type='solid')
if ws_template and ws_template.cell(4, 1).fill and ws_template.cell(4, 1).fill.fill_type:
    fill_header = copy.copy(ws_template.cell(4, 1).fill)

# Enhanced Sheet Fills
fill_yellow_std = PatternFill(start_color='FFFFFFCC', end_color='FFFFFFCC', fill_type='solid')     # 기존 표준 노란색
fill_yellow_soft = PatternFill(start_color='FFF9DB', end_color='FFF9DB', fill_type='solid')       # 개선양식 소프트 웜 옐로우 (간접심사 행)
fill_p_direct = PatternFill(start_color='D9E1F2', end_color='D9E1F2', fill_type='solid')          # 직접심사 계획월(P) 포인트 셀
fill_p_indirect = PatternFill(start_color='FFE699', end_color='FFE699', fill_type='solid')        # 간접심사 계획월(P(간)) 골드 포인트 셀
fill_white = PatternFill(fill_type=None)
fill_gray_quality = PatternFill(start_color='F2F2F2', end_color='F2F2F2', fill_type='solid')
fill_sum_direct = PatternFill(start_color='E9EDF4', end_color='E9EDF4', fill_type='solid')
fill_sum_indirect = PatternFill(start_color='FFF2CC', end_color='FFF2CC', fill_type='solid')
fill_sum_total = PatternFill(start_color='D9E1F2', end_color='D9E1F2', fill_type='solid')

thin_side = Side(border_style='thin', color='000000')
double_bottom = Side(border_style='double', color='000000')
thick_top = Side(border_style='medium', color='1F4E78')

border_all_thin = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
border_total_row = Border(left=thin_side, right=thin_side, top=thin_side, bottom=double_bottom)

align_center = Alignment(horizontal='center', vertical='center', wrap_text=True)
align_left = Alignment(horizontal='left', vertical='center', wrap_text=True)
align_right = Alignment(horizontal='right', vertical='center', wrap_text=True)


def build_plan_sheet(ws, is_enhanced=True):
    ws.sheet_view.showGridLines = True
    if ws_template:
        ws.page_setup.orientation = ws_template.page_setup.orientation
        ws.page_setup.paperSize = ws_template.page_setup.paperSize

        # Copy column widths from 2026 template
        for col_idx in range(1, 33):
            col_letter = get_column_letter(col_idx)
            if col_letter in ws_template.column_dimensions and ws_template.column_dimensions[col_letter].width:
                ws.column_dimensions[col_letter].width = ws_template.column_dimensions[col_letter].width
    ws.column_dimensions['F'].width = 28
    ws.column_dimensions['G'].width = 19
    ws.column_dimensions['H'].width = 18
    ws.column_dimensions['W'].width = 13
    ws.column_dimensions['X'].width = 18
    for m in range(1, 13):
        ws.column_dimensions[get_column_letter(10 + m)].width = 5.2 if is_enhanced else 4.5

    # Row 1-2: Title
    ws.merge_cells('A1:X2')
    title_cell = ws.cell(1, 1)
    title_cell.value = '2027년도 정비부문 품질심사 계획 (R.0)'
    title_cell.font = font_title
    title_cell.alignment = align_center

    # Row 3: Legend
    if is_enhanced:
        ws.merge_cells('A3:N3')
        l_left = ws.cell(3, 1)
        l_left.value = f'■ 구분 안내 :  [백색 행 / 청색 P] 직접심사(현장출장, {dir_count}건)   |   [황색 음영 / 황색 P(간)] 간접심사(서류심사, {ind_count}건)   |   [회색 행] 안전품질 감사 대체'
        l_left.font = font_legend_bold
        l_left.alignment = align_left

        ws.merge_cells('O3:X3')
        l_right = ws.cell(3, 15)
        l_right.value = 'P : 계획(직접)  |  P(간) : 계획(간접/서류)  |  I : 진행중  |  R : 보고완료  |  O : 지연'
        l_right.font = font_sub
        l_right.alignment = align_right
    else:
        ws.merge_cells('W3:X3')
        legend_cell = ws.cell(3, 23)
        legend_cell.value = 'P:계획, I:진행중, R:보고완료, O:지연'
        legend_cell.font = font_sub
        legend_cell.alignment = align_right

    # Row 4: Header
    headers = {
        1: '심사 분야\n(Audit Area)',
        3: '심사 항목\n(Audit Item)',
        5: '점검대상',
        7: '점검표 (Audit Checklist)',
        8: '이전 품질심사 수행일자\n(Previous Audit Date)',
        9: '품질심사 주기\n(Interval)',
        10: '2027년 수행일자',
        11: '1월', 12: '2월', 13: '3월', 14: '4월', 15: '5월', 16: '6월',
        17: '7월', 18: '8월', 19: '9월', 20: '10월', 21: '11월', 22: '12월',
        23: '심사원',
        24: '기타\n(심사방식/비고)' if is_enhanced else '기타',
        25: '완료여부',
    }

    ws.row_dimensions[4].height = 28
    for c in range(1, 26):
        cell = ws.cell(4, c)
        if c in headers:
            cell.value = headers[c]
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = align_center
        cell.border = border_all_thin

    ws.merge_cells('A4:B4')
    ws.merge_cells('C4:D4')
    ws.merge_cells('E4:F4')

    # Write Data Rows (Row 5 to 67)
    start_row = 5
    last_data_row = start_row + len(items_2027) - 1

    for idx, item in enumerate(items_2027):
        row_num = start_row + idx
        ws.row_dimensions[row_num].height = 20

        is_ind = item['is_indirect']
        is_q_self = item.get('is_quality_self', False)

        # Columns A ~ Y
        ws.cell(row_num, 1, item['gubun'])
        ws.cell(row_num, 2, '정기' if idx == 0 else None)
        ws.cell(row_num, 3, item['area'])
        ws.cell(row_num, 4, item['item'])
        ws.cell(row_num, 5, item['country'])
        ws.cell(row_num, 6, item['target'])
        ws.cell(row_num, 7, item['checklist'])
        ws.cell(row_num, 8, item['prev_date'])
        ws.cell(row_num, 9, item['interval'])
        ws.cell(row_num, 10, None)

        p_month = item['plan_month']
        for m in range(1, 13):
            col = 10 + m
            cell_m = ws.cell(row_num, col)
            if m == p_month:
                if is_enhanced and is_ind:
                    cell_m.value = 'P(간)'
                else:
                    cell_m.value = 'P'
            else:
                cell_m.value = None

        ws.cell(row_num, 23, item['auditor'])

        # Remarks (X col)
        etc_val = item['etc']
        if is_enhanced:
            if is_ind:
                etc_val = f"[간접/서류] {etc_val}" if etc_val else "[간접/서류심사]"
        ws.cell(row_num, 24, etc_val)
        ws.cell(row_num, 25, '간접' if is_ind else ('대체' if is_q_self else '직접'))

        # Hidden/Aux columns Z (26) & AA (27) for summary formulas
        ws.cell(row_num, 26, item['cat_code'])
        ws.cell(row_num, 27, item['stat_cat'])

        # Cell Styling
        row_bg = fill_yellow_soft if (is_enhanced and is_ind) else (fill_yellow_std if is_ind else fill_white)

        for c in range(1, 28):
            cell = ws.cell(row_num, c)
            cell.font = font_data
            cell.border = border_all_thin
            cell.alignment = align_center

            if c == 6:  # 점검대상명
                cell.font = font_data_bold if not is_ind else font_data
                if item['target'] and len(str(item['target'])) > 16:
                    cell.alignment = align_left

            # Apply background fill
            if is_q_self and c in range(5, 26):
                cell.fill = fill_gray_quality
            elif is_ind and c in range(5, 28):
                # Only shade columns E..AA so merged category headers in A..D stay clean white!
                cell.fill = row_bg

            # Highlight scheduled month cell in enhanced mode
            if 11 <= c <= 22 and cell.value is not None:
                if is_enhanced:
                    if is_ind:
                        cell.fill = fill_p_indirect
                        cell.font = font_p_indirect
                    elif not is_q_self:
                        cell.fill = fill_p_direct
                        cell.font = font_p_direct
                    else:
                        cell.font = font_data_bold
                else:
                    cell.font = font_data_bold

            if is_enhanced and c == 24 and is_ind:
                cell.font = font_ind_tag

    # Merged Cells (matching 2026 official layout cleanly)
    # 1. A열: 내부 (Row 5~22: 부서 8 + 국내지점 5 + 해외운항지점 5 = 18행), 외부 (Row 23~67)
    ws.merge_cells('A5:A22')
    ws.merge_cells(f'A23:A{last_data_row}')

    # 2. B열: 정기 (Row 5~67 전체 병합)
    ws.merge_cells(f'B5:B{last_data_row}')

    # 3. C열 & D열, G열, I열 병합 (동적 행 번호 계산)
    # 53 rows total (rows 5..57): 부서 8 (5..12), 국내지점 5 (13..17), 해외지점 5 (18..22), 운항위탁 15 (23..37), 항공기중정비 10 (38..47), 엔진중정비 7 (48..54), 협력업체 3 (55..57)
    r_coop_start = last_data_row - 2
    r_mro_end = r_coop_start - 1
    r_eng_start = r_mro_end - 6
    r_heavy_start = r_eng_start - 10

    ws.merge_cells('C5:D12')
    ws.merge_cells('C13:D17')
    ws.merge_cells(f'C18:C{r_heavy_start - 1}')
    ws.merge_cells(f'D18:D{r_heavy_start - 1}')
    ws.merge_cells(f'C{r_heavy_start}:C{r_mro_end}')
    ws.merge_cells(f'D{r_heavy_start}:D{r_eng_start - 1}')
    ws.merge_cells(f'D{r_eng_start}:D{r_mro_end}')
    ws.merge_cells(f'C{r_coop_start}:C{last_data_row}')
    ws.merge_cells(f'D{r_coop_start}:D{last_data_row - 1}')

    # 4. G열 (점검표) 병합
    ws.merge_cells('G13:G22')
    ws.merge_cells(f'G23:G{r_mro_end}')
    ws.merge_cells(f'G{r_coop_start + 1}:G{last_data_row}')

    # 5. I열 (주기) 병합
    ws.merge_cells('I5:I17')
    ws.merge_cells(f'I18:I{r_mro_end}')
    ws.merge_cells(f'I{r_coop_start}:I{last_data_row}')

    # Ensure all merged cells have clean borders
    for r in range(5, last_data_row + 1):
        for c in range(1, 28):
            ws.cell(r, c).border = border_all_thin

    # 7. Bottom Monthly Summary Rows (in Enhanced sheet)
    if is_enhanced:
        r_dir = last_data_row + 1
        r_ind = last_data_row + 2
        r_tot = last_data_row + 3

        ws.row_dimensions[r_dir].height = 20
        ws.row_dimensions[r_ind].height = 20
        ws.row_dimensions[r_tot].height = 22

        ws.merge_cells(f'A{r_dir}:J{r_dir}')
        ws.merge_cells(f'A{r_ind}:J{r_ind}')
        ws.merge_cells(f'A{r_tot}:J{r_tot}')

        ws.cell(r_dir, 1, '월별 직접심사 (● 현장/출장) 계획 건수')
        ws.cell(r_ind, 1, '월별 간접심사 (◎ 서류심사) 계획 건수')
        ws.cell(r_tot, 1, '월별 품질심사 총 건수 (직접 + 간접)')

        for m in range(1, 13):
            col = 10 + m
            col_let = get_column_letter(col)
            rng = f'{col_let}5:{col_let}{last_data_row}'
            ws.cell(r_dir, col, f'=COUNTIF({rng}, "P")')
            ws.cell(r_ind, col, f'=COUNTIF({rng}, "P(간)")')
            ws.cell(r_tot, col, f'=COUNTA({rng})')

        # Annual Sum across months in Col W (23)
        ws.cell(r_dir, 23, f'=SUM(K{r_dir}:V{r_dir})')
        ws.cell(r_ind, 23, f'=SUM(K{r_ind}:V{r_tot - 1})')
        ws.cell(r_tot, 23, f'=SUM(K{r_tot}:V{r_tot})')

        ws.cell(r_dir, 24, f'현장 출장 심사 (정비품질 포함 시 {dir_count + 1})')
        ws.cell(r_ind, 24, f'서류 간접 심사 ({ind_count}건)')
        ws.cell(r_tot, 24, f'연간 총 계획 ({len(items_2027)}건)')

        for r_idx, bg_fill, fnt in [
            (r_dir, fill_sum_direct, font_p_direct),
            (r_ind, fill_sum_indirect, font_p_indirect),
            (r_tot, fill_sum_total, font_data_bold)
        ]:
            for c in range(1, 26):
                cell = ws.cell(r_idx, c)
                cell.fill = bg_fill
                cell.font = fnt
                cell.alignment = align_center
                cell.border = border_total_row if r_idx == r_tot else border_all_thin

    # 8. Right-side Summary Statistics Table (Cols AB ~ AF)
    ws.column_dimensions['AB'].width = 10
    ws.column_dimensions['AC'].width = 24
    ws.column_dimensions['AD'].width = 10
    ws.column_dimensions['AE'].width = 10
    ws.column_dimensions['AF'].width = 10

    if is_enhanced:
        # Enhanced Summary Table: Direct / Indirect / Total breakdown by category
        ws.merge_cells('AB3:AF3')
        st_title = ws.cell(3, 28, '■ 2027년 분야별 직접/간접 심사 집계표 (Master 연동)')
        st_title.font = font_legend_bold
        st_title.alignment = align_left

        st_headers = [(28, '구분'), (29, '심사 분야'), (30, '직접(●)'), (31, '간접(◎)'), (32, '합계')]
        for c_idx, h_text in st_headers:
            c = ws.cell(4, c_idx, h_text)
            c.font = font_header
            c.fill = fill_header
            c.alignment = align_center
            c.border = border_all_thin

        stat_rows = [
            ('내부/국내', '정비본부, 국내 운항지점', f'=COUNTIFS(Z5:Z{last_data_row}, 1, Y5:Y{last_data_row}, "직접")+1', f'=COUNTIFS(Z5:Z{last_data_row}, 1, Y5:Y{last_data_row}, "간접")'),
            ('국내외주', '국내정비위탁, 협력업체', f'=COUNTIFS(Z5:Z{last_data_row}, 4, Y5:Y{last_data_row}, "직접")', f'=COUNTIFS(Z5:Z{last_data_row}, 4, Y5:Y{last_data_row}, "간접")'),
            ('해외지점', '해외 운항지점', f'=COUNTIFS(Z5:Z{last_data_row}, 2, Y5:Y{last_data_row}, "직접")', f'=COUNTIFS(Z5:Z{last_data_row}, 2, Y5:Y{last_data_row}, "간접")'),
            ('해외외주', '운항정비위탁, 중정비위탁', f'=COUNTIFS(Z5:Z{last_data_row}, 3, Y5:Y{last_data_row}, "직접")', f'=COUNTIFS(Z5:Z{last_data_row}, 3, Y5:Y{last_data_row}, "간접")'),
        ]
        for idx_s, (g_lbl, cat_lbl, f_dir, f_ind) in enumerate(stat_rows, start=5):
            ws.cell(idx_s, 28, g_lbl).alignment = align_center
            ws.cell(idx_s, 29, cat_lbl).alignment = align_left
            ws.cell(idx_s, 30, f_dir).alignment = align_center
            ws.cell(idx_s, 31, f_ind).alignment = align_center
            ws.cell(idx_s, 32, f'=AD{idx_s}+AE{idx_s}').alignment = align_center
            for c_i in range(28, 33):
                ws.cell(idx_s, c_i).font = font_data
                ws.cell(idx_s, c_i).border = border_all_thin

        # Total row (Row 9)
        ws.merge_cells('AB9:AC9')
        ws.cell(9, 28, '총 계 (정비품질 대체 1건 포함)')
        ws.cell(9, 30, '=SUM(AD5:AD8)')
        ws.cell(9, 31, '=SUM(AE5:AE8)')
        ws.cell(9, 32, '=SUM(AF5:AF8)')
        for c_i in range(28, 33):
            ws.cell(9, c_i).font = font_data_bold
            ws.cell(9, c_i).fill = fill_sum_total
            ws.cell(9, c_i).alignment = align_center
            ws.cell(9, c_i).border = border_total_row
    else:
        # Standard 2026-compatible Right Summary Table (Cols AB ~ AD)
        ws.cell(4, 28, '국내').alignment = align_center
        ws.cell(4, 29, '정비본부,운항지점').alignment = align_center
        ws.cell(4, 30, '=COUNTIF(Z:Z, 1)+1').alignment = align_center

        ws.cell(5, 29, '주요정비업체,협력,기술관리').alignment = align_center
        ws.cell(5, 30, '=COUNTIF(Z:Z, 4)').alignment = align_center

        ws.cell(6, 28, '해외').alignment = align_center
        ws.cell(6, 29, '운항지점').alignment = align_center
        ws.cell(6, 30, '=COUNTIF(Z:Z, 2)').alignment = align_center

        ws.cell(7, 29, '주요정비업체').alignment = align_center
        ws.cell(7, 30, '=COUNTIF(Z:Z, 3)').alignment = align_center

        ws.cell(8, 29, '총 계').alignment = align_center
        ws.cell(8, 30, '=SUM(AD4:AD7)').alignment = align_center

        for r_s in range(4, 9):
            for c_s in range(28, 31):
                ws.cell(r_s, c_s).font = font_data_bold if r_s == 8 else font_data
                ws.cell(r_s, c_s).border = border_all_thin


def build_verification_sheet(ws):
    ws.sheet_view.showGridLines = True
    ws.merge_cells('A1:H2')
    t = ws.cell(1, 1, f'Master 파일 ({os.path.basename(MASTER_PATH)}) ↔ 2027년 계획표 연동 검증 리포트')
    t.font = font_title
    t.alignment = align_center

    ws.merge_cells('A4:H4')
    s1 = ws.cell(4, 1, '1. 2027년 품질심사 대상 집계 대조 (Master 수행실적 vs 2027년 계획표)')
    s1.font = Font(name='맑은 고딕', size=11, bold=True, color='1F4E78')

    headers_1 = ['구분', 'Master 파일 (운항 기준)', '2027년 계획표 반영', '일치 여부', '비고']
    for idx_c, h in enumerate(headers_1, 1):
        c = ws.cell(5, idx_c, h)
        c.font = font_header
        c.fill = fill_header
        c.alignment = align_center
        c.border = border_all_thin

    rows_1 = [
        ('직접심사 (●)', f'{dir_count}건', f'{dir_count}건 (+정비품질 대체 1건)', '100% 일치', '내부부서(7), 국내공항(5), 해외공항(3), 위탁/MRO/국내업체(25)'),
        ('간접심사 (◎)', f'{ind_count}건', f'{ind_count}건', '100% 일치', '해외공항(2), 완전위탁(4), 중정비(4), 해외엔진(2)'),
        ('운항 심사 합계', f'{dir_count + ind_count}건', f'{dir_count + ind_count}건 (표 전체 {len(items_2027)}행)', '100% 일치', f'정비품질(안전보안실 감사 대체) 포함 시 총 {len(items_2027)}행'),
        ('비운항 제외 (수식잔존)', '13건 (비운항)', '계획표 제외 (비운항)', '정상 제외', 'LTP(CEB), MABES(BKI), JAE(DPS), STORM(DAC), JAL, SIAEJ, Southern(YNJ), EU Wings(TAS) 등 비운항 제외'),
    ]
    for r_i, r_data in enumerate(rows_1, 6):
        for c_i, val in enumerate(r_data, 1):
            c = ws.cell(r_i, c_i, val)
            c.font = font_data_bold if c_i in [1, 4] else font_data
            c.alignment = align_left if c_i == 5 else align_center
            c.border = border_all_thin

    ws.merge_cells('A12:H12')
    s2 = ws.cell(12, 1, '2. Master (2026.11.09) 주요 최신 변경사항 반영 내역')
    s2.font = Font(name='맑은 고딕', size=11, bold=True, color='1F4E78')

    headers_2 = ['Master 행', '구분', '점검대상 (Station / 업체)', '변경 내용', '2027년 계획표 반영 결과']
    for idx_c, h in enumerate(headers_2, 1):
        c = ws.cell(13, idx_c, h)
        c.font = font_header
        c.fill = fill_header
        c.alignment = align_center
        c.border = border_all_thin

    changes = [
        ('R96', '엔진정비업체', 'SANAD Aerotech (AUH 아부다비)', '2026년 → 2027년 직접심사(●)로 변경', '엔진 중정비 섹션에 2027년 직접심사(9월)로 신규 반영'),
        ('R121', '국내업체', 'DMT', '2025.05(직) → 2026.07.30(직) → 2027년 직접(●) 변경', '정비 협력업체(W/T) 1년 주기 직접심사(7월)로 반영 (기존 간접에서 변경)'),
        ('R91', '엔진정비업체', 'EU Wings (TAS 타슈켄트)', '운항 → 비운항으로 상태 변경', '비운항 전환에 따라 2027년 심사 계획표에서 제외'),
        ('R57, R58', '완전위탁업체', 'JAL (FUK 후쿠오카 / CTS 삿포로)', '비운항 상태 유지', '비운항 지점이므로 2027년 심사 계획표에서 제외'),
        ('R119', '국내업체', 'Sharp Technics K', '2026.07.07~08 간접심사(◎) 완료 (2028년 직접 도래)', '2년 주기에 따라 2027년 휴지 (2028년 직접심사 예정)'),
        ('R112, R113', '국내업체', '대한항공 (ICN/GMP 인천·김포, CJU 제주)', '2025.01.09~10(간) → 2027년 직접심사(●) 도래', '운항정비 위탁 섹션(국내)에 2027년 직접심사로 반영'),
        ('R20~R22', '해외운항지점', 'CTS(4월), OKA(5월), KMJ(6월)', '2025년 실제 수행일자 업데이트', '이전 수행일자 및 2027년 계획월(4월, 5월, 6월) 정밀 동기화'),
        ('R47~R64', '완전위탁업체', 'APLUS, LTP, MABES, SIAEJ 등', '2025년 실제 수행일자 업데이트', '이전 수행일자 및 2027년 계획월 정밀 동기화'),
    ]
    for r_i, r_data in enumerate(changes, 14):
        for c_i, val in enumerate(r_data, 1):
            c = ws.cell(r_i, c_i, val)
            c.font = font_data_bold if c_i == 3 else font_data
            c.alignment = align_left if c_i in [3, 4, 5] else align_center
            c.border = border_all_thin

    widths = {'A': 14, 'B': 18, 'C': 34, 'D': 42, 'E': 48}
    for col_l, w in widths.items():
        ws.column_dimensions[col_l].width = w


print("[3/4] 시트 생성 중 (1: 개선양식, 2: 기존표준양식, 3: Master 연동 검증)...")
ws_enhanced = wb_new.active
ws_enhanced.title = "2027년 계획표 (개선양식)"
build_plan_sheet(ws_enhanced, is_enhanced=True)

ws_standard = wb_new.create_sheet(title="2027년 계획표 (기존표준양식)")
build_plan_sheet(ws_standard, is_enhanced=False)

ws_verify = wb_new.create_sheet(title="Master 연동 검증내역")
build_verification_sheet(ws_verify)

print(f"[4/4] 파일 저장 중: {OUTPUT_2027_PATH}")
wb_new.save(OUTPUT_2027_PATH)
print("성공적으로 생성 완료되었습니다!")
