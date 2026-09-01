"""내부 오류를 알맞은 HTTP 상태 코드와 메시지로 바꾼다."""

# 오류를 HTTP 응답으로 바꿔 주는 예외다.
from fastapi import HTTPException

# 거부 종류를 HTTP 상태 코드로 옮기는 표다. 여기 없으면 400 으로 본다.
STATUS = {"not_found": 404, "conflict": 409, "validation": 422}


# 상품 CRUD 의 ProductError 를 HTTPException 으로
def product_http(exc):
    # 화면이 종류를 보고 다르게 처리할 수 있게 두 값을 같이 담는다.
    detail = {"kind": exc.kind, "message": exc.message}
    # 어느 칸 때문인지 알 때만 그 이름도 담는다.
    if exc.field:
        # 화면이 그 칸에 바로 표시할 수 있다.
        detail["field"] = exc.field
    # 표에 없는 종류면 400 으로 둔다.
    return HTTPException(status_code=STATUS.get(exc.kind, 400), detail=detail)
