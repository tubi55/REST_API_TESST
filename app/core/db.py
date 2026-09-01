"""SQLite 연결을 관리하고 공통 DB 작업 함수를 제공한다."""

# 파이썬에 기본으로 들어 있는 SQLite 도구다.
import sqlite3

# 스레드마다 따로 값을 두기 위해 사용한다.
import threading

# with 문으로 쓸 수 있는 함수를 만들기 위해 사용한다.
from contextlib import contextmanager

# DB 파일 위치를 설정에서 가져온다.
from app.core.config import DB_PATH

# 스레드마다 다른 값을 담는 상자다. 여기에 스레드별 연결을 넣는다.
_local = threading.local()

# 중복 키 같은 제약 위반 오류다. 이 이름으로 다른 파일이 잡을 수 있게 한다.
IntegrityError = sqlite3.IntegrityError


# 이 스레드의 연결. 없으면 만든다
def connection():
    # 이 스레드에 이미 연결이 있는지 본다. 없으면 None 이다.
    con = getattr(_local, "con", None)
    # 아직 없으면 새로 만든다.
    if con is None:
        # check_same_thread=False 는 만든 스레드 밖에서도 쓸 수 있게 한다.
        con = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
        # WAL 은 읽기와 쓰기가 서로를 덜 막게 하는 기록 방식이다.
        con.execute("PRAGMA journal_mode = WAL")
        # 잠겨 있으면 바로 실패하지 않고 5초까지 기다린다.
        con.execute("PRAGMA busy_timeout = 5000")
        # 외래 키 제약을 실제로 지키게 켠다. SQLite 는 기본이 꺼짐이다.
        con.execute("PRAGMA foreign_keys = ON")
        # 다음 호출부터 다시 쓰도록 이 스레드 상자에 넣어 둔다.
        _local.con = con
    # 이 스레드가 쓸 연결을 돌려준다.
    return con


# 여러 줄을 튜플 목록으로 꺼낸다
def query(sql, params=()):
    # fetchall 은 결과를 전부 읽어 목록으로 준다.
    return connection().execute(sql, params).fetchall()


# 한 줄만 꺼낸다. 없으면 None
def one(sql, params=()):
    # fetchone 은 첫 줄 하나만 준다.
    return connection().execute(sql, params).fetchone()


# 컬럼 이름이 붙은 딕셔너리 목록으로 꺼낸다
def dicts(sql, params=()):
    # 커서에는 결과와 함께 컬럼 정보도 들어 있다.
    cur = connection().execute(sql, params)
    # description 의 각 항목 첫 칸이 컬럼 이름이다.
    columns = [c[0] for c in cur.description]
    # zip 으로 이름과 값을 짝지어 줄마다 딕셔너리를 만든다.
    return [dict(zip(columns, row)) for row in cur.fetchall()]


# 지금 이 스레드가 transaction() 안에 있나
def _in_transaction():
    # depth 가 없으면 0 으로 보고, 0보다 크면 묶음 안이다.
    return getattr(_local, "depth", 0) > 0


# 여러 문장을 한 덩어리로 묶는다. 중간에 터지면 통째로 되돌린다
@contextmanager
def transaction():
    # 이 스레드의 연결을 얻는다.
    con = connection()
    # 묶음에 들어갈 때마다 깊이를 하나 올린다. 중첩해서 써도 안전하다.
    _local.depth = getattr(_local, "depth", 0) + 1
    # 여기서 아래 코드가 실행될 자리를 만든다.
    try:
        # with 블록 안의 코드가 여기서 돈다.
        yield
    # 어떤 오류든 잡는다. 중간에 멈춘 채로 두면 안 되기 때문이다.
    except BaseException:
        # 빠져나오므로 깊이를 하나 내린다.
        _local.depth -= 1
        # 가장 바깥 묶음일 때만 실제로 되돌린다.
        if not _in_transaction():
            # 이 묶음에서 바꾼 것을 전부 취소한다.
            con.rollback()
        # 오류는 삼키지 않고 부른 쪽으로 그대로 올린다.
        raise
    # 오류 없이 끝났을 때다.
    else:
        # 빠져나오므로 깊이를 하나 내린다.
        _local.depth -= 1
        # 가장 바깥 묶음일 때만 실제로 저장한다.
        if not _in_transaction():
            # 이 묶음에서 바꾼 것을 한꺼번에 확정한다.
            con.commit()


# INSERT · UPDATE · DELETE 를 하고 커밋한다. 바뀐 줄 수를 돌려준다
def execute(sql, params=()):
    # 이 스레드의 연결을 얻는다.
    con = connection()
    # SQL 을 실행하고 커서를 받는다.
    cur = con.execute(sql, params)
    # 묶음 안이면 바깥에서 한꺼번에 저장하므로 여기서는 안 한다.
    if not _in_transaction():
        # 혼자 도는 문장이면 바로 확정한다.
        con.commit()
    # 실제로 바뀐 줄 수를 돌려준다.
    return cur.rowcount


# INSERT 를 하고 새로 생긴 줄 번호를 돌려준다. 한 줄도 안 들어갔으면 None
def insert(sql, params=()):
    # 이 스레드의 연결을 얻는다.
    con = connection()
    # SQL 을 실행하고 커서를 받는다.
    cur = con.execute(sql, params)
    # 묶음 안이면 바깥에서 한꺼번에 저장한다.
    if not _in_transaction():
        # 혼자 도는 문장이면 바로 확정한다.
        con.commit()
    # 들어간 줄이 있을 때만 새로 생긴 줄 번호를 준다.
    return cur.lastrowid if cur.rowcount else None


# 같은 문장을 여러 값으로 한 번에 실행하고 커밋한다
def executemany(sql, rows):
    # 이 스레드의 연결을 얻는다.
    con = connection()
    # 같은 SQL 에 값 목록을 차례로 넣어 한 번에 처리한다.
    cur = con.executemany(sql, rows)
    # 묶음 안이면 바깥에서 한꺼번에 저장한다.
    if not _in_transaction():
        # 혼자 도는 문장이면 바로 확정한다.
        con.commit()
    # 실제로 바뀐 줄 수를 돌려준다.
    return cur.rowcount
