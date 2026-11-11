import sqlite3
import os
import re
import glob
import datetime
import openpyxl

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "audit.db")

def get_latest_master_excel():
    files = sorted(glob.glob(os.path.join(BASE_DIR, "(Master)*.xlsm")))
    if files:
        return files[-1]
    return os.path.join(BASE_DIR, "(Master) 정비본부 품질심사 실시이력(2026.11.11).xlsm")

# 행 번호(r: 6~135) 또는 지점명 기준 기종/엔진/담당심사원/예정월 메타데이터
ROW_METADATA = {
    # 해외운항지점 (R006 ~ R044)
    6:  {"name": "GUM (괌)", "ac": "B738", "eng": "CFM56", "aud25": "이진성", "aud27": "최병근", "m26": 10},
    7:  {"name": "SPN (사이판)", "ac": "B738", "eng": "CFM56", "aud26": "이진성", "m26": 11},
    8:  {"name": "SYD (시드니)", "ac": "A332,A333", "eng": "PW4100,TRENT700"},
    9:  {"name": "VTE (비엔티엔)", "ac": "B738", "eng": "CFM56"},
    10: {"name": "CNX (치앙마이)", "ac": "B738", "eng": "CFM56"},
    11: {"name": "SGN (호치민)", "ac": "B738,B38M", "eng": "CFM56,LEAP-1B", "m26": 10},
    12: {"name": "DAD (다낭)", "ac": "B738,B38M,A333", "eng": "CFM56,LEAP-1B,TRENT700", "aud26": "원대연, 최병근", "m26": 8},
    13: {"name": "CXR (나트랑)", "ac": "B738,B38M,A333", "eng": "CFM56,LEAP-1B,TRENT700", "aud25": "박병권, 최병근", "aud27": "이진성", "m26": 2},
    14: {"name": "HAN (하노이)", "ac": "B738,B38M", "eng": "CFM56,LEAP-1B"},
    15: {"name": "DMK (돈므앙)", "ac": "B738,A333", "eng": "CFM56,TRENT700"},
    16: {"name": "KLO (칼리보)", "ac": "B738", "eng": "CFM56", "aud26": "유준열", "m26": 11},
    17: {"name": "CRK (클락)", "ac": "B738,B38M", "eng": "CFM56,LEAP-1B"},
    18: {"name": "CEB (세부)", "ac": "B738", "eng": "CFM56", "aud26": "박병권", "m26": 10},
    19: {"name": "TAG (보홀)", "ac": "B738,B38M", "eng": "CFM56,LEAP-1B"},
    20: {"name": "CTS (치토세)", "ac": "B738,B38M,A333", "eng": "CFM56,LEAP-1B,TRENT700", "aud25": "최병근", "aud27": "김주원", "m26": 4},
    21: {"name": "OKA (오키나와)", "ac": "B738,B38M", "eng": "CFM56,LEAP-1B", "aud25": "박병권", "aud27": "박병권", "m26": 5},
    22: {"name": "KMJ (구마모토)", "ac": "B738,B38M", "eng": "CFM56,LEAP-1B", "aud25": "원대연", "aud27": "원대연", "m26": 6},
    23: {"name": "KIX (오사카)", "ac": "B738,B38M,A333", "eng": "CFM56,LEAP-1B,TRENT700", "aud26": "김주원", "m26": 9},
    24: {"name": "FUK (후쿠오카)", "ac": "B738,B38M,A333", "eng": "CFM56,LEAP-1B,TRENT700", "aud26": "원대연", "m26": 9},
    25: {"name": "NRT (나리타)", "ac": "B738,B38M,A333", "eng": "CFM56,LEAP-1B,TRENT700", "aud26": "최병근", "m26": 9},
    26: {"name": "OIT (오이타)", "ac": "B738", "eng": "CFM56"},
    27: {"name": "NGO (나고야)", "ac": "B738", "eng": "CFM56"},
    28: {"name": "KKJ (기타규슈)", "ac": "B738", "eng": "CFM56"},
    29: {"name": "KOJ (가고시마)", "ac": "B738", "eng": "CFM56"},
    30: {"name": "HSG (사가)", "ac": "B738", "eng": "CFM56", "aud26": "최병근", "m26": 10},
    31: {"name": "WNZ (원저우)", "ac": "B738", "eng": "CFM56"},
    32: {"name": "SHE (심양)", "ac": "B738", "eng": "CFM56"},
    33: {"name": "WUH (우한)", "ac": "B738", "eng": "CFM56"},
    34: {"name": "DYG (장가계)", "ac": "B738", "eng": "CFM56", "aud26": "김주원", "m26": 10},
    35: {"name": "TAO (칭다오)", "ac": "B738", "eng": "CFM56"},
    36: {"name": "TNA (제남)", "ac": "B738", "eng": "CFM56"},
    37: {"name": "YNJ (연길)", "ac": "B738", "eng": "CFM56", "aud26": "최병근", "m26": 11},
    38: {"name": "TSN (텐진)", "ac": "B738", "eng": "CFM56"},
    39: {"name": "MFM (마카오)", "ac": "B738", "eng": "CFM56"},
    40: {"name": "BKI (코타키나발루)", "ac": "B738,B38M", "eng": "CFM56,LEAP-1B", "aud26": "유준열", "m26": 12},
    41: {"name": "UBN (울란바트로)", "ac": "B738,B38M,A333", "eng": "CFM56,LEAP-1B,TRENT700", "aud26": "박병권", "m26": 9},
    42: {"name": "KHV (하바롭스크)", "ac": "B738", "eng": "CFM56"},
    43: {"name": "VVO (블라디보스톡)", "ac": "B738", "eng": "CFM56"},
    44: {"name": "FRU (비슈케크)", "ac": "B738,B38M", "eng": "CFM56,LEAP-1B", "aud26": "이진성", "m26": 9},

    # 완전위탁업체 -> 운항정비 위탁 (R045 ~ R088)
    45: {"name": "TG (BKK 방콕)", "ac": "B738,A332,A333", "eng": "CFM56,PW4100,TRENT700", "aud25": "유준열", "aud27": "박병권"},
    46: {"name": "TG (CNX 치앙마이)", "ac": "B738,B38M", "eng": "CFM56,LEAP-1B", "aud25": "최병근", "aud26": "박병권"},
    47: {"name": "APLUS (KLO 칼리보)", "ac": "B738", "eng": "CFM56", "aud25": "박병권, 이진성", "aud27": "유준열"},
    48: {"name": "LTP (CEB 세부)", "ac": "B738", "eng": "CFM56", "aud25": "송동훈, 김주원", "aud27": "박병권"},
    49: {"name": "MABES (BKI 코타키나발루)", "ac": "B738", "eng": "CFM56", "aud25": "원대연, 박현", "aud27": "유준열"},
    50: {"name": "JAE (DPS 발리)", "ac": "B738,B38M", "eng": "CFM56,LEAP-1B", "aud25": "유준열, 박현", "aud27": "원대연"},
    51: {"name": "STORM AVIATION (DAC 다카)", "ac": "A333", "eng": "TRENT700", "aud25": "박병권, 유준열", "aud27": "김주원"},
    52: {"name": "PAPAS (HKG 홍콩)", "ac": "B738,A333,B773", "eng": "CFM56,TRENT700,GE90", "aud25": "이진성", "aud27": "권혁"},
    53: {"name": "Mandarin Airlines (RMQ 타이중)", "ac": "B738,B38M", "eng": "CFM56,LEAP-1B", "aud26": "이진성"},
    54: {"name": "CHINA AIRLINES Ltd (TSA 송산)", "ac": "B738,B38M,A333", "eng": "CFM56,LEAP-1B,TRENT700", "aud25": "최병근, 박현", "aud26": "권혁"},
    55: {"name": "CHINA AIRLINES Ltd (TPE 타오위엔)", "ac": "B738,B38M,A333", "eng": "CFM56,LEAP-1B,TRENT700", "aud25": "최병근, 박현", "aud26": "권혁"},
    56: {"name": "CHINA AIRLINES Ltd (KHH 가오슝)", "ac": "B738,B38M", "eng": "CFM56,LEAP-1B", "aud25": "임주한, 이진성", "aud26": "권혁"},
    57: {"name": "JAL (FUK 후쿠오카)", "ac": "B738,B38M,A333", "eng": "CFM56,LEAP-1B,TRENT700", "aud25": "박현"},
    58: {"name": "JAL (CTS 삿포로)", "ac": "B738,B38M,A333", "eng": "CFM56,LEAP-1B,TRENT700", "aud25": "박현"},
    59: {"name": "Menzies Macau (MFM 마카오)", "ac": "B738,B38M", "eng": "CFM56,LEAP-1B", "aud26": "최병근, 이진성"},
    60: {"name": "SIAEJ (FUK 후쿠오카)", "ac": "B738,B38M,A333", "eng": "CFM56,LEAP-1B,TRENT700", "aud25": "박병권", "aud27": "원대연"},
    61: {"name": "SIAEJ (CTS 삿포로)", "ac": "B738,B38M,A333", "eng": "CFM56,LEAP-1B,TRENT700", "aud25": "박병권", "aud27": "김주원"},
    62: {"name": "SIAEJ (KIX 오사카)", "ac": "B738,B38M,A333,B773", "eng": "CFM56,LEAP-1B,TRENT700,GE90", "aud25": "임주한, 박병권", "aud27": "김주원"},
    63: {"name": "SIAEJ (NRT 도쿄)", "ac": "B738,B38M,A333,B773", "eng": "CFM56,LEAP-1B,TRENT700,GE90", "aud25": "박병권", "aud27": "최병근"},
    64: {"name": "SIAEJ (NGO 나고야)", "ac": "B738", "eng": "CFM56", "aud25": "박병권", "aud27": "최병근"},
    65: {"name": "EASTEC (베이징)", "ac": "B738,B38M", "eng": "CFM56,LEAP-1B", "aud26": "김주원"},
    66: {"name": "EASTEC (TAO 칭타오)", "ac": "B738", "eng": "CFM56", "aud25": "최병근", "aud26": "유준열"},
    67: {"name": "EASTEC (WUH 우한)", "ac": "B738", "eng": "CFM56", "aud25": "최병근", "aud27": "김주원"},
    68: {"name": "EASTEC (TNA 지난)", "ac": "B738", "eng": "CFM56", "aud26": "김주원, 유준열"},
    69: {"name": "Southern (SHE 선양)", "ac": "B738,A332", "eng": "CFM56,PW4100", "aud26": "최병근", "m26": 10},
    70: {"name": "Southern (YNJ 연길)", "ac": "B738", "eng": "CFM56", "aud25": "최병근", "aud27": "최병근"},
    71: {"name": "Southern (DYG 장자제)", "ac": "B738", "eng": "CFM56"},
    72: {"name": "HNA (HAK 하이커우)", "ac": "B738", "eng": "CFM56", "aud25": "박현", "aud27": "김주원"},
    73: {"name": "HNA (SYX 싼야)", "ac": "B738", "eng": "CFM56", "aud25": "박현", "aud27": "유준열"},
    74: {"name": "EASTEC (YNJ 연길)", "ac": "B738", "eng": "CFM56", "aud25": "임주한, 최병근", "aud27": "최병근"},
    75: {"name": "VAECO (HAN 하노이)", "ac": "B738,B38M", "eng": "CFM56,LEAP-1B", "aud26": "송동훈, 박현"},
    76: {"name": "VAECO (DAD 다낭)", "ac": "B738,B38M,A333", "eng": "CFM56,LEAP-1B,TRENT700", "aud26": "원대연, 최병근"},
    77: {"name": "VAECO (CXR 나트랑)", "ac": "B738,B38M,A333", "eng": "CFM56,LEAP-1B,TRENT700", "aud25": "박병권, 최병근", "aud27": "이진성"},
    78: {"name": "VAECO (PQC 푸꾸옥)", "ac": "B738,B38M", "eng": "CFM56,LEAP-1B", "aud25": "김주원", "aud27": "원대연"},
    79: {"name": "GMF (CGK 자카르타)", "ac": "A333", "eng": "TRENT700", "aud26": "원대연, 이진성"},
    80: {"name": "SIAEC (SIN 싱가포르)", "ac": "B38M,A332,A333", "eng": "LEAP-1B,PW4100,TRENT700", "aud26": "박병권, 이진성"},
    81: {"name": "Heston MRO (SYD 시드니)", "ac": "A332,A333", "eng": "PW4100,TRENT700", "aud26": "유준열"},
    82: {"name": "Avia Technics - ZAG (자그레브)", "ac": "A333", "eng": "TRENT700", "aud26": "권혁"},
    83: {"name": "Nayak Aero - CDG (파리)", "ac": "A332,A333,B773", "eng": "PW4100,TRENT700,GE90", "aud25": "박현", "aud27": "이진성"},
    84: {"name": "Atitech - FCO (로마)", "ac": "A332,A333,B773", "eng": "PW4100,TRENT700,GE90", "aud25": "박병권", "aud27": "권혁"},
    85: {"name": "KLM - BCN (바르셀로나)", "ac": "A332,A333,B773", "eng": "PW4100,TRENT700,GE90", "aud25": "최병근", "aud27": "박병권"},
    86: {"name": "KLM - CAI (카이로)", "ac": "A332,A333", "eng": "PW4100,TRENT700", "aud26": "권혁"},
    87: {"name": "Atitech - FRA (프랑크푸르트)", "ac": "A332,A333", "eng": "PW4100,TRENT700", "aud26": "이진성"},
    88: {"name": "Southbreeze - YVR (벤쿠버)", "ac": "A333,B773", "eng": "TRENT700,GE90", "aud25": "원대연, 김한민", "aud27": "유준열"},

    # 엔진정비업체 -> 중정비 위탁 (R089 ~ R098)
    89: {"name": "ST Aerospace Engines Pte Ltd (SIN)", "ac": "B738", "eng": "CFM56", "aud26": "최병근"},
    90: {"name": "SAESL (SIN 싱가폴)", "ac": "A333", "eng": "TRENT700", "aud26": "박병권, 최병근"},
    91: {"name": "EU Wings (TAS)", "ac": "A333", "eng": "TRENT700", "aud25": "이진성, 최수연"},
    92: {"name": "ST Aerospace Engines Pte Ltd (XIAMEN)", "ac": "B738", "eng": "CFM56", "aud25": "이진성", "aud27": "최병근", "m25": 8},
    93: {"name": "HAESL (HKG)", "ac": "A333", "eng": "TRENT700", "aud26": "박현"},
    94: {"name": "GMF (CGK 자카르타) ENG", "ac": "B738", "eng": "CFM56", "aud25": "박현", "aud27": "최병근, 박현"},
    95: {"name": "GE Aircraft Engine Services (Wales)", "ac": "B738,B773", "eng": "CFM56,GE90", "aud25": "유준열", "aud27": "박현"},
    96: {"name": "SANAD Aerotech (AUH 아부다비)", "ac": "A333", "eng": "TRENT700", "aud27": "박현", "m27": 9},
    97: {"name": "Standard Aero (위니펙)", "ac": "B738", "eng": "CFM56", "aud26": "이진성"},
    98: {"name": "GA Telesis (HEL 헬싱키)", "ac": "B738,A333", "eng": "CFM56,TRENT700", "aud26": "원대연, 이진성"},

    # 중정비업체 -> 중정비 위탁 (R099 ~ R111)
    99:  {"name": "AMECO (CTU)", "ac": "B738,A332,A333", "eng": "CFM56,PW4100,TRENT700", "aud25": "유준열", "aud27": "김주원"},
    100: {"name": "Air Asia Company Ltd (TNN) - Heavy", "ac": "B738", "eng": "CFM56", "aud25": "원대연", "aud27": "권혁"},
    101: {"name": "SIAEP (CRK 클락) - HEAVY", "ac": "B738,B38M", "eng": "CFM56,LEAP-1B", "aud25": "원대연, 김주원", "aud27": "원대연"},
    102: {"name": "LTP (MNL 마닐라) - HEAVY", "ac": "B738,A333", "eng": "CFM56,TRENT700", "aud25": "유준열, 최병근", "aud27": "박병권"},
    103: {"name": "MIAT Mongolian Airlines (ULN)", "ac": "B738", "eng": "CFM56", "aud25": "박병권", "aud27": "이진성"},
    104: {"name": "GMF (CGK 자카르타) - C/K", "ac": "B738,A333", "eng": "CFM56,TRENT700", "aud25": "박현", "aud27": "원대연, 이진성"},
    105: {"name": "EASTEC (KMG)", "ac": "B738", "eng": "CFM56", "aud26": "김주원"},
    106: {"name": "STAECO (TNA)", "ac": "B738,B38M", "eng": "CFM56,LEAP-1B", "aud26": "박병권"},
    107: {"name": "STATCO (XIANMEN) - ENGINE", "ac": "B738", "eng": "CFM56", "aud25": "이진성", "aud27": "최병근"},
    108: {"name": "HAITE (TIANJIN TSN 톈진)", "ac": "B738", "eng": "CFM56", "aud25": "박병권, 박현", "aud27": "김주원"},
    109: {"name": "STARCO (SHA 상하이)", "ac": "B738,A332,A333", "eng": "CFM56,PW4100,TRENT700", "aud26": "박병권, 최병근"},
    110: {"name": "GCAM (HAK 하이커우)", "ac": "B738,A333", "eng": "CFM56,TRENT700", "aud26": "원대연, 김주원"},
    111: {"name": "HAECO (XMN)", "ac": "B738,B38M,A333,B773", "eng": "CFM56,LEAP-1B,TRENT700,GE90", "aud26": "최병근", "m26": 10},

    # 국내업체 (R112 ~ R135)
    112: {"name": "대한항공 (ICN, GMP 인천,김포)", "cat": "운항정비 위탁", "intv": 2, "ac": "B738,B38M,A332,A333,B773", "eng": "CFM56,LEAP-1B,PW4100,TRENT700,GE90", "aud25": "박현", "aud27": "권혁, 김주원"},
    113: {"name": "대한항공 (CJU 제주)", "cat": "운항정비 위탁", "intv": 2, "ac": "B738,B38M,A333", "eng": "CFM56,LEAP-1B,TRENT700", "aud25": "박현", "aud27": "권혁, 김주원"},
    114: {"name": "N3 ENGINE OVERHAUL SERVICES", "cat": "중정비 위탁", "intv": 2, "ac": "A333", "eng": "TRENT700", "aud25": "박병권, 최병근", "aud27": "박현"},
    115: {"name": "Lufthansa Technik AG (Engine / HAM)", "cat": "중정비 위탁", "intv": 2, "ac": "A333,B773", "eng": "TRENT700,GE90", "aud25": "이진성, 최병근", "aud27": "박현"},
    116: {"name": "대한항공 (중정비)", "cat": "중정비 위탁", "intv": 2, "ac": "B738,B38M,A332,A333,B773", "eng": "CFM56,LEAP-1B,PW4100,TRENT700,GE90", "aud25": "박현", "aud27": "권혁, 김주원"},
    117: {"name": "GE ON WINGS KOREA", "cat": "중정비 위탁", "intv": 2, "ac": "B738,B38M", "eng": "CFM56,LEAP-1B", "aud25": "최병근", "aud27": "박현"},
    118: {"name": "KAEMS", "cat": "중정비 위탁", "intv": 2, "ac": "B738,B38M", "eng": "CFM56,LEAP-1B", "aud25": "박현", "aud27": "유준열"},
    119: {"name": "Sharp Technics K", "cat": "중정비 위탁", "intv": 2, "ac": "B738,B38M", "eng": "CFM56,LEAP-1B", "aud26": "유준열"},
    120: {"name": "대한항공 (기술관리, 직접 1년)", "cat": "운항정비 위탁", "intv": 2, "ac": "A332,A333,B773", "eng": "PW4100,TRENT700,GE90", "aud26": "권혁, 김주원"},
    121: {"name": "DMT", "cat": "정비 협력업체", "intv": 1, "ac": "B738,B38M,A333", "eng": "", "aud25": "박현", "aud26": "박현", "m26": 7},
    122: {"name": "대동금속", "cat": "정비 협력업체", "intv": 1, "ac": "B738,B38M", "eng": "", "aud26": "최병근", "m26": 6},
    123: {"name": "고암에이스항공", "cat": "정비 협력업체", "intv": 1, "ac": "B738,B38M,A333", "eng": "", "aud26": "박병권", "m26": 8},
    124: {"name": "항공기기술", "cat": "내부심사", "intv": 1, "ac": "B738,B38M,A332,A333,B773", "eng": "CFM56,LEAP-1B,PW4100,TRENT700,GE90", "aud26": "권혁, 최병근", "m26": 9, "d24": "2024-09-01"},
    125: {"name": "엔진기술", "cat": "내부심사", "intv": 1, "ac": "B738,B38M,A332,A333,B773", "eng": "CFM56,LEAP-1B,PW4100,TRENT700,GE90", "aud26": "이진성, 김주원", "m26": 6, "d26": "2026-06-25", "st26": "완료", "d24": "2024-09-01"},
    126: {"name": "정비기획", "cat": "내부심사", "intv": 1, "ac": "B738,B38M,A332,A333,B773", "eng": "CFM56,LEAP-1B,PW4100,TRENT700,GE90", "aud26": "박병권, 최병근", "m26": 8, "d24": "2024-11-01"},
    127: {"name": "정비자재", "cat": "내부심사", "intv": 1, "ac": "B738,B38M,A332,A333,B773", "eng": "CFM56,LEAP-1B,PW4100,TRENT700,GE90", "aud25": "권혁, 박현", "aud26": "원대연, 유준열", "m26": 10, "d25": "2025-03-11", "d24": "2024-03-01"},
    128: {"name": "정비통제", "cat": "내부심사", "intv": 1, "ac": "B738,B38M,A332,A333,B773", "eng": "CFM56,LEAP-1B,PW4100,TRENT700,GE90", "aud26": "송동훈, 김주원", "m26": 11, "d24": "2024-11-01"},
    129: {"name": "운항정비1,2", "cat": "내부심사", "intv": 1, "ac": "B738,B38M,A332,A333,B773", "eng": "CFM56,LEAP-1B,PW4100,TRENT700,GE90", "aud25": "최병근, 박현", "aud26": "박병권, 권혁", "m26": 7, "d25": "2025-08-18", "d24": "2024-03-01"},
    130: {"name": "부품수리", "cat": "내부심사", "intv": 1, "ac": "B738,B38M", "eng": "CFM56,LEAP-1B", "aud25": "이병철", "aud26": "박병권", "m26": 3, "d26": "2026-03-25", "st26": "완료", "d25": "2025-09-24", "d24": "2024-05-01"},
    131: {"name": "CJU (제주)", "cat": "운항정비 지점", "intv": 1, "ac": "B738,B38M,A333", "eng": "CFM56,LEAP-1B,TRENT700", "aud25": "이진성", "aud26": "원대연", "m26": 8, "d25": "2025-07-18", "d24": "2024-07-01"},
    132: {"name": "TAE (대구)", "cat": "운항정비 지점", "intv": 1, "ac": "B738,B38M", "eng": "CFM56,LEAP-1B", "aud26": "송동훈", "m26": 9, "d24": "2024-04-01"},
    133: {"name": "KWJ (광주)", "cat": "운항정비 지점", "intv": 1, "ac": "B738", "eng": "CFM56", "aud25": "김한민", "aud26": "이진성", "m26": 5, "d26": "2026-05-29", "st26": "완료", "d25": "2025-05-29", "d24": "2024-05-01"},
    134: {"name": "PUS (부산)", "cat": "운항정비 지점", "intv": 1, "ac": "B738,B38M", "eng": "CFM56,LEAP-1B", "aud25": "최문성", "aud26": "원대연", "m26": 10, "d25": "2025-10-16", "d24": "2024-08-01"},
    135: {"name": "CJJ (청주)", "cat": "운항정비 지점", "intv": 1, "ac": "B738,B38M", "eng": "CFM56,LEAP-1B", "aud25": "이병철", "aud26": "이진성", "m26": 11, "d25": "2025-11-20", "d24": "2024-11-01"},
}

