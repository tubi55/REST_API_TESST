"""고객 데이터를 조회하고 고객 관련 기능에 제공한다."""

# 컬럼 이름이 붙은 dicts 와 튜플로 받는 query 를 가져온다.
from app.core.db import dicts, query


# 한 명의 프로필. 없으면 None
def find_profile(customer_id):
    # 필요한 컬럼만 골라 읽는다. 별표로 전부 읽지 않는다.
    rows = dicts("""
        SELECT customer_id, name, age, gender, skin_type, city
        FROM customers WHERE customer_id = ?
    """, (customer_id,))
    # 한 명만 찾는 질의이므로 첫 줄만 준다. 없으면 None 이다.
    return rows[0] if rows else None


# 고객 목록과 각자 구매 건수
def list_with_counts():
    # LEFT JOIN 이라 구매가 하나도 없는 고객도 목록에 남는다.
    return dicts("""
        SELECT customers.customer_id, customers.name, customers.age, customers.gender,
               customers.skin_type, customers.city,
               COUNT(purchases.purchase_id) AS n_purchases
        FROM customers
        LEFT JOIN purchases ON purchases.customer_id = customers.customer_id
                           AND purchases.is_holdout = 0
        GROUP BY customers.customer_id
        ORDER BY customers.customer_id
    """)


# 마스킹 사전에 쓸 이름들. NULL 과 빈 칸은 여기서 거른다
def distinct_names():
    # 결과가 (이름,) 모양의 한 칸짜리 줄이라 괄호로 풀어 받는다.
    return [name for (name,) in query(
        # DISTINCT 는 같은 이름을 한 번만 준다.
        "SELECT DISTINCT name FROM customers WHERE name IS NOT NULL AND name != ''")]


# 마스킹 사전에 쓸 도시들
def distinct_cities():
    # 이름과 같은 방식으로 도시 이름만 뽑는다.
    return [city for (city,) in query(
        # 값이 없거나 빈 칸인 줄은 사전에 넣지 않는다.
        "SELECT DISTINCT city FROM customers WHERE city IS NOT NULL AND city != ''")]


# 고객 아이디 전부. 아이디 순. 채점 도구가 전수를 돌 때 쓴다
def all_ids():
    # 아이디 한 칸만 읽어 목록으로 만든다.
    return [cid for (cid,) in query(
        # 채점 결과가 흔들리지 않게 아이디 순으로 고정한다.
        "SELECT customer_id FROM customers ORDER BY customer_id")]
