import http.server
import json
import sqlite3
import urllib.parse
import os
import datetime
import re
import calendar
import uuid
import secrets
import io
import base64
import openpyxl

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHECKLIST_DIR = os.path.join(BASE_DIR, "품질심사 체크리스트")
os.makedirs(CHECKLIST_DIR, exist_ok=True)
DB_PATH = os.path.join(BASE_DIR, "audit.db")
STATIC_DIR = os.path.join(BASE_DIR, "static")
if not os.path.exists(STATIC_DIR):
    alt_static = os.path.join(os.path.dirname(BASE_DIR), "static")
    if os.path.exists(alt_static):
        STATIC_DIR = alt_static
PORT = 8000

# 메모리 세션 저장소 (token -> user_dict)
ACTIVE_SESSIONS = {}

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _add_months(date_str, months):
    """날짜 문자열(YYYY-MM-DD)에서 N개월 후 날짜를 반환"""
    if not date_str:
        return None
    try:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        m = dt.month - 1 + months
        year = dt.year + m // 12
        month = m % 12 + 1
        day = min(dt.day, calendar.monthrange(year, month)[1])
        return datetime.date(year, month, day).strftime("%Y-%m-%d")
    except Exception:
        return None


def _auditor_status(next_refresher_due, next_eval_due):
    """심사원 종합 자격 상태를 계산하여 반환 (정상/임박/만료)"""
    today = datetime.date.today()
    warn_days = 180  # 6개월 기준

    def _status_for(due_str):
        if not due_str:
            return "정상"  # 만료일 없는 경우(신규) 정상으로 처리
        try:
            due = datetime.datetime.strptime(due_str, "%Y-%m-%d").date()
            delta = (due - today).days
            if delta < 0:
                return "만료"
            elif delta <= warn_days:
                return "임박"
            else:
                return "정상"
        except Exception:
            return "정상"

    s_refresh = _status_for(next_refresher_due)
    s_eval = _status_for(next_eval_due)

    # 우선순위: 만료 > 임박 > 정상
    priority = {"만료": 2, "임박": 1, "정상": 0}
    worst = max(s_refresh, s_eval, key=lambda x: priority[x])
    return worst, s_refresh, s_eval


def _ensure_auditors_table():
    """auditors 테이블이 없으면 생성"""
    conn = get_db_connection()
    c = conn.cursor()
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
    conn.commit()
    conn.close()


# 앱 시작 시 테이블 보장
def _ensure_targets_schema():
    """audit_targets 테이블에 aircraft_types, engine_types 컬럼이 없으면 추가"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("PRAGMA table_info(audit_targets)")
    cols = [r["name"] for r in c.fetchall()]
    if "aircraft_types" not in cols:
        try:
            c.execute("ALTER TABLE audit_targets ADD COLUMN aircraft_types TEXT DEFAULT ''")
        except Exception:
            pass
    if "engine_types" not in cols:
        try:
            c.execute("ALTER TABLE audit_targets ADD COLUMN engine_types TEXT DEFAULT ''")
        except Exception:
            pass
    conn.commit()
    conn.close()

def _ensure_users_table():
    """users 테이블 생성 및 초기 계정(admin + auditors) 자동 동기화"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            employee_id TEXT,
            auditor_id INTEGER,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (auditor_id) REFERENCES auditors(id)
        )
    """)
    # admin 계정 없으면 기본 생성
    c.execute("SELECT id FROM users WHERE username = ?", ("admin",))
    if not c.fetchone():
        c.execute("""
            INSERT INTO users (username, password, name, role)
            VALUES ('admin', 'admin1234', '시스템 관리자', 'admin')
        """)

    # 심사원 목록을 users 테이블에 동기화
    c.execute("SELECT id, name_kr, employee_id FROM auditors")
    for aud_id, name_kr, emp_id in c.fetchall():
        if emp_id:
            c.execute("SELECT id FROM users WHERE username = ?", (emp_id,))
            if not c.fetchone():
                c.execute("""
                    INSERT INTO users (username, password, name, role, employee_id, auditor_id)
                    VALUES (?, '1234', ?, 'user', ?, ?)
                """, (emp_id, name_kr, emp_id, aud_id))
    conn.commit()
    conn.close()

def _ensure_findings_schema():
    """audit_findings 및 audit_focus_notes 테이블 생성 보장"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS audit_findings (
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
        CREATE TABLE IF NOT EXISTS audit_focus_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id INTEGER NOT NULL UNIQUE,
            focus_points TEXT DEFAULT '',
            checklist_notes TEXT DEFAULT '',
            updated_by TEXT DEFAULT '',
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (target_id) REFERENCES audit_targets(id)
        )
    """)
    conn.commit()
    conn.close()

_ensure_auditors_table()
_ensure_targets_schema()
_ensure_users_table()
_ensure_findings_schema()

# 계획표(2027년 정비부문 품질심사 계획표 R.0) 기준 표준 점검표 카탈로그 매핑
STANDARD_CHECKLIST_CATALOG = [
    {"code": "TW-MNT-001", "title": "항공기기술 품질심사 점검표", "category": "내부 부서", "targets": "항공기기술"},
    {"code": "TW-MNT-002", "title": "정비기획 품질심사 점검표", "category": "내부 부서", "targets": "정비기획"},
    {"code": "TW-MNT-003", "title": "정비자재 품질심사 점검표", "category": "내부 부서", "targets": "정비자재"},
    {"code": "TW-MNT-005", "title": "정비통제 품질심사 점검표", "category": "내부 부서", "targets": "정비통제"},
    {"code": "TW-MNT-007", "title": "주재정비공항 품질심사 점검표", "category": "해외운항지점,국내운항지점", "targets": "국내운항지점,해외운항지점"},
    {"code": "TW-MNT-008", "title": "위탁정비업체 품질심사 점검표", "category": "완전위탁업체,엔진정비업체,중정비업체,국내업체", "targets": "완전위탁업체,엔진정비업체,중정비업체,대한항공,KAEMS,N3,Lufthansa,GE ON WINGS,Sharp"},
    {"code": "TW-MNT-010", "title": "정비기지공항(운항정비1,2) 품질심사 점검표", "category": "내부 부서", "targets": "운항정비1,2"},
    {"code": "TW-MNT-012", "title": "부품수리 품질심사 점검표", "category": "내부 부서", "targets": "부품수리"},
    {"code": "TW-MNT-013", "title": "도급업체 품질심사 점검표", "category": "국내업체", "targets": "대동금속"},
    {"code": "TW-MNT-014", "title": "엔진기술 / 협력업체 품질심사 점검표", "category": "내부 부서,국내업체", "targets": "엔진기술,고암에이스항공,DMT"},
]

def resolve_default_template_code(station_name: str, category: str) -> str:
    """심사 대상명 및 A열 카테고리에 따른 기본 점검표 코드(TW-MNT-xxx) 자동 매핑"""
    s = (station_name or "").strip()
    cat = (category or "").strip()
    if cat == "내부 부서" or "내부" in cat:
        if "항공기기술" in s:
            return "TW-MNT-001"
        if "정비기획" in s:
            return "TW-MNT-002"
        if "정비자재" in s:
            return "TW-MNT-003"
        if "정비통제" in s:
            return "TW-MNT-005"
        if "운항정비" in s:
            return "TW-MNT-010"
        if "부품수리" in s:
            return "TW-MNT-012"
        if "엔진기술" in s:
            return "TW-MNT-014"
        return "TW-MNT-005"
    if cat in ("해외운항지점", "국내운항지점"):
        return "TW-MNT-007"
    if cat == "국내업체":
        if "대동금속" in s:
            return "TW-MNT-013"
        if "고암" in s or "DMT" in s.upper():
            return "TW-MNT-014"
        return "TW-MNT-008"
    return "TW-MNT-008"

def _ensure_checklists_schema():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS checklist_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            revision TEXT DEFAULT '',
            category TEXT DEFAULT '',
            target_keywords TEXT DEFAULT '',
            excel_path TEXT DEFAULT '',
            header_title TEXT DEFAULT '',
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS checklist_template_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            seq_no INTEGER DEFAULT 0,
            section_no TEXT DEFAULT '',
            item_no TEXT NOT NULL,
            requirement TEXT NOT NULL,
            external_ref TEXT DEFAULT '',
            internal_ref TEXT DEFAULT '',
            excel_row INTEGER DEFAULT 0,
            FOREIGN KEY (template_id) REFERENCES checklist_templates(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS checklist_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            audit_year INTEGER NOT NULL DEFAULT 2026,
            audit_no TEXT DEFAULT 'YY-QA-XXX',
            audit_date TEXT DEFAULT '',
            auditor TEXT DEFAULT '',
            audit_purpose TEXT DEFAULT 'Schedule',
            audit_purpose_other TEXT DEFAULT '',
            auditee_team TEXT DEFAULT '',
            auditee_coordinator TEXT DEFAULT '',
            auditee_title TEXT DEFAULT '',
            auditee_phone TEXT DEFAULT '',
            remark TEXT DEFAULT '',
            status TEXT DEFAULT '작성중',
            responses_json TEXT DEFAULT '{}',
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (template_id) REFERENCES checklist_templates(id),
            FOREIGN KEY (target_id) REFERENCES audit_targets(id)
        )
    """)
    # 표준 카탈로그 기본 레코드 보장
    for item in STANDARD_CHECKLIST_CATALOG:
        c.execute("SELECT id FROM checklist_templates WHERE code = ?", (item["code"],))
        if not c.fetchone():
            c.execute("""
                INSERT INTO checklist_templates (code, title, category, target_keywords)
                VALUES (?, ?, ?, ?)
            """, (item["code"], item["title"], item["category"], item["targets"]))
    conn.commit()
    conn.close()

