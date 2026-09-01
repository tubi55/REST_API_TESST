"""여러 API에서 공통으로 사용하는 인증과 사용량 검사를 제공한다."""

# 요청을 거절할 때 HTTP 상태와 함께 알리기 위해 사용한다.
from fastapi import HTTPException

# 지금 요청이 누구의 어느 기능인지 담는 trace 와 사용량을 세는 usage 다.
from app.core import trace, usage

# 토큰과 사용자 아이디를 확인하는 함수다. 여기서 다시 내보낸다.
from app.core.auth import caller

# 상품 쓰기 문이 열려 있는지 정한 설정값이다.
from app.core.config import PRODUCT_WRITE_ENABLED


# 이 요청이 누구의 무슨 기능인지 남긴다. 관측 콜백과 임베딩기가 이걸 보고 기록한다
def meter(user, feature):
    # 쿼터를 안 세는 기능은 칸을 잡지 않고 맥락만 남긴다.
    trace.set_context(user, feature)


# LLM 을 부르기 전에 통과해야 하는 관문. 잡아 둔 칸의 번호를 돌려준다
def guard(user, feature):
    # 쿼터가 남아 있을 때만 한 칸을 잡는다. 다 썼으면 None 이 온다.
    log_id = usage.reserve(user, feature)
    # 못 잡았으면 오늘 쓸 수 있는 양을 다 쓴 것이다.
    if log_id is None:
        # 몇 번 썼는지 보여 주려고 다시 센다.
        used = usage.used_today(user)
        # 429 는 너무 많이 불렀다는 뜻의 상태 코드다.
        raise HTTPException(
            # 상태 코드를 숫자로 적는다.
            status_code=429,
            # 얼마나 썼고 한도가 얼마인지 같이 알려 준다.
            detail=f"오늘 사용량을 다 썼다 ({used}/{usage.DAILY_QUOTA}). 내일 다시.")
    # 잡아 둔 칸 번호를 맥락에 담아 둔다. 호출이 끝나면 관측 콜백이 그 칸을 채운다.
    trace.set_context(user, feature, log_id=log_id)
    # 부르는 쪽도 이 번호로 직접 정산할 수 있게 돌려준다.
    return log_id


# 상품 쓰기 문이 열려 있나. 닫혀 있으면 405
def writable():
    # 설정으로 꺼 두면 만들기 · 고치기 · 지우기를 막는다.
    if not PRODUCT_WRITE_ENABLED:
        # 405 는 이 주소에 그 방법은 쓸 수 없다는 뜻이다.
        raise HTTPException(
            # 상태 코드를 숫자로 적는다.
            status_code=405,
            # 왜 막혔는지와 함께 대신 쓸 수 있는 길을 알려 준다.
            detail="상품 쓰기 API 가 꺼져 있다. 상품 원본은 이 서버가 소유하지 않는다. "
                   # 벡터만 맞추고 싶을 때 부를 주소다.
                   "벡터를 맞추려면 POST /api/products/{id}/reindex 를 쓴다")


# 라우터가 쓰는 이름 넷이다. caller 는 여기서 다시 내보내는 것이다.
__all__ = ["caller", "guard", "meter", "writable"]
