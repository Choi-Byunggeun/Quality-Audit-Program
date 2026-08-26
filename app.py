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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "audit.db")
STATIC_DIR = os.path.join(BASE_DIR, "static")
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

_ensure_auditors_table()
_ensure_targets_schema()
_ensure_users_table()

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
        for year in range(start_year, end_year + 1):
            if year in existing_histories:
                db_record = existing_histories[year]
                audit_type = db_record["audit_type"] or "직접"
                schedule[year] = {
                    "id": db_record["id"],
                    "target_id": target_id,
                    "year": year,
                    "audit_type": audit_type,
                    "status": db_record["status"],
                    "is_event": db_record["is_event"],
                    "event_detail": db_record["event_detail"],
                    "remarks": db_record["remarks"] or "정기 직접심사",
                    "scheduled_date": db_record["scheduled_date"] or f"{year}-06-01",
                    "auditor": db_record["auditor"] or "",
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
                    "remarks": "연례 정기 직접심사 (매년 1회)",
                    "scheduled_date": f"{year}-06-01",
                    "auditor": "",
                    "symbol": "●"
                }
        return schedule

    # 1 & 4. 일반 항목 (base_interval == 2): 2년 주기 교차 편성 및 수동 입력 동적 롤링 (Reset & Roll-over)
    if last_audit:
        ref_year = last_audit["year"]
        ref_type = last_audit["audit_type"]
    else:
        ref_year, ref_type = None, None
        
    for year in range(start_year, end_year + 1):
        # 4.1 수동 입력된 DB 기록이 있는 경우 -> 해당 입력 시점을 새 기준(Anchor)으로 롤링 리셋
        if year in existing_histories:
            db_record = existing_histories[year]
            a_type = db_record["audit_type"] or ("간접" if ref_type == "직접" else "직접")
            schedule[year] = {
                "id": db_record["id"],
                "target_id": target_id,
                "year": year,
                "audit_type": a_type,
                "status": db_record["status"],
                "is_event": db_record["is_event"],
                "event_detail": db_record["event_detail"],
                "remarks": db_record["remarks"] or "",
                "scheduled_date": db_record["scheduled_date"] or f"{year}-06-01",
                "auditor": db_record["auditor"] or "",
                "symbol": "◎" if a_type == "간접" else "●"
            }
            ref_year = year
            ref_type = a_type
            continue
            
        # 4.2 신규 기종/지점 이벤트 등록이 있는 경우 -> 간접심사 배정 및 롤링 리셋
        if year in events:
            audit_type = "간접"
            detail = events[year]
            scheduled_date = f"{year}-06-01"
            
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
                "auditor": "",
                "symbol": "◎"
            }
            ref_year = year
            ref_type = "간접"
            continue

        # 4.3 자동 인터벌 계산 (2년 교차 롤링)
        if ref_year is not None:
            diff = year - ref_year
            if diff == 2:
                audit_type = "간접" if ref_type == "직접" else "직접"
                symbol = "◎" if audit_type == "간접" else "●"
                scheduled_date = f"{year}-06-01"
                
                schedule[year] = {
                    "id": None,
                    "target_id": target_id,
                    "year": year,
                    "audit_type": audit_type,
                    "status": "계획",
                    "is_event": False,
                    "event_detail": None,
                    "remarks": "2년 주기 정기 심사",
                    "scheduled_date": scheduled_date,
                    "auditor": "",
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
                    "remarks": "2년 주기 정기 심사",
                    "scheduled_date": f"{year}-06-01",
                    "auditor": "",
                    "symbol": symbol
                }
                ref_year = year
                ref_type = audit_type
            else:
                schedule[year] = None
        else:
            # 3. 과거 이력이 없는 신규 운항 대상: 시작 연도에 최초 직접심사(●) 편성
            if year == start_year:
                audit_type = "직접"
                scheduled_date = f"{year}-06-01"
                schedule[year] = {
                    "id": None,
                    "target_id": target_id,
                    "year": year,
                    "audit_type": audit_type,
                    "status": "계획",
                    "is_event": False,
                    "event_detail": None,
                    "remarks": "신규 운항 대상 최초 직접심사",
                    "scheduled_date": scheduled_date,
                    "auditor": "",
                    "symbol": "●"
                }
                ref_year = year
                ref_type = audit_type
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
                # 비운항 제외 스케줄 생성
                scheds = generate_schedule_for_target_api(t["id"], start_year=year, end_year=year)
                val = scheds.get(year)
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
                scheds = generate_schedule_for_target_api(t["id"], start_year=year, end_year=year)
                val = scheds.get(year)
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
                scheds = generate_schedule_for_target_api(t["id"], start_year=year, end_year=year)
                val = scheds.get(year)
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
            
            # 3. 비운항 -> 운항으로 변경 시 즉시 신규 카운팅/최초 직접심사 스케줄링 생성
            if old_op_status == "비운항" and new_op_status == "운항":
                cursor.execute("""
                    SELECT id FROM audit_history WHERE target_id = ? AND year >= 2026
                """, (target_id,))
                future_histories = cursor.fetchall()
                if not future_histories:
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
