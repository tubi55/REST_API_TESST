"""내용이 바뀐 데이터만 찾아 벡터를 최신 상태로 맞춘다."""

# 벡터 저장소 객체를 얻는 함수다.
from app.adapters.stores import get_store

# 벡터의 차원과 임베딩 모델 이름을 설정에서 가져온다.
from app.core.config import EMBED_DIM, EMBED_MODEL

# 글을 벡터로 바꾸는 임베딩기를 얻는 함수다.
from app.core.embedder import get_embeddings

# 글의 지문을 만드는 순수 함수다.
from app.domain.embedding_text import source_hash


# 이 글로 만든 벡터인지 알아보는 지문. 모델 이름을 같이 넣는다
def fingerprint(text, model=EMBED_MODEL):
    # 모델이 바뀌면 같은 글이어도 지문이 달라져 벡터를 다시 만든다.
    return source_hash(f"{model}\n{text}")


# ids 와 texts 를 저장소와 맞춘다. 바뀐 것만 임베딩하고 없어진 것은 지운다
def sync(kind, ids, texts, *, payloads=None, payload_columns=None,
         # full 이 참이면 전량으로 다시 만든다.
         full=False, model=EMBED_MODEL):
    # 벡터 저장소를 얻는다.
    store = get_store()
    # 지금 글들의 지문을 미리 다 만들어 둔다.
    fingerprints = [fingerprint(text, model) for text in texts]

    # 전량이면 저장된 지문을 안 본다. 어차피 표를 새로 만든다.
    known = {} if full else store.hashes(kind)
    # 전량이거나 저장된 것이 하나도 없으면 표부터 새로 만든다.
    if full or not known:
        # 표를 지우고 새 구조로 다시 만든다.
        store.recreate(kind, dim=EMBED_DIM, model=model, payload_columns=payload_columns)
        # 표를 비웠으니 아는 지문도 없다.
        known = {}

    # 저장된 지문과 지금 지문이 다른 것만 고른다. 자리 번호로 모은다.
    todo = [i for i, (item_id, mark) in enumerate(zip(ids, fingerprints))
            # 처음 보는 아이디면 get 이 None 을 주므로 다르다고 판정된다.
            if known.get(str(item_id)) != mark]

    # 다시 만들 것이 있을 때만 임베딩을 부른다. 여기가 돈과 시간이 드는 자리다.
    if todo:
        # 고른 글만 모아 한 번에 벡터로 바꾼다.
        vectors = get_embeddings().embed_documents([texts[i] for i in todo])
        # 만든 벡터를 저장소에 넣거나 갈아 끼운다.
        store.upsert(
            # 어느 종류인지 알려 준다.
            kind,
            # 고른 자리의 아이디만 넘긴다.
            [ids[i] for i in todo],
            # 방금 만든 벡터들이다.
            vectors,
            # 어떤 모델로 만들었는지 같이 적는다.
            model=model,
            # 다음에 비교할 지문도 같이 적는다.
            hashes=[fingerprints[i] for i in todo],
            # 곁에 같이 넣을 값도 같은 자리만 골라 넘긴다.
            payloads={name: [values[i] for i in todo]
                      # payloads 를 안 받았으면 빈 딕셔너리로 둔다.
                      for name, values in (payloads or {}).items()},
        )

    # 지금 살아 있는 아이디를 글자로 모아 둔다.
    alive = {str(item_id) for item_id in ids}
    # 저장소에는 있는데 지금 목록에 없는 것이 원본에서 사라진 것이다.
    gone = [item_id for item_id in known if item_id not in alive]
    # 사라진 것의 벡터를 지운다. 목록이 비면 저장소가 알아서 넘어간다.
    store.delete(kind, gone)

    # 몇 개를 만들고 건너뛰고 지웠는지 알려 준다.
    return {"embedded": len(todo), "skipped": len(ids) - len(todo), "deleted": len(gone)}


# 한 건만 맞춘다. 상품 CRUD 가 부르는 자리다
def sync_one(kind, item_id, text, *, payloads=None, model=EMBED_MODEL):
    # 벡터 저장소를 얻는다.
    store = get_store()
    # 지금 글의 지문을 만든다.
    mark = fingerprint(text, model)
    # ids= 를 붙여 그 한 건의 지문만 읽는다. 표를 통째로 읽지 않는다.
    if store.hashes(kind, ids=[item_id]).get(str(item_id)) == mark:
        # 지문이 같으면 글이 안 바뀐 것이므로 임베딩을 부르지 않는다.
        return {"embedded": 0, "skipped": 1, "deleted": 0}

    # 글 하나여도 목록에 담아 넘긴다. 돌아오는 것도 목록이다.
    vector = get_embeddings().embed_documents([text])
    # 만든 벡터 하나를 저장소에 넣거나 갈아 끼운다.
    store.upsert(kind, [item_id], vector, model=model, hashes=[mark],
                 # 곁에 같이 넣을 값도 한 건짜리 목록으로 바꿔 넘긴다.
                 payloads={name: [value] for name, value in (payloads or {}).items()})
    # 한 건을 새로 만들었다고 알려 준다.
    return {"embedded": 1, "skipped": 0, "deleted": 0}
