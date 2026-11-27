import base64
import http.client
import json
import os
import sqlite3
import threading
import urllib.parse


_tls = threading.local()


def _get_http_conn(scheme: str, host: str, port, timeout: int):
    pool = getattr(_tls, "http_conns", None)
    if pool is None:
        pool = {}
        _tls.http_conns = pool
    key = (scheme, host, port)
    conn = pool.get(key)
    if conn is None:
        if scheme == "http":
            conn = http.client.HTTPConnection(host, port, timeout=timeout)
        else:
            conn = http.client.HTTPSConnection(host, port, timeout=timeout)
        pool[key] = conn
    return conn


def _drop_http_conn(scheme: str, host: str, port):
    pool = getattr(_tls, "http_conns", None)
    if not pool:
        return
    conn = pool.pop((scheme, host, port), None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass


def _normalize_turso_url(url: str) -> str:
    url = (url or "").strip()
    if url.startswith("libsql://"):
        url = "https://" + url[len("libsql://"):]
    elif url.startswith("wss://"):
        url = "https://" + url[len("wss://"):]
    elif url.startswith("ws://"):
        url = "http://" + url[len("ws://"):]
    return url.rstrip("/")


def is_turso_enabled() -> bool:
    return bool(os.environ.get("TURSO_DATABASE_URL", "").strip() and os.environ.get("TURSO_AUTH_TOKEN", "").strip())


def _encode_arg(val):
    if val is None:
        return {"type": "null"}
    if isinstance(val, bool):
        return {"type": "integer", "value": "1" if val else "0"}
    if isinstance(val, int):
        return {"type": "integer", "value": str(val)}
    if isinstance(val, float):
        return {"type": "float", "value": val}
    if isinstance(val, (bytes, bytearray, memoryview)):
        return {"type": "blob", "base64": base64.b64encode(bytes(val)).decode("ascii")}
    return {"type": "text", "value": str(val)}


def _decode_cell(cell):
    ctype = cell.get("type")
    if ctype == "null" or ctype is None:
        return None
    if ctype == "integer":
        return int(cell["value"])
    if ctype == "float":
        return float(cell["value"])
    if ctype == "blob":
        return base64.b64decode(cell.get("base64", ""))
    return cell.get("value", "")


class TursoRow:
    """sqlite3.Row 호환 객체 (인덱스 접근, 컬럼명 접근, dict(row) 변환 지원)"""

    def __init__(self, columns, values):
        self._columns = list(columns)
        self._values = list(values)
        self._map = {col: val for col, val in zip(self._columns, self._values)}

    def keys(self):
        return self._columns

    def get(self, key, default=None):
        return self._map.get(key, default)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        if isinstance(key, slice):
            return self._values[key]
        return self._map[key]

    def __contains__(self, key):
        return key in self._map

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __repr__(self):
        return f"TursoRow({self._map!r})"


class TursoCursor:
    def __init__(self, conn):
        self._conn = conn
        self._rows = []
        self._columns = []
        self._index = 0
        self.lastrowid = None
        self.rowcount = -1

    def execute(self, sql, params=None):
        stmt = {"sql": sql}
        if params:
            if isinstance(params, dict):
                stmt["named_args"] = [
                    {"name": k, "value": _encode_arg(v)} for k, v in params.items()
                ]
            else:
                stmt["args"] = [_encode_arg(v) for v in params]

        result = self._conn._pipeline_execute([stmt])[0]
        self._columns = [c.get("name") for c in result.get("cols", [])]
        raw_rows = result.get("rows", [])
        self._rows = [
            TursoRow(self._columns, [_decode_cell(cell) for cell in r])
            for r in raw_rows
        ]
        self._index = 0
        lid = result.get("last_insert_rowid")
        self.lastrowid = int(lid) if lid is not None else None
        self.rowcount = result.get("affected_row_count", len(self._rows))
        return self

    def fetchone(self):
        if self._index < len(self._rows):
            row = self._rows[self._index]
            self._index += 1
            return row
        return None

    def fetchall(self):
        rows = self._rows[self._index:]
        self._index = len(self._rows)
        return rows

    def close(self):
        self._rows = []


class TursoConnection:
    """Turso Hrana HTTP v2 Pipeline 기반 sqlite3.Connection 호환 래퍼"""

    def __init__(self, url: str, auth_token: str, timeout: int = 20):
        self.base_url = _normalize_turso_url(url)
        self.endpoint = f"{self.base_url}/v2/pipeline"
        parsed = urllib.parse.urlparse(self.endpoint)
        self._scheme = parsed.scheme or "https"
        self._host = parsed.hostname or ""
        self._port = parsed.port
        self._path = parsed.path or "/v2/pipeline"
        self.auth_token = auth_token.strip()
        self.timeout = timeout
        self.row_factory = None

    def _pipeline_execute(self, stmts):
        requests_payload = [{"type": "execute", "stmt": s} for s in stmts]
        requests_payload.append({"type": "close"})
        body = json.dumps({"requests": requests_payload}).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
            "Connection": "keep-alive",
        }

        resp_bytes = None
        status = 0
        for attempt in range(2):
            http_conn = _get_http_conn(self._scheme, self._host, self._port, self.timeout)
            try:
                http_conn.request("POST", self._path, body=body, headers=headers)
                resp = http_conn.getresponse()
                status = resp.status
                resp_bytes = resp.read()
                if resp.will_close:
                    _drop_http_conn(self._scheme, self._host, self._port)
                break
            except (http.client.HTTPException, OSError) as e:
                _drop_http_conn(self._scheme, self._host, self._port)
                if attempt == 1:
                    raise sqlite3.OperationalError(f"Turso connection error: {e}") from e
            except Exception as e:
                _drop_http_conn(self._scheme, self._host, self._port)
                raise sqlite3.OperationalError(f"Turso connection error: {e}") from e

        if status >= 400:
            err_body = (resp_bytes or b"").decode("utf-8", errors="ignore")
            raise sqlite3.OperationalError(f"Turso HTTP {status}: {err_body}")

        data = json.loads((resp_bytes or b"{}").decode("utf-8"))

        results = data.get("results", [])
        parsed = []
        for idx in range(len(stmts)):
            if idx >= len(results):
                raise sqlite3.OperationalError("Turso pipeline returned incomplete results")
            item = results[idx]
            if item.get("type") != "ok":
                err_msg = item.get("error", {}).get("message", str(item))
                raise sqlite3.OperationalError(f"Turso SQL error: {err_msg}")
            parsed.append(item.get("response", {}).get("result", {}))
        return parsed

    def execute_batch(self, statements):
        """statements: list of (sql, params_tuple_dict_or_None)"""
        stmts = []
        for sql, params in statements:
            stmt = {"sql": sql}
            if params:
                if isinstance(params, dict):
                    stmt["named_args"] = [
                        {"name": k, "value": _encode_arg(v)} for k, v in params.items()
                    ]
                else:
                    stmt["args"] = [_encode_arg(v) for v in params]
            stmts.append(stmt)
        if not stmts:
            return []
        return self._pipeline_execute(stmts)

    def cursor(self):
        return TursoCursor(self)

    def commit(self):
        # Hrana HTTP pipeline은 각 execute가 즉시 커밋됨
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def _result_to_rows(result):
    cols = [c.get("name") for c in result.get("cols", [])]
    return [TursoRow(cols, [_decode_cell(cell) for cell in r]) for r in result.get("rows", [])]


def execute_batch_rows(conn, statements):
    """단일 왕복(Turso) 또는 단일 연결(SQLite)로 다수 SQL을 일괄 실행하고 각 쿼리의 행 리스트 반환"""
    if isinstance(conn, TursoConnection):
        return [_result_to_rows(res) for res in conn.execute_batch(statements)]
    results = []
    c = conn.cursor()
    try:
        for sql, params in statements:
            c.execute(sql, params or ())
            results.append(c.fetchall() if c.description else [])
    finally:
        c.close()
    return results


def get_db_connection(local_db_path: str):
    """환경변수(TURSO_DATABASE_URL, TURSO_AUTH_TOKEN)가 있으면 Turso, 없으면 로컬 SQLite 연결"""
    if is_turso_enabled():
        return TursoConnection(
            os.environ["TURSO_DATABASE_URL"],
            os.environ["TURSO_AUTH_TOKEN"],
        )
    conn = sqlite3.connect(local_db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn
