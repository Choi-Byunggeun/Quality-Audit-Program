import base64
import json
import os
import sqlite3
import urllib.error
import urllib.request


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
        self.auth_token = auth_token.strip()
        self.timeout = timeout
        self.row_factory = None

    def _pipeline_execute(self, stmts):
        requests_payload = [{"type": "execute", "stmt": s} for s in stmts]
        requests_payload.append({"type": "close"})
        body = json.dumps({"requests": requests_payload}).encode("utf-8")

        req = urllib.request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.auth_token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="ignore")
            except Exception:
                pass
            raise sqlite3.OperationalError(f"Turso HTTP {e.code}: {err_body}") from e
        except Exception as e:
            raise sqlite3.OperationalError(f"Turso connection error: {e}") from e

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
        """statements: list of (sql, params_tuple_or_None)"""
        stmts = []
        for sql, params in statements:
            stmt = {"sql": sql}
            if params:
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


def get_db_connection(local_db_path: str):
    """환경변수(TURSO_DATABASE_URL, TURSO_AUTH_TOKEN)가 있으면 Turso, 없으면 로컬 SQLite 연결"""
    if is_turso_enabled():
        return TursoConnection(
            os.environ["TURSO_DATABASE_URL"],
            os.environ["TURSO_AUTH_TOKEN"],
        )
    conn = sqlite3.connect(local_db_path)
    conn.row_factory = sqlite3.Row
    return conn
