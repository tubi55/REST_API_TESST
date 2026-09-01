"""모델 사용 기록을 저장하고 사용자별 사용량을 확인한다."""

# 표를 바꾸는 execute, 넣고 줄 번호를 받는 insert, 읽는 query 를 가져온다.
from app.core.db import execute, insert, query


# 표가 없으면 만든다. 서버가 뜰 때 한 번 부른다
def ensure_table():
    # IF NOT EXISTS 가 있어서 이미 있으면 아무 일도 안 한다.
    execute("""
        CREATE TABLE IF NOT EXISTS usage_log (
            id          INTEGER PRIMARY KEY,
            at          TEXT NOT NULL,
            user_id     TEXT NOT NULL,
            feature     TEXT NOT NULL,
            model       TEXT NOT NULL,
            in_tokens   INTEGER,
            out_tokens  INTEGER,
            seconds     REAL,
            cost_usd    REAL NOT NULL
        )
    """)
    # 사용자와 시각으로 자주 세므로 그 두 컬럼에 색인을 만든다.
    execute("CREATE INDEX IF NOT EXISTS idx_usage_user_at ON usage_log(user_id, at)")


# 쿼터가 남아 있을 때만 한 칸을 잡는다. 잡았으면 그 줄 번호, 다 썼으면 None.
def reserve_log(*, at, user_id, feature, day, quota_features, limit):
    # 셀 기능 개수만큼 IN 절의 '?' 를 만든다.
    marks = ", ".join("?" * len(quota_features))
    # 세는 일과 넣는 일을 SQL 한 문장으로 묶는다. 나눠 하면 그 사이에 끼어들 수 있다.
    return insert(f"""
        INSERT INTO usage_log (at, user_id, feature, model,
                               in_tokens, out_tokens, seconds, cost_usd)
        SELECT ?, ?, ?, '', NULL, NULL, NULL, 0.0
        WHERE (SELECT COUNT(*) FROM usage_log
               WHERE user_id = ? AND at LIKE ? AND feature IN ({marks})) < ?
    """, (at, user_id, feature, user_id, f"{day}%") + tuple(quota_features) + (limit,))


# 잡아 둔 칸에 실제로 얼마가 들었는지 적는다
def settle_log(log_id, *, model, in_tokens, out_tokens, seconds, cost):
    # 미리 잡아 둔 줄 하나만 골라 값을 채운다.
    execute("""
        UPDATE usage_log
        SET model = ?, in_tokens = ?, out_tokens = ?, seconds = ?, cost_usd = ?
        WHERE id = ?
    """, (model, in_tokens, out_tokens, seconds, cost, log_id))


# 사용 기록 한 줄을 넣는다
def insert_log(*, at, user_id, feature, model, in_tokens, out_tokens, seconds, cost):
    # 쿼터를 안 세는 기능은 미리 잡지 않고 여기서 바로 한 줄을 넣는다.
    execute("""
        INSERT INTO usage_log (at, user_id, feature, model, in_tokens, out_tokens,
                               seconds, cost_usd)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (at, user_id, feature, model, in_tokens, out_tokens, seconds, cost))


# 그 날짜에 이 사용자가 그 기능들을 몇 번 썼나. day 는 'YYYY-MM-DD' 다
def count_today(user_id, day, features):
    # 셀 기능 개수만큼 IN 절의 '?' 를 만든다.
    marks = ", ".join("?" * len(features))
    # 몇 줄인지만 세면 되므로 COUNT 를 쓴다.
    return query(
        # 시각이 '2026-08-28T21:03:11' 이라 날짜로 시작하는 줄만 고른다.
        f"SELECT COUNT(*) FROM usage_log "
        # 기능 목록에 든 것만 센다.
        f"WHERE user_id = ? AND at LIKE ? AND feature IN ({marks})",
        # 결과는 줄 하나에 칸 하나라 [0][0] 으로 숫자만 꺼낸다.
        (user_id, f"{day}%") + tuple(features))[0][0]
