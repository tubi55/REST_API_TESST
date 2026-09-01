"""API 통합 시험. 진짜 앱을 세우고 HTTP 로 부른다."""

import json
import threading

import pytest

from app.api import dependencies
from app.core import db, embedder, usage
from app.features import answering, products, readiness
from app.repositories import get_product_repo
from tests.api.conftest import BrokenEmbedder

product_repo = get_product_repo()

DRAFT = {"name": "시험용 크림", "brand": "시험", "category": "크림", "price": 10000,
         "skinType": "건성", "ingredient": "세라마이드", "concern": "보습",
         "tags": "시험", "description": "API 시험용", "volume": "50ml"}


# 상품 하나를 만들고 시험이 끝나면 지운다
@pytest.fixture
def made(client):
    created = client.post("/api/products", json=DRAFT)
    assert created.status_code == 201
    product_id = created.json()["productId"]
    yield created.json()
    client.delete(f"/api/products/{product_id}")


def test_임베딩이_실패해도_상품_수정이_안_사라진다(client, made, monkeypatch):
    monkeypatch.setattr(embedder, "_embeddings", BrokenEmbedder())

    got = client.patch(f"/api/products/{made['productId']}", json={"price": 22000})

    assert got.status_code == 200
    assert got.json()["price"] == 22000
    assert got.json()["needsEmbedding"] is True

    monkeypatch.undo()
    again = client.patch(f"/api/products/{made['productId']}", json={"price": 22000})
    assert again.json()["needsEmbedding"] is False
    assert again.json()["price"] == 22000


def test_size_상한을_넘기면_422(client):
    assert client.get("/api/products", params={"size": 101}).status_code == 422
    assert client.get("/api/products", params={"size": 0}).status_code == 422
    assert client.get("/api/products", params={"page": -1}).status_code == 422
    assert client.get("/api/products", params={"size": 100}).status_code == 200


def test_번호가_겹치면_다시_뽑는다(client, monkeypatch):
    taken = client.get("/api/products", params={"size": 1, "sort": "productId",
                                                "order": "desc"}).json()
    already = taken["content"][0]["productId"]

    real = product_repo.next_id
    calls = []

    def collide():
        calls.append(1)
        return already if len(calls) == 1 else real()

    monkeypatch.setattr(product_repo, "next_id", collide)
    made = client.post("/api/products", json=DRAFT)

    assert made.status_code == 201
    assert made.json()["productId"] != already
    assert len(calls) == 2
    client.delete(f"/api/products/{made.json()['productId']}")


