import sqlite3
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "audit.db")

# 정규화된 대상처 이름 매핑 규칙 (5대 표준 분류 체계: 내부심사, 운항정비 지점, 운항정비 위탁, 중정비 위탁, 정비 협력업체)
TARGET_DEFINITIONS = [
    # 1. 내부심사 (1년 주기, base_interval=1)
    {"name": "항공기기술팀", "category": "내부심사", "base_interval": 1, "aircraft_types": "B738,B38M,A332,A333", "engine_types": "CFM56,LEAP-1B,PW4100,TRENT700", "aliases": ["항공기기술", "항공기기술팀"]},
    {"name": "엔진기술팀", "category": "내부심사", "base_interval": 1, "aircraft_types": "B738,B38M,A332,A333", "engine_types": "CFM56,LEAP-1B,PW4100,TRENT700", "aliases": ["엔진기술", "엔진기술팀"]},
    {"name": "정비기획팀", "category": "내부심사", "base_interval": 1, "aircraft_types": "B738,B38M,A332,A333", "engine_types": "CFM56,LEAP-1B,PW4100,TRENT700", "aliases": ["정비기획", "정비기획팀"]},
    {"name": "정비자재팀", "category": "내부심사", "base_interval": 1, "aircraft_types": "B738,B38M,A332,A333", "engine_types": "CFM56,LEAP-1B,PW4100,TRENT700", "aliases": ["정비자재", "정비자재팀"]},
    {"name": "정비통제팀", "category": "내부심사", "base_interval": 1, "aircraft_types": "B738,B38M,A332,A333", "engine_types": "CFM56,LEAP-1B,PW4100,TRENT700", "aliases": ["정비통제", "정비통제팀"]},
    {"name": "운항정비 1,2팀", "category": "내부심사", "base_interval": 1, "aircraft_types": "B738,B38M,A332,A333", "engine_types": "CFM56,LEAP-1B,PW4100,TRENT700", "aliases": ["운항정비 1,2", "운항정비 1팀", "운항정비 2팀", "운항정비 1,2팀", "운항정비1, 2팀", "운항정비1팀 / 2팀"]},
    {"name": "부품수리파트", "category": "내부심사", "base_interval": 1, "aircraft_types": "B738,B38M", "engine_types": "CFM56,LEAP-1B", "aliases": ["부품수리", "부품수리파트"]},
    {"name": "정비품질팀", "category": "내부심사", "base_interval": 1, "aircraft_types": "B738,B38M,A332,A333", "engine_types": "CFM56,LEAP-1B,PW4100,TRENT700", "aliases": ["정비품질", "정비품질팀"]},

    # 2. 운항정비 지점 (국내: 1년 주기, 해외: 2년 주기)
    {"name": "CJU (제주)", "category": "운항정비 지점", "base_interval": 1, "aircraft_types": "B738,B38M,A333", "engine_types": "CFM56,LEAP-1B,TRENT700", "aliases": ["CJU", "제주지점", "CJU (제주)"]},
    {"name": "TAE (대구)", "category": "운항정비 지점", "base_interval": 1, "aircraft_types": "B738,B38M", "engine_types": "CFM56,LEAP-1B", "aliases": ["TAE", "대구지점", "TAE (대구)"]},
    {"name": "KWJ (광주)", "category": "운항정비 지점", "base_interval": 1, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["KWJ", "광주지점", "KWJ (광주)"]},
    {"name": "PUS (부산)", "category": "운항정비 지점", "base_interval": 1, "aircraft_types": "B738,B38M", "engine_types": "CFM56,LEAP-1B", "aliases": ["PUS", "부산지점", "PUS (부산)", "PUS (김해)"]},
    {"name": "CJJ (청주)", "category": "운항정비 지점", "base_interval": 1, "aircraft_types": "B738,B38M", "engine_types": "CFM56,LEAP-1B", "aliases": ["CJJ", "청주지점", "CJJ (청주)"]},
    {"name": "SPN (사이판)", "category": "운항정비 지점", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["SPN (사이판)", "SPN", "사이판지점"]},
    {"name": "KLO (칼리보)", "category": "운항정비 지점", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["KLO (칼리보)", "KLO", "칼리보지점"]},
    {"name": "CEB (세부)", "category": "운항정비 지점", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["CEB (세부)", "CEB", "세부지점"]},
    {"name": "KIX (간사이/오사카)", "category": "운항정비 지점", "base_interval": 2, "aircraft_types": "B738,B38M,A333", "engine_types": "CFM56,LEAP-1B,TRENT700", "aliases": ["KIX (간사이)", "KIX (오사카)", "KIX", "간사이지점"]},
    {"name": "FUK (후쿠오카)", "category": "운항정비 지점", "base_interval": 2, "aircraft_types": "B738,B38M", "engine_types": "CFM56,LEAP-1B", "aliases": ["FUK (후쿠오카)", "FUK", "후쿠오카지점"]},
    {"name": "NRT (나리타)", "category": "운항정비 지점", "base_interval": 2, "aircraft_types": "B738,B38M,A333", "engine_types": "CFM56,LEAP-1B,TRENT700", "aliases": ["NRT (나리타)", "NRT", "나리타지점"]},
    {"name": "GUM (괌)", "category": "운항정비 지점", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["GUM (괌)", "GUM(괌)", "GUM"]},
    {"name": "CTS (치토세)", "category": "운항정비 지점", "base_interval": 2, "aircraft_types": "B738,B38M", "engine_types": "CFM56,LEAP-1B", "aliases": ["CTS (치토세)", "CTS(치토세)", "CTS"]},
    {"name": "OKA (오키나와)", "category": "운항정비 지점", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["OKA (오키나와)", "OKA(오키나와)", "OKA"]},
    {"name": "KMJ (구마모토)", "category": "운항정비 지점", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["KMJ (구마모토)", "KMJ(구마모토)", "KMJ"]},
    {"name": "FRU (비슈케크)", "category": "운항정비 지점", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["FRU (비슈케크)", "FRU(비슈케크)", "FRU"]},
    {"name": "DAD (다낭)", "category": "운항정비 지점", "base_interval": 2, "aircraft_types": "B738,B38M,A333", "engine_types": "CFM56,LEAP-1B,TRENT700", "aliases": ["DAD (다낭)", "DAD", "DAD지점 (다낭)"]},
    {"name": "SGN (호치민)", "category": "운항정비 지점", "base_interval": 2, "aircraft_types": "B738,B38M", "engine_types": "CFM56,LEAP-1B", "aliases": ["SGN (호치민)", "SGN"]},
    {"name": "BKI (코타키나발루)", "category": "운항정비 지점", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["BKI (코타키나발루)", "BKI"]},
    {"name": "UBN (울란바토르)", "category": "운항정비 지점", "base_interval": 2, "aircraft_types": "B738,B38M,A333", "engine_types": "CFM56,LEAP-1B,TRENT700", "aliases": ["UBN (울란바토르)", "UBN(울란바토르)", "UBN"]},
    {"name": "DYG (장자제)", "category": "운항정비 지점", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["DYG (장자제)", "DYG(장가계)", "DYG(장자제)", "DYG"]},
    {"name": "YNJ (연길)", "category": "운항정비 지점", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["YNJ (연길)", "YNJ(옌지)", "YNJ(연길)", "YNJ"]},
    {"name": "HSG (사가)", "category": "운항정비 지점", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["HSG (사가)", "HSG"]},

    # 3. 운항정비 위탁 (2년 주기, base_interval=2)
    {"name": "Heston MRO (SYD 시드니)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "A332,A333", "engine_types": "PW4100,TRENT700", "aliases": ["Heston MRO (SYD 시드니)", "Heston MRO Pty - SYD (시드니)", "Heston MRO Pty Ltd - SYD지점"]},
    {"name": "Avia Technics (ZAG 자그레브)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "A333", "engine_types": "TRENT700", "aliases": ["Avia Technics (ZAG 자그레브)", "Avia Technics - ZAG (자그레브)", "Avia Technics - ZAG지점"]},
    {"name": "EASTEC (PKX 베이징)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738,B38M", "engine_types": "CFM56,LEAP-1B", "aliases": ["EASTEC (PKX 베이징)", "EASTEC - PKX (베이징)", "EASTEC - PKX지점"]},
    {"name": "EASTEC (TAO 칭타오)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["EASTEC (TAO 칭타오)"]},
    {"name": "EASTEC (YNJ 연길)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["EASTEC (YNJ 연길)"]},
    {"name": "EASTEC (WUH 우한)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["EASTEC (WUH 우한)"]},
    {"name": "EASTEC (TNA 지난)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["EASTEC (TNA 지난)"]},
    {"name": "JAL (FUK 후쿠오카)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738,B38M,A333", "engine_types": "CFM56,LEAP-1B,TRENT700", "aliases": ["JAL (FUK 후쿠오카)", "JAL - FUK (후쿠오카)"]},
    {"name": "JAL (CTS 삿포로)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738,B38M", "engine_types": "CFM56,LEAP-1B", "aliases": ["JAL (CTS 삿포로)"]},
    {"name": "VAECO (PQC 푸꾸옥)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738,B38M", "engine_types": "CFM56,LEAP-1B", "aliases": ["VAECO (PQC 푸꾸옥)", "VAECO (PQC)"]},
    {"name": "VAECO (CXR 나트랑)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738,B38M,A333", "engine_types": "CFM56,LEAP-1B,TRENT700", "aliases": ["VAECO (CXR 나트랑)", "VAECO (CXR)"]},
    {"name": "VAECO (HAN 하노이)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738,B38M", "engine_types": "CFM56,LEAP-1B", "aliases": ["VAECO (HAN 하노이)", "VAECO - HAN (하노이)"]},
    {"name": "VAECO (DAD 다낭)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738,B38M,A333", "engine_types": "CFM56,LEAP-1B,TRENT700", "aliases": ["VAECO (DAD 다낭)", "VAECO - DAD (다낭)"]},
    {"name": "SIAEC (SIN 싱가포르)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738,B38M,A333", "engine_types": "CFM56,LEAP-1B,TRENT700", "aliases": ["SIAEC (SIN 싱가포르)", "SIAEC - SIN (싱가포르)"]},
    {"name": "China Airlines (TPE 타오위엔)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738,B38M", "engine_types": "CFM56,LEAP-1B", "aliases": ["China Airlines (TPE 타오위엔)", "CHINA AIRLINES (TPE 타이위엔)", "CHINA AIRLINES (TPE 타오위엔)"]},
    {"name": "China Airlines (TSA 송산)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["China Airlines (TSA 송산)", "CHINA AIRLINES (TSA 송산)"]},
    {"name": "China Airlines (KHH 가오슝)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["China Airlines (KHH 가오슝)", "CHINA AIRLINES (KHH 가오슝)"]},
    {"name": "Mandarin Airlines (RMQ 타이중)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738,B38M", "engine_types": "CFM56,LEAP-1B", "aliases": ["Mandarin Airlines (RMQ 타이중)", "Mandarin Airlines-RMQ (타이중)", "Mandarin Airlines - RMQ지점"]},
    {"name": "Papas (HKG 홍콩)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738,B773", "engine_types": "CFM56,GE90", "aliases": ["Papas (HKG 홍콩)", "PAPAS - HKG (홍콩)", "PAPAS - HKG지점"]},
    {"name": "Atitech (FCO 로마)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "A333,A332", "engine_types": "TRENT700,PW4100", "aliases": ["Atitech (FCO 로마)", "Atitech - FCO (로마)", "Atitech S.p.A (FCO 로마)"]},
    {"name": "Atitech (FRA 프랑크푸르트)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "A333", "engine_types": "TRENT700", "aliases": ["Atitech (FRA 프랑크푸르트)", "Atitech - FRA (프랑크프루트)", "Atitech (FRA)"]},
    {"name": "Nayak (CDG 파리)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "A333", "engine_types": "TRENT700", "aliases": ["Nayak (CDG 파리)", "Nayak Aero - CDG (파리)", "Nayak LM-GmbH (CDG 파리)", "Nayak Aero - CDG지점"]},
    {"name": "KLM (BCN 바르셀로나)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "A333", "engine_types": "TRENT700", "aliases": ["KLM (BCN 바르셀로나)", "KLM - BCN (바르셀로나)", "KLM (BCN)"]},
    {"name": "Southern (SHE 선양)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["Southern (SHE 선양)", "Southern - SHE (선양)"]},
    {"name": "Koreanair (ICN,GMP 운항위탁)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738,B38M,A332,A333", "engine_types": "CFM56,LEAP-1B,PW4100,TRENT700", "aliases": ["Koreanair (ICN,GMP 인천,김포)", "Koreanair (ICN,GMP)"]},
    {"name": "Koreanair (CJU 운항위탁)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738,B38M,A333", "engine_types": "CFM56,LEAP-1B,TRENT700", "aliases": ["Koreanair (CJU 제주)", "Koreanair (CJU)"]},
    {"name": "Koreanair (기술관리)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "A332,A333", "engine_types": "PW4100,TRENT700", "aliases": ["Koreanair (항공기 기술관리)", "대한항공 (기술관리)"]},
    {"name": "HNA (HAK 하이커우)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["HNA (HAK 하이커우)"]},
    {"name": "HNA (SYX 산야)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["HNA (SYX 산야)"]},
    {"name": "JAE (DPS 발리)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["JAE (DPS 발리)"]},
    {"name": "South Breeze Aviation (YVR 벤쿠버)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "A333", "engine_types": "TRENT700", "aliases": ["South Breeze Aviation (YVR 벤쿠버)"]},
    {"name": "SIAEJ (FUK 후쿠오카)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738,B38M", "engine_types": "CFM56,LEAP-1B", "aliases": ["SIAEJ (FUK 후쿠오카)"]},
    {"name": "SIAEJ (CTS 삿포로)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738,B38M", "engine_types": "CFM56,LEAP-1B", "aliases": ["SIAEJ (CTS 삿포로)"]},
    {"name": "SIAEJ (KIX 오사카)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738,B38M,A333", "engine_types": "CFM56,LEAP-1B,TRENT700", "aliases": ["SIAEJ (KIX 오사카)"]},
    {"name": "SIAECJ (NRT 도쿄)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738,B38M,A333", "engine_types": "CFM56,LEAP-1B,TRENT700", "aliases": ["SIAECJ (NRT 도쿄)"]},
    {"name": "SIAECJ (NGO 나고야)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["SIAECJ (NGO 나고야)"]},
    {"name": "Thai Airways (BKK 방콕)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738,A332,A333", "engine_types": "CFM56,PW4100,TRENT700", "aliases": ["TG (BKK 방콕)", "Thai Airways (BKK 방콕)"]},
    {"name": "Thai Airways (CNX 치앙마이)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["TG (CNX 치앙마이)", "Thai Airways (CNX 치앙마이)"]},
    {"name": "APLUS (KLO 칼리보)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["APLUS (KLO 칼리보)"]},
    {"name": "LTP (CEB 세부)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["LTP (CEB 세부)"]},
    {"name": "MABES (BKI 코타키나발루)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["MABES (BKI 코타키나발루)"]},
    {"name": "STORM AVIATION (DAC 다카)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "A333", "engine_types": "TRENT700", "aliases": ["STORM AVIATION (DAC 다카)"]},
    {"name": "EU Wings (TAS 타슈켄트)", "category": "운항정비 위탁", "base_interval": 2, "aircraft_types": "A333", "engine_types": "TRENT700", "aliases": ["EU Wings (TAS 타슈켄트)"]},

    # 4. 중정비 위탁 (2년 주기, base_interval=2)
    {"name": "STAECO (TNA 지난)", "category": "중정비 위탁", "base_interval": 2, "aircraft_types": "B738,B38M", "engine_types": "CFM56,LEAP-1B", "aliases": ["STAECO (TNA 지난)", "STAECO - TNA (지난)", "STAECO (지난)", "TNA 지난(A/C)"]},
    {"name": "EASTEC (KMG 쿤밍)", "category": "중정비 위탁", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["EASTEC (KMG 쿤밍)", "EASTEC - KMG (쿤밍)", "EASTEC - KMG 쿤밍(A/C)"]},
    {"name": "GMF (CGK 자카르타)", "category": "중정비 위탁", "base_interval": 2, "aircraft_types": "B738,A333", "engine_types": "CFM56,TRENT700", "aliases": ["GMF (CGK 자카르타)", "GMF (CGK)"]},
    {"name": "STARCO (SHA 상하이)", "category": "중정비 위탁", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["STARCO (SHA 상하이)"]},
    {"name": "ST Engineering Aerospace Engines", "category": "중정비 위탁", "base_interval": 2, "aircraft_types": "B738,A333", "engine_types": "CFM56,TRENT700", "aliases": ["ST Engineering Aerospace Engines", "ST AEROSPACE ENGINES (SIN)"]},
    {"name": "HAECO (XMN 샤먼)", "category": "중정비 위탁", "base_interval": 2, "aircraft_types": "B738,B38M,A333", "engine_types": "CFM56,LEAP-1B,TRENT700", "aliases": ["HAECO (XMN 샤먼)", "HAECO - XNM (샤먼)", "HAECO (XMN)"]},
    {"name": "Standard Aero (위니펙)", "category": "중정비 위탁", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["Standard Aero (위니펙)", "STANDARD AERO((위니펙)", "STANDARD AERO"]},
    {"name": "Sharp Technics K", "category": "중정비 위탁", "base_interval": 2, "aircraft_types": "B738,B38M", "engine_types": "CFM56,LEAP-1B", "aliases": ["Sharp Technics K", "SHARP TECHNICS K"]},
    {"name": "HAESL (HKG)", "category": "중정비 위탁", "base_interval": 2, "aircraft_types": "A333", "engine_types": "TRENT700", "aliases": ["HAESL (HKG)", "HAESL"]},
    {"name": "SANAD Aerotech (AUH)", "category": "중정비 위탁", "base_interval": 2, "aircraft_types": "A333", "engine_types": "TRENT700", "aliases": ["SANAD Aerotech (AUH)"]},
    {"name": "Koreanair (중정비)", "category": "중정비 위탁", "base_interval": 2, "aircraft_types": "B738,B38M,A332,A333", "engine_types": "CFM56,LEAP-1B,PW4100,TRENT700", "aliases": ["Koreanair (중정비)", "대한항공 (중정비)", "대한항공 (기체/엔진)"]},
    {"name": "TIANJIN HAITE (TSN 텐진)", "category": "중정비 위탁", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["TIANJIN HAITE (TSN 텐진)"]},
    {"name": "SIAEP (CRK 클락)", "category": "중정비 위탁", "base_interval": 2, "aircraft_types": "B738,B38M", "engine_types": "CFM56,LEAP-1B", "aliases": ["SIAEP (CRK 클락)"]},
    {"name": "LTP (MNL 마닐라)", "category": "중정비 위탁", "base_interval": 2, "aircraft_types": "B738,A333", "engine_types": "CFM56,TRENT700", "aliases": ["LTP (MNL 마닐라)"]},
    {"name": "KAEMS", "category": "중정비 위탁", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["KAEMS"]},
    {"name": "STATCO (XIAMEN 샤먼)", "category": "중정비 위탁", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["STATCO (XIAMEN 샤먼)", "STATCO (XIAMEN)"]},
    {"name": "GE ENGINE SERVICES (WALES)", "category": "중정비 위탁", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["GE ENGINE SERVICES (WALES)"]},
    {"name": "GE ON WINGS KOREA", "category": "중정비 위탁", "base_interval": 2, "aircraft_types": "B738,B38M", "engine_types": "CFM56,LEAP-1B", "aliases": ["GE ON WINGS KOREA"]},
    {"name": "Lufthansa Technik AG", "category": "중정비 위탁", "base_interval": 2, "aircraft_types": "A333,B773", "engine_types": "TRENT700,GE90", "aliases": ["Lufthansa Technik AG"]},
    {"name": "N3 Engine Overhaul Services", "category": "중정비 위탁", "base_interval": 2, "aircraft_types": "A333", "engine_types": "TRENT700", "aliases": ["N3 Engine Overhaul Services"]},
    {"name": "AMECO (CTU 청두)", "category": "중정비 위탁", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["AMECO (CTU 청두)", "AMECO (CTU)"]},
    {"name": "AIR ASIA (TNN 타이난)", "category": "중정비 위탁", "base_interval": 2, "aircraft_types": "B738", "engine_types": "CFM56", "aliases": ["AIR ASIA (TNN 타이난)", "AIR ASIA (TNN)"]},

    # 5. 정비 협력업체 (1년 주기, base_interval=1)
    {"name": "대동금속", "category": "정비 협력업체", "base_interval": 1, "aircraft_types": "B738,B38M", "engine_types": "", "aliases": ["대동금속"]},
    {"name": "디엠티 (DMT)", "category": "정비 협력업체", "base_interval": 1, "aircraft_types": "B738,B38M,A333", "engine_types": "", "aliases": ["디엠티", "DMT"]}
]

def find_standard_target(raw_name):
    clean = raw_name.strip()
    clean_lower = clean.lower().replace(" ", "").replace("-", "").replace("–", "")
    for defn in TARGET_DEFINITIONS:
        for alias in defn["aliases"]:
            a_clean = alias.lower().replace(" ", "").replace("-", "").replace("–", "")
            if a_clean == clean_lower:
                return defn
    # Prefix / Substring matching
    for defn in TARGET_DEFINITIONS:
        for alias in defn["aliases"]:
            a_clean = alias.lower().replace(" ", "").replace("-", "")
            if len(a_clean) >= 3 and (a_clean in clean_lower or clean_lower in a_clean):
                return defn
    return {
        "name": clean,
        "category": "운항정비 위탁",
        "base_interval": 2,
        "aircraft_types": "",
        "engine_types": ""
    }

def rebuild_clean_database():
    print(f"Rebuilding normalized database: {DB_PATH}")
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

    target_map = {} # standard_name -> id

    def get_or_create(raw_name):
        defn = find_standard_target(raw_name)
        std_name = defn["name"]
        if std_name in target_map:
            return target_map[std_name]
        
        c.execute("""
            INSERT INTO audit_targets (category, operation_status, station_name, base_interval, aircraft_types, engine_types)
            VALUES (?, '운항', ?, ?, ?, ?)
        """, (defn["category"], std_name, defn.get("base_interval", 2), defn.get("aircraft_types", ""), defn.get("engine_types", "")))
        tid = c.lastrowid
        target_map[std_name] = tid
        return tid

    # Target definition preload
    for defn in TARGET_DEFINITIONS:
        get_or_create(defn["name"])

    def add_history(raw_name, year, audit_type, status, date_str, auditor="", remarks=""):
        tid = get_or_create(raw_name)
        c.execute("SELECT id, status FROM audit_history WHERE target_id = ? AND year = ?", (tid, year))
        existing = c.fetchall()
        if existing:
            if status == "계획" and any(r[1] == "완료" for r in existing):
                return
            if status == "완료":
                c.execute("DELETE FROM audit_history WHERE target_id = ? AND year = ? AND status = '계획'", (tid, year))

        c.execute("""
            INSERT INTO audit_history (target_id, year, audit_type, status, scheduled_date, auditor, remarks)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (tid, year, audit_type, status, date_str, auditor, remarks))

    # --- 1. 2024년 데이터 (직접/간접) ---
    h_2024 = [
        ("항공기기술팀", "직접", "2024-09-01"), ("엔진기술팀", "직접", "2024-09-01"), ("정비기획팀", "직접", "2024-11-01"),
        ("정비자재팀", "직접", "2024-03-01"), ("정비통제팀", "직접", "2024-11-01"), ("운항정비 1,2팀", "직접", "2024-03-01"),
        ("부품수리파트", "직접", "2024-05-01"), ("CJU (제주)", "직접", "2024-07-01"), ("TAE (대구)", "직접", "2024-04-01"),
        ("KWJ (광주)", "직접", "2024-05-01"), ("PUS (부산)", "직접", "2024-08-01"), ("CJJ (청주)", "직접", "2024-11-01"),
        ("대동금속", "직접", "2024-08-01"),
        # 간접
        ("SPN (사이판)", "간접", "2024-11-01"), ("SGN (호치민)", "간접", "2024-10-01"), ("CEB (세부)", "간접", "2024-10-01"),
        ("KLO (칼리보)", "간접", "2024-11-01"), ("KIX (간사이/오사카)", "간접", "2024-11-01"), ("FUK (후쿠오카)", "간접", "2024-10-01"),
        ("NRT (나리타)", "간접", "2024-11-01"), ("JAL (FUK 후쿠오카)", "간접", "2024-11-01"), ("Papas (HKG 홍콩)", "간접", "2024-07-01"),
        ("VAECO (DAD 다낭)", "간접", "2024-12-01"), ("VAECO (HAN 하노이)", "간접", "2024-12-01"), ("SIAEC (SIN 싱가포르)", "간접", "2024-09-01"),
        # 직접
        ("FRU (비슈케크)", "직접", "2024-09-01"), ("DAD (다낭)", "직접", "2024-06-01"), ("BKI (코타키나발루)", "직접", "2024-11-01"),
        ("UBN (울란바토르)", "직접", "2024-09-01"), ("DYG (장자제)", "직접", "2024-10-01"), ("YNJ (연길)", "직접", "2024-11-01"),
        ("HSG (사가)", "직접", "2024-10-01"), ("Mandarin Airlines (RMQ 타이중)", "직접", "2024-01-01"), ("EASTEC (PKX 베이징)", "직접", "2024-06-01"),
        ("Southern (SHE 선양)", "직접", "2024-10-01"), ("Avia Technics (ZAG 자그레브)", "직접", "2024-06-01"), ("Nayak (CDG 파리)", "직접", "2024-06-01"),
        ("Atitech (FCO 로마)", "직접", "2024-08-01"), ("KLM (BCN 바르셀로나)", "직접", "2024-08-01"), ("Atitech (FRA 프랑크푸르트)", "직접", "2024-09-01"),
        ("Heston MRO (SYD 시드니)", "직접", "2024-02-01"), ("Koreanair (중정비)", "직접", "2024-05-01"), ("STAECO (TNA 지난)", "직접", "2024-03-01"),
        ("EASTEC (KMG 쿤밍)", "직접", "2024-02-01"), ("HAECO (XMN 샤먼)", "직접", "2024-10-01"), ("Standard Aero (위니펙)", "직접", "2024-06-01")
    ]
    for target, atype, sdate in h_2024:
        add_history(target, 2024, atype, "완료", sdate, remarks="2024년도 수행완료")

    # --- 2. 2025년 데이터 ---
    h_2025 = [
        ("정비자재팀", "직접", "완료", "2025-03-11", "권혁, 박현", "정기 직접심사"),
        ("정비자재팀", "직접", "완료", "2025-11-17", "박현, 최병근", "특별심사"),
        ("운항정비 1,2팀", "직접", "완료", "2025-08-18", "최병근, 박현", "OJT: 최문성, 김주원"),
        ("부품수리파트", "직접", "완료", "2025-09-24", "이병철", "OJT: 이치규"),
        ("정비품질팀", "직접", "완료", "2025-04-29", "", "안전품질 정기 심사로 대체"),
        ("CJU (제주)", "직접", "완료", "2025-07-18", "이진성", "OJT: 송동훈"),
        ("KWJ (광주)", "직접", "완료", "2025-05-29", "김한민", ""),
        ("PUS (부산)", "직접", "완료", "2025-10-16", "최문성", ""),
        ("CJJ (청주)", "직접", "완료", "2025-11-20", "이병철", ""),
        ("GUM (괌)", "간접", "완료", "2025-10-15", "이진성", "2년 주기 간접"),
        ("CTS (치토세)", "간접", "완료", "2025-04-10", "최병근", "2년 주기 간접"),
        ("OKA (오키나와)", "간접", "완료", "2025-05-28", "박병권", "2년 주기 간접"),
        ("HNA (HAK 하이커우)", "간접", "완료", "2025-08-12", "박현", "2년 주기 간접"),
        ("HNA (SYX 산야)", "간접", "완료", "2025-08-12", "박현", "2년 주기 간접"),
        ("VAECO (PQC 푸꾸옥)", "간접", "완료", "2025-12-01", "김주원", "B38M 기종 추가"),
        ("Mandarin Airlines (RMQ 타이중)", "간접", "완료", "2025-12-01", "이진성", "B38M 기종 추가"),
        ("GMF (CGK 자카르타)", "간접", "완료", "2025-03-04", "박현", "2년 주기 간접"),
        ("AMECO (CTU 청두)", "간접", "완료", "2025-10-13", "유준열", "2년 주기 간접"),
        ("Koreanair (중정비)", "간접", "완료", "2025-01-09", "박현", "서류심사"),
        ("KAEMS", "간접", "완료", "2025-09-11", "박현", "2년 주기 간접"),
        ("STATCO (XIAMEN 샤먼)", "간접", "완료", "2025-11-17", "이진성", "2년 주기 간접"),
        ("GE ENGINE SERVICES (WALES)", "간접", "완료", "2025-06-23", "유준열", "2년 주기 간접"),
        ("GE ON WINGS KOREA", "간접", "완료", "2025-05-26", "최병근", "2년 주기 간접"),
        ("KMJ (구마모토)", "직접", "완료", "2025-06-09", "원대연", ""),
        ("EASTEC (YNJ 연길)", "직접", "완료", "2025-06-24", "임주한, 최병근", "초도"),
        ("EASTEC (TAO 칭타오)", "직접", "완료", "2025-10-29", "최병근", "초도"),
        ("EASTEC (WUH 우한)", "직접", "완료", "2025-10-29", "최병근", "초도"),
        ("VAECO (CXR 나트랑)", "직접", "완료", "2025-02-25", "박병권, 최병근", "주재정비 포함"),
        ("VAECO (PQC 푸꾸옥)", "직접", "완료", "2025-10-01", "김주원", "초도"),
        ("China Airlines (TSA 송산)", "직접", "완료", "2025-07-08", "최병근, 박현", ""),
        ("China Airlines (TPE 타오위엔)", "직접", "완료", "2025-07-08", "최병근, 박현", ""),
        ("China Airlines (KHH 가오슝)", "직접", "완료", "2025-07-07", "임주한, 이진성", ""),
        ("JAE (DPS 발리)", "직접", "완료", "2025-04-15", "유준열, 박현", "초도"),
        ("Papas (HKG 홍콩)", "직접", "완료", "2025-09-24", "이진성", "B777 기종추가"),
        ("Atitech (FCO 로마)", "직접", "완료", "2025-02-18", "박병권", "기종추가"),
        ("Nayak (CDG 파리)", "직접", "완료", "2025-02-18", "박현", "기종추가"),
        ("KLM (BCN 바르셀로나)", "직접", "완료", "2025-09-08", "최병근", ""),
        ("Koreanair (ICN,GMP 운항위탁)", "직접", "완료", "2025-01-09", "박현", ""),
        ("Koreanair (CJU 운항위탁)", "직접", "완료", "2025-01-09", "박현", ""),
        ("South Breeze Aviation (YVR 벤쿠버)", "직접", "완료", "2025-04-15", "원대연, 김한민", "초도"),
        ("JAL (CTS 삿포로)", "직접", "완료", "2025-02-11", "박현", "지점추가"),
        ("JAL (FUK 후쿠오카)", "직접", "완료", "2025-02-11", "박현", "기종추가"),
        ("SIAEJ (FUK 후쿠오카)", "직접", "완료", "2025-09-11", "박병권", "지점추가"),
        ("SIAEJ (CTS 삿포로)", "직접", "완료", "2025-09-11", "박병권", "지점추가"),
        ("SIAEJ (KIX 오사카)", "직접", "완료", "2025-08-18", "임주한, 박병권", "초도"),
        ("SIAECJ (NRT 도쿄)", "직접", "완료", "2025-09-11", "박병권", "지점추가"),
        ("SIAECJ (NGO 나고야)", "직접", "완료", "2025-09-11", "박병권", "지점추가"),
        ("Thai Airways (BKK 방콕)", "직접", "완료", "2025-04-22", "유준열", "A332 기종추가"),
        ("Thai Airways (CNX 치앙마이)", "직접", "완료", "2025-10-15", "최병근", "B738 기종추가"),
        ("APLUS (KLO 칼리보)", "직접", "완료", "2025-11-05", "박병권, 이진성", "초도"),
        ("LTP (CEB 세부)", "직접", "완료", "2025-10-28", "송동훈, 김주원", "초도"),
        ("MABES (BKI 코타키나발루)", "직접", "완료", "2025-11-26", "원대연, 박현", "초도"),
        ("STORM AVIATION (DAC 다카)", "직접", "완료", "2025-11-20", "박병권, 유준열", "초도"),
        ("EU Wings (TAS 타슈켄트)", "직접", "완료", "2025-05-05", "이진성, 최수연", "초도"),
        ("Koreanair (기술관리)", "직접", "완료", "2025-01-09", "최수연, 박현", "초도"),
        ("TIANJIN HAITE (TSN 텐진)", "직접", "완료", "2025-03-17", "박병권, 박현", "초도"),
        ("SIAEP (CRK 클락)", "직접", "완료", "2025-09-10", "원대연, 김주원", "초도"),
        ("LTP (MNL 마닐라)", "직접", "완료", "2025-10-21", "유준열, 최병근", "초도"),
        ("Lufthansa Technik AG", "직접", "완료", "2025-04-16", "이진성, 최병근", "초도"),
        ("N3 Engine Overhaul Services", "직접", "완료", "2025-09-16", "박병권, 최병근", "초도"),
        ("디엠티 (DMT)", "직접", "완료", "2025-05-23", "박현", "초도")
    ]
    for target, atype, st, sdate, aud, rmk in h_2025:
        add_history(target, 2025, atype, st, sdate, aud, rmk)

    # --- 3. 2026년 데이터 ---
    h_2026 = [
        # 완료 (R)
        ("STARCO (SHA 상하이)", "직접", "완료", "2026-02-02", "박병권, 최병근", "2026.02.02 ~ 02.05"),
        ("GMF (CGK 자카르타)", "직접", "완료", "2026-02-25", "원대연, 이진성", "2026.02.25 ~ 26"),
        ("부품수리파트", "직접", "완료", "2026-03-25", "박병권", "2026.03.25"),
        ("정비품질팀", "직접", "완료", "2026-03-17", "", "2026.03.17 ~ 19"),
        ("Heston MRO (SYD 시드니)", "간접", "완료", "2026-03-06", "유준열", "2026.03.06"),
        ("EASTEC (KMG 쿤밍)", "간접", "완료", "2026-03-09", "김주원", "2026.03.09"),
        ("STAECO (TNA 지난)", "간접", "완료", "2026-03-18", "박병권", "2026.03.18"),
        ("ST Engineering Aerospace Engines", "간접", "완료", "2026-03-26", "최병근", "2026.03.26"),
        ("EASTEC (TNA 지난)", "간접", "완료", "2026-04-10", "김주원, 유준열", "2026.04.10, 2026.06.16"),
        ("KWJ (광주)", "직접", "완료", "2026-05-29", "이진성", "2026.05.29"),
        ("엔진기술팀", "직접", "완료", "2026-06-25", "이진성", "2026.06.25"),
        ("EASTEC (PKX 베이징)", "간접", "완료", "2026-06-01", "김주원", ""),
        ("EASTEC (TAO 칭타오)", "간접", "완료", "2026-06-16", "유준열", "2026.06.16"),
        ("Avia Technics (ZAG 자그레브)", "간접", "완료", "2026-06-18", "권혁", "2026.06.18"),
        ("Koreanair (기술관리)", "직접", "완료", "2026-06-01", "권혁, 김주원", ""),
        ("대동금속", "직접", "완료", "2026-06-01", "최병근", ""),

        # 계획 (P)
        ("운항정비 1,2팀", "직접", "계획", "2026-07-01", "박병권, 권혁", "2026년 계획"),
        ("정비기획팀", "직접", "계획", "2026-08-01", "박병권, 최병근", "2026년 계획"),
        ("정비자재팀", "직접", "계획", "2026-10-01", "원대연, 유준열", "2026년 계획"),
        ("정비통제팀", "직접", "계획", "2026-11-01", "송동훈, 김주원", "2026년 계획"),
        ("항공기기술팀", "직접", "계획", "2026-11-01", "이진성, 최병근", "2026년 계획"),
        ("CJU (제주)", "직접", "계획", "2026-08-01", "원대연", "2026년 계획"),
        ("TAE (대구)", "직접", "계획", "2026-09-01", "송동훈", "2026년 계획"),
        ("PUS (부산)", "직접", "계획", "2026-10-01", "원대연", "2026년 계획"),
        ("CJJ (청주)", "직접", "계획", "2026-11-01", "이진성", "2026년 계획"),
        ("SPN (사이판)", "직접", "계획", "2026-11-01", "이진성", "2026년 계획"),
        ("KLO (칼리보)", "직접", "계획", "2026-08-01", "유준열", "2026년 계획"),
        ("CEB (세부)", "직접", "계획", "2026-10-01", "박병권", "2026년 계획"),
        ("KIX (간사이/오사카)", "직접", "계획", "2026-08-01", "김주원", "2026년 계획"),
        ("FUK (후쿠오카)", "직접", "계획", "2026-09-01", "원대연", "2026년 계획"),
        ("NRT (나리타)", "직접", "계획", "2026-10-01", "최병근", "2026년 계획"),
        ("VAECO (HAN 하노이)", "직접", "계획", "2026-08-01", "송동훈, 박현", "2026년 계획"),
        ("VAECO (DAD 다낭)", "직접", "계획", "2026-08-01", "원대연, 최병근", "2026년 계획"),
        ("SIAEC (SIN 싱가포르)", "직접", "계획", "2026-09-01", "박병권, 이진성", "2026년 계획"),
        ("SANAD Aerotech (AUH)", "직접", "계획", "2026-09-01", "", "2026년 계획"),
        ("디엠티 (DMT)", "직접", "계획", "2026-07-01", "박현", "2026년 계획"),
        
        ("YNJ (연길)", "간접", "계획", "2026-07-01", "최병근", "2026년 계획"),
        ("BKI (코타키나발루)", "간접", "계획", "2026-08-01", "유준열", "2026년 계획"),
        ("UBN (울란바토르)", "간접", "계획", "2026-09-01", "박병권", "2026년 계획"),
        ("FRU (비슈케크)", "간접", "계획", "2026-09-01", "이진성", "2026년 계획"),
        ("DYG (장자제)", "간접", "계획", "2026-10-01", "김주원", "2026년 계획"),
        ("HSG (사가)", "간접", "계획", "2026-10-01", "최병근", "2026년 계획"),
        ("China Airlines (TPE 타오위엔)", "간접", "계획", "2026-08-01", "권혁", "2026년 계획"),
        ("China Airlines (TSA 송산)", "간접", "계획", "2026-08-01", "권혁", "2026년 계획"),
        ("China Airlines (KHH 가오슝)", "간접", "계획", "2026-08-01", "권혁", "2026년 계획"),
        ("Mandarin Airlines (RMQ 타이중)", "간접", "계획", "2026-08-01", "이진성", "2026년 계획"),
        ("Thai Airways (CNX 치앙마이)", "간접", "계획", "2026-07-01", "박병권", "2026년 계획"),
        ("Southern (SHE 선양)", "간접", "계획", "2026-10-01", "최병근", "2026년 계획"),
        ("Atitech (FRA 프랑크푸르트)", "간접", "계획", "2026-09-01", "이진성", "2026년 계획"),
        ("HAECO (XMN 샤먼)", "간접", "계획", "2026-10-01", "최병근", "2026년 계획"),
        ("Sharp Technics K", "간접", "계획", "2026-06-01", "유준열", "2026년 계획"),
        ("HAESL (HKG)", "간접", "계획", "2026-07-01", "박현", "2026년 계획"),
        ("Standard Aero (위니펙)", "간접", "계획", "2026-07-01", "이진성", "2026년 계획")
    ]
    for target, atype, st, sdate, aud, rmk in h_2026:
        add_history(target, 2026, atype, st, sdate, aud, rmk)

    # --- 4. 샘플 지적사항 (Findings / CAR) 및 사전 착안사항 등록 ---
    sample_findings = [
        # VAECO (DAD 다낭)
        {
            "target": "VAECO (DAD 다낭)", "date": "2024-12-01", "type": "CAR", "tag": "공구관리",
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
            "target": "VAECO (DAD 다낭)", "date": "2026-03-10", "type": "Observation", "tag": "자재관리",
            "title": "화학물질(Sealant) 보관 온도 관리 기록 미흡",
            "detail": "냉장 보관이 요구되는 실란트 보관용 소형 냉장고의 일일 온도 점검표 일부 날짜 기록 공란 발생.",
            "reg": "정비자재 관리지침 제8조", "root": "주말 야간 당직자 점검 루틴 누락",
            "action": "디지털 온습도 로거 설치 및 자동 알람 시스템 구축 중",
            "status": "조치중", "due": "2026-08-30", "auditor": "이진성"
        },
        # VAECO (HAN 하노이)
        {
            "target": "VAECO (HAN 하노이)", "date": "2024-12-01", "type": "Finding", "tag": "기술문서",
            "title": "오프라인 AMM(Aircraft Maintenance Manual) 최신 개정판 미동기화",
            "detail": "현장 정비 태블릿 내 저장된 오프라인 기술도면 및 AMM Rev.84가 최신 본부 Rev.86과 2개월 간 동기화되지 않은 채 사용됨.",
            "reg": "기술도서 관리규정 4.2", "root": "정기 네트워크 접속 동기화 주기 미설정",
            "action": "매주 월요일 정기 자동 클라우드 동기화 스크립트 배포 및 동기화 실패 시 알림 팝업 기능 적용",
            "status": "조치완료", "due": "2024-12-20", "auditor": "송동훈"
        },
        {
            "target": "VAECO (HAN 하노이)", "date": "2025-06-20", "type": "CAR", "tag": "교육훈련",
            "title": "B38M 기종 한정 자격 정비사 OJT 이력카드 미보관",
            "detail": "당사 B38M 투입 노선에 배정된 현지 정비사의 기종 교육 수료증 사본 및 OJT 실습 평가표가 현장에 구비되지 않음.",
            "reg": "품질보증기준 2.1 (인력자격관리)", "root": "본사 교육팀 - 해외 지점 간 자격증빙 문서 송부 지연",
            "action": "본사 ERP와 연동된 심사원/정비사 통합 자격 포털에서 실시간 PDF 확인 체계로 전환",
            "status": "조치완료", "due": "2025-07-15", "auditor": "박현"
        },
        # VAECO (CXR 나트랑)
        {
            "target": "VAECO (CXR 나트랑)", "date": "2025-02-25", "type": "Finding", "tag": "공구관리",
            "title": "특수장비(Ground Power Unit 케이블) 피복 손상 미조치",
            "detail": "항공기 전원 공급용 GPU 케이블 외피 마모로 내부 심선 노출 위험 확인.",
            "reg": "지상지원장비 안전규정 제11조", "root": "일일 장비 육안점검 미실시",
            "action": "해당 GPU 케이블 전면 교체 및 주간 GSE 정밀 점검표 작성 의무화",
            "status": "조치완료", "due": "2025-03-15", "auditor": "박병권"
        },
        # STAECO (TNA 지난)
        {
            "target": "STAECO (TNA 지난)", "date": "2024-03-01", "type": "CAR", "tag": "작업환경/시설",
            "title": "C-Check 격납고 내 방폭 조명 및 집진 설비 환기 필터 청결도 미달",
            "detail": "페인팅 및 샌딩 구역 내 환기 필터의 차압 게이지 적정 범위를 초과하여 분진 축적 위험.",
            "reg": "중정비 품질안전기준 7.3", "root": "정기 청소 교체 주기 미준수",
            "action": "집진 필터 전면 교체 및 분기별 차압 게이지 일일 모니터링 대장 비치",
            "status": "조치완료", "due": "2024-04-15", "auditor": "박병권"
        }
    ]

    for f in sample_findings:
        tid = get_or_create(f["target"])
        c.execute("""
            INSERT INTO audit_findings (target_id, audit_date, finding_type, category_tag, title, finding_detail, regulation_ref, root_cause, action_taken, action_status, due_date, auditor)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (tid, f["date"], f["type"], f["tag"], f["title"], f["detail"], f["reg"], f["root"], f["action"], f["status"], f["due"], f["auditor"]))

    # 사전 착안사항 메모 등록
    sample_focus_notes = [
        {
            "target": "VAECO (DAD 다낭)",
            "focus": "1. 2024년 토크렌치 교정 만료 지적 및 2025년 점검표 서명 누락 이력 관련, 현장 공구실 실사 및 Transit 체크시트 실시간 서명 여부 집중 확인 필요.\n2. 2026년 하계 증편에 따른 신규 교대근무 정비사 OJT 및 휴먼에러 방지 절차 중점 점검.\n3. 온습도 민감 자재(실란트/페인트) 보관 로거 기록 확인.",
            "checklist": "- [ ] 공구실 토크렌치 및 측정공구 검교정 스티커/유효기간 전수 확인\n- [ ] 최근 3개월 Transit Check 점검표 서명 및 누락 여부 표본 20건 샘플링\n- [ ] B738/B38M 최신 AMM 오프라인 태블릿 동기화 일자 확인\n- [ ] 비상 안전장구 및 항공기 지상 유도 장비 관리 상태 점검",
            "by": "최병근 (심사기획)"
        },
        {
            "target": "VAECO (HAN 하노이)",
            "focus": "1. 기술도서 오프라인 클라우드 동기화 시스템 정상 작동 여부 재확인.\n2. B38M 및 신규 투입 기종 자격자 인력풀 및 정비사 교육 이력 카드 점검.\n3. 야간 운항편 정비 시 조명 장비 및 안전보호구 착용 실태 확인.",
            "checklist": "- [ ] 태블릿 내 AMM/FIM 최신 리비전 대조\n- [ ] 현지 투입 정비사 기종 한정 자격증 및 당사 위탁 승인서 확인\n- [ ] 결함 처리 로그북 기입 정확도 및 CRS(승인서) 발급 절차 확인",
            "by": "송동훈 (품질기획)"
        }
    ]

    for fn in sample_focus_notes:
        tid = get_or_create(fn["target"])
        c.execute("""
            INSERT INTO audit_focus_notes (target_id, focus_points, checklist_notes, updated_by)
            VALUES (?, ?, ?, ?)
        """, (tid, fn["focus"], fn["checklist"], fn["by"]))

    conn.commit()

    c.execute("SELECT COUNT(*) FROM audit_targets")
    t_cnt = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM audit_history")
    h_cnt = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM audit_findings")
    f_cnt = c.fetchone()[0]
    print(f"\n[성공] 5대 분류 정규화 완료! 대상처: {t_cnt}개, 심사 이력: {h_cnt}건, 등록 지적사항: {f_cnt}건")
    conn.close()

if __name__ == "__main__":
    rebuild_clean_database()
