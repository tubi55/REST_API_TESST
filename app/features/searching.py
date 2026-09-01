"""입력 글을 벡터로 바꾸고 저장소에서 비슷한 데이터를 찾는다."""

# 임베딩기가 준 목록을 저장소가 쓰는 행렬 형태로 맞추기 위해 사용한다.
import numpy as np

# 벡터 저장소 객체를 얻는 함수다.
from app.adapters.stores import get_store

# 글을 벡터로 바꾸는 임베딩기를 얻는 함수다.
from app.core.embedder import get_embeddings

# 사전을 붙여 개인정보를 지우는 함수다.
from app.features.privacy import mask_text

# 추천하면 안 되는 상품과 그 근거를 주는 함수들이다.
from app.features.safety_filter import blocked_for, reason_for

# 고객 · 상품 · 구매 표에 닿는 저장소를 얻는 함수들이다.
from app.repositories import get_customer_repo, get_product_repo, get_purchase_repo

# 이 파일에서 계속 쓸 고객 저장소를 한 번만 잡아 둔다.
customer_repo = get_customer_repo()

# 이 파일에서 계속 쓸 상품 저장소를 한 번만 잡아 둔다.
product_repo = get_product_repo()

# 이 파일에서 계속 쓸 구매 저장소를 한 번만 잡아 둔다.
purchase_repo = get_purchase_repo()

# 후보를 몇 개까지 볼지 정한 값이다. docs/measurements.md 의 천장 표에서 나왔다.
N_CANDIDATES = 20

# 조각 벡터 옆에 같이 저장해 둔 값들이다. 이 이름으로 한 번에 읽는다.
CHUNK_PAYLOAD = ("product_id", "product_name", "section", "section_text")


# 이력에 있는 카테고리의 상품만 남긴다
def filter_by_history_category(customer_id):
    # 실제 질의는 저장소가 한다. 여기서는 이름만 붙여 준다.
    return purchase_repo.history_category_product_ids(customer_id)


# 이미 산 상품 아이디들
def already_bought(customer_id):
    # 이미 산 것을 다시 추천하지 않으려고 쓴다.
    return purchase_repo.bought_product_ids(customer_id)


# 추천 후보를 만든다. (후보, 안전 필터로 뺀 것, 쓴 필터 이름) 을 돌려준다
def candidates(customer_id, n=N_CANDIDATES, use_filter=True):
    # 벡터 저장소를 얻는다.
    store = get_store()
    # 그런 고객이 있는지 먼저 본다.
    profile = customer_repo.find_profile(customer_id)
    # 고객이 없거나 그 고객의 벡터가 아직 없으면 비슷한 것을 찾을 수 없다.
    if profile is None or not store.has("customer", customer_id):
        # 빈 결과와 함께 왜 못 했는지 알려 준다.
        return [], [], "고객 벡터 없음"
    # 안전 필터에 쓸 피부 타입을 꺼내 둔다.
    skin_type = profile["skin_type"]

    # 벡터가 있는 상품만 후보가 될 수 있다. 지문 목록의 열쇠가 곧 아이디다.
    allowed = set(store.hashes("product"))
    # 어떤 필터를 썼는지 화면에 알려 주려고 담아 둔다.
    filter_used = "없음"

    # 필터를 끄고 부를 수도 있다. 채점 도구가 비교할 때 쓴다.
    if use_filter:
        # 이 고객이 사 본 카테고리의 상품 아이디를 모은다.
        by_category = filter_by_history_category(customer_id)
        # 이력이 아예 없는 고객이면 걸 것이 없다.
        if by_category:
            # &= 는 양쪽에 다 있는 것만 남긴다.
            allowed &= by_category
            # 실제로 걸었으므로 이름을 바꿔 둔다.
            filter_used = "이력 카테고리"

    # -= 는 오른쪽에 있는 것을 빼낸다. 이미 산 상품을 후보에서 뺀다.
    allowed -= already_bought(customer_id)

    # 남은 후보 중 이 피부 타입에 권하면 안 되는 것을 골라낸다.
    banned = blocked_for(skin_type) & allowed
    # 그것들을 후보에서 뺀다.
    allowed -= banned

    # 이 고객의 취향 벡터를 꺼낸다.
    me = store.get_vector("customer", customer_id)
    # 남은 후보 안에서만 가까운 것부터 n 개를 찾는다.
    ranked = store.search("product", me, n, only_ids=allowed)

    # 점수는 빼고 아이디 순서만 따로 모은다.
    picked_ids = [pid for pid, _ in ranked]
    # 아이디로 점수를 바로 찾을 수 있게 딕셔너리로도 만들어 둔다.
    picked_scores = dict(ranked)

    # 카드에 필요한 값을 한 번에 읽어 아이디로 찾을 수 있게 만든다.
    detail = {row["product_id"]: row for row in product_repo.find_cards(picked_ids)}
    # 화면에 줄 후보를 담을 목록이다.
    out = []
    # start=1 이라 번호가 1 부터 붙는다. 이 번호를 모델이 답으로 가리킨다.
    for number, pid in enumerate(picked_ids, start=1):
        # 상품 정보를 펼쳐 넣고 번호와 점수를 더한다.
        out.append({**detail[pid], "number": number,
                    # 점수는 소수점 넷째 자리까지만 보여 준다.
                    "score": round(picked_scores[pid], 4),
                    # 이유는 모델이 나중에 채우고, 이 후보는 막힌 것이 아니다.
                    "reason": "", "blocked": False, "blocked_reason": ""})

    # 막힌 상품도 순서를 고정해 화면이 흔들리지 않게 한다.
    banned_ids = sorted(banned)
    # 막힌 상품의 카드 정보도 한 번에 읽는다.
    banned_rows = {row["product_id"]: row
                   # 아이디로 바로 찾을 수 있게 딕셔너리로 만든다.
                   for row in product_repo.find_cards(banned_ids)}
    # 막힌 상품은 번호와 점수 없이, 대신 막힌 근거를 붙여 보여 준다.
    blocked_out = [{**banned_rows[pid], "number": 0, "score": 0.0, "reason": "",
                    # 근거 문장을 같이 넣는다. 근거 없는 차단은 사람이 못 고친다.
                    "blocked": True, "blocked_reason": reason_for(pid)}
                   # 카드 정보를 못 읽은 아이디는 건너뛴다.
                   for pid in banned_ids if pid in banned_rows]

    # 후보, 막힌 것, 쓴 필터 이름 셋을 함께 돌려준다.
    return out, blocked_out, filter_used


