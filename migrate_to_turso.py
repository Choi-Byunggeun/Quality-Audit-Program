import os
import sqlite3
import sys
import db_adapter

LOCAL_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit.db")


def migrate():
    url = os.environ.get("TURSO_DATABASE_URL", "").strip()
    token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
    if not url or not token:
        print("ERROR: TURSO_DATABASE_URL and TURSO_AUTH_TOKEN environment variables are required.")
        sys.exit(1)

    local = sqlite3.connect(LOCAL_DB)
    lc = local.cursor()

    turso = db_adapter.TursoConnection(url, token, timeout=60)

    # 1. 스키마 조회 (sqlite_sequence, sqlite_stat 등 내부 테이블 제외)
    lc.execute("""
        SELECT name, sql FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL
        ORDER BY rowid ASC
    """)
    tables = lc.fetchall()

    print(f"Found {len(tables)} tables in {LOCAL_DB}: {[t[0] for t in tables]}")

    # 외래키 제약 무시 후 기존 테이블 초기화 및 재생성
    setup_stmts = [("PRAGMA foreign_keys = OFF", None)]
    for tname, _ in reversed(tables):
        setup_stmts.append((f'DROP TABLE IF EXISTS "{tname}"', None))
    for tname, ddl in tables:
        setup_stmts.append((ddl, None))
    turso.execute_batch(setup_stmts)
    print("Schema recreated on Turso.")

    # 2. 각 테이블 데이터 배치 이관
    for tname, _ in tables:
        lc.execute(f'SELECT * FROM "{tname}"')
        cols = [d[0] for d in lc.description]
        rows = lc.fetchall()
        if not rows:
            print(f"  - {tname}: 0 rows")
            continue

        placeholders = ", ".join(["?"] * len(cols))
        col_list = ", ".join([f'"{c}"' for c in cols])
        insert_sql = f'INSERT INTO "{tname}" ({col_list}) VALUES ({placeholders})'

        batch_size = 50
        for i in range(0, len(rows), batch_size):
            chunk = rows[i:i + batch_size]
            stmts = [(insert_sql, tuple(r)) for r in chunk]
            turso.execute_batch(stmts)
        print(f"  - {tname}: {len(rows)} rows migrated")

    # 3. 인덱스 등 추가 객체 이관
    lc.execute("""
        SELECT name, sql FROM sqlite_master
        WHERE type = 'index' AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL
    """)
    indexes = lc.fetchall()
    if indexes:
        turso.execute_batch([(sql, None) for _, sql in indexes])
        print(f"Created {len(indexes)} indexes on Turso.")

    # 4. 검증
    tc = turso.cursor()
    for tname, _ in tables:
        lc.execute(f'SELECT COUNT(*) FROM "{tname}"')
        lcnt = lc.fetchone()[0]
        tc.execute(f'SELECT COUNT(*) FROM "{tname}"')
        tcnt = tc.fetchone()[0]
        if lcnt != tcnt:
            print(f"WARNING: Count mismatch for {tname}: local={lcnt}, turso={tcnt}")
    print("Migration completed successfully!")
    local.close()


if __name__ == "__main__":
    migrate()