def test_동시에_만들어도_아이디가_안_겹친다(client):
    made, failed = [], []

    def create():
        try:
            made.append(products.create_product(
                {"name": "동시 시험", "brand": "시험", "category": "크림",
                 "price": 1000, "skin_type": "건성", "ingredient": "",
                 "concern": "", "tags": "", "description": "", "volume": ""})
            ["product_id"])
        except Exception as exc:
            failed.append(exc)

    threads = [threading.Thread(target=create) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert failed == []
    assert len(set(made)) == len(made) == 5
    for product_id in made:
        products.delete_product(product_id)


def test_외래키가_실제로_걸린다(client):
    with pytest.raises(db.IntegrityError):
        db.execute(
            "INSERT INTO purchases (purchase_id, customer_id, product_id, "
            "purchased_at, quantity, rating, review, is_holdout) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("시험-없는상품", "C001", "P없음", "2026-08-28", 1, 5, "", 0))


def test_구매_이력이_있는_상품은_못_지운다(client):
    used = client.get("/api/products/P001")
    assert used.status_code == 200

    gone = client.delete("/api/products/P001")

    assert gone.status_code == 409
    assert gone.json()["detail"]["kind"] == "conflict"
    assert client.get("/api/products/P001").status_code == 200


def test_없는_고객과_상품은_404(client):
    assert client.get("/api/customers/C없음").status_code == 404
    assert client.get("/api/customers/C없음/recommend").status_code == 404
    assert client.get("/api/customers/C없음/similar-reviews").status_code == 404
    assert client.get("/api/products/P없음").status_code == 404
    assert client.delete("/api/products/P없음").status_code == 404


def test_별점과_후기가_비어_있어도_대시보드가_돈다(client):
    customer = client.get("/api/customers").json()[0]["customer_id"]
    db.execute(
        "INSERT INTO purchases (purchase_id, customer_id, product_id, purchased_at, "
        "quantity, rating, review, is_holdout) VALUES (?, ?, ?, ?, ?, NULL, NULL, 0)",
        ("시험-빈후기", customer, "P001", "2026-08-28", 1))
    try:
        got = client.get(f"/api/customers/{customer}")

        assert got.status_code == 200
        empty = [row for row in got.json()["purchases"] if row["rating"] is None]
        assert len(empty) == 1
        assert empty[0]["review"] is None
        assert empty[0]["review_masked"] == ""
    finally:
        db.execute("DELETE FROM purchases WHERE purchase_id = ?", ("시험-빈후기",))


def test_토큰이_없거나_틀리면_401(bare):
    user = {"X-User-Id": "test-user"}

    assert bare.get("/api/usage", headers=user).status_code == 401
    assert bare.get("/api/usage", headers={**user, "Authorization": "Bearer nope"}
                    ).status_code == 401
    assert bare.get("/api/usage", headers={**user, "Authorization": "dev-token"}
                    ).status_code == 401
    assert bare.get("/api/usage", headers={"Authorization": "Bearer dev-token"}
                    ).status_code == 400
    assert bare.get("/health").status_code == 200


def test_스트리밍이_순서를_지킨다(client, monkeypatch):
    monkeypatch.setattr(answering, "stream", lambda *a, **kw: iter(["가", "나"]))

    with client.stream("POST", "/api/ask", json={"question": "배송은 얼마나 걸리나요"}) as got:
        assert got.status_code == 200
        lines = [json.loads(line) for line in got.iter_lines() if line.strip()]

    assert [line["type"] for line in lines] == ["route", "sources", "delta", "delta", "done"]
    assert lines[0]["kind"] == "product"
    assert isinstance(lines[1]["sources"], list)
    assert "".join(line["text"] for line in lines if line["type"] == "delta") == "가나"


def test_쿼터를_동시에_두드려도_상한을_안_넘는다(client, monkeypatch):
    monkeypatch.setattr(usage, "DAILY_QUOTA", 3)
    user = "쿼터-시험"
    got = []

    def grab():
        got.append(usage.reserve(user, "ask"))

    threads = [threading.Thread(target=grab) for _ in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    try:
        assert len([x for x in got if x is not None]) == 3
        assert len([x for x in got if x is None]) == 9
        assert usage.used_today(user) == 3
    finally:
        db.execute("DELETE FROM usage_log WHERE user_id = ?", (user,))


def test_잡아_둔_칸을_채우지_두_번_세지_않는다(client):
    user = "정산-시험"
    try:
        log_id = usage.reserve(user, "ask")

        assert usage.used_today(user) == 1
        usage.settle(log_id, model="gpt-4o-mini", in_tokens=1000, out_tokens=500)
        assert usage.used_today(user) == 1
        row = db.one("SELECT model, in_tokens, cost_usd FROM usage_log WHERE id = ?",
                     (log_id,))
        assert row[0] == "gpt-4o-mini"
        assert row[1] == 1000
        assert row[2] > 0
    finally:
        db.execute("DELETE FROM usage_log WHERE user_id = ?", (user,))


def test_삭제가_중간에_터지면_통째로_되돌아간다(client, made, monkeypatch):
    product_id = made["productId"]
    db.execute("INSERT INTO sections (section_id, product_id, section, text, n_tokens) "
               "VALUES (?, ?, ?, ?, ?)", (990001, product_id, "주의사항", "시험용", 3))

    def blow_up(_product_id):
        raise RuntimeError("여기서 죽는다")

    monkeypatch.setattr(product_repo, "delete", blow_up)

    with pytest.raises(RuntimeError):
        products.delete_product(product_id)

    monkeypatch.undo()
    assert db.one("SELECT COUNT(*) FROM sections WHERE product_id = ?",
                  (product_id,))[0] == 1
    assert client.get(f"/api/products/{product_id}").status_code == 200

    db.execute("DELETE FROM sections WHERE section_id = ?", (990001,))


def test_reindex_는_몇_번을_불러도_같다(client, made, monkeypatch):
    product_id = made["productId"]

    monkeypatch.setattr(embedder, "_embeddings", BrokenEmbedder())
    stale = client.patch(f"/api/products/{product_id}", json={"price": 33000})
    assert stale.json()["needsEmbedding"] is True

    monkeypatch.undo()
    fixed = client.post(f"/api/products/{product_id}/reindex")
    assert fixed.status_code == 200
    assert fixed.json()["needsEmbedding"] is False
    assert fixed.json()["price"] == 33000

    again = client.post(f"/api/products/{product_id}/reindex")
    assert again.status_code == 200
    assert again.json()["needsEmbedding"] is False

    assert client.post("/api/products/P없음/reindex").status_code == 404


def test_쓰기_스위치를_끄면_읽기와_reindex_만_남는다(client, made, monkeypatch):
    monkeypatch.setattr(dependencies, "PRODUCT_WRITE_ENABLED", False)
    product_id = made["productId"]

    assert client.post("/api/products", json=DRAFT).status_code == 405
    assert client.patch(f"/api/products/{product_id}", json={"price": 1}).status_code == 405
    assert client.delete(f"/api/products/{product_id}").status_code == 405

    assert client.get(f"/api/products/{product_id}").status_code == 200
    assert client.post(f"/api/products/{product_id}/reindex").status_code == 200


def test_살아있나와_준비됐나가_다른_질문이다(bare):
    alive = bare.get("/health")
    assert alive.status_code == 200
    assert alive.json()["ok"] is True

    ready = bare.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["ready"] is True
    assert set(ready.json()["checks"]) == {"db", "vectors", "embedder"}
    assert all(ready.json()["checks"].values())


def test_준비가_안_되면_503_이고_이유는_안_샌다(bare, monkeypatch):
    def broken():
        raise RuntimeError("접속 문자열 sqlite:///secret/path.db 가 섞인 오류")

    monkeypatch.setattr(readiness, "_db_ok", broken)
    monkeypatch.setattr(readiness, "CHECKS",
                        (("db", broken), ("vectors", lambda: True),
                         ("embedder", lambda: True)))

    got = bare.get("/ready")

    assert got.status_code == 503
    assert got.json()["ready"] is False
    assert got.json()["checks"]["db"] is False
    assert "secret" not in got.text
    assert bare.get("/health").status_code == 200


def test_스트리밍이_실패해도_예외_글이_안_나간다(client, monkeypatch):
    def blow_up(*a, **kw):
        raise RuntimeError("sqlite:///C:/secret/cosmetic.db 에 붙지 못했다")

    monkeypatch.setattr(answering, "stream", blow_up)

    with client.stream("POST", "/api/ask", json={"question": "배송은 얼마나 걸리나요"}) as got:
        assert got.status_code == 200
        raw = [line for line in got.iter_lines() if line.strip()]

    lines = [json.loads(line) for line in raw]
    kinds = [line["type"] for line in lines]
    assert "error" in kinds
    assert kinds[-1] == "done"

    error = next(line for line in lines if line["type"] == "error")
    assert error["message"] == "답을 만들지 못했다"
    body = "".join(raw)
    assert "sqlite" not in body
    assert "secret" not in body
