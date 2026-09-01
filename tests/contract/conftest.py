"""계약 시험이 쓸 저장소를 만들어 준다."""

import sqlite3

import pytest

from app.adapters.stores.sqlite_store import SqliteVectorStore
from app.core import db

PRODUCT_IDS = ["P001", "P002", "P003", "P004"]
CHUNK_ROWS = [("1", "P001"), ("2", "P001"), ("3", "P002"), ("4", "P003")]


# 시험에 쓸 상품 아이디 목록
@pytest.fixture
def products():
    return list(PRODUCT_IDS)


# (조각 아이디, 그 조각이 딸린 상품)
@pytest.fixture
def chunks():
    return list(CHUNK_ROWS)


# 임시 DB 에 붙인 벡터 저장소 하나
@pytest.fixture
def store(tmp_path, monkeypatch):
    path = tmp_path / "contract.db"
    seed = sqlite3.connect(path)
    seed.execute("CREATE TABLE products (product_id TEXT PRIMARY KEY, name TEXT)")
    seed.execute("CREATE TABLE chunks (chunk_id INTEGER PRIMARY KEY, product_id TEXT)")
    seed.executemany("INSERT INTO products VALUES (?, ?)",
                     [(pid, f"상품 {pid}") for pid in PRODUCT_IDS])
    seed.executemany("INSERT INTO chunks VALUES (?, ?)", CHUNK_ROWS)
    seed.commit()
    seed.close()

    monkeypatch.setattr(db, "DB_PATH", str(path))
    previous = getattr(db._local, "con", None)
    db._local.con = None
    try:
        yield SqliteVectorStore()
    finally:
        opened = getattr(db._local, "con", None)
        if opened is not None:
            opened.close()
        db._local.con = previous
