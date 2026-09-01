"""데이터를 임베딩에 사용할 텍스트로 바꾼다."""

# 글의 지문을 만들기 위해 사용한다.
import hashlib

# 값이 몇 번 나왔는지 세기 위해 사용한다.
from collections import Counter

# 함수가 어떤 값을 받고 주는지 적어 두기 위해 사용한다.
from typing import Any, Mapping

# 상품 문장을 만들 때 쓰는 컬럼 이름과 그 순서다.
PRODUCT_FIELDS = ("name", "brand", "category", "price", "skin_type",
                  # 뒤쪽 다섯 개는 성분과 고민, 태그, 설명이다.
                  "ingredient", "concern", "tags", "description")


# 상품 한 건을 검색용 문장 하나로 만든다
def product_text(row: Mapping[str, Any] | tuple) -> str:
    # 딕셔너리로 들어오면 위에 적어 둔 순서대로 값을 꺼내 튜플로 바꾼다.
    if isinstance(row, Mapping):
        # 이렇게 하면 아래 코드는 딕셔너리든 튜플이든 같은 방식으로 다룬다.
        row = tuple(row[field] for field in PRODUCT_FIELDS)

    # 아홉 개의 값을 한 번에 각각의 이름으로 받는다.
    name, brand, category, price, skin_type, ingredient, concern, tags, desc = row
    # 가운뎃점으로 이어 붙여 사람이 읽을 수 있는 한 줄로 만든다.
    return (f"{name} · {brand} · {category} · {price}원 · {skin_type} · "
            # 나머지 값도 같은 방식으로 이어 붙인다.
            f"{ingredient} · {concern} · {tags} · {desc}")


# 값 목록에서 제일 자주 나온 n 개를 가운뎃점으로 잇는다
def top(values: list[str], n: int = 3) -> str:
    # most_common 은 (값, 횟수) 를 많은 순으로 준다. 횟수는 안 쓰므로 밑줄로 받는다.
    return " · ".join(value for value, _ in Counter(values).most_common(n))


# 고객 한 명의 구매 이력을 취향 한 줄로 줄인다
def customer_text(skin_type: str, purchases: list[tuple]) -> str:
    # 각 구매의 마지막 칸이 별점이다. 앞의 값들은 *_ 로 한꺼번에 버린다.
    ratings = [rating for *_, rating in purchases]
    # 피부 타입과 자주 산 카테고리를 먼저 적는다.
    return (f"{skin_type} 피부 · 선호 카테고리 {top([p[1] for p in purchases])} · "
            # 두 번째 칸에서 성분을 모아 자주 나온 것을 적는다.
            f"자주 쓴 성분 {top([p[2] for p in purchases])} · "
            # 세 번째 칸에서 고민을 모아 자주 나온 것을 적는다.
            f"관심 고민 {top([p[3] for p in purchases])} · "
            # 평균 별점은 소수점 한 자리까지만 적는다.
            f"평균 별점 {sum(ratings) / len(ratings):.1f}")


# 임베딩에 넣은 글의 지문. 이 값이 그대로면 벡터를 다시 만들지 않는다
def source_hash(text: str) -> str:
    # 글이 조금만 달라도 값이 크게 바뀐다. 앞 16글자만 써도 서로 겹치지 않는다.
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:16]
