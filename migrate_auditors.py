"""
migrate_auditors.py
- auditors 테이블 생성
- 품질심사원 현황 엑셀 데이터 임포트
"""
import sqlite3
import os
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "audit.db")

# ── 엑셀에서 파싱한 실제 데이터 (한글명 하드코딩 매핑) ──
# 컬럼: (name_kr, name_en, department, employee_id, qualification, cert_number,
#         initial_training_date, last_refresher_date, initial_eval_date, last_eval_date, remarks)
AUDITOR_DATA = [
    # 1 박영일 PARK YOUNG IL CM T250286 초도교육 2026-01-14 OJT 미완(X) → 평가 이력 없음
    ("박영일", "PARK YOUNG IL", "CM", "T250286",
     "티웨이항공 품질심사원 양성", "품질 승인서 2026-0725",
     "2026-01-14", None,   # initial_training, last_refresher
     "2026-01-14", None,   # initial_eval, last_eval
     "OJT 미완료"),

    # 2 송동훈 SONG DONG HUN EM T240952
    ("송동훈", "SONG DONG HUN", "EM", "T240952",
     "티웨이항공 품질심사원 양성", "품질 AM2025-289",
     "2025-06-11", "2025-06-11",
     "2025-07-30", "2025-07-30",
     ""),

    # 3 원대연 WON DAE YEON SM T200001
    ("원대연", "WON DAE YEON", "SM", "T200001",
     "티웨이항공 품질심사원 양성", "품질 AM2020-067",
     "2012-03-13", "2025-02-28",
     "2014-07-03", "2024-08-12",
     ""),

    # 4 곽성주 KWAK SUNG JOO SM T220007
    ("곽성주", "KWAK SUNG JOO", "SM", "T220007",
     "티웨이항공 품질심사원 양성", "품질 승인서 2026-0725",
     "2026-01-14", None,
     "2026-01-14", None,
     ""),

    # 5 박병권 PARK BYOUNG KWON Manager T160098
    ("박병권", "PARK BYOUNG KWON", "Manager", "T160098",
     "티웨이항공 품질심사원 양성", "품질 AM2019-151",
     "2019-03-14", "2025-05-13",
     "2024-10-14", "2024-10-14",
     ""),

    # 6 유준열 YOU JUN YEOL Manager T180261
    ("유준열", "YOU JUN YEOL", "Manager", "T180261",
     "티웨이항공 품질심사원 양성", "품질 AM2021-326",
     "2021-11-24", "2025-09-17",
     "2024-03-22", "2025-11-27",
     ""),

    # 7 최병근 CHOI BYUNG GEUN Manager T180476
    ("최병근", "CHOI BYUNG GEUN", "Manager", "T180476",
     "티웨이항공 품질심사원 양성", "품질 AM2021-326",
     "2021-11-24", "2025-11-12",
     "2022-03-28", "2025-11-19",
     ""),

    # 8 권혁 KWON HYEOK Manager T180169
    ("권혁", "KWON HYEOK", "Manager", "T180169",
     "티웨이항공 품질심사원 양성", "품질 AM2021-358",
     "2021-12-22", "2025-05-13",
     "2022-02-21", "2025-03-13",
     ""),

    # 9 이진성 LEE JIN SUNG Manager T160291
    ("이진성", "LEE JIN SUNG", "Manager", "T160291",
     "티웨이항공 품질심사원 양성", "품질 AM2024-033",
     "2024-01-12", "2025-09-17",
     "2024-03-20", "2025-11-14",
     ""),

    # 10 박현 PARK HYUN Manager T180479
    ("박현", "PARK HYUN", "Manager", "T180479",
     "티웨이항공 품질심사원 양성", "품질 AM2023-433",
     "2023-10-13", "2025-11-12",
     "2024-03-22", "2025-11-19",
     ""),

    # 11 최문성 CHOI MOON SUNG SM T220044
    ("최문성", "CHOI MOON SUNG", "SM", "T220044",
     "티웨이항공 품질심사원 양성", "품질 AM2025-381",
     "2025-08-13", "2025-08-13",
     "2025-11-06", "2025-11-06",
     ""),

    # 12 김주원 KIM JU WON Manager T180496
    ("김주원", "KIM JU WON", "Manager", "T180496",
     "티웨이항공 품질심사원 양성", "품질 AM2025-381",
     "2025-08-13", "2025-08-13",
     "2025-09-23", "2025-09-23",
     ""),

    # 13 유진우 YOO JIN WOO Manager T220180
    ("유진우", "YOO JIN WOO", "Manager", "T220180",
     "티웨이항공 품질심사원 양성", "품질 승인서 2026-0725",
     "2026-01-14", None,
     "2026-01-14", None,
     ""),

    # 14 김지훈 KIM JI HUN Manager T130001
    ("김지훈", "KIM JI HUN", "Manager", "T130001",
     "티웨이항공 품질심사원 양성", "승인서(임시) 제2026-0112호",
     "2026-05-13", None,
     "2026-05-13", None,
     "OJT 미완료"),

    # 15 양원 YANG WON Manager T170149
    ("양원", "YANG WON", "Manager", "T170149",
     "티웨이항공 품질심사원 양성", "승인서(임시) 제2026-0112호",
     "2026-05-13", None,
     "2026-05-13", None,
     "OJT 미완료"),

    # 16 안민형 ANH MIN HYUNG Manager T180267
    ("안민형", "ANH MIN HYUNG", "Manager", "T180267",
     "티웨이항공 품질심사원 양성", "승인서(임시) 제2026-0112호",
     "2026-05-13", None,
     "2026-05-13", None,
     "OJT 미완료"),
]


