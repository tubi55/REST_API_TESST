"""API 시험이 쓸 서버를 세운다."""

import hashlib
import random
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.adapters import stores
from app.core import config, db, embedder
from app.features.embedding_sync import sync
from tests.api import seed

HEADERS = {"Authorization": "Bearer dev-token", "X-User-Id": "test-user"}

DIM = 8

CHUNK_PAYLOAD = {"section_id": "int", "product_id": "text", "section": "text",
                 "product_name": "text", "text": "text", "section_text": "text"}


# 글자 하나에 벡터 하나. 같은 글이면 같은 벡터고 길이는 1 이다
def vector_of(text):
    seed = int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16)
    dice = random.Random(seed)
    raw = [dice.uniform(-1, 1) for _ in range(DIM)]
    length = sum(x * x for x in raw) ** 0.5
    return [x / length for x in raw]


# 글자에서 늘 같은 벡터를 만드는 가짜 임베딩기
class FakeEmbedder:
    def embed_query(self, text):
        return vector_of(text)

    def embed_documents(self, texts):
        return [vector_of(text) for text in texts]


# 임베딩기가 죽어 있을 때. Ollama 를 내린 것과 같은 상황이다
class BrokenEmbedder:
    def embed_query(self, text):
        raise RuntimeError("임베딩기가 죽었다")

    def embed_documents(self, texts):
        raise RuntimeError("임베딩기가 죽었다")


# 네 벌을 가짜로 채운다. embed.py 가 하는 일인데 모델을 안 올린다
def build_vectors():
    rows = db.query("""
        SELECT chunks.chunk_id, chunks.section_id, chunks.product_id, chunks.section,
               products.name, chunks.text, sections.text
        FROM chunks
        JOIN products ON products.product_id = chunks.product_id
        JOIN sections ON sections.section_id = chunks.section_id
        ORDER BY chunks.chunk_id
    """)
    sync("chunk", [r[0] for r in rows], [r[5] for r in rows], full=True,
         payload_columns=CHUNK_PAYLOAD,
         payloads={"section_id": [r[1] for r in rows],
                   "product_id": [r[2] for r in rows],
                   "section": [r[3] for r in rows],
                   "product_name": [r[4] for r in rows],
                   "text": [r[5] for r in rows],
                   "section_text": [r[6] for r in rows]})

    for kind, sql in (
            ("product", "SELECT product_id, name FROM products ORDER BY product_id"),
            ("customer", "SELECT customer_id, customer_id FROM customers"),
            ("review", "SELECT purchase_id, purchase_id FROM purchases "
                       "WHERE is_holdout = 0 AND review IS NOT NULL AND review != ''")):
        rows = db.query(sql)
        sync(kind, [r[0] for r in rows], [str(r[1]) for r in rows], full=True)


# 진짜 DB 가 쓸 만한가. 파일을 새로 만들지 않고 본다
def _real_db_ready():
    if not Path(config.DB_PATH).exists():
        return False
    return bool(db.one("SELECT name FROM sqlite_master WHERE name = 'products'"))


# 임시 DB 에 붙인 시험용 서버 하나. 시험 전체가 같이 쓴다
@pytest.fixture(scope="session")
def client(tmp_path_factory):
    path = tmp_path_factory.mktemp("api") / "api.db"

    if _real_db_ready():
        source = sqlite3.connect(config.DB_PATH)
        target = sqlite3.connect(path)
        source.backup(target)
        target.close()
        source.close()
    else:
        seed.build(path)

    patch = pytest.MonkeyPatch()
    patch.setattr(db, "DB_PATH", str(path))
    patch.setattr(db._local, "con", None, raising=False)
    patch.setattr(stores, "_store", None)
    patch.setattr(embedder, "warm_up", lambda: None)
    patch.setattr(embedder, "_embeddings", embedder._Metered(FakeEmbedder()))

    assert db.DB_PATH != config.DB_PATH
    build_vectors()

    from app.main import app

    with TestClient(app) as opened:
        opened.headers.update(HEADERS)
        yield opened

    patch.undo()
    db._local.con = None


# 기본 헤더를 뗀 같은 서버. 인증 시험이 헤더를 하나씩 골라 넣는다
@pytest.fixture
def bare(client):
    kept = client.headers.copy()
    client.headers.clear()
    yield client
    client.headers.clear()
    client.headers.update(kept)