# 후기로 비슷한 후기를 찾는다. 낱말이 안 겹쳐도 뜻이 통하면 찾아온다
def search_reviews(text, k=5, exclude_customer_id=None):
    # 저장소가 float32 행렬을 쓰므로 같은 형태로 맞춰 넘긴다.
    query_vector = np.asarray(get_embeddings().embed_query(text), dtype="float32")

    # 아래에서 같은 글과 본인 후기를 걸러 내므로 넉넉히 받아 둔다.
    found = get_store().search("review", query_vector, k + 60)
    # 하나도 못 찾았으면 더 할 일이 없다.
    if not found:
        # 빈 목록을 준다.
        return []

    # 찾은 구매 번호의 후기 내용을 한 번에 읽는다.
    rows = purchase_repo.find_reviews([purchase_id for purchase_id, _ in found])

    # 결과 목록과, 이미 나온 글을 담아 둘 집합이다. 질문 글 자체도 넣어 둔다.
    out, seen = [], {(text or "").strip()}
    # 점수가 높은 것부터 하나씩 본다.
    for purchase_id, score in found:
        # 그 구매의 후기 정보를 꺼낸다.
        row = rows.get(purchase_id)
        # 못 읽었거나 본인이 쓴 후기면 건너뛴다.
        if row is None or row["customer_id"] == exclude_customer_id:
            # 다음 후보로 넘어간다.
            continue
        # 앞뒤 공백을 뗀 본문으로 같은 글인지 비교한다.
        body = (row["review"] or "").strip()
        # 이미 나온 글이면 또 보여 주지 않는다.
        if body in seen:
            # 다음 후보로 넘어간다.
            continue
        # 이 글을 봤다고 적어 둔다.
        seen.add(body)
        # 화면에 줄 모양으로 담는다.
        out.append({"purchase_id": purchase_id,
                    # 어떤 상품의 후기인지 이름을 같이 준다.
                    "product_name": row["product_name"],
                    # 그 후기의 별점이다.
                    "rating": row["rating"],
                    # 점수는 소수점 넷째 자리까지만 보여 준다.
                    "score": round(score, 4),
                    # 밖으로 나가는 글이므로 개인정보를 가린다.
                    "review": mask_text(row["review"] or "")})
        # 원하는 개수를 채웠으면 더 볼 필요가 없다.
        if len(out) == k:
            # 반복을 멈춘다.
            break
    # 걸러 낸 뒤 남은 후기 목록을 돌려준다.
    return out


# 질문으로 조각을 찾고 원문 섹션을 같이 들고 온다 (small-to-big)
def search_chunks(question, k=4, product_ids_only=None):
    # 저장소가 float32 행렬을 쓰므로 같은 형태로 맞춰 넘긴다.
    query_vector = np.asarray(get_embeddings().embed_query(question), dtype="float32")
    # 벡터 저장소를 얻는다.
    store = get_store()

    # 안 좁히면 전체 조각이 대상이다.
    only_ids = None
    # 특정 상품으로 좁히라는 요청을 받았을 때다.
    if product_ids_only:
        # 그 상품들에 딸린 조각 아이디를 모은다.
        only_ids = store.chunk_ids_for_products(product_ids_only)
        # 딸린 조각이 하나도 없으면 찾을 것이 없다.
        if not only_ids:
            # 빈 목록을 준다.
            return []

    # 좁힌 범위 안에서 가까운 조각 k 개를 찾는다.
    found = store.search("chunk", query_vector, k, only_ids=only_ids)
    # 하나도 못 찾았으면 더 할 일이 없다.
    if not found:
        # 빈 목록을 준다.
        return []

    # 조각 옆에 베껴 둔 값을 한 번에 읽는다. 조각마다 따로 묻지 않는다.
    rows = store.fetch_payloads("chunk", [chunk_id for chunk_id, _ in found],
                                # 위에 정해 둔 네 컬럼만 읽는다.
                                CHUNK_PAYLOAD)

    # 화면과 프롬프트에 줄 목록이다.
    out = []
    # 점수가 높은 것부터 하나씩 본다.
    for chunk_id, score in found:
        # 그 조각의 베껴 둔 값을 꺼낸다.
        row = rows.get(chunk_id)
        # 못 읽었으면 건너뛴다.
        if row is None:
            # 다음 조각으로 넘어간다.
            continue
        # 어느 상품의 어느 섹션인지와 함께 담는다.
        out.append({"product_id": row["product_id"],
                    # 화면에 보일 상품 이름이다.
                    "product_name": row["product_name"],
                    # 그 조각이 속한 섹션 이름이다.
                    "section": row["section"],
                    # 점수는 소수점 넷째 자리까지만 보여 준다.
                    "score": round(score, 4),
                    # 찾은 것은 작은 조각이지만 돌려주는 것은 섹션 원문 전체다.
                    "text": row["section_text"]})
    # 찾은 자료 목록을 돌려준다.
    return out
