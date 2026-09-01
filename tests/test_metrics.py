"""추천 지표 시험. DB 없이 돈다."""

import numpy as np

from pipeline.prep.metrics import calculate_scores, hit_at


def test_정답이_1위면_hit는_전부_100():
    scores = np.array([[0.9, 0.1], [0.2, 0.8]])
    got = hit_at(scores, ["C1", "C2"], ["P1", "P2"], {}, {"C1": "P1", "C2": "P2"})
    assert got == {1: 100.0, 3: 100.0, 5: 100.0}


def test_이미_산_상품은_후보에서_빠진다():
    scores = np.array([[0.9, 0.5]])
    got = hit_at(scores, ["C1"], ["P1", "P2"], {"C1": {"P1"}}, {"C1": "P2"})
    assert got[1] == 100.0


def test_k가_커지면_비율이_안_줄어든다():
    scores = np.array([[0.1, 0.9, 0.5]])
    got = hit_at(scores, ["C1"], ["P1", "P2", "P3"], {}, {"C1": "P1"})
    assert got[1] <= got[3] <= got[5]


def test_세_방법이_모두_고객x상품_모양을_준다():
    customers = np.array([[1.0, 0.0], [0.0, 1.0]])
    products = np.array([[1.0, 0.0], [0.0, 1.0]])
    chunks = np.array([[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]])
    got = calculate_scores(customers, products, chunks,
                           chunk_ids=[1, 2, 3], product_ids=["P1", "P2"],
                           product_of={1: "P1", 2: "P1", 3: "P2"})
    assert len(got) == 3
    for matrix in got.values():
        assert matrix.shape == (2, 2)


def test_max는_mean보다_크거나_같다():
    customers = np.array([[1.0, 0.0]])
    products = np.array([[1.0, 0.0]])
    chunks = np.array([[1.0, 0.0], [0.0, 1.0]])
    got = calculate_scores(customers, products, chunks,
                           chunk_ids=[1, 2], product_ids=["P1"],
                           product_of={1: "P1", 2: "P1"})
    assert got["조각 벡터 · max 로 합치기"][0][0] >= got["조각 벡터 · mean 으로 합치기"][0][0]