def parse_and_import_checklist_excel(excel_path: str, override_code: str = None, override_category: str = None):
    """엑셀 점검표 파일(예: (TW-MNT-005) 정비통제 품질심사 점검표 (R.13).xlsx)을 파싱하여 DB에 등록/업데이트"""
    if not os.path.exists(excel_path):
        return None
    fname = os.path.basename(excel_path)
    # 계획표 엑셀 파일은 제외
    if "계획표" in fname or "실시이력" in fname or "스케줄" in fname or "현황" in fname or "검토요청서" in fname:
        return None

    try:
        wb = openpyxl.load_workbook(excel_path, data_only=True)
    except Exception:
        return None

    ws = wb["CheckList"] if "CheckList" in wb.sheetnames else wb.active
    # Requirement 헤더 행 탐색 (보통 15행)
    header_row = None
    for r in range(1, min(30, ws.max_row + 1)):
        row_vals = [str(ws.cell(r, col).value or "").strip() for col in range(1, min(14, ws.max_column + 1))]
        if any("Requirement" in v for v in row_vals):
            header_row = r
            break
    if not header_row:
        return None

    # 파일명에서 코드(TW-MNT-xxx), 제목, 리비전(R.xx) 추출
    m_code = re.search(r'(TW-[A-Z]+-\d+)', fname, re.IGNORECASE)
    code = (override_code or (m_code.group(1).upper() if m_code else os.path.splitext(fname)[0][:20])).strip()

    m_rev = re.search(r'\((R\.\d+)\)', fname, re.IGNORECASE)
    revision = m_rev.group(1).upper() if m_rev else ""

    header_title = str(ws.cell(1, 1).value or "").strip()
    clean_title = re.sub(r'^\([^)]+\)\s*', '', os.path.splitext(fname)[0])
    clean_title = re.sub(r'\s*\(R\.\d+\)\s*$', '', clean_title).strip()
    if not clean_title:
        clean_title = header_title or code

    # 표준 카탈로그에서 기본 카테고리/타겟 참조
    std_entry = next((x for x in STANDARD_CHECKLIST_CATALOG if x["code"] == code), None)
    category = override_category or (std_entry["category"] if std_entry else "내부 부서")
    target_kw = std_entry["targets"] if std_entry else ""

    items = []
    last_section = ""
    seq_counter = 0
    for r in range(header_row + 1, ws.max_row + 1):
        req_val = ws.cell(r, 4).value
        item_no_val = ws.cell(r, 3).value
        if req_val is None or str(req_val).strip() == "":
            continue
        seq_counter += 1
        raw_seq = ws.cell(r, 1).value
        seq_no = int(raw_seq) if isinstance(raw_seq, (int, float)) else seq_counter
        sec_val = ws.cell(r, 2).value
        if sec_val is not None and str(sec_val).strip() != "":
            last_section = str(sec_val).strip()
        item_no = str(item_no_val if item_no_val is not None else seq_counter).strip()
        requirement = str(req_val).strip()
        ext_ref = str(ws.cell(r, 5).value or "").strip()
        int_ref = str(ws.cell(r, 6).value or "").strip()
        items.append({
            "seq_no": seq_no,
            "section_no": last_section,
            "item_no": item_no,
            "requirement": requirement,
            "external_ref": ext_ref,
            "internal_ref": int_ref,
            "excel_row": r
        })

    if not items:
        return None

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM checklist_templates WHERE code = ?", (code,))
    row = c.fetchone()
    if row:
        tid = row["id"]
        c.execute("""
            UPDATE checklist_templates
            SET title = ?, revision = ?, category = ?, target_keywords = ?,
                excel_path = ?, header_title = ?, updated_at = datetime('now','localtime')
            WHERE id = ?
        """, (clean_title, revision, category, target_kw, excel_path, header_title, tid))
    else:
        c.execute("""
            INSERT INTO checklist_templates (code, title, revision, category, target_keywords, excel_path, header_title)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (code, clean_title, revision, category, target_kw, excel_path, header_title))
        tid = c.lastrowid

    c.execute("DELETE FROM checklist_template_items WHERE template_id = ?", (tid,))
    for it in items:
        c.execute("""
            INSERT INTO checklist_template_items
            (template_id, seq_no, section_no, item_no, requirement, external_ref, internal_ref, excel_row)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (tid, it["seq_no"], it["section_no"], it["item_no"], it["requirement"], it["external_ref"], it["internal_ref"], it["excel_row"]))

    conn.commit()
    conn.close()
    return {"id": tid, "code": code, "title": clean_title, "revision": revision, "item_count": len(items)}

def sync_checklist_templates_from_excel():
    """품질심사 체크리스트 폴더 및 루트 폴더의 점검표 엑셀을 스캔하여 자동 등록"""
    scan_dirs = [CHECKLIST_DIR, BASE_DIR]
    imported = []
    seen_codes = set()
    for d in scan_dirs:
        if not os.path.exists(d):
            continue
        for fname in sorted(os.listdir(d)):
            if not fname.lower().endswith((".xlsx", ".xlsm")) or fname.startswith("~$"):
                continue
            fpath = os.path.join(d, fname)
            res = parse_and_import_checklist_excel(fpath)
            if res and res["code"] not in seen_codes:
                seen_codes.add(res["code"])
                imported.append(res)
    return imported

_ensure_checklists_schema()
sync_checklist_templates_from_excel()

def generate_schedule_for_target_api(target_id: int, start_year: int = 2026, end_year: int = 2030):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM audit_targets WHERE id = ?", (target_id,))
    target = cursor.fetchone()
    if not target:
        conn.close()
        return {}
        
    op_status = target["operation_status"]
    base_interval = target["base_interval"] or 2
    
    # 3. 비운항 상태 로직: 비운항인 경우 계획을 편성/카운팅하지 않음
    if op_status == "비운항":
        conn.close()
        return {year: None for year in range(start_year, end_year + 1)}
        
    # 과거 최근 심사 이력 조회
    cursor.execute("""
        SELECT year, audit_type, scheduled_date, auditor, status FROM audit_history 
        WHERE target_id = ? AND year < ?
        ORDER BY year DESC LIMIT 1
    """, (target_id, start_year))
    last_audit = cursor.fetchone()
    
    # 이벤트 조회
    cursor.execute("""
        SELECT event_year, detail FROM schedule_events
        WHERE target_id = ? AND event_year BETWEEN ? AND ?
    """, (target_id, start_year, end_year))
    events = {r["event_year"]: r["detail"] for r in cursor.fetchall()}
    
    # 현재 연도 범위 내 DB에 저장된 심사 계획/이력
    cursor.execute("""
        SELECT * FROM audit_history
        WHERE target_id = ? AND year BETWEEN ? AND ?
    """, (target_id, start_year, end_year))
    existing_histories = {r["year"]: dict(r) for r in cursor.fetchall()}
    
    conn.close()
    
    schedule = {}
    
    # 2. 국내/공항 STATION 및 내부팀 항목 (base_interval == 1): 간접심사 없이 매년 1회 직접심사(●)
    if base_interval == 1:
        ref_month = 6
        ref_auditor = ""
        if last_audit:
            ref_auditor = last_audit["auditor"] or ""
            if last_audit["scheduled_date"]:
                try:
                    ref_month = int(last_audit["scheduled_date"].split("-")[1])
                except Exception:
                    ref_month = 6

        for year in range(start_year, end_year + 1):
            if year in existing_histories:
                db_record = existing_histories[year]
                audit_type = db_record["audit_type"] or "직접"
                s_date = db_record["scheduled_date"] or f"{year}-{ref_month:02d}-01"
                try:
                    ref_month = int(s_date.split("-")[1])
                except Exception:
                    pass
                if db_record["auditor"]:
                    ref_auditor = db_record["auditor"]
                schedule[year] = {
                    "id": db_record["id"],
                    "target_id": target_id,
                    "year": year,
                    "audit_type": audit_type,
                    "status": db_record["status"],
                    "is_event": db_record["is_event"],
                    "event_detail": db_record["event_detail"],
                    "remarks": db_record["remarks"] or "정기 직접심사",
                    "scheduled_date": s_date,
                    "auditor": db_record["auditor"] or ref_auditor,
                    "symbol": "◎" if audit_type == "간접" else "●"
                }
            else:
                schedule[year] = {
                    "id": None,
                    "target_id": target_id,
                    "year": year,
                    "audit_type": "직접",
                    "status": "계획",
                    "is_event": False,
                    "event_detail": None,
                    "remarks": f"연례 정기 직접심사 ({ref_month}월)",
                    "scheduled_date": f"{year}-{ref_month:02d}-01",
                    "auditor": ref_auditor,
                    "symbol": "●"
                }
        return schedule

    # 1 & 4. 일반 항목 (base_interval == 2): 2년 주기 교차 편성 및 수동 입력 동적 롤링 (Reset & Roll-over)
    if last_audit:
        ref_year = last_audit["year"]
        ref_type = last_audit["audit_type"]
        ref_month = 6
        ref_auditor = last_audit["auditor"] or ""
        if last_audit["scheduled_date"]:
            try:
                ref_month = int(last_audit["scheduled_date"].split("-")[1])
            except Exception:
                ref_month = 6
    else:
        ref_year, ref_type, ref_month, ref_auditor = None, None, 6, ""
        
    for year in range(start_year, end_year + 1):
        # 4.1 수동 입력된 DB 기록이 있는 경우 -> 해당 입력 시점을 새 기준(Anchor)으로 롤링 리셋
        if year in existing_histories:
            db_record = existing_histories[year]
            a_type = db_record["audit_type"] or ("간접" if ref_type == "직접" else "직접")
            s_date = db_record["scheduled_date"] or f"{year}-{ref_month:02d}-01"
            if s_date:
                try:
                    ref_month = int(s_date.split("-")[1])
                except Exception:
                    pass
            if db_record["auditor"]:
                ref_auditor = db_record["auditor"]
            schedule[year] = {
                "id": db_record["id"],
                "target_id": target_id,
                "year": year,
                "audit_type": a_type,
                "status": db_record["status"],
                "is_event": db_record["is_event"],
                "event_detail": db_record["event_detail"],
                "remarks": db_record["remarks"] or "",
                "scheduled_date": s_date,
                "auditor": db_record["auditor"] or ref_auditor,
                "symbol": "◎" if a_type == "간접" else "●"
            }
            ref_year = year
            ref_type = a_type
            continue
            
        # 4.2 신규 기종/지점 이벤트 등록이 있는 경우 -> 간접심사 배정 및 롤링 리셋
        if year in events:
            audit_type = "간접"
            detail = events[year]
            scheduled_date = f"{year}-{ref_month:02d}-01"
            
            schedule[year] = {
                "id": None,
                "target_id": target_id,
                "year": year,
                "audit_type": audit_type,
                "status": "계획",
                "is_event": True,
                "event_detail": detail,
                "remarks": f"기종/지점 추가 이벤트 ({detail})",
                "scheduled_date": scheduled_date,
                "auditor": ref_auditor,
                "symbol": "◎"
            }
            ref_year = year
            ref_type = "간접"
            continue

        # 4.3 자동 인터벌 계산 (2년 교차 롤링 - 이전 수행 월 유지)
        if ref_year is not None:
            diff = year - ref_year
            if diff == 2:
                audit_type = "간접" if ref_type == "직접" else "직접"
                symbol = "◎" if audit_type == "간접" else "●"
                scheduled_date = f"{year}-{ref_month:02d}-01"
                
                schedule[year] = {
                    "id": None,
                    "target_id": target_id,
                    "year": year,
                    "audit_type": audit_type,
                    "status": "계획",
                    "is_event": False,
                    "event_detail": None,
                    "remarks": f"2년 주기 정기 심사 ({ref_month}월)",
                    "scheduled_date": scheduled_date,
                    "auditor": ref_auditor,
                    "symbol": symbol
                }
                ref_year = year
                ref_type = audit_type
            elif diff > 2 and diff % 2 == 0:
                # 2년 단위 주기 유지
                steps = diff // 2
                cur_type = ref_type
                for _ in range(steps):
                    cur_type = "간접" if cur_type == "직접" else "직접"
                
                audit_type = cur_type
                symbol = "◎" if audit_type == "간접" else "●"
                schedule[year] = {
                    "id": None,
                    "target_id": target_id,
                    "year": year,
                    "audit_type": audit_type,
                    "status": "계획",
                    "is_event": False,
                    "event_detail": None,
                    "remarks": f"2년 주기 정기 심사 ({ref_month}월)",
                    "scheduled_date": f"{year}-{ref_month:02d}-01",
                    "auditor": ref_auditor,
                    "symbol": symbol
                }
                ref_year = year
                ref_type = audit_type
            else:
                schedule[year] = None
        else:
            schedule[year] = None
                
    return schedule

