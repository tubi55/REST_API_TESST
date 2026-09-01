"""파이프라인이 만든 DB와 벡터를 실제로 사용할 수 있는지 검사한다."""

import sqlite3
import sys
import time

sys.stdout.reconfigure(errors="replace")

from app.core.config import DB_PATH, EMBED_DIM, EMBED_MAX_TOKENS, EMBED_MODEL
from app.domain.embedding_text import PRODUCT_FIELDS, product_text
from pipeline.prep import checks
from pipeline.prep.chunking import count_tokens
from pipeline.prep.inspect import inspect
from pipeline.prep.metrics import calculate_scores, hit_at

con = sqlite3.connect(DB_PATH)
results = []
shown = 0

PREVIEW = 60

KINDS = (("chunk", "chunk_id"), ("product", "product_id"),
         ("customer", "customer_id"), ("review", "purchase_id"))

TABLES = ("customers", "products", "purchases", "product_details",
          "sections", "chunks", "chunk_vectors", "product_vectors",
          "customer_vectors", "review_vectors")


# 구간 제목을 찍는다
def banner(title):
    print()
    print("=" * 74)
    print(title)
    print("=" * 74)


# 아직 안 찍은 판정만 찍는다
def report():
    global shown
    for ok, message in results[shown:]:
        print(f"  [{'OK  ' if ok else '문제'}] {message}")
    shown = len(results)


banner("1. 개수")
counts = checks.check_table_data(con, TABLES, results)
for table, n in counts.items():
    print(f"  {table:18s} {n:>7,}")
print()
checks.check_copied_values(con, results)
report()

banner("2. 벡터")
vectors, models = checks.check_vector_data(con, KINDS, EMBED_DIM, EMBED_MODEL, results)
for kind, _key in KINDS:
    _ids, matrix = vectors[kind]
    print(f"  {kind:9s} {matrix.shape[0]:>6,} x {matrix.shape[1]}  "
          f"모델 {', '.join(models[kind])}")
print()
report()

banner("3. 저장 방식")
storage = checks.check_vector_storage(con, KINDS, vectors, EMBED_DIM)
print(f"  벡터 {storage['vector_count']:,}개 ({EMBED_DIM}차원)")
print(f"      문자   {storage['text_bytes'] / 1024 / 1024:>5.1f}MB   (지금 이 방식)")
print(f"      BLOB   {storage['blob_bytes'] / 1024 / 1024:>5.1f}MB   (같은 숫자를 이진으로)")
print(f"      -> 문자가 {storage['ratio']:.1f}배 크다")

banner("4. 토큰")
token_result = checks.check_token_sizes(con, EMBED_MAX_TOKENS, results)
print(f"  조각 평균 {token_result['average_chunk_tokens']:.1f}토큰 · "
      f"제일 긴 것 {token_result['max_chunk_tokens']}토큰")
print(f"  상한 대비 여유가 {token_result['headroom'] * 100:.0f}% 남았다")
print()
report()

banner("5. 한 상품의 조각 점수를 어떻게 합치나 (max vs mean)")

customer_ids, customer_matrix = vectors["customer"]
product_ids, product_matrix = vectors["product"]
chunk_ids, chunk_matrix = vectors["chunk"]

answers = dict(con.execute(
    "SELECT customer_id, product_id FROM purchases WHERE is_holdout = 1"))
bought = {}
for customer_id, product_id in con.execute(
        "SELECT customer_id, product_id FROM purchases WHERE is_holdout = 0"):
    bought.setdefault(customer_id, set()).add(product_id)
product_of = dict(con.execute("SELECT chunk_id, product_id FROM chunks"))

product_rows = con.execute(
    f"SELECT {', '.join(PRODUCT_FIELDS)} FROM products ORDER BY product_id").fetchall()
average_product_tokens = sum(
    count_tokens(product_text(row)) for row in product_rows) / len(product_rows)

average_tokens = {
    "상품 요약 벡터 (기준선)": average_product_tokens,
    "조각 벡터 · max 로 합치기": token_result["average_chunk_tokens"],
    "조각 벡터 · mean 으로 합치기": token_result["average_chunk_tokens"],
}

started = time.perf_counter()
score_sets = calculate_scores(customer_matrix, product_matrix, chunk_matrix,
                              chunk_ids, product_ids, product_of)
elapsed = time.perf_counter() - started

print(f"  고객 {len(customer_ids)}명 · 상품 {len(product_ids)}개 · "
      f"조각 {len(chunk_ids):,}개 전부 비교하는 데 {elapsed * 1000:.0f}ms\n")
print(f"  {'무엇으로 찾나':28s} {'평균 토큰':>10s} "
      f"{'hit@1':>7s} {'hit@3':>7s} {'hit@5':>7s}")

for label, scores in score_sets.items():
    hits = hit_at(scores, customer_ids, product_ids, bought, answers)
    print(f"  {label:28s} {average_tokens[label]:>10.1f} "
          f"{hits[1]:>6.1f}% {hits[3]:>6.1f}% {hits[5]:>6.1f}%")

print()
print("  읽는 법: 자의 흔들림이 30명 표본에서 16.7%p 다 (docs/measurements.md).")
print("  300명 전수는 그만큼은 아니지만 1%p 남짓한 차이는 여전히 못 믿는다.")
print("  그리고 상세 조각은 애초에 추천 신호가 아니다. 추천은 상품 요약 벡터로 한다.")

banner("6. 눈으로. 네 벌 모두 던져 본다")


# 찾은 것을 사람이 읽을 모양으로 찍는다
def show(kind, questions, top_k=3, reverse=False):
    direction = "가장 먼" if reverse else "가장 가까운"
    for question, rows in inspect(con, kind, questions,
                                  top_k=top_k, reverse=reverse).items():
        print(f"\n  Q. {question}  ({kind} 중 {direction} {top_k}개)")
        for _item_id, label, text, score in rows:
            flat = text.replace("\n", " ")[:PREVIEW]
            print(f"     {score:.3f}  [{label}] {flat}...")


show("chunk", ["배송은 얼마나 걸리나요", "환불하고 싶은데 어떻게 하나요"])
show("review", ["배송이 너무 느렸어요"], top_k=2)
show("product", ["건성 피부에 좋은 수분 크림"], top_k=2)
show("customer", ["민감성 피부인 사람"], top_k=2)

print()
for word in ("환불", "반품", "교환"):
    n = con.execute("SELECT COUNT(*) FROM chunks WHERE body LIKE ?",
                    (f"%{word}%",)).fetchone()[0]
    print(f"  '{word}' 이 들어간 조각: {n:,}개")
print("  우리 문서는 '환불' 을 한 번도 안 쓴다. '교환·반품' 으로만 적혀 있다.")
print(f"  지금 임베딩은 {EMBED_MODEL} 이다. 모델마다 이 둘을 잇기도 하고 못 잇기도 한다")
print("  (docs/measurements.md 참조). 어느 쪽이든 벡터 검색만 믿으면 안 된다.")

problems = checks.failures(results)
print()
print("=" * 74)
if problems:
    print(f"문제 {len(problems)}건. 앱을 붙이기 전에 고친다")
    for message in problems:
        print(f"  - {message}")
else:
    print("전부 통과. 다음은 uvicorn app.main:app --reload")
print("=" * 74)
con.close()