def add_months(date_str, months):
    """날짜 문자열에서 N개월 후 날짜를 YYYY-MM-DD로 반환"""
    if not date_str:
        return None
    try:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        month = dt.month - 1 + months
        year = dt.year + month // 12
        month = month % 12 + 1
        import calendar
        day = min(dt.day, calendar.monthrange(year, month)[1])
        return datetime.date(year, month, day).strftime("%Y-%m-%d")
    except Exception:
        return None


def migrate():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 테이블 생성
    c.execute("""
        CREATE TABLE IF NOT EXISTS auditors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_kr TEXT NOT NULL,
            name_en TEXT,
            department TEXT,
            employee_id TEXT UNIQUE,
            contact TEXT DEFAULT '',
            qualification TEXT,
            cert_number TEXT,
            initial_training_date TEXT,
            last_refresher_date TEXT,
            next_refresher_due TEXT,
            initial_eval_date TEXT,
            last_eval_date TEXT,
            next_eval_due TEXT,
            remarks TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    # 기존 데이터가 없을 때만 임포트
    c.execute("SELECT COUNT(*) FROM auditors")
    count = c.fetchone()[0]
    if count == 0:
        print("auditors 테이블이 비어있습니다. 엑셀 데이터를 임포트합니다...")
        for row in AUDITOR_DATA:
            (name_kr, name_en, dept, emp_id, qual, cert,
             init_train, last_refresh,
             init_eval, last_eval, remarks) = row

            # 자동 계산: 보수교육 만료일
            base_refresh = last_refresh if last_refresh else init_train
            next_refresh = add_months(base_refresh, 24)

            # 자동 계산: 평가 만료일
            base_eval = last_eval if last_eval else init_eval
            next_eval = add_months(base_eval, 24)

            c.execute("""
                INSERT OR IGNORE INTO auditors
                (name_kr, name_en, department, employee_id, qualification, cert_number,
                 initial_training_date, last_refresher_date, next_refresher_due,
                 initial_eval_date, last_eval_date, next_eval_due, remarks)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name_kr, name_en, dept, emp_id, qual, cert,
                  init_train, last_refresh, next_refresh,
                  init_eval, last_eval, next_eval, remarks))
        print(f"  → {len(AUDITOR_DATA)}명 임포트 완료")
    else:
        print(f"auditors 테이블에 이미 {count}명의 데이터가 있습니다. 임포트 건너뜀.")

    conn.commit()
    conn.close()
    print("마이그레이션 완료!")


if __name__ == "__main__":
    migrate()