class BuiltinWebServer(http.server.BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        # Suppress logging
        pass

    def send_json_response(self, data, status_code=200):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.end_headers()

    def get_current_user(self):
        auth_header = self.headers.get('Authorization', '')
        token = None
        if auth_header.startswith('Bearer '):
            token = auth_header[7:].strip()
        if not token:
            cookie_header = self.headers.get('Cookie', '')
            for cookie in cookie_header.split(';'):
                if 'session_token=' in cookie:
                    token = cookie.split('session_token=')[1].strip()
                    break
        if token and token in ACTIVE_SESSIONS:
            return ACTIVE_SESSIONS[token]
        return None

    def serve_static_file(self, file_path, content_type):
        if os.path.exists(file_path) and os.path.isfile(file_path):
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.end_headers()
            with open(file_path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404, "File Not Found")

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        # 1. Static Assets Serving
        if path == "/" or path == "/index.html":
            self.serve_static_file(os.path.join(STATIC_DIR, "index.html"), "text/html; charset=utf-8")
            return
        elif path.startswith("/static/"):
            relative_path = path[8:]
            file_path = os.path.join(STATIC_DIR, relative_path)
            
            if file_path.endswith(".css"):
                content_type = "text/css"
            elif file_path.endswith(".js"):
                content_type = "application/javascript"
            elif file_path.endswith(".png"):
                content_type = "image/png"
            elif file_path.endswith(".webp"):
                content_type = "image/webp"
            elif file_path.endswith(".svg"):
                content_type = "image/svg+xml"
            elif file_path.endswith(".json"):
                content_type = "application/json"
            else:
                content_type = "text/plain"
                
            self.serve_static_file(file_path, content_type)
            return

        # 2. REST API endpoints
        elif path == "/api/targets":
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_targets ORDER BY id ASC")
            targets = [dict(r) for r in cursor.fetchall()]
            conn.close()
            self.send_json_response(targets)
            return

        elif path == "/api/targets/tree":
            conn = get_db_connection()
            cursor = conn.cursor()
            categories = ["해외운항지점", "완전위탁업체", "엔진정비업체", "중정비업체", "국내업체", "내부 부서", "국내운항지점"]
            cursor.execute("""
                SELECT t.*, 
                    (SELECT COUNT(*) FROM audit_findings f WHERE f.target_id = t.id) as total_findings,
                    (SELECT COUNT(*) FROM audit_findings f WHERE f.target_id = t.id AND f.action_status != '조치완료') as open_findings,
                    (SELECT MAX(scheduled_date) FROM audit_history h WHERE h.target_id = t.id AND h.status = '완료') as last_audit_date,
                    (SELECT MIN(scheduled_date) FROM audit_history h WHERE h.target_id = t.id AND h.status = '계획') as next_audit_date
                FROM audit_targets t
                ORDER BY t.id ASC
            """)
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()

            tree = {cat: [] for cat in categories}
            for r in rows:
                cat = r.get("category", "완전위탁업체")
                if cat not in tree:
                    tree[cat] = []
                tree[cat].append(r)

            self.send_json_response({
                "categories": categories,
                "tree": tree,
                "total_targets": len(rows)
            })
            return

        elif path.startswith("/api/targets/") and path.endswith("/analysis"):
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[0] == "api" and parts[1] == "targets" and parts[3] == "analysis":
                try:
                    target_id = int(parts[2])
                except ValueError:
                    self.send_json_response({"detail": "잘못된 대상 ID입니다."}, 400)
                    return

                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM audit_targets WHERE id = ?", (target_id,))
                target = cursor.fetchone()
                if not target:
                    conn.close()
                    self.send_json_response({"detail": "심사 대상을 찾을 수 없습니다."}, 404)
                    return
                target_dict = dict(target)

                # 심사 이력
                cursor.execute("""
                    SELECT * FROM audit_history 
                    WHERE target_id = ? 
                    ORDER BY year DESC, scheduled_date DESC
                """, (target_id,))
                histories = [dict(r) for r in cursor.fetchall()]

                # 지적/개선조치 사항
                cursor.execute("""
                    SELECT * FROM audit_findings 
                    WHERE target_id = ? 
                    ORDER BY audit_date DESC, id DESC
                """, (target_id,))
                findings = [dict(r) for r in cursor.fetchall()]

                # 카테고리별/태그별 통계
                cursor.execute("""
                    SELECT category_tag, COUNT(*) as count 
                    FROM audit_findings 
                    WHERE target_id = ? AND category_tag != ''
                    GROUP BY category_tag
                    ORDER BY count DESC
                """, (target_id,))
                tag_stats = [dict(r) for r in cursor.fetchall()]

                # 사전 착안사항 메모
                cursor.execute("SELECT * FROM audit_focus_notes WHERE target_id = ?", (target_id,))
                focus_note = cursor.fetchone()
                focus_dict = dict(focus_note) if focus_note else None

                conn.close()
                multi_year_schedule = generate_schedule_for_target_api(target_id, 2026, 2030)

                self.send_json_response({
                    "target": target_dict,
                    "histories": histories,
                    "findings": findings,
                    "tag_stats": tag_stats,
                    "focus_note": focus_dict,
                    "schedule_2026_2030": multi_year_schedule
                })
                return

        elif path == "/api/dashboard":
            year = int(query_params.get("year", [2026])[0])
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_targets")
            targets = cursor.fetchall()
            conn.close()
            
            current_month = datetime.datetime.now().month
            total_count = 0
            direct_count = 0
            indirect_count = 0
            this_month_list = []
            year_audit_list = []
            
            for t in targets:
                # 비운항 제외 스케줄 생성 (2026년 이후는 2026년 기준 롤링, 2025년 이전은 실제 DB 이력만 반영)
                sched_start = 2026 if year >= 2026 else year
                scheds = generate_schedule_for_target_api(t["id"], start_year=sched_start, end_year=year)
                val = scheds.get(year)
                if year < 2026 and val and val.get("id") is None:
                    val = None
                if val:
                    total_count += 1
                    if val["audit_type"] == "직접":
                        direct_count += 1
                    else:
                        indirect_count += 1
                        
                    audit_item = {
                        "id": val["id"],
                        "target_id": t["id"],
                        "station_name": t["station_name"],
                        "category": t["category"],
                        "operation_status": t["operation_status"],
                        "base_interval": t["base_interval"],
                        "audit_type": val["audit_type"],
                        "scheduled_date": val["scheduled_date"],
                        "auditor": val["auditor"],
                        "status": val["status"],
                        "symbol": val["symbol"],
                        "remarks": val["remarks"]
                    }
                    year_audit_list.append(audit_item)
                    
                    date_str = val["scheduled_date"]
                    try:
                        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                        if dt.month == current_month:
                            this_month_list.append(audit_item)
                    except Exception:
                        pass
                        
            self.send_json_response({
                "year": year,
                "current_month": current_month,
                "stats": {
                    "total": total_count,
                    "direct": direct_count,
                    "indirect": indirect_count
                },
                "this_month_audits": this_month_list,
                "year_audits": year_audit_list
            })
            return

        elif path == "/api/calendar":
            year = int(query_params.get("year", [2026])[0])
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_targets")
            targets = cursor.fetchall()
            conn.close()
            
            calendar_data = {m: [] for m in range(1, 13)}
            
            for t in targets:
                sched_start = 2026 if year >= 2026 else year
                scheds = generate_schedule_for_target_api(t["id"], start_year=sched_start, end_year=year)
                val = scheds.get(year)
                if year < 2026 and val and val.get("id") is None:
                    val = None
                if val:
                    date_str = val["scheduled_date"]
                    try:
                        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                        month = dt.month
                        day = dt.day
                        calendar_data[month].append({
                            "id": val["id"],
                            "target_id": t["id"],
                            "station_name": t["station_name"],
                            "category": t["category"],
                            "operation_status": t["operation_status"],
                            "base_interval": t["base_interval"],
                            "audit_type": val["audit_type"],
                            "scheduled_date": val["scheduled_date"],
                            "day": day,
                            "auditor": val["auditor"],
                            "status": val["status"],
                            "symbol": val["symbol"],
                            "remarks": val["remarks"]
                        })
                    except Exception:
                        calendar_data[6].append({
                            "id": val["id"],
                            "target_id": t["id"],
                            "station_name": t["station_name"],
                            "category": t["category"],
                            "operation_status": t["operation_status"],
                            "base_interval": t["base_interval"],
                            "audit_type": val["audit_type"],
                            "scheduled_date": val["scheduled_date"],
                            "day": 1,
                            "auditor": val["auditor"],
                            "status": val["status"],
                            "symbol": val["symbol"],
                            "remarks": val["remarks"]
                        })
            self.send_json_response(calendar_data)
            return

        elif path == "/api/multi_year_schedule":
            start_year = int(query_params.get("start_year", [2026])[0])
            end_year = int(query_params.get("end_year", [2030])[0])
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_targets ORDER BY id ASC")
            targets = [dict(r) for r in cursor.fetchall()]
            conn.close()
            
            result = []
            for t in targets:
                scheds = generate_schedule_for_target_api(t["id"], start_year=start_year, end_year=end_year)
                target_item = dict(t)
                target_item["schedule"] = scheds
                result.append(target_item)
                
            self.send_json_response(result)
            return

        elif path == "/api/list":
            year = int(query_params.get("year", [2026])[0])
            month = int(query_params.get("month", [8])[0])
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_targets")
            targets = cursor.fetchall()
            conn.close()
            
            filtered_list = []
            
            for t in targets:
                sched_start = 2026 if year >= 2026 else year
                scheds = generate_schedule_for_target_api(t["id"], start_year=sched_start, end_year=year)
                val = scheds.get(year)
                if year < 2026 and val and val.get("id") is None:
                    val = None
                if val:
                    date_str = val["scheduled_date"]
                    try:
                        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                        if dt.year == year and dt.month == month:
                            filtered_list.append({
                                "id": val["id"],
                                "target_id": t["id"],
                                "station_name": t["station_name"],
                                "category": t["category"],
                                "operation_status": t["operation_status"],
                                "base_interval": t["base_interval"],
                                "audit_type": val["audit_type"],
                                "scheduled_date": val["scheduled_date"],
                                "auditor": val["auditor"],
                                "status": val["status"],
                                "symbol": val["symbol"],
                                "remarks": val["remarks"]
                            })
                    except Exception:
                        pass
            self.send_json_response(filtered_list)
            return

        # ── 심사원 관리 API ────────────────────────────────────────
        elif path == "/api/auditors":
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM auditors ORDER BY id ASC")
            rows = [dict(r) for r in c.fetchall()]
            conn.close()

            today = datetime.date.today()
            warn_days = 180
            for row in rows:
                overall, s_r, s_e = _auditor_status(
                    row.get("next_refresher_due"),
                    row.get("next_eval_due")
                )
                row["status"] = overall
                row["refresh_status"] = s_r
                row["eval_status"] = s_e

                # D-day 계산
                for key, due_key in [("refresh_days_left", "next_refresher_due"),
                                     ("eval_days_left", "next_eval_due")]:
                    due_str = row.get(due_key)
                    if due_str:
                        try:
                            due = datetime.datetime.strptime(due_str, "%Y-%m-%d").date()
                            row[key] = (due - today).days
                        except Exception:
                            row[key] = None
                    else:
                        row[key] = None

            self.send_json_response(rows)
            return

        elif path == "/api/auditors/alerts":
            """만료 6개월 이내(교육 또는 평가) 심사원 목록 반환"""
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM auditors ORDER BY id ASC")
            rows = [dict(r) for r in c.fetchall()]
            conn.close()

            today = datetime.date.today()
            warn_days = 180
            alerts = []
            for row in rows:
                overall, s_r, s_e = _auditor_status(
                    row.get("next_refresher_due"),
                    row.get("next_eval_due")
                )
                messages = []
                if s_r in ("임박", "만료"):
                    due_str = row.get("next_refresher_due", "")
                    label = "만료" if s_r == "만료" else "만료 6개월 이내"
                    messages.append(f"보수교육 {label} (만료일: {due_str})")                
                if s_e in ("임박", "만료"):
                    due_str = row.get("next_eval_due", "")
                    label = "만료" if s_e == "만료" else "만료 6개월 이내"
                    messages.append(f"정기평가 {label} (만료일: {due_str})")
                if messages:
                    alerts.append({
                        "id": row["id"],
                        "name_kr": row["name_kr"],
                        "name_en": row["name_en"],
                        "department": row["department"],
                        "employee_id": row["employee_id"],
                        "status": overall,
                        "refresh_status": s_r,
                        "eval_status": s_e,
                        "next_refresher_due": row.get("next_refresher_due"),
                        "next_eval_due": row.get("next_eval_due"),
                        "messages": messages
                    })
            self.send_json_response({"alerts": alerts, "count": len(alerts)})
            return

        # ── 인증 및 사용자 정보 API ──────────────────────────────────
        elif path == "/api/auth/me":
            user = self.get_current_user()
            if user:
                self.send_json_response({"authenticated": True, "user": user})
            else:
                self.send_json_response({"authenticated": False, "user": None})
            return

        elif path == "/api/users":
            user = self.get_current_user()
            if not user or user.get("role") != "admin":
                self.send_json_response({"detail": "관리자 권한이 필요합니다."}, 403)
                return
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("""
                SELECT u.id, u.username, u.name, u.role, u.employee_id, u.auditor_id, u.created_at,
                       a.department, a.qualification, a.cert_number
                FROM users u
                LEFT JOIN auditors a ON u.auditor_id = a.id
                ORDER BY CASE WHEN u.role = 'admin' THEN 0 ELSE 1 END, u.id ASC
            """)
            users = [dict(r) for r in c.fetchall()]
            conn.close()
            self.send_json_response(users)
            return

        # ── 품질심사 체크리스트(설문형 점검표) & 엑셀 다운로드 API ───────────
        elif path == "/api/checklists/templates":
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("""
                SELECT t.*,
                       (SELECT COUNT(*) FROM checklist_template_items i WHERE i.template_id = t.id) as item_count,
                       (SELECT COUNT(*) FROM checklist_sessions s WHERE s.template_id = t.id) as session_count
                FROM checklist_templates t
                ORDER BY t.code ASC
            """)
            templates = []
            for r in c.fetchall():
                d = dict(r)
                d["has_excel"] = bool(d.get("excel_path") and os.path.exists(d["excel_path"]))
                d["excel_filename"] = os.path.basename(d["excel_path"]) if d.get("excel_path") else ""
                templates.append(d)
            conn.close()
            self.send_json_response(templates)
            return

        elif path == "/api/checklists/sessions":
            year = query_params.get("year", [None])[0]
            target_id = query_params.get("target_id", [None])[0]
            conn = get_db_connection()
            c = conn.cursor()
            sql = """
                SELECT s.*,
                       t.station_name, t.category as target_category, t.operation_status,
                       tpl.code as template_code, tpl.title as template_title, tpl.revision as template_revision,
                       (SELECT COUNT(*) FROM checklist_template_items i WHERE i.template_id = s.template_id) as total_items
                FROM checklist_sessions s
                JOIN audit_targets t ON s.target_id = t.id
                JOIN checklist_templates tpl ON s.template_id = tpl.id
                WHERE 1=1
            """
            params = []
            if year:
                sql += " AND s.audit_year = ?"
                params.append(int(year))
            if target_id:
                sql += " AND s.target_id = ?"
                params.append(int(target_id))
            sql += " ORDER BY s.updated_at DESC, s.id DESC"
            c.execute(sql, tuple(params))
            rows = []
            for r in c.fetchall():
                d = dict(r)
                try:
                    resp = json.loads(d.get("responses_json") or "{}")
                except Exception:
                    resp = {}
                s_cnt = sum(1 for v in resp.values() if isinstance(v, dict) and v.get("result") == "S")
                us_cnt = sum(1 for v in resp.values() if isinstance(v, dict) and v.get("result") == "U/S")
                na_cnt = sum(1 for v in resp.values() if isinstance(v, dict) and v.get("result") == "N/A")
                d["s_count"] = s_cnt
                d["us_count"] = us_cnt
                d["na_count"] = na_cnt
                d["answered_count"] = s_cnt + us_cnt + na_cnt
                rows.append(d)
            conn.close()
            self.send_json_response(rows)
            return

        elif path == "/api/checklists/session/load":
            target_id = int(query_params.get("target_id", [0])[0])
            year = int(query_params.get("year", [2026])[0])
            req_tpl_code = query_params.get("template_code", [None])[0]
            session_id = query_params.get("session_id", [None])[0]

            conn = get_db_connection()
            c = conn.cursor()

            session_row = None
            if session_id:
                c.execute("SELECT * FROM checklist_sessions WHERE id = ?", (int(session_id),))
                session_row = c.fetchone()
                if session_row:
                    target_id = session_row["target_id"]
                    year = session_row["audit_year"]

            c.execute("SELECT * FROM audit_targets WHERE id = ?", (target_id,))
            target = c.fetchone()
            if not target:
                conn.close()
                self.send_json_response({"detail": "심사 대상을 찾을 수 없습니다."}, 404)
                return
            target_dict = dict(target)

            # 매칭되는 기본 점검표 코드 결정
            default_code = req_tpl_code or resolve_default_template_code(target_dict["station_name"], target_dict["category"])

            if not session_row and not req_tpl_code:
                c.execute("""
                    SELECT * FROM checklist_sessions
                    WHERE target_id = ? AND audit_year = ?
                    ORDER BY updated_at DESC LIMIT 1
                """, (target_id, year))
                session_row = c.fetchone()

            if session_row and not req_tpl_code:
                c.execute("SELECT * FROM checklist_templates WHERE id = ?", (session_row["template_id"],))
                tpl_row = c.fetchone()
            else:
                c.execute("SELECT * FROM checklist_templates WHERE code = ?", (default_code,))
                tpl_row = c.fetchone()
                if not tpl_row:
                    c.execute("SELECT * FROM checklist_templates ORDER BY id ASC LIMIT 1")
                    tpl_row = c.fetchone()

            tpl_dict = dict(tpl_row) if tpl_row else None
            items = []
            fallback_used = False
            if tpl_dict:
                c.execute("""
                    SELECT * FROM checklist_template_items
                    WHERE template_id = ?
                    ORDER BY excel_row ASC, seq_no ASC, id ASC
                """, (tpl_dict["id"],))
                items = [dict(r) for r in c.fetchall()]
                # 아직 해당 양식의 엑셀 파일이 등록되지 않아 문항이 0개인 경우, 예시 양식(TW-MNT-005 등 문항이 있는 템플릿) 문항을 안내와 함께 로드
                if len(items) == 0:
                    c.execute("""
                        SELECT tpl.* FROM checklist_templates tpl
                        WHERE EXISTS (SELECT 1 FROM checklist_template_items i WHERE i.template_id = tpl.id)
                        ORDER BY CASE WHEN tpl.code = 'TW-MNT-005' THEN 0 ELSE 1 END, tpl.id ASC
                        LIMIT 1
                    """)
                    fb_tpl = c.fetchone()
                    if fb_tpl:
                        c.execute("""
                            SELECT * FROM checklist_template_items
                            WHERE template_id = ?
                            ORDER BY excel_row ASC, seq_no ASC, id ASC
                        """, (fb_tpl["id"],))
                        items = [dict(r) for r in c.fetchall()]
                        fallback_used = True
                        tpl_dict["fallback_from_code"] = fb_tpl["code"]
                        tpl_dict["fallback_from_title"] = fb_tpl["title"]

            # 해당 연도 스케줄 정보(심사일자, 담당 심사원) 자동 채움 참조
            sched_map = generate_schedule_for_target_api(target_id, start_year=min(2026, year), end_year=max(2026, year))
            yr_sched = sched_map.get(year) or {}

            if session_row:
                sess_dict = dict(session_row)
                try:
                    sess_dict["responses"] = json.loads(sess_dict.get("responses_json") or "{}")
                except Exception:
                    sess_dict["responses"] = {}
            else:
                short_yr = str(year)[-2:]
                num_suffix = re.sub(r'\D', '', (tpl_dict["code"] if tpl_dict else "001")) or "001"
                sess_dict = {
                    "id": None,
                    "template_id": tpl_dict["id"] if tpl_dict else 1,
                    "target_id": target_id,
                    "audit_year": year,
                    "audit_no": f"{short_yr}-QA-{int(num_suffix):03d}",
                    "audit_date": yr_sched.get("scheduled_date") or datetime.date.today().strftime("%Y-%m-%d"),
                    "auditor": yr_sched.get("auditor") or "",
                    "audit_purpose": "Schedule",
                    "audit_purpose_other": "",
                    "auditee_team": target_dict["station_name"],
                    "auditee_coordinator": "",
                    "auditee_title": "",
                    "auditee_phone": "",
                    "remark": yr_sched.get("remarks") or "",
                    "status": "작성중",
                    "responses": {}
                }

            conn.close()
            self.send_json_response({
                "target": target_dict,
                "template": tpl_dict,
                "default_template_code": default_code,
                "fallback_used": fallback_used,
                "items": items,
                "session": sess_dict
            })
            return

        elif path.startswith("/api/checklists/session/") and path.endswith("/export"):
            parts = path.strip("/").split("/")
            try:
                session_id = int(parts[3])
            except (IndexError, ValueError):
                self.send_json_response({"detail": "잘못된 세션 ID입니다."}, 400)
                return

            conn = get_db_connection()
            c = conn.cursor()
            c.execute("""
                SELECT s.*, t.station_name, t.category as target_category,
                       tpl.code as tpl_code, tpl.title as tpl_title, tpl.revision as tpl_rev,
                       tpl.excel_path as tpl_excel_path, tpl.header_title as tpl_header_title
                FROM checklist_sessions s
                JOIN audit_targets t ON s.target_id = t.id
                JOIN checklist_templates tpl ON s.template_id = tpl.id
                WHERE s.id = ?
            """, (session_id,))
            sess = c.fetchone()
            if not sess:
                conn.close()
                self.send_json_response({"detail": "저장된 체크리스트 세션을 찾을 수 없습니다."}, 404)
                return
            sess_dict = dict(sess)

            c.execute("""
                SELECT * FROM checklist_template_items
                WHERE template_id = ?
                ORDER BY excel_row ASC, seq_no ASC, id ASC
            """, (sess_dict["template_id"],))
            items = [dict(r) for r in c.fetchall()]

            # 만약 해당 템플릿에 직접 등록된 문항이 없어 기본 양식(TW-MNT-005)으로 작성된 경우 폴백
            excel_path = sess_dict.get("tpl_excel_path") or ""
            if not items or not excel_path or not os.path.exists(excel_path):
                c.execute("SELECT * FROM checklist_templates WHERE code = 'TW-MNT-005' LIMIT 1")
                fb = c.fetchone()
                if fb:
                    if not excel_path or not os.path.exists(excel_path):
                        excel_path = fb["excel_path"]
                    if not items:
                        c.execute("SELECT * FROM checklist_template_items WHERE template_id = ? ORDER BY excel_row ASC", (fb["id"],))
                        items = [dict(r) for r in c.fetchall()]
            conn.close()

            if not excel_path or not os.path.exists(excel_path):
                self.send_json_response({"detail": "원본 점검표 엑셀 파일을 찾을 수 없습니다."}, 404)
                return

            try:
                 responses = json.loads(sess_dict.get("responses_json") or "{}")
            except Exception:
                responses = {}

            # 원본 엑셀 양식을 그대로 로드하여 셀 스타일/병합/서식 100% 보존
            wb = openpyxl.load_workbook(excel_path)
            ws = wb["CheckList"] if "CheckList" in wb.sheetnames else wb.active

            # 상단 심사 기본정보 기입 (병합 셀의 좌상단 셀에만 값을 넣어 양식 깨짐 방지)
            ws["A4"].value = sess_dict.get("audit_no") or "YY-QA-XXX"
            ws["E4"].value = sess_dict.get("audit_date") or ""
            ws["I4"].value = sess_dict.get("auditor") or ""

            purpose = sess_dict.get("audit_purpose") or "Schedule"
            purpose_other = sess_dict.get("audit_purpose_other") or "                            "
            ws["E6"].value = " ■ Schedule" if purpose == "Schedule" else " □ Schedule"
            ws["G6"].value = " ■ Unscheduled" if purpose == "Unscheduled" else " □ Unscheduled"
            ws["K6"].value = f"■ Others({purpose_other})" if purpose == "Others" else "□ Others(                            )"

            ws["A9"].value = sess_dict.get("auditee_team") or sess_dict.get("station_name") or ""
            ws["D9"].value = sess_dict.get("auditee_coordinator") or ""
            ws["E9"].value = sess_dict.get("auditee_title") or ""
            ws["I9"].value = sess_dict.get("auditee_phone") or ""
            ws["A14"].value = sess_dict.get("remark") or ""

            # 각 문항별 S(7열), U/S(8열), N/A(9열), N/O(10열), OBS(11열)에 선택 항목은 'Y', 나머지는 'N' 표기 + Comments(12열)
            for it in items:
                r = it.get("excel_row")
                if not r or r < 16:
                    continue
                ans = responses.get(str(it["id"])) or responses.get(it["item_no"]) or responses.get(str(it.get("seq_no"))) or {}
                res_val = ans.get("result") or ans.get("choice") or ""
                comment_val = ans.get("comment", "")

                ws.cell(r, 7).value = "Y" if res_val == "S" else "N"
                ws.cell(r, 8).value = "Y" if res_val == "U/S" else "N"
                ws.cell(r, 9).value = "Y" if res_val == "N/A" else "N"
                ws.cell(r, 10).value = "N"
                ws.cell(r, 11).value = "N"
                ws.cell(r, 12).value = comment_val if comment_val else None

            buf = io.BytesIO()
            wb.save(buf)
            excel_bytes = buf.getvalue()

            rev_tag = f" ({sess_dict['tpl_rev']})" if sess_dict.get("tpl_rev") else ""
            safe_station = re.sub(r'[\\/:*?"<>|]', '_', sess_dict.get("station_name") or "")
            out_filename = f"({sess_dict['tpl_code']}) {safe_station} 품질심사 점검표{rev_tag}_{sess_dict.get('audit_date') or sess_dict['audit_year']}.xlsx"
            encoded_fname = urllib.parse.quote(out_filename)

            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{encoded_fname}")
            self.send_header("Content-Length", str(len(excel_bytes)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(excel_bytes)
            return

        elif path == "/api/plan/export":
            plan_path = os.path.join(BASE_DIR, "2027년 정비부문 품질심사 계획표 (R.0).xlsx")
            if not os.path.exists(plan_path):
                alt_plan = os.path.join(CHECKLIST_DIR, "2027년 정비부문 품질심사 계획표 (R.0).xlsx")
                if os.path.exists(alt_plan):
                    plan_path = alt_plan
            if not os.path.exists(plan_path):
                self.send_json_response({"detail": "계획표 엑셀 파일을 찾을 수 없습니다."}, 404)
                return
            with open(plan_path, "rb") as f:
                data_bytes = f.read()
            encoded_fname = urllib.parse.quote("2027년 정비부문 품질심사 계획표 (R.0).xlsx")
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{encoded_fname}")
            self.send_header("Content-Length", str(len(data_bytes)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data_bytes)
            return

        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))

        # 4. 수동 입력 시 인터벌 재계산 (동적 롤링 로직)
        if path == "/api/history/update":
            target_id = int(data["target_id"])
            year = int(data["year"])
            audit_type = data["audit_type"]
            status = data["status"]
            scheduled_date = data["scheduled_date"]
            auditor = data.get("auditor", "")
            remarks = data.get("remarks", "")
            record_id = data.get("id")

            # Validate date
            try:
                dt = datetime.datetime.strptime(scheduled_date, "%Y-%m-%d")
                if dt.year != year:
                    self.send_json_response({"detail": "예정일 연도가 일치하지 않습니다."}, 400)
                    return
            except ValueError:
                self.send_json_response({"detail": "날짜 형식이 올바르지 않습니다. (YYYY-MM-DD)"}, 400)
                return

            conn = get_db_connection()
            cursor = conn.cursor()

            if record_id:
                cursor.execute("""
                    UPDATE audit_history 
                    SET scheduled_date = ?, auditor = ?, status = ?, remarks = ?, audit_type = ?
                    WHERE id = ?
                """, (scheduled_date, auditor, status, remarks, audit_type, record_id))
            else:
                cursor.execute("""
                    SELECT id FROM audit_history WHERE target_id = ? AND year = ?
                """, (target_id, year))
                existing = cursor.fetchone()
                
                if existing:
                    cursor.execute("""
                        UPDATE audit_history 
                        SET scheduled_date = ?, auditor = ?, status = ?, remarks = ?, audit_type = ?
                        WHERE id = ?
                    """, (scheduled_date, auditor, status, remarks, audit_type, existing["id"]))
                else:
                    cursor.execute("""
                        INSERT INTO audit_history (target_id, year, audit_type, status, scheduled_date, auditor, remarks)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (target_id, year, audit_type, status, scheduled_date, auditor, remarks))

            # 해당 연도 이후의 임의 수동 계획 중 롤오버 충돌 방지를 위해 자동 계획 재계산이 전파됨
            conn.commit()
            conn.close()
            self.send_json_response({"status": "success", "message": f"{year}년 {audit_type}심사 계획이 저장되었으며, 이후 2026~2030년 인터벌이 동적으로 재계산(Roll-over)되었습니다."})
            return

        elif path == "/api/event/add":
            target_id = int(data["target_id"])
            year = int(data["year"])
            detail = data["detail"]

            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO schedule_events (target_id, event_year, event_type, detail)
                VALUES (?, ?, 'FLEET_ADDED', ?)
            """, (target_id, year, detail))

            # 이벤트 등록 시 해당 연도를 간접심사(◎)로 저장하여 이후 2년 교차 롤링 유도
            cursor.execute("""
                SELECT id FROM audit_history WHERE target_id = ? AND year = ?
            """, (target_id, year))
            existing = cursor.fetchone()
            
            scheduled_date = f"{year}-06-01"
            if existing:
                cursor.execute("""
                    UPDATE audit_history 
                    SET audit_type = '간접', is_event = 1, event_detail = ?, scheduled_date = ?
                    WHERE id = ?
                """, (detail, scheduled_date, existing["id"]))
            else:
                cursor.execute("""
                    INSERT INTO audit_history (target_id, year, audit_type, status, is_event, event_detail, scheduled_date, remarks)
                    VALUES (?, ?, '간접', '계획', 1, ?, ?, ?)
                """, (target_id, year, detail, scheduled_date, f"이벤트: {detail}"))

            conn.commit()
            conn.close()
            self.send_json_response({"status": "success", "message": "이벤트가 등록되었으며 이후 2년 주기 일정이 자동 롤오버(Reset & Roll-over)되었습니다."})
            return

        elif path == "/api/target/add":
            category = data["category"]
            station_name = data["station_name"]
            operation_status = data["operation_status"]
            base_interval = int(data.get("base_interval", 2))
            aircraft_types = data.get("aircraft_types", "")
            engine_types = data.get("engine_types", "")
            
            first_audit_type = data.get("first_audit_type", "직접")
            first_scheduled_date = data.get("first_scheduled_date", "2026-06-01")
            first_auditor = data.get("first_auditor", "")
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO audit_targets (category, operation_status, station_name, base_interval, aircraft_types, engine_types)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (category, operation_status, station_name, base_interval, aircraft_types, engine_types))
            target_id = cursor.lastrowid
            
            if operation_status == "운항":
                cursor.execute("""
                    INSERT INTO audit_history (target_id, year, audit_type, status, scheduled_date, auditor, remarks)
                    VALUES (?, 2026, ?, '계획', ?, ?, '최초 신규 등록')
                """, (target_id, first_audit_type, first_scheduled_date, first_auditor))
            
            conn.commit()
            conn.close()
            self.send_json_response({"status": "success", "message": "신규 심사 대상이 등록되었습니다."})
            return

        elif path == "/api/target/update":
            target_id = int(data["id"])
            category = data["category"]
            station_name = data["station_name"]
            new_op_status = data["operation_status"]
            base_interval = int(data.get("base_interval", 2))
            aircraft_types = data.get("aircraft_types", "")
            engine_types = data.get("engine_types", "")
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 이전 상태 확인
            cursor.execute("SELECT operation_status FROM audit_targets WHERE id = ?", (target_id,))
            old_row = cursor.fetchone()
            old_op_status = old_row["operation_status"] if old_row else "운항"
            
            cursor.execute("""
                UPDATE audit_targets 
                SET category = ?, station_name = ?, operation_status = ?, base_interval = ?,
                    aircraft_types = ?, engine_types = ?
                WHERE id = ?
            """, (category, station_name, new_op_status, base_interval, aircraft_types, engine_types, target_id))
            
            # 3. 비운항 -> 운항으로 변경 시 과거/미래 이력이 전혀 없는 경우에만 최초 직접심사 스케줄링 생성
            if old_op_status == "비운항" and new_op_status == "운항":
                cursor.execute("""
                    SELECT id FROM audit_history WHERE target_id = ?
                """, (target_id,))
                any_histories = cursor.fetchall()
                if not any_histories:
                    cursor.execute("""
                        INSERT INTO audit_history (target_id, year, audit_type, status, scheduled_date, auditor, remarks)
                        VALUES (?, 2026, '직접', '계획', '2026-06-01', '', '운항 재개 신규 최초 직접심사')
                    """, (target_id,))
            
            conn.commit()
            conn.close()
            self.send_json_response({"status": "success", "message": "심사 대상 정보가 성공적으로 수정되었습니다."})
            return

        # ── 심사원 CRUD ────────────────────────────────────────────
        elif path == "/api/auditor/add":
            name_kr = data.get("name_kr", "").strip()
            if not name_kr:
                self.send_json_response({"detail": "심사원명(한글)은 필수입니다."}, 400)
                return

            init_train = data.get("initial_training_date") or None
            last_refresh = data.get("last_refresher_date") or None
            init_eval = data.get("initial_eval_date") or None
            last_eval = data.get("last_eval_date") or None

            base_refresh = last_refresh if last_refresh else init_train
            next_refresh = _add_months(base_refresh, 24)
            base_eval = last_eval if last_eval else init_eval
            next_eval = _add_months(base_eval, 24)

            conn = get_db_connection()
            c = conn.cursor()
            try:
                c.execute("""
                    INSERT INTO auditors
                    (name_kr, name_en, department, employee_id, contact, qualification, cert_number,
                     initial_training_date, last_refresher_date, next_refresher_due,
                     initial_eval_date, last_eval_date, next_eval_due, remarks)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    name_kr, data.get("name_en", ""), data.get("department", ""),
                    data.get("employee_id", "") or None, data.get("contact", ""),
                    data.get("qualification", ""), data.get("cert_number", ""),
                    init_train, last_refresh, next_refresh,
                    init_eval, last_eval, next_eval,
                    data.get("remarks", "")
                ))
                conn.commit()
                self.send_json_response({"status": "success", "message": "심사원이 등록되었습니다."})
            except sqlite3.IntegrityError:
                self.send_json_response({"detail": "동일한 사번의 심사원이 이미 존재합니다."}, 400)
            finally:
                conn.close()
            return

        elif path == "/api/auditor/update":
            auditor_id = int(data["id"])
            init_train = data.get("initial_training_date") or None
            last_refresh = data.get("last_refresher_date") or None
            init_eval = data.get("initial_eval_date") or None
            last_eval = data.get("last_eval_date") or None

            base_refresh = last_refresh if last_refresh else init_train
            next_refresh = _add_months(base_refresh, 24)
            base_eval = last_eval if last_eval else init_eval
            next_eval = _add_months(base_eval, 24)

            conn = get_db_connection()
            c = conn.cursor()
            c.execute("""
                UPDATE auditors SET
                    name_kr = ?, name_en = ?, department = ?, employee_id = ?,
                    contact = ?, qualification = ?, cert_number = ?,
                    initial_training_date = ?, last_refresher_date = ?, next_refresher_due = ?,
                    initial_eval_date = ?, last_eval_date = ?, next_eval_due = ?,
                    remarks = ?,
                    updated_at = datetime('now','localtime')
                WHERE id = ?
            """, (
                data.get("name_kr", ""), data.get("name_en", ""),
                data.get("department", ""), data.get("employee_id", "") or None,
                data.get("contact", ""), data.get("qualification", ""),
                data.get("cert_number", ""),
                init_train, last_refresh, next_refresh,
                init_eval, last_eval, next_eval,
                data.get("remarks", ""), auditor_id
            ))
            conn.commit()
            conn.close()
            self.send_json_response({"status": "success", "message": "심사원 정보가 수정되었습니다."})
            return

        elif path == "/api/auditor/delete":
            auditor_id = int(data["id"])
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("DELETE FROM users WHERE auditor_id = ? AND role != 'admin'", (auditor_id,))
            c.execute("DELETE FROM auditors WHERE id = ?", (auditor_id,))
            conn.commit()
            conn.close()
            self.send_json_response({"status": "success", "message": "심사원이 삭제되었습니다."})
            return

        elif path == "/api/target/delete":
            target_id = int(data["id"])
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM audit_targets WHERE id = ?", (target_id,))
            cursor.execute("DELETE FROM audit_history WHERE target_id = ?", (target_id,))
            cursor.execute("DELETE FROM schedule_events WHERE target_id = ?", (target_id,))
            
            conn.commit()
            conn.close()
            self.send_json_response({"status": "success", "message": "심사 대상 및 연결된 모든 데이터가 삭제되었습니다."})
            return

        # ── 인증 및 계정 관리 API ──────────────────────────────────
        elif path == "/api/auth/login":
            username = data.get("username", "").strip()
            password = data.get("password", "").strip()
            if not username or not password:
                self.send_json_response({"detail": "아이디(사번)와 비밀번호를 입력해주세요."}, 400)
                return
            
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("""
                SELECT u.id, u.username, u.password, u.name, u.role, u.employee_id, u.auditor_id,
                       a.department, a.qualification, a.cert_number
                FROM users u
                LEFT JOIN auditors a ON u.auditor_id = a.id
                WHERE u.username = ?
            """, (username,))
            user_row = c.fetchone()
            conn.close()
            
            if not user_row or user_row["password"] != password:
                self.send_json_response({"detail": "아이디 또는 비밀번호가 일치하지 않습니다."}, 401)
                return
            
            user_info = {
                "id": user_row["id"],
                "username": user_row["username"],
                "name": user_row["name"],
                "role": user_row["role"],
                "employee_id": user_row["employee_id"],
                "auditor_id": user_row["auditor_id"],
                "department": user_row["department"] or "",
                "qualification": user_row["qualification"] or "",
                "cert_number": user_row["cert_number"] or ""
            }
            token = secrets.token_hex(24)
            ACTIVE_SESSIONS[token] = user_info
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Set-Cookie', f'session_token={token}; Path=/; HttpOnly; SameSite=Lax')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "success",
                "token": token,
                "user": user_info
            }, ensure_ascii=False).encode('utf-8'))
            return

        elif path == "/api/auth/logout":
            auth_header = self.headers.get('Authorization', '')
            token = auth_header[7:].strip() if auth_header.startswith('Bearer ') else None
            if not token:
                cookie_header = self.headers.get('Cookie', '')
                for cookie in cookie_header.split(';'):
                    if 'session_token=' in cookie:
                        token = cookie.split('session_token=')[1].strip()
                        break
            if token and token in ACTIVE_SESSIONS:
                del ACTIVE_SESSIONS[token]
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Set-Cookie', 'session_token=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "message": "로그아웃 되었습니다."}, ensure_ascii=False).encode('utf-8'))
            return

        elif path == "/api/auth/change_password":
            user = self.get_current_user()
            if not user:
                self.send_json_response({"detail": "로그인이 필요합니다."}, 401)
                return
            old_pw = data.get("old_password", "").strip()
            new_pw = data.get("new_password", "").strip()
            if not old_pw or not new_pw:
                self.send_json_response({"detail": "현재 비밀번호와 새 비밀번호를 입력해주세요."}, 400)
                return
            if len(new_pw) < 4:
                self.send_json_response({"detail": "새 비밀번호는 최소 4자 이상이어야 합니다."}, 400)
                return
            
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT password FROM users WHERE id = ?", (user["id"],))
            cur_pw = c.fetchone()
            if not cur_pw or cur_pw["password"] != old_pw:
                conn.close()
                self.send_json_response({"detail": "현재 비밀번호가 일치하지 않습니다."}, 400)
                return
            
            c.execute("UPDATE users SET password = ? WHERE id = ?", (new_pw, user["id"]))
            conn.commit()
            conn.close()
            self.send_json_response({"status": "success", "message": "비밀번호가 성공적으로 변경되었습니다."})
            return

        elif path == "/api/users/reset_password":
            user = self.get_current_user()
            if not user or user.get("role") != "admin":
                self.send_json_response({"detail": "관리자 권한이 필요합니다."}, 403)
                return
            target_user_id = data.get("user_id")
            new_pw = data.get("new_password", "1234").strip()
            if not target_user_id:
                self.send_json_response({"detail": "사용자 ID가 필요합니다."}, 400)
                return
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("UPDATE users SET password = ? WHERE id = ?", (new_pw, target_user_id))
            conn.commit()
            conn.close()
            self.send_json_response({"status": "success", "message": f"비밀번호가 '{new_pw}'(으)로 초기화되었습니다."})
            return

        elif path == "/api/findings/add":
            user = self.get_current_user()
            target_id = data.get("target_id")
            title = data.get("title", "").strip()
            if not target_id or not title:
                self.send_json_response({"detail": "심사 대상과 제목은 필수 항목입니다."}, 400)
                return

            conn = get_db_connection()
            c = conn.cursor()
            c.execute("""
                INSERT INTO audit_findings (
                    target_id, audit_date, finding_type, category_tag, title, 
                    finding_detail, regulation_ref, root_cause, action_taken, 
                    action_status, due_date, auditor
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                target_id,
                data.get("audit_date") or datetime.date.today().strftime("%Y-%m-%d"),
                data.get("finding_type") or "Finding",
                data.get("category_tag", "").strip(),
                title,
                data.get("finding_detail", "").strip(),
                data.get("regulation_ref", "").strip(),
                data.get("root_cause", "").strip(),
                data.get("action_taken", "").strip(),
                data.get("action_status") or "조치완료",
                data.get("due_date", ""),
                data.get("auditor", "").strip() or (user["name"] if user else "")
            ))
            fid = c.lastrowid
            conn.commit()
            conn.close()
            self.send_json_response({"status": "success", "id": fid, "message": "지적/개선조치 사항이 성공적으로 등록되었습니다."})
            return

        elif path == "/api/findings/update":
            user = self.get_current_user()
            fid = data.get("id")
            if not fid:
                self.send_json_response({"detail": "지적사항 ID가 필요합니다."}, 400)
                return

            conn = get_db_connection()
            c = conn.cursor()
            c.execute("""
                UPDATE audit_findings SET
                    audit_date = ?, finding_type = ?, category_tag = ?, title = ?,
                    finding_detail = ?, regulation_ref = ?, root_cause = ?, action_taken = ?,
                    action_status = ?, due_date = ?, auditor = ?
                WHERE id = ?
            """, (
                data.get("audit_date"),
                data.get("finding_type"),
                data.get("category_tag", ""),
                data.get("title"),
                data.get("finding_detail", ""),
                data.get("regulation_ref", ""),
                data.get("root_cause", ""),
                data.get("action_taken", ""),
                data.get("action_status"),
                data.get("due_date", ""),
                data.get("auditor", ""),
                fid
            ))
            conn.commit()
            conn.close()
            self.send_json_response({"status": "success", "message": "지적사항이 성공적으로 수정되었습니다."})
            return

        elif path == "/api/findings/delete":
            user = self.get_current_user()
            fid = data.get("id")
            if not fid:
                self.send_json_response({"detail": "지적사항 ID가 필요합니다."}, 400)
                return

            conn = get_db_connection()
            c = conn.cursor()
            c.execute("DELETE FROM audit_findings WHERE id = ?", (fid,))
            conn.commit()
            conn.close()
            self.send_json_response({"status": "success", "message": "지적사항이 삭제되었습니다."})
            return

        elif path == "/api/targets/focus-notes":
            user = self.get_current_user()
            target_id = data.get("target_id")
            if not target_id:
                self.send_json_response({"detail": "심사 대상 ID가 필요합니다."}, 400)
                return

            focus_points = data.get("focus_points", "")
            checklist_notes = data.get("checklist_notes", "")
            updater_name = user["name"] if user else "심사원"

            conn = get_db_connection()
            c = conn.cursor()
            c.execute("""
                INSERT INTO audit_focus_notes (target_id, focus_points, checklist_notes, updated_by, updated_at)
                VALUES (?, ?, ?, ?, datetime('now','localtime'))
                ON CONFLICT(target_id) DO UPDATE SET
                    focus_points = excluded.focus_points,
                    checklist_notes = excluded.checklist_notes,
                    updated_by = excluded.updated_by,
                    updated_at = datetime('now','localtime')
            """, (target_id, focus_points, checklist_notes, updater_name))
            conn.commit()
            conn.close()
            self.send_json_response({"status": "success", "message": "사전 심사 착안사항 및 체크리스트가 저장되었습니다."})
            return

        elif path == "/api/findings/import":
            user = self.get_current_user()
            items = data.get("items", [])
            if not items:
                self.send_json_response({"detail": "임포트할 데이터가 없습니다."}, 400)
                return

            conn = get_db_connection()
            c = conn.cursor()
            imported_count = 0
            for item in items:
                target_id = item.get("target_id")
                if not target_id:
                    tname = item.get("target_name")
                    if tname:
                        c.execute("SELECT id FROM audit_targets WHERE station_name = ? OR station_name LIKE ?", (tname, f"%{tname}%"))
                        row = c.fetchone()
                        if row:
                            target_id = row[0]
                if not target_id:
                    continue
                
                title = item.get("title", "").strip()
                if not title:
                    continue

                c.execute("""
                    INSERT INTO audit_findings (
                        target_id, audit_date, finding_type, category_tag, title, 
                        finding_detail, regulation_ref, root_cause, action_taken, 
                        action_status, due_date, auditor
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    target_id,
                    item.get("audit_date") or datetime.date.today().strftime("%Y-%m-%d"),
                    item.get("finding_type") or "Finding",
                    item.get("category_tag", "").strip(),
                    title,
                    item.get("finding_detail", "").strip(),
                    item.get("regulation_ref", "").strip(),
                    item.get("root_cause", "").strip(),
                    item.get("action_taken", "").strip(),
                    item.get("action_status") or "조치완료",
                    item.get("due_date", ""),
                    item.get("auditor", "").strip()
                ))
                imported_count += 1

            conn.commit()
            conn.close()
            self.send_json_response({"status": "success", "count": imported_count, "message": f"{imported_count}건의 지적/개선조치 사항이 일괄 등록되었습니다."})
            return

        # ── 품질심사 체크리스트 저장 / 엑셀 업로드 / 폴더 스캔 API ────────────
        elif path == "/api/checklists/session/save":
            session_id = data.get("id")
            template_id = int(data["template_id"])
            target_id = int(data["target_id"])
            audit_year = int(data.get("audit_year", 2026))
            audit_no = data.get("audit_no", "YY-QA-XXX").strip()
            audit_date = data.get("audit_date", "").strip() or datetime.date.today().strftime("%Y-%m-%d")
            auditor = data.get("auditor", "").strip()
            audit_purpose = data.get("audit_purpose", "Schedule").strip()
            audit_purpose_other = data.get("audit_purpose_other", "").strip()
            auditee_team = data.get("auditee_team", "").strip()
            auditee_coordinator = data.get("auditee_coordinator", "").strip()
            auditee_title = data.get("auditee_title", "").strip()
            auditee_phone = data.get("auditee_phone", "").strip()
            remark = data.get("remark", "").strip()
            status = data.get("status", "작성중").strip()
            responses = data.get("responses", {})
            responses_json = json.dumps(responses, ensure_ascii=False)
            sync_findings = bool(data.get("sync_findings", status == "완료"))

            conn = get_db_connection()
            c = conn.cursor()

            if session_id:
                c.execute("""
                    UPDATE checklist_sessions SET
                        template_id = ?, target_id = ?, audit_year = ?,
                        audit_no = ?, audit_date = ?, auditor = ?,
                        audit_purpose = ?, audit_purpose_other = ?,
                        auditee_team = ?, auditee_coordinator = ?, auditee_title = ?, auditee_phone = ?,
                        remark = ?, status = ?, responses_json = ?,
                        updated_at = datetime('now','localtime')
                    WHERE id = ?
                """, (
                    template_id, target_id, audit_year,
                    audit_no, audit_date, auditor,
                    audit_purpose, audit_purpose_other,
                    auditee_team, auditee_coordinator, auditee_title, auditee_phone,
                    remark, status, responses_json, int(session_id)
                ))
                saved_id = int(session_id)
            else:
                c.execute("""
                    INSERT INTO checklist_sessions (
                        template_id, target_id, audit_year,
                        audit_no, audit_date, auditor,
                        audit_purpose, audit_purpose_other,
                        auditee_team, auditee_coordinator, auditee_title, auditee_phone,
                        remark, status, responses_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    template_id, target_id, audit_year,
                    audit_no, audit_date, auditor,
                    audit_purpose, audit_purpose_other,
                    auditee_team, auditee_coordinator, auditee_title, auditee_phone,
                    remark, status, responses_json
                ))
                saved_id = c.lastrowid

            # U/S(부적합) 항목을 [심사 대상 분석] 지적사항(Finding) DB에 자동 연동
            synced_findings_count = 0
            if sync_findings:
                # 심사완료 시 연간 심사 계획(audit_history) 상태도 '완료'로 자동 업데이트
                if status == "완료":
                    c.execute("""
                        SELECT id FROM audit_history WHERE target_id = ? AND year = ?
                    """, (target_id, audit_year))
                    hist_row = c.fetchone()
                    if hist_row:
                        c.execute("""
                            UPDATE audit_history
                            SET status = '완료', scheduled_date = ?, auditor = ?
                            WHERE id = ?
                        """, (audit_date, auditor, hist_row["id"]))
                    else:
                        c.execute("""
                            INSERT INTO audit_history (target_id, year, audit_type, status, scheduled_date, auditor, remarks)
                            VALUES (?, ?, '직접', '완료', ?, ?, '품질심사 점검표 수행 완료')
                        """, (target_id, audit_year, audit_date, auditor))

                c.execute("SELECT * FROM checklist_template_items WHERE template_id = ?", (template_id,))
                raw_items = [dict(r) for r in c.fetchall()]
                if not raw_items:
                    c.execute("SELECT id FROM checklist_templates WHERE code = 'TW-MNT-005' LIMIT 1")
                    fb = c.fetchone()
                    if fb:
                        c.execute("SELECT * FROM checklist_template_items WHERE template_id = ?", (fb["id"],))
                        raw_items = [dict(r) for r in c.fetchall()]
                item_map = {}
                for r in raw_items:
                    item_map[str(r["id"])] = r
                    if r.get("item_no"):
                        item_map[str(r["item_no"])] = r
                    if r.get("seq_no"):
                        item_map[str(r["seq_no"])] = r

                for item_key, ans in responses.items():
                    if not isinstance(ans, dict):
                        continue
                    res_val = ans.get("result") or ans.get("choice") or ""
                    if res_val != "U/S":
                        continue
                    it = item_map.get(str(item_key))
                    if not it:
                        continue
                    item_no_str = it["item_no"]
                    comment_txt = (ans.get("comment") or "").strip()
                    finding_title = f"[점검표 {item_no_str}] {it['requirement'].splitlines()[0][:80]}"
                    finding_detail = comment_txt if comment_txt else f"점검표 문항({item_no_str}) 부적합(U/S) 판정: {it['requirement']}"
                    refs = [r for r in [it.get("internal_ref"), it.get("external_ref")] if r and r != "-"]
                    reg_ref = " / ".join(refs)

                    # 동일 대상·일자·문항번호 중복 등록 방지
                    c.execute("""
                        SELECT id FROM audit_findings
                        WHERE target_id = ? AND audit_date = ? AND title LIKE ?
                    """, (target_id, audit_date, f"[점검표 {item_no_str}]%"))
                    existing_f = c.fetchone()
                    if existing_f:
                        c.execute("""
                            UPDATE audit_findings
                            SET finding_detail = ?, regulation_ref = ?, auditor = ?
                            WHERE id = ?
                        """, (finding_detail, reg_ref, auditor, existing_f["id"]))
                    else:
                        c.execute("""
                            INSERT INTO audit_findings (
                                target_id, audit_date, finding_type, category_tag,
                                title, finding_detail, regulation_ref, action_status, auditor
                            ) VALUES (?, ?, 'Finding', '체크리스트 부적합(U/S)', ?, ?, ?, '조치중', ?)
                        """, (target_id, audit_date, finding_title, finding_detail, reg_ref, auditor))
                    synced_findings_count += 1

            conn.commit()
            conn.close()
            msg = "체크리스트가 저장되었습니다."
            if sync_findings and synced_findings_count > 0:
                msg += f" (부적합 U/S {synced_findings_count}건이 [심사 대상 분석] 지적사항에 자동 연동되었습니다.)"
            self.send_json_response({
                "status": "success",
                "id": saved_id,
                "synced_findings": synced_findings_count,
                "message": msg
            })
            return

        elif path == "/api/checklists/session/delete":
            sid = int(data["id"])
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("DELETE FROM checklist_sessions WHERE id = ?", (sid,))
            conn.commit()
            conn.close()
            self.send_json_response({"status": "success", "message": "체크리스트 작성 내역이 삭제되었습니다."})
            return

        elif path == "/api/checklists/upload_excel":
            filename = os.path.basename(data.get("filename", "")).strip()
            b64_content = data.get("content_base64", "")
            override_code = data.get("code", "").strip() or None
            override_cat = data.get("category", "").strip() or None
            if not filename or not b64_content:
                self.send_json_response({"detail": "업로드할 엑셀 파일명과 데이터가 필요합니다."}, 400)
                return
            save_path = os.path.join(CHECKLIST_DIR, filename)
            try:
                raw_bytes = base64.b64decode(b64_content)
                with open(save_path, "wb") as f:
                    f.write(raw_bytes)
                parsed = parse_and_import_checklist_excel(save_path, override_code=override_code, override_category=override_cat)
                if not parsed:
                    self.send_json_response({"detail": "엑셀 파일에서 CheckList 시트(Requirement 컬럼)를 찾지 못했습니다. 표준 점검표 양식인지 확인해 주세요."}, 400)
                    return
                self.send_json_response({
                    "status": "success",
                    "template": parsed,
                    "message": f"[{parsed['code']}] {parsed['title']} ({parsed['item_count']}개 문항) 점검표가 성공적으로 등록되었습니다!"
                })
            except Exception as e:
                self.send_json_response({"detail": f"엑셀 파싱 중 오류가 발생했습니다: {str(e)}"}, 500)
            return

        elif path == "/api/checklists/rescan":
            imported = sync_checklist_templates_from_excel()
            self.send_json_response({
                "status": "success",
                "imported": imported,
                "message": f"[품질심사 체크리스트] 폴더 스캔 완료: {len(imported)}개 엑셀 점검표가 동기화되었습니다."
            })
            return

        else:
            self.send_error(404, "Not Found")

def run(server_class=http.server.ThreadingHTTPServer, handler_class=BuiltinWebServer):
    server_address = ('', PORT)
    httpd = server_class(server_address, handler_class)
    print(f"Server running at http://localhost:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()

if __name__ == '__main__':
    run()