def parse_excel_date(val, default_year, default_month=6):
    if val is not None:
        if isinstance(val, (datetime.datetime, datetime.date)):
            return val.strftime("%Y-%m-%d"), True
        s = str(val).strip()
        # YYYY.MM.DD or YYYY-MM-DD
        m = re.search(r'(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})', s)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return f"{y:04d}-{mo:02d}-{d:02d}", True
        # YYYY.MM or YYYY-MM
        m_ym = re.search(r'(20\d{2})[.\-/](\d{1,2})', s)
        if m_ym:
            y, mo = int(m_ym.group(1)), int(m_ym.group(2))
            return f"{y:04d}-{mo:02d}-01", True
    return f"{default_year:04d}-{default_month:02d}-01", False

def rebuild_clean_database(excel_path=None):
    if not excel_path:
        excel_path = get_latest_master_excel()
    print(f"Syncing database from Master Excel: {os.path.basename(excel_path)}")

    wb_d = openpyxl.load_workbook(excel_path, data_only=True)
    ws_d = wb_d["수행실적"]
    wb_f = openpyxl.load_workbook(excel_path, data_only=False)
    ws_f = wb_f["수행실적"]

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("DROP TABLE IF EXISTS audit_focus_notes")
    c.execute("DROP TABLE IF EXISTS audit_findings")
    c.execute("DROP TABLE IF EXISTS schedule_events")
    c.execute("DROP TABLE IF EXISTS audit_history")
    c.execute("DROP TABLE IF EXISTS audit_targets")

    c.execute("""
    CREATE TABLE audit_targets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        operation_status TEXT NOT NULL DEFAULT '운항',
        station_name TEXT NOT NULL UNIQUE,
        base_interval INTEGER DEFAULT 2,
        aircraft_types TEXT DEFAULT '',
        engine_types TEXT DEFAULT ''
    )
    """)

    c.execute("""
    CREATE TABLE audit_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_id INTEGER NOT NULL,
        year INTEGER NOT NULL,
        audit_type TEXT NOT NULL,
        status TEXT NOT NULL,
        is_event INTEGER DEFAULT 0,
        event_detail TEXT,
        remarks TEXT,
        scheduled_date TEXT,
        auditor TEXT,
        FOREIGN KEY (target_id) REFERENCES audit_targets(id)
    )
    """)

    c.execute("""
    CREATE TABLE schedule_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_id INTEGER NOT NULL,
        event_year INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        detail TEXT NOT NULL,
        FOREIGN KEY (target_id) REFERENCES audit_targets(id)
    )
    """)

    c.execute("""
    CREATE TABLE audit_findings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_id INTEGER NOT NULL,
        audit_date TEXT NOT NULL,
        finding_type TEXT NOT NULL DEFAULT 'Finding',
        category_tag TEXT DEFAULT '',
        title TEXT NOT NULL,
        finding_detail TEXT NOT NULL,
        regulation_ref TEXT DEFAULT '',
        root_cause TEXT DEFAULT '',
        action_taken TEXT DEFAULT '',
        action_status TEXT NOT NULL DEFAULT '조치완료',
        due_date TEXT DEFAULT '',
        auditor TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (target_id) REFERENCES audit_targets(id)
    )
    """)

    c.execute("""
    CREATE TABLE audit_focus_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_id INTEGER NOT NULL UNIQUE,
        focus_points TEXT DEFAULT '',
        checklist_notes TEXT DEFAULT '',
        updated_by TEXT DEFAULT '',
        updated_at TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (target_id) REFERENCES audit_targets(id)
    )
    """)

    target_map = {}  # station_name -> target_id
    last_raw_cat = ""

    for r in range(6, ws_d.max_row + 1):
        c_val = ws_d.cell(r, 1).value
        if c_val:
            last_raw_cat = str(c_val).strip()
        op_raw = str(ws_d.cell(r, 2).value or "").strip()
        st_raw = re.sub(r'\s+', ' ', str(ws_d.cell(r, 3).value or "")).strip()
        if not st_raw:
            continue

        op_status = "비운항" if op_raw == "비운항" else "운항"
        meta = ROW_METADATA.get(r, {})

        # 표준 5대 분류 및 주기 결정
        if "cat" in meta:
            std_cat = meta["cat"]
            base_interval = meta.get("intv", 2)
        elif last_raw_cat == "해외운항지점":
            std_cat = "운항정비 지점"
            base_interval = 2
        elif last_raw_cat == "완전위탁업체":
            std_cat = "운항정비 위탁"
            base_interval = 2
        elif last_raw_cat in ("엔진정비업체", "중정비업체"):
            std_cat = "중정비 위탁"
            base_interval = 2
        else:
            std_cat = "운항정비 위탁"
            base_interval = 2

        station_name = meta.get("name", st_raw)
        if station_name in target_map:
            station_name = f"{station_name} ({last_raw_cat})"

        ac_types = meta.get("ac", "")
        eng_types = meta.get("eng", "")

        c.execute("""
            INSERT INTO audit_targets (category, operation_status, station_name, base_interval, aircraft_types, engine_types)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (std_cat, op_status, station_name, base_interval, ac_types, eng_types))
        tid = c.lastrowid
        target_map[station_name] = tid

        # 연도별 이력/계획 파싱 (2023, 2024, 2025, 2026 + 수동 2027)
        last_known_month = meta.get("m26", 6)

        for yr, col_sym in [(2023, 14), (2024, 12), (2025, 10), (2026, 8), (2027, 6)]:
            sym = str(ws_d.cell(r, col_sym).value or "").strip()
            det = ws_d.cell(r, col_sym + 1).value
            f_sym = str(ws_f.cell(r, col_sym).value or "").strip()
            is_formula = f_sym.startswith("=")

            # 2027년은 수동으로 직접/간접 기호가 기입된 특수 대상(예: R096 SANAD Aerotech)만 DB에 저장하고 나머지는 동적 롤링
            if yr == 2027:
                if base_interval == 1 or is_formula:
                    continue

            if sym not in ("●", "◎"):
                # 내부심사/국내지점(R124~R135)의 2024/2025년 보조 이력 반영
                if yr == 2024 and "d24" in meta:
                    c.execute("""
                        INSERT INTO audit_history (target_id, year, audit_type, status, scheduled_date, auditor, remarks)
                        VALUES (?, 2024, '직접', '완료', ?, '', '2024년도 수행완료')
                    """, (tid, meta["d24"]))
                elif yr == 2025 and "d25" in meta:
                    c.execute("""
                        INSERT INTO audit_history (target_id, year, audit_type, status, scheduled_date, auditor, remarks)
                        VALUES (?, 2025, '직접', '완료', ?, ?, '2025년도 수행완료')
                    """, (tid, meta["d25"], meta.get("aud25", "")))
                continue

            audit_type = "직접" if sym == "●" else "간접"
            default_mo = meta.get(f"m{yr % 100}", last_known_month)
            s_date, has_exact_date = parse_excel_date(det, yr, default_mo)
            try:
                last_known_month = int(s_date.split("-")[1])
            except Exception:
                pass

            if yr <= 2025:
                status_str = "완료"
                auditor = meta.get(f"aud{yr % 100}", meta.get("aud27", ""))
                det_str = str(det).strip() if det is not None else ""
                if isinstance(det, (datetime.datetime, datetime.date)):
                    det_str = det.strftime("%Y.%m.%d")
                remarks = det_str if det_str and det_str != "None" else f"{yr}년도 수행완료"
            elif yr == 2026:
                if "d26" in meta:
                    s_date = meta["d26"]
                if "st26" in meta:
                    status_str = meta["st26"]
                else:
                    status_str = "완료" if has_exact_date else "계획"
                auditor = meta.get("aud26", meta.get("aud25", ""))
                det_str = str(det).strip() if det is not None else ""
                remarks = det_str if det_str and det_str != "None" else "2026년 정기심사"
            else:
                # 2027 manual entry (e.g. SANAD Aerotech)
                status_str = "계획"
                auditor = meta.get("aud27", "")
                remarks = "2027년 초도/정기 직접심사"

            c.execute("""
                INSERT INTO audit_history (target_id, year, audit_type, status, scheduled_date, auditor, remarks)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (tid, yr, audit_type, status_str, s_date, auditor, remarks))

    # 샘플 지적사항 (Findings / CAR) 및 사전 착안사항 등록
    sample_findings = [
        {
            "target": "VAECO (DAD 다낭)", "date": "2024-12-23", "type": "CAR", "tag": "공구관리",
            "title": "교정검사 유효기간 만료 측정공구(Torque Wrench) 정비박스 보관",
            "detail": "라인정비 전용 공구박스 내 토크렌치(T-104)의 검교정 유효기간이 2024.11.15부로 만료되었으나 불출대장 미기입 및 격리보관 미이행 상태로 방치됨.",
            "reg": "정비규정 제5장 제12조 (공구 및 장비 관리)", "root": "정비 교대 근무 시 공구 점검 주기 목록 대조 누락 및 현장 담당자 교정 일정 인계 미흡",
            "action": "해당 공구 즉시 폐기 및 교정 완료품 재배치, 전 라인 공구에 대한 전수 점검 실시 및 월간 검교정 현황판 신설 부착 완료",
            "status": "조치완료", "due": "2024-12-31", "auditor": "최병근"
        },
        {
            "target": "VAECO (DAD 다낭)", "date": "2025-08-15", "type": "Finding", "tag": "작업절차",
            "title": "Transit Check 정비점검표(Worksheet) 서명 누락 및 기입 지연",
            "detail": "TW123편 도착 후 진행된 Transit Check 점검표 중 타이어 마모도 기입란 서명이 출항 직전까지 누락되어 사후 서명된 이력 확인.",
            "reg": "운항정비 절차 매뉴얼 3.4절 (정비기록 및 서명)", "root": "동시 다발적 지상조업 상황에서 체크리스트 실시간 서명 절차 미준수",
            "action": "현장 정비사 전원 대상 표준 작업절차(SOP) 재교육 및 지상 조업 종료 즉시 전산 입력 확인 프로세스 도입",
            "status": "조치완료", "due": "2025-09-10", "auditor": "원대연"
        },
        {
            "target": "VAECO (DAD 다낭)", "date": "2026-08-13", "type": "Observation", "tag": "자재관리",
            "title": "화학물질(Sealant) 보관 온도 관리 기록 미흡",
            "detail": "냉장 보관이 요구되는 실란트 보관용 소형 냉장고의 일일 온도 점검표 일부 날짜 기록 공란 발생.",
            "reg": "정비자재 관리지침 제8조", "root": "주말 야간 당직자 점검 루틴 누락",
            "action": "디지털 온습도 로거 설치 및 자동 알람 시스템 구축 중",
            "status": "조치중", "due": "2026-09-30", "auditor": "원대연, 최병근"
        },
        {
            "target": "VAECO (HAN 하노이)", "date": "2024-12-23", "type": "Finding", "tag": "기술문서",
            "title": "오프라인 AMM(Aircraft Maintenance Manual) 최신 개정판 미동기화",
            "detail": "현장 정비 태블릿 내 저장된 오프라인 기술도면 및 AMM Rev.84가 최신 본부 Rev.86과 2개월 간 동기화되지 않은 채 사용됨.",
            "reg": "기술도서 관리규정 4.2", "root": "정기 네트워크 접속 동기화 주기 미설정",
            "action": "매주 월요일 정기 자동 클라우드 동기화 스크립트 배포 및 동기화 실패 시 알림 팝업 기능 적용",
            "status": "조치완료", "due": "2025-01-20", "auditor": "송동훈"
        },
        {
            "target": "VAECO (CXR 나트랑)", "date": "2025-02-25", "type": "Finding", "tag": "공구관리",
            "title": "특수장비(Ground Power Unit 케이블) 피복 손상 미조치",
            "detail": "항공기 전원 공급용 GPU 케이블 외피 마모로 내부 심선 노출 위험 확인.",
            "reg": "지상지원장비 안전규정 제11조", "root": "일일 장비 육안점검 미실시",
            "action": "해당 GPU 케이블 전면 교체 및 주간 GSE 정밀 점검표 작성 의무화",
            "status": "조치완료", "due": "2025-03-15", "auditor": "박병권"
        },
        {
            "target": "STAECO (TNA)", "date": "2024-03-08", "type": "CAR", "tag": "작업환경/시설",
            "title": "C-Check 격납고 내 방폭 조명 및 집진 설비 환기 필터 청결도 미달",
            "detail": "페인팅 및 샌딩 구역 내 환기 필터의 차압 게이지 적정 범위를 초과하여 분진 축적 위험.",
            "reg": "중정비 품질안전기준 7.3", "root": "정기 청소 교체 주기 미준수",
            "action": "집진 필터 전면 교체 및 분기별 차압 게이지 일일 모니터링 대장 비치",
            "status": "조치완료", "due": "2024-04-15", "auditor": "박병권"
        }
    ]

    for f in sample_findings:
        tid = target_map.get(f["target"])
        if tid:
            c.execute("""
                INSERT INTO audit_findings (target_id, audit_date, finding_type, category_tag, title, finding_detail, regulation_ref, root_cause, action_taken, action_status, due_date, auditor)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (tid, f["date"], f["type"], f["tag"], f["title"], f["detail"], f["reg"], f["root"], f["action"], f["status"], f["due"], f["auditor"]))

    sample_focus_notes = [
        {
            "target": "VAECO (DAD 다낭)",
            "focus": "1. 2024년 토크렌치 교정 만료 지적 및 2025년 점검표 서명 누락 이력 관련, 현장 공구실 실사 및 Transit 체크시트 실시간 서명 여부 집중 확인 필요.\n2. 2026년 하계 증편에 따른 신규 교대근무 정비사 OJT 및 휴먼에러 방지 절차 중점 점검.\n3. 온습도 민감 자재(실란트/페인트) 보관 로거 기록 확인.",
            "checklist": "- [ ] 공구실 토크렌치 및 측정공구 검교정 스티커/유효기간 전수 확인\n- [ ] 최근 3개월 Transit Check 점검표 서명 및 누락 여부 표본 20건 샘플링\n- [ ] B738/B38M 최신 AMM 오프라인 태블릿 동기화 일자 확인\n- [ ] 비상 안전장구 및 항공기 지상 유도 장비 관리 상태 점검",
            "by": "최병근 (심사기획)"
        },
        {
            "target": "VAECO (HAN 하노이)",
            "focus": "1. 현재 비운항 지점 상태이나 재운항 대비 기술도서 클라우드 동기화 및 현지 정비사 기종 자격 유지 현황 확인.\n2. B38M 및 신규 투입 기종 자격자 인력풀 점검.",
            "checklist": "- [ ] 태블릿 내 AMM/FIM 최신 리비전 대조\n- [ ] 현지 투입 정비사 기종 한정 자격증 및 당사 위탁 승인서 확인",
            "by": "송동훈 (품질기획)"
        }
    ]

    for fn in sample_focus_notes:
        tid = target_map.get(fn["target"])
        if tid:
            c.execute("""
                INSERT INTO audit_focus_notes (target_id, focus_points, checklist_notes, updated_by)
                VALUES (?, ?, ?, ?)
            """, (tid, fn["focus"], fn["checklist"], fn["by"]))

    conn.commit()

    c.execute("SELECT COUNT(*), SUM(CASE WHEN operation_status='운항' THEN 1 ELSE 0 END), SUM(CASE WHEN operation_status='비운항' THEN 1 ELSE 0 END) FROM audit_targets")
    t_cnt, op_cnt, non_op_cnt = c.fetchone()
    c.execute("SELECT COUNT(*) FROM audit_history")
    h_cnt = c.fetchone()[0]
    print(f"[성공] Master 엑셀 동기화 완료! 전체 대상: {t_cnt}개 (운항: {op_cnt}개, 비운항: {non_op_cnt}개), 심사 이력: {h_cnt}건")
    conn.close()

if __name__ == "__main__":
    rebuild_clean_database()
