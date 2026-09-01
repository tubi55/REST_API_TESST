"""DB 테이블 구조를 현재 코드에 필요한 형태로 맞춘다."""

# 표를 바꾸는 execute 와 한 줄만 읽는 one 을 가져온다.
from app.core.db import execute, one


# 버전 표 자체. 이건 0번이라 여기서 직접 만든다
def ensure_version_table():
    # IF NOT EXISTS 가 있어서 이미 있으면 아무 일도 안 한다.
    execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version    INTEGER PRIMARY KEY,
            name       TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
    """)


# 지금 이 DB 가 어디까지 왔나. 아무것도 안 적혀 있으면 0
def current_version():
    # MAX 는 표가 비어 있어도 줄 하나를 주는데 그 값이 NULL 이다.
    row = one("SELECT MAX(version) FROM schema_version")
    # 그래서 NULL 이면 0 으로 바꾸고, 줄 자체가 없어도 0 으로 본다.
    return (row[0] or 0) if row else 0


# 한 단계를 마쳤다고 적는다. 이미 적혀 있으면 그대로 둔다
def record_version(version, name, at):
    # INSERT OR IGNORE 는 같은 번호가 이미 있으면 조용히 넘어간다.
    execute("INSERT OR IGNORE INTO schema_version (version, name, applied_at) "
            # 값은 SQL 글자에 섞지 않고 '?' 자리로 넘긴다.
            "VALUES (?, ?, ?)", (version, name, at))
