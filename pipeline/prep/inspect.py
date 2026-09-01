"""검색어와 비슷한 데이터를 찾아 사람이 확인할 수 있게 반환한다."""

import numpy as np

from app.adapters.stores import get_store
from app.core.embedder import get_embeddings

LABELS = {
    "chunk": ("chunk_vectors", "chunk_id", "product_name || ' > ' || section", "section_text"),
    "product": ("products", "product_id", "name", "description"),
    "customer": ("customers", "customer_id", "name", "skin_type || ' · ' || city"),
    "review": ("purchases", "purchase_id", "customer_id || ' · ' || product_id", "review"),
}


# 질문마다 가까운 것 top_k 개를 찾는다. {질문: [(아이디, 이름표, 글, 점수), ...]}
def inspect(con, kind, questions, top_k=3, reverse=False):
    if kind not in LABELS:
        raise ValueError(f"모르는 종류다: {kind} (아는 것: {', '.join(LABELS)})")

    table, key, label_sql, text_sql = LABELS[kind]
    store = get_store()

    model = get_embeddings()
    vectors = np.array(model.embed_documents(questions), dtype="float32")

    meta = {str(row[0]): (row[1], row[2] or "")
            for row in con.execute(
                f"SELECT {key}, {label_sql}, {text_sql} FROM {table}")}

    found = {}
    for question, vector in zip(questions, vectors):
        rows = []
        for item_id, score in store.search(kind, vector, top_k, reverse=reverse):
            label, text = meta.get(item_id, (item_id, ""))
            rows.append((item_id, label, text, score))
        found[question] = rows

    return found
