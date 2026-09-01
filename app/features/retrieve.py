"""정형 데이터 조회와 벡터 검색 함수를 한곳에 모아 제공한다."""

# 고객 목록과 대시보드를 만드는 함수들이다.
from app.features.profile import customer_list, dashboard

# 벡터로 찾는 함수들을 가져온다.
from app.features.searching import (
    # 추천 후보를 몇 개까지 볼지 정한 값이다.
    N_CANDIDATES,
    # 고객에게 맞는 상품 후보를 뽑는 함수다.
    candidates,
    # 문서 조각을 찾는 함수다.
    search_chunks,
    # 후기를 찾는 함수다.
    search_reviews,
)

# 이 모듈에서 밖으로 내보내는 이름들이다. 부르는 쪽은 여기만 보면 된다.
__all__ = ["N_CANDIDATES", "candidates", "customer_list", "dashboard",
           # 이름 순서로 적어 두면 빠진 것을 찾기 쉽다.
           "search_chunks", "search_reviews"]
