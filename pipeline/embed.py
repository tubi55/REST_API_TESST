"""상품, 고객, 후기, 문서 조각을 벡터로 만들어 저장한다."""

import sqlite3
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(errors="replace")

from app.core.config import DB_PATH, EMBED_MODEL
from app.domain.embedding_text import customer_text, product_text
from app.features.embedding_sync import sync

FULL = "--full" in sys.argv

con = sqlite3.connect(DB_PATH)
con.execute("PRAGMA foreign_keys = ON")

CHUNK_PAYLOAD = {
    "section_id": "int",
    "product_id": "text",
    "section": "text",
    "product_name": "text",
    "text": "text",
    "section_text": "text",
}

targets = {}

rows = con.execute("""
    SELECT chunks.chunk_id, chunks.section_id, chunks.product_id, chunks.section,
           products.name, chunks.text, sections.text
    FROM chunks
    JOIN products ON products.product_id = chunks.product_id
    JOIN sections ON sections.section_id = chunks.section_id
    ORDER BY chunks.chunk_id
""").fetchall()
targets["chunk"] = {
    "ids": [r[0] for r in rows],
    "texts": [r[5] for r in rows],
    "payload_columns": CHUNK_PAYLOAD,
    "payloads": {
        "section_id": [r[1] for r in rows],
        "product_id": [r[2] for r in rows],
        "section": [r[3] for r in rows],
        "product_name": [r[4] for r in rows],
        "text": [r[5] for r in rows],
        "section_text": [r[6] for r in rows],
    },
}

rows = con.execute("""
    SELECT product_id, name, brand, category, price, skin_type,
           ingredient, concern, tags, description
    FROM products ORDER BY product_id
""").fetchall()
targets["product"] = {"ids": [r[0] for r in rows],
                      "texts": [product_text(r[1:]) for r in rows]}

history = {}
for cid, category, ingredient, concern, rating in con.execute("""
    SELECT purchases.customer_id, products.category, products.ingredient,
           products.concern, purchases.rating
    FROM purchases
    JOIN products ON products.product_id = purchases.product_id
    WHERE purchases.is_holdout = 0
    ORDER BY purchases.customer_id, purchases.purchased_at
"""):
    history.setdefault(cid, []).append((None, category, ingredient, concern, rating))

skin_of = dict(con.execute("SELECT customer_id, skin_type FROM customers"))
cids = [c for (c,) in con.execute("SELECT customer_id FROM customers ORDER BY customer_id")
        if c in history]
targets["customer"] = {"ids": cids,
                       "texts": [customer_text(skin_of[c], history[c]) for c in cids]}

rows = con.execute("""
    SELECT purchase_id, review FROM purchases
    WHERE is_holdout = 0 AND review IS NOT NULL AND review != ''
    ORDER BY purchase_id
""").fetchall()
targets["review"] = {"ids": [r[0] for r in rows], "texts": [r[1] for r in rows]}

print("=" * 70)
print(f"임베딩 {EMBED_MODEL}   ({'전량' if FULL else '증분'})")
print("=" * 70)
print(f"  {'무엇':10s} {'대상':>7s} {'새로':>7s} {'그대로':>7s} {'지움':>6s} {'걸린시간':>10s}")

for kind, target in targets.items():
    started = time.perf_counter()
    result = sync(kind, target["ids"], target["texts"],
                  payloads=target.get("payloads"),
                  payload_columns=target.get("payload_columns"),
                  full=FULL)
    elapsed = time.perf_counter() - started
    print(f"  {kind:10s} {len(target['ids']):>7,} {result['embedded']:>7,} "
          f"{result['skipped']:>7,} {result['deleted']:>6,} {elapsed:>9.1f}초")

print(f"\n  {Path(DB_PATH).name} ({Path(DB_PATH).stat().st_size / 1024:,.0f}KB)")
print("  다음: python -m pipeline verify")
con.close()
