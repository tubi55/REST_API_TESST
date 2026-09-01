"""추천 결과가 정답을 얼마나 잘 찾았는지 계산한다."""

import numpy as np


# 고객 x 상품 점수를 세 가지 방법으로 만든다. 모양은 전부 (고객 수, 상품 수)
def calculate_scores(customer_matrix, product_matrix, chunk_matrix,
                     chunk_ids, product_ids, product_of):
    product_scores = customer_matrix @ product_matrix.T
    chunk_scores = customer_matrix @ chunk_matrix.T

    columns_of = {}
    for column, chunk_id in enumerate(chunk_ids):
        columns_of.setdefault(product_of[chunk_id], []).append(column)

    max_scores = np.stack(
        [chunk_scores[:, columns_of[pid]].max(axis=1) for pid in product_ids], axis=1)
    mean_scores = np.stack(
        [chunk_scores[:, columns_of[pid]].mean(axis=1) for pid in product_ids], axis=1)

    return {"상품 요약 벡터 (기준선)": product_scores,
            "조각 벡터 · max 로 합치기": max_scores,
            "조각 벡터 · mean 으로 합치기": mean_scores}


# 숨겨 둔 정답이 상위 k 안에 오나 센다. {k: 맞힌 비율(%)} 을 돌려준다
def hit_at(scores, customer_ids, product_ids, bought, answers, ks=(1, 3, 5)):
    hits = {k: 0 for k in ks}
    for row, customer_id in enumerate(customer_ids):
        ranked = [product_ids[i] for i in np.argsort(-scores[row])
                  if product_ids[i] not in bought.get(customer_id, ())]
        for k in ks:
            hits[k] += answers[customer_id] in ranked[:k]
    return {k: count / len(customer_ids) * 100 for k, count in hits.items()}
