"""구매 이력에서 만든 정답으로 상품 추천 품질을 측정한다."""

import sys
import time

import numpy as np

sys.stdout.reconfigure(errors="replace")

from app.features.retrieve import N_CANDIDATES, candidates, dashboard
from app.repositories import customers as customer_repo
from app.repositories import purchases as purchase_repo

ANSWERS = purchase_repo.holdout_answers()
CUSTOMERS = customer_repo.all_ids()


# 벡터 순위로만 잰다. hit@1/3/5 와 천장(후보 안에 정답이 있나)
def score_vector(customer_ids, use_filter=True):
    hits = {1: 0, 3: 0, 5: 0}
    ceiling = 0
    for cid in customer_ids:
        picks, _blocked, _used = candidates(cid, use_filter=use_filter)
        ranked = [row["product_id"] for row in picks]
        if ANSWERS[cid] in ranked:
            ceiling += 1
        for k in hits:
            if ANSWERS[cid] in ranked[:k]:
                hits[k] += 1
    n = len(customer_ids)
    return {k: v / n * 100 for k, v in hits.items()}, ceiling / n * 100


print("=" * 74)
print("A. 벡터만. 조건을 걸고 안 걸고")
print("=" * 74)
print(f"  고객 {len(CUSTOMERS)}명 · 후보 {N_CANDIDATES}개까지 본다\n")
print(f"  {'조건':16s} {'hit@1':>7s} {'hit@3':>7s} {'hit@5':>7s} {'천장@20':>8s}")

for label, use_filter in (("없음", False), ("이력 카테고리", True)):
    started = time.perf_counter()
    hits, ceiling = score_vector(CUSTOMERS, use_filter=use_filter)
    print(f"  {label:16s} {hits[1]:>6.1f}% {hits[3]:>6.1f}% {hits[5]:>6.1f}% "
          f"{ceiling:>7.1f}%   ({time.perf_counter() - started:.1f}초)")

print("\n  천장은 '후보 안에 정답이 있는 비율'이다. LLM 이 아무리 잘해도 이걸 못 넘는다.")
print("  조건을 걸면 정밀도는 오르고 천장은 내려간다. 공짜가 아니다")

print()
print("=" * 74)
print("B. 자의 흔들림. 같은 방법을 표본만 바꿔 네 번 잰다")
print("=" * 74)
print("  방법을 안 바꿨는데도 숫자가 이만큼 움직인다.")
print("  이 폭보다 작은 차이를 보고 '좋아졌다'고 말하면 안 된다.\n")

rng = np.random.default_rng(20260812)
sample_size = 30
values = []
for run in range(4):
    sample = list(rng.choice(CUSTOMERS, size=sample_size, replace=False))
    hits, _ceiling = score_vector(sample)
    values.append(hits[5])
    print(f"  {run + 1}회차 (무작위 {sample_size}명)  hit@5 {hits[5]:>5.1f}%")

print(f"\n  폭: {min(values):.1f}% ~ {max(values):.1f}%  ->  "
      f"{max(values) - min(values):.1f}%p 가 '아무것도 안 바꿨을 때의 흔들림'이다")
print(f"  참고: 300명 전체로 재면 {score_vector(CUSTOMERS)[0][5]:.1f}% 다. "
      "표본이 작을수록 더 흔들린다")

if "--llm" in sys.argv:
    at = sys.argv.index("--llm") + 1
    n = int(sys.argv[at]) if len(sys.argv) > at else 30
    from app.adapters.llm import recommend

    print()
    print("=" * 74)
    print(f"C. 벡터 + LLM. 후보 {N_CANDIDATES}개에서 LLM 이 5개를 고른다 ({n}명)")
    print("=" * 74)

    hit_vec = hit_llm = 0
    n_full = n_retry = n_fail = 0
    started = time.perf_counter()

    for i, cid in enumerate(CUSTOMERS[:n], start=1):
        picks, _blocked, _used = candidates(cid)
        ranked = [row["product_id"] for row in picks]
        hit_vec += ANSWERS[cid] in ranked[:5]

        result, retries, error = recommend(picks, dashboard(cid))
        n_retry += retries
        if result is None:
            n_fail += 1
            continue
        if len(result.picks) == 5:
            n_full += 1
        chosen = [picks[p.number - 1]["product_id"] for p in result.picks]
        hit_llm += ANSWERS[cid] in chosen

        elapsed = time.perf_counter() - started
        print(f"  {i:>3}/{n}  벡터 {hit_vec / i * 100:>5.1f}%  LLM {hit_llm / i * 100:>5.1f}%  "
              f"({elapsed / i:.0f}초/건)", end="\r")

    print(" " * 70, end="\r")
    print(f"  벡터 상위 5개    hit@5 {hit_vec / n * 100:>5.1f}%")
    print(f"  LLM 이 고른 5개  hit@5 {hit_llm / n * 100:>5.1f}%")
    print(f"  5개를 다 낸 사람 {n_full}/{n} · 재시도 총 {n_retry}회 · 끝내 실패 {n_fail}명")
    print(f"  총 {time.perf_counter() - started:.0f}초")
    print("\n  읽는 법: B 에서 잰 흔들림보다 작은 차이는 못 믿는다")
