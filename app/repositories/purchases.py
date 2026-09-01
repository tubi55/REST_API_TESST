"""구매 이력과 후기를 조회한다."""

# 컬럼 이름이 붙은 dicts, 한 줄만 읽는 one, 튜플로 받는 query 를 가져온다.
from app.core.db import dicts, one, query


# 한 고객의 구매 이력. 최근 것부터
def find_by_customer(customer_id):
    # is_holdout = 0 은 채점용으로 숨겨 둔 구매를 빼고 본다는 뜻이다.
    return dicts("""
        SELECT products.product_id, products.name, products.category, products.price,
               purchases.purchased_at, purchases.rating, purchases.review
        FROM purchases
        JOIN products ON purchases.product_id = products.product_id
        WHERE purchases.customer_id = ? AND purchases.is_holdout = 0
        ORDER BY purchases.purchased_at DESC
    """, (customer_id,))


# 이미 산 상품 아이디들
def bought_product_ids(customer_id):
    # 중괄호로 감싸면 집합이 된다. 같은 상품을 두 번 사도 하나로 남는다.
    return {row[0] for row in query("""
        SELECT product_id FROM purchases
        WHERE customer_id = ? AND is_holdout = 0
    """, (customer_id,))}


# 이력에 있는 카테고리에 속하는 상품 아이디들
def history_category_product_ids(customer_id):
    # 괄호 안의 질의가 이 고객이 사 본 카테고리를 먼저 구하고, 바깥이 그 카테고리의 상품을 모은다.
    return {row[0] for row in query("""
        SELECT product_id FROM products WHERE category IN (
            SELECT products.category FROM purchases
            JOIN products ON purchases.product_id = products.product_id
            WHERE purchases.customer_id = ? AND purchases.is_holdout = 0)
    """, (customer_id,))}


# 이 구매 번호들의 후기. {구매번호: 행} 으로 돌려준다
def find_reviews(purchase_ids):
    # 번호가 없으면 DB 를 건드리지 않는다.
    if not purchase_ids:
        # 빈 딕셔너리를 주면 부르는 쪽이 그대로 돌 수 있다.
        return {}
    # 번호 개수만큼 IN 절의 '?' 를 만든다.
    marks = ", ".join("?" * len(purchase_ids))
    # 구매 번호를 열쇠로 삼아 한 번에 찾아 쓸 수 있게 딕셔너리로 만든다.
    return {row["purchase_id"]: row for row in dicts(f"""
        SELECT purchases.purchase_id, purchases.customer_id, purchases.rating,
               purchases.review, products.name AS product_name
        FROM purchases
        JOIN products ON products.product_id = purchases.product_id
        WHERE purchases.purchase_id IN ({marks})
    """, tuple(purchase_ids))}


# 이 상품이 몇 번 팔렸나. 지워도 되는지 정하는 재료다
def count_for_product(product_id):
    # COUNT 는 줄 하나에 칸 하나로 오므로 [0] 으로 숫자만 꺼낸다.
    return one("SELECT COUNT(*) FROM purchases WHERE product_id = ?", (product_id,))[0]


# 채점용으로 숨겨 둔 정답. {고객: 상품} 으로 돌려준다
def holdout_answers():
    # 두 칸짜리 줄 목록을 dict 로 감싸면 앞 칸이 열쇠, 뒤 칸이 값이 된다.
    return dict(query(
        # is_holdout = 1 인 구매가 채점할 때 맞혀야 할 정답이다.
        "SELECT customer_id, product_id FROM purchases WHERE is_holdout = 1"))
