"""긴 상품 상세 글을 검색에 사용할 작은 조각으로 나누어 저장한다."""

import sqlite3
import statistics
import sys
from pathlib import Path

sys.stdout.reconfigure(errors="replace")

from huggingface_hub.utils import disable_progress_bars
from huggingface_hub.utils import logging as hub_logging
from transformers import logging as hf_logging

hf_logging.set_verbosity_error()
hf_logging.disable_progress_bar()
hub_logging.set_verbosity_error()
disable_progress_bars()

from app.core.config import DB_PATH, EMBED_MAX_TOKENS, EMBED_TOKENIZER
from pipeline.prep import chunking, storage
from pipeline.prep.options import CHUNK_OVERLAP, CHUNK_SIZE, PREFIX_BUDGET, RESPLIT_OVER

con = sqlite3.connect(DB_PATH)
con.execute("PRAGMA foreign_keys = ON")

ntok = chunking.count_tokens


# 분포 한 줄. 최소 / 중앙 / 최대
def dist(values):
    return (f"최소 {min(values):>5,} · 중앙 {int(statistics.median(values)):>5,} · "
            f"최대 {max(values):>5,}")


details = con.execute("""
    SELECT product_details.product_id, products.name, product_details.detail
    FROM product_details
    JOIN products ON product_details.product_id = products.product_id
    ORDER BY product_details.product_id
""").fetchall()

print(f"상품 상세 {len(details)}건을 읽었다\n")


print("=" * 74)
print("① 왜 자르나. 통째로 넣으면 뒤가 잘린다")
print("=" * 74)

full_tokens = [ntok(detail) for _, _, detail in details]
over = [n for n in full_tokens if n > EMBED_MAX_TOKENS]
fits = [min(n, EMBED_MAX_TOKENS) / n for n in full_tokens]

print(f"  임베딩 모델 상한 : {EMBED_MAX_TOKENS} 토큰 ({EMBED_TOKENIZER})")
print(f"  상세 토큰 분포   : {dist(full_tokens)}")
print(f"  상한 초과        : {len(over)}/{len(full_tokens)}건 "
      f"({len(over) / len(full_tokens) * 100:.0f}%)")
print(f"  평균 수용률      : {sum(fits) / len(fits) * 100:.0f}%  "
      f"(나머지는 모델에 닿지도 못한다)")
print("  뒤가 잘린다는 건 '배송 및 교환'·'자주 묻는 질문'이 통째로 사라진다는 뜻이다\n")


print("=" * 74)
print("② 2단 구조. 사람이 만든 경계로 자르고, 넘치는 것만 다시 자른다 (실무 표준)")
print("=" * 74)
print(f"  설정: CHUNK_SIZE {CHUNK_SIZE} · OVERLAP {CHUNK_OVERLAP} · "
      f"PREFIX_BUDGET {PREFIX_BUDGET} -> 다시 자를 문턱 {RESPLIT_OVER}")
print("  (prep/options.py 에 있다. 이 파일에는 숫자가 없다)\n")

sections, chunks, n_resplit = chunking.split_details(details)

section_tokens = [section["n_tokens"] for section in sections]
chunk_tokens = [ntok(chunk["body"]) for chunk in chunks]
print(f"  {'':14s}{'개수':>8s}   분포")
print(f"  0단 (통째로)  {len(full_tokens):>8,}   {dist(full_tokens)}")
print(f"  1단 (섹션)    {len(sections):>8,}   {dist(section_tokens)}")
print(f"  2단 (조각)    {len(chunks):>8,}   {dist(chunk_tokens)}")
print(f"\n  상한({EMBED_MAX_TOKENS}) 초과가 {len(over)}건 -> "
      f"{sum(n > EMBED_MAX_TOKENS for n in chunk_tokens)}건이 됐다")
print(f"  다시 자른 섹션: {n_resplit}개 / {len(sections):,}개 "
      f"(대부분은 헤더 한 번으로 충분했다)\n")

print("=" * 74)
print("③ 문맥 유지. 조각 앞에 제목과 섹션명을 붙여서 저장한다")
print("=" * 74)
print("  '민감성 피부에는 사용을 권하지 않습니다' 만 떼어 놓으면 어느 제품 얘긴지 모른다.")
print("  임베딩은 그 조각의 글자만 본다. 그래서 출처를 글자로 적어 넣는다\n")

example = next(chunk for chunk in chunks if chunk["section"] == "주의사항")
print(f"  붙이기 전: {example['body'][:56]}...")
print(f"  붙인 뒤  : {example['text'][:56]}...\n")


storage.save_sections_and_chunks(con, sections, chunks)

stored = [n for (n,) in con.execute("SELECT n_tokens FROM chunks")]
print("=" * 74)
print("④ 저장. sections · chunks")
print("=" * 74)
print(f"  sections {len(sections):>6,}행")
print(f"  chunks   {len(chunks):>6,}행  ·  접두어까지 넣은 토큰 {dist(stored)}")
print(f"  상한({EMBED_MAX_TOKENS}) 초과: {sum(n > EMBED_MAX_TOKENS for n in stored)}개")

print(f"\n  {Path(DB_PATH).name} ({Path(DB_PATH).stat().st_size / 1024:,.0f}KB)")
print("  다음: python -m pipeline embed")
con.close()
