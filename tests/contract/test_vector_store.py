"""벡터 저장소가 지켜야 할 약속. app/domain/ports.py 의 VectorStore 다."""

import pytest

MODEL = "시험용-모델"
DIM = 2

NORTH = [1.0, 0.0]
TILTED = [0.6, 0.8]
EAST = [0.0, 1.0]

VECTORS = {"P001": NORTH, "P002": TILTED, "P003": EAST}


# 표를 새로 만들고 준 벡터를 넣는다. 시험마다 되풀이되는 준비다
def fill(store, kind, rows, *, payloads=None, payload_columns=None):
    ids = list(rows)
    store.recreate(kind, dim=DIM, model=MODEL, payload_columns=payload_columns)
    store.upsert(kind, ids, [rows[i] for i in ids], model=MODEL,
                 hashes=[f"지문-{i}" for i in ids], payloads=payloads)


def test_넣은_순서가_순위를_안_바꾼다(store):
    fill(store, "product", VECTORS)
    forward = store.search("product", NORTH, 3)

    fill(store, "product", dict(reversed(list(VECTORS.items()))))
    backward = store.search("product", NORTH, 3)

    assert [pid for pid, _ in forward] == ["P001", "P002", "P003"]
    assert forward == backward


def test_only_ids_로_좁히면_그_안에서만_나온다(store):
    fill(store, "product", VECTORS)

    found = store.search("product", NORTH, 3, only_ids=["P002", "P003"])

    assert [pid for pid, _ in found] == ["P002", "P003"]


def test_없는_아이디로_좁히면_아무것도_안_나온다(store):
    fill(store, "product", VECTORS)

    assert store.search("product", NORTH, 3, only_ids=["P004"]) == []


def test_점수가_같으면_아이디_순이다(store):
    same = {"P001": NORTH, "P002": NORTH, "P003": NORTH}
    fill(store, "product", same)
    first = store.search("product", NORTH, 2)

    fill(store, "product", dict(reversed(list(same.items()))))
    second = store.search("product", NORTH, 2)

    assert [pid for pid, _ in first] == ["P001", "P002"]
    assert first == second
    assert store.search("product", NORTH, 2) == first


def test_지운_것이_hashes_에서_사라진다(store):
    fill(store, "product", VECTORS)
    assert set(store.hashes("product")) == {"P001", "P002", "P003"}

    store.delete("product", ["P002"])

    assert set(store.hashes("product")) == {"P001", "P003"}
    assert store.has("product", "P002") is False
    assert [pid for pid, _ in store.search("product", NORTH, 3)] == ["P001", "P003"]


def test_지문이_넣은_그대로_돌아온다(store):
    fill(store, "product", VECTORS)

    assert store.hashes("product")["P002"] == "지문-P002"


def test_지문을_아이디로_좁혀_물을_수_있다(store):
    fill(store, "product", VECTORS)

    assert store.hashes("product", ids=["P001", "P003"]) == {
        "P001": "지문-P001", "P003": "지문-P003"}
    everything = store.hashes("product")
    assert store.hashes("product", ids=list(everything)) == everything


def test_없는_아이디로_좁히면_그_자리만_빈다(store):
    fill(store, "product", VECTORS)

    assert store.hashes("product", ids=["P001", "P없음"]) == {"P001": "지문-P001"}
    assert store.hashes("product", ids=[]) == {}


def test_표를_만들기_전에_좁혀_물어도_안_죽는다(store):
    assert store.hashes("review", ids=["1"]) == {}


def test_같은_아이디를_다시_넣으면_덮는다(store):
    fill(store, "product", VECTORS)
    store.upsert("product", ["P001"], [EAST], model=MODEL, hashes=["지문-바뀜"])

    assert store.hashes("product")["P001"] == "지문-바뀜"
    assert len(store.hashes("product")) == 3
    assert [pid for pid, _ in store.search("product", NORTH, 1)] == ["P002"]


def test_빈_표에서도_안_죽는다(store):
    store.recreate("product", dim=DIM, model=MODEL)

    assert store.search("product", NORTH, 3) == []
    assert store.hashes("product") == {}
    assert store.has("product", "P001") is False
    assert store.get_vector("product", "P001") is None
    assert store.delete("product", []) is None


def test_표를_만들기_전에_물어도_안_죽는다(store):
    assert store.hashes("customer") == {}


def test_모르는_kind_는_조용히_넘어가지_않는다(store):
    with pytest.raises(KeyError):
        store.search("없는종류", NORTH, 3)


def test_조각을_상품으로_좁힌다(store, chunks):
    rows = {chunk_id: NORTH for chunk_id, _ in chunks}
    fill(store, "chunk", rows,
         payload_columns={"product_id": "text", "product_name": "text"},
         payloads={"product_id": [pid for _, pid in chunks],
                   "product_name": [f"상품 {pid}" for _, pid in chunks]})

    found = store.chunk_ids_for_products(["P001", "P002"])

    assert sorted(found) == ["1", "2", "3"]
    assert store.chunk_ids_for_products([]) == []
    assert store.chunk_ids_for_products(["P004"]) == []


def test_베껴_둔_값을_한_번에_읽는다(store, chunks):
    rows = {chunk_id: NORTH for chunk_id, _ in chunks}
    fill(store, "chunk", rows,
         payload_columns={"product_id": "text", "product_name": "text"},
         payloads={"product_id": [pid for _, pid in chunks],
                   "product_name": [f"상품 {pid}" for _, pid in chunks]})

    got = store.fetch_payloads("chunk", ["1", "3"], ["product_id", "product_name"])

    assert got == {"1": {"product_id": "P001", "product_name": "상품 P001"},
                   "3": {"product_id": "P002", "product_name": "상품 P002"}}
    assert store.fetch_payloads("chunk", [], ["product_id"]) == {}


def test_없는_컬럼을_읽으려_하면_거절한다(store, chunks):
    rows = {chunk_id: NORTH for chunk_id, _ in chunks}
    fill(store, "chunk", rows, payload_columns={"product_id": "text"},
         payloads={"product_id": [pid for _, pid in chunks]})

    with pytest.raises(ValueError):
        store.fetch_payloads("chunk", ["1"], ["없는컬럼"])


def test_set_payload_는_벡터를_안_건드린다(store, chunks):
    rows = {chunk_id: NORTH for chunk_id, _ in chunks}
    fill(store, "chunk", rows,
         payload_columns={"product_id": "text", "product_name": "text"},
         payloads={"product_id": [pid for _, pid in chunks],
                   "product_name": [f"상품 {pid}" for _, pid in chunks]})
    before = store.search("chunk", NORTH, 4)

    store.set_payload("chunk", ["1", "2"], "product_name", "이름 바뀜")

    assert store.fetch_payloads("chunk", ["1"], ["product_name"]) == {
        "1": {"product_name": "이름 바뀜"}}
    assert store.fetch_payloads("chunk", ["3"], ["product_name"]) == {
        "3": {"product_name": "상품 P002"}}
    assert store.search("chunk", NORTH, 4) == before
    assert store.hashes("chunk")["1"] == "지문-1"


def test_recreate_는_전에_있던_것을_지운다(store):
    fill(store, "product", VECTORS)
    store.recreate("product", dim=DIM, model=MODEL)

    assert store.hashes("product") == {}
    assert store.search("product", NORTH, 3) == []


def test_뒤에서부터_찾을_수도_있다(store):
    fill(store, "product", VECTORS)

    found = store.search("product", NORTH, 3, reverse=True)

    assert [pid for pid, _ in found] == ["P003", "P002", "P001"]
