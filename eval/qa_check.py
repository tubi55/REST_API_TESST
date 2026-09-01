"""상품 질문에 필요한 문서 조각이 검색되는지 측정한다."""

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(errors="replace")

from app.features.retrieve import search_chunks
from app.repositories import details as detail_repo

GOLDEN = json.loads((Path(__file__).parent / "qa_golden.json").read_text(encoding="utf-8"))
ITEMS = GOLDEN["items"]

print("=" * 74)
print("1. 골든셋이 데이터와 맞나. keywords 가 그 섹션에 정말 있는가")
print("=" * 74)

broken = []
for item in ITEMS:
    text = detail_repo.find_section(item["product_id"], item["section"])
    if text is None:
        broken.append((item["id"], "그런 섹션이 없다"))
        continue
    missing = [w for w in item["keywords"] if w not in text]
    if missing:
        broken.append((item["id"], f"원문에 없는 낱말: {missing}"))

print(f"  문항 {len(ITEMS)}개 · 어긋난 것 {len(broken)}개")
for qid, reason in broken:
    print(f"      {qid}번: {reason}")
if not broken:
    print("  전부 원문에 있는 말이다. 이제 이걸 자로 쓸 수 있다")

print()
print("=" * 74)
print("2. 질문을 던져 정답 섹션이 상위에 오나 (조각 검색)")
print("=" * 74)

hits = {1: 0, 3: 0, 5: 0}
misses = []
for item in ITEMS:
    found = search_chunks(item["question"], k=5)
    ranks = [(s["product_id"], s["section"]) for s in found]
    target = (item["product_id"], item["section"])

    section_only = [s for _, s in ranks]

    for k in hits:
        ok = target in ranks[:k] or item["section"] in section_only[:k]
        if ok:
            hits[k] += 1
    if item["section"] not in section_only[:5]:
        misses.append((item, section_only))

n = len(ITEMS)
print(f"  hit@1 {hits[1] / n * 100:.0f}%  ·  hit@3 {hits[3] / n * 100:.0f}%  "
      f"·  hit@5 {hits[5] / n * 100:.0f}%   ({n}문항)")

if misses:
    print(f"\n  못 찾은 것 {len(misses)}개. 왜 못 찾았는지를 본다:")
    for item, got in misses:
        print(f"      {item['id']:>2}. {item['question']}")
        print(f"          정답 [{item['section']}] · 검색 결과 {got[:3]}")
