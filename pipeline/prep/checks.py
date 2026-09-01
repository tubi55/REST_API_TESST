"""파이프라인 결과의 개수, 차원, 누락 여부를 검사한다."""

import json

import numpy as np


# 문자로 저장된 벡터를 numpy 행렬로 되살린다. (아이디 목록, 행렬) 을 돌려준다
def load_vectors(con, table, key):
    ids, rows = [], []
    for row_id, vector in con.execute(f"SELECT {key}, vector FROM {table}"):
        ids.append(row_id)
        rows.append(json.loads(vector))
    return ids, np.array(rows, dtype="float32")


# 판정 하나를 쌓는다. 무엇을 검사했는지는 모르고 이미 판정된 참거짓만 받는다
def check(ok, message, results):
    results.append((bool(ok), message))
    return ok


# 표마다 몇 행인가. 벡터가 빠진 행은 없는가. {표 이름: 행 수} 를 돌려준다
def check_table_data(con, table_names, results):
    counts = {table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
              for table in table_names}

    check(counts["chunk_vectors"] == counts["chunks"],
          f"모든 조각에 벡터가 있다 ({counts['chunk_vectors']:,}/{counts['chunks']:,})",
          results)
    check(counts["product_vectors"] == counts["products"],
          f"모든 상품에 벡터가 있다 ({counts['product_vectors']:,}/{counts['products']:,})",
          results)

    orphan = con.execute("""
        SELECT COUNT(*) FROM chunks
        WHERE section_id NOT IN (SELECT section_id FROM sections)
    """).fetchone()[0]
    check(orphan == 0,
          f"조각이 전부 원문 섹션에 연결돼 있다 (끊긴 것 {orphan}개)", results)

    fk_errors = con.execute("PRAGMA foreign_key_check").fetchall()
    check(len(fk_errors) == 0, f"FK 위반 없음 (어긴 행 {len(fk_errors)}개)", results)

    holdout = con.execute(
        "SELECT COUNT(*) FROM purchases WHERE is_holdout = 1").fetchone()[0]
    check(holdout == counts["customers"],
          f"채점용 정답이 고객당 1건이다 ({holdout}건 / 고객 {counts['customers']}명)",
          results)

    return counts


# 네 벌을 되살려 차원 · 모델 · 정규화를 본다. (벡터, 종류별 모델 이름) 을 돌려준다
def check_vector_data(con, kinds, expected_dim, expected_model, results):
    vectors, models = {}, {}
    for kind, key in kinds:
        vectors[kind] = load_vectors(con, f"{kind}_vectors", key)
        models[kind] = [m for (m,) in
                        con.execute(f"SELECT DISTINCT model FROM {kind}_vectors")]

    all_dims = {matrix.shape[1] for _, matrix in vectors.values()}
    check(all_dims == {expected_dim},
          f"네 벌 모두 {expected_dim}차원이다 (실제 {all_dims})", results)

    all_models = {model for names in models.values() for model in names}
    check(all_models == {expected_model},
          f"네 벌이 같은 모델로 만들어졌다 (실제 {all_models})", results)

    worst = max(abs(np.linalg.norm(matrix, axis=1) - 1).max()
                for _, matrix in vectors.values())
    check(worst < 1e-3,
          f"전부 길이 1 로 정규화돼 있다 (제일 어긋난 것도 {worst:.6f})", results)

    return vectors, models


# 문자로 넣은 대가를 크기로 잰다
def check_vector_storage(con, kinds, vectors, embed_dim):
    vector_count = sum(matrix.shape[0] for _, matrix in vectors.values())
    text_bytes = sum(
        con.execute(f"SELECT COALESCE(SUM(LENGTH(vector)), 0) FROM {kind}_vectors")
           .fetchone()[0]
        for kind, _ in kinds)
    blob_bytes = vector_count * embed_dim * 4

    return {"vector_count": vector_count, "text_bytes": text_bytes,
            "blob_bytes": blob_bytes, "ratio": text_bytes / blob_bytes}


# 상한을 넘어 조용히 잘리는 조각이 있는가
def check_token_sizes(con, max_tokens, results):
    chunk_tokens = sorted(n for (n,) in con.execute("SELECT n_tokens FROM chunks"))
    section_tokens = [n for (n,) in con.execute("SELECT n_tokens FROM sections")]

    over = sum(n > max_tokens for n in chunk_tokens)
    check(over == 0, f"상한({max_tokens}) 을 넘는 조각 {over}개", results)

    return {"chunk_tokens": chunk_tokens, "section_tokens": section_tokens,
            "over": over,
            "average_chunk_tokens": sum(chunk_tokens) / len(chunk_tokens),
            "max_chunk_tokens": max(chunk_tokens),
            "headroom": 1 - max(chunk_tokens) / max_tokens}


# 검색용으로 베껴 둔 값이 원본과 같은가
def check_copied_values(con, results):
    stale = con.execute("""
        SELECT COUNT(*) FROM chunk_vectors
        JOIN chunks   ON chunks.chunk_id     = chunk_vectors.chunk_id
        JOIN sections ON sections.section_id = chunk_vectors.section_id
        JOIN products ON products.product_id = chunk_vectors.product_id
        WHERE chunk_vectors.section_id   != chunks.section_id
           OR chunk_vectors.section      != chunks.section
           OR chunk_vectors.text         != chunks.text
           OR chunk_vectors.section_text != sections.text
           OR chunk_vectors.product_name != products.name
    """).fetchone()[0]
    check(stale == 0,
          f"검색용 표에 베껴 둔 값이 원본과 같다 (어긋난 행 {stale}개)", results)
    return stale


# 쌓인 판정에서 실패한 문장만 고른다
def failures(results):
    return [message for ok, message in results if not ok]
