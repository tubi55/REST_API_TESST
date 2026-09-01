"""고객 기본 정보와 구매 이력을 한 번에 조회할 수 있게 모은다."""

# 사전을 붙여 개인정보를 지우는 함수다.
from app.features.privacy import mask_text

# 고객 표와 구매 표에 닿는 저장소를 얻는 함수들이다.
from app.repositories import get_customer_repo, get_purchase_repo

# 이 파일에서 계속 쓸 고객 저장소를 한 번만 잡아 둔다.
customer_repo = get_customer_repo()

# 이 파일에서 계속 쓸 구매 저장소를 한 번만 잡아 둔다.
purchase_repo = get_purchase_repo()


# 고객 목록과 각자 구매 건수
def customer_list():
    # 세는 일은 SQL 이 한다. 여기서는 그대로 넘겨준다.
    return customer_repo.list_with_counts()


# 한 고객의 프로필 · 구매 이력 · 집계. 없으면 None
def dashboard(customer_id):
    # 먼저 그런 고객이 있는지 본다.
    profile = customer_repo.find_profile(customer_id)
    # 없으면 뒤 작업을 할 이유가 없다.
    if profile is None:
        # 부르는 쪽이 None 을 보고 404 로 바꾼다.
        return None

    # 그 고객의 구매 이력을 최근 것부터 읽는다.
    purchases = purchase_repo.find_by_customer(customer_id)

    # 후기에는 이름과 연락처가 섞여 있을 수 있다.
    for row in purchases:
        # 가린 글을 따로 담는다. 원문은 그대로 두고 나가는 쪽에서만 가린 것을 쓴다.
        row["review_masked"] = mask_text(row["review"] or "")

    # 카테고리별로 몇 건을 샀는지 셀 딕셔너리다.
    by_category = {}
    # 구매를 하나씩 보면서 센다.
    for row in purchases:
        # 처음 보는 카테고리면 get 이 0 을 주므로 거기서 1 이 된다.
        by_category[row["category"]] = by_category.get(row["category"], 0) + 1

    # 별점이 비어 있는 구매는 평균에서 뺀다.
    ratings = [row["rating"] for row in purchases if row["rating"] is not None]
    # 화면 한 장에 필요한 값을 한 덩어리로 만들어 돌려준다.
    return {
        # 별표 두 개는 프로필의 값을 그대로 펼쳐 넣는다는 뜻이다.
        "customer": {**profile, "n_purchases": len(purchases)},
        # 별점이 하나도 없으면 0으로 나누게 되므로 None 으로 둔다.
        "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        # 산 상품 가격을 모두 더한 값이다.
        "total_spent": sum(row["price"] for row in purchases),
        # 위에서 센 카테고리별 건수다.
        "by_category": by_category,
        # 후기를 가린 값이 붙은 구매 이력 전체다.
        "purchases": purchases,
    }
