"""상품 상세 문서와 문서에서 나눈 조각을 조회한다."""

# 표를 바꾸는 execute, 한 줄만 읽는 one, 여러 줄을 읽는 query 를 가져온다.
from app.core.db import execute, one, query


# 주의사항 섹션 전부. 안전 필터가 금지 목록을 만드는 재료다
def caution_sections():
    # 섹션 이름을 '?' 자리로 넘겨 SQL 글자에 직접 섞지 않는다.
    return query("SELECT product_id, text FROM sections WHERE section = ?",
                 # 값이 하나여도 튜플이어야 하므로 뒤에 쉼표를 붙인다.
                 ("주의사항",))


# 이 상품의 조각 번호들. 벡터를 지우거나 베껴 둔 값을 고칠 때 쓴다
def chunk_ids_for_product(product_id):
    # 벡터 저장소가 아이디를 글자로 다루므로 여기서도 글자로 맞춘다.
    return [str(row[0]) for row in
            # 이 상품에 딸린 조각 번호만 읽는다.
            query("SELECT chunk_id FROM chunks WHERE product_id = ?", (product_id,))]


# 이 상품의 상세 파생물을 전부 지운다
def delete_for_product(product_id):
    # 조각을 먼저 지운다.
    execute("DELETE FROM chunks WHERE product_id = ?", (product_id,))
    # 섹션을 지운다.
    execute("DELETE FROM sections WHERE product_id = ?", (product_id,))
    # 마지막으로 상세 원문을 지운다.
    execute("DELETE FROM product_details WHERE product_id = ?", (product_id,))


# 그 상품의 그 섹션 원문. 없으면 None
def find_section(product_id, section):
    # 상품과 섹션 이름이 둘 다 맞는 줄 하나를 찾는다.
    row = one("SELECT text FROM sections WHERE product_id = ? AND section = ?",
              # 두 값을 '?' 가 나오는 순서대로 넘긴다.
              (product_id, section))
    # 줄이 있으면 첫 칸인 본문을, 없으면 None 을 준다.
    return row[0] if row else None
