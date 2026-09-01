"""HTTP 헤더의 서비스 토큰과 사용자 ID를 확인한다."""

# 토큰을 안전하게 비교하기 위해 사용한다.
import secrets

# 헤더를 받아 오고 인증 실패를 HTTP 오류로 알리기 위해 사용한다.
from fastapi import Header, HTTPException, status

# 운영 환경인지 여부와 환경변수를 읽는 함수를 가져온다.
from app.core.config import IS_PROD, env

# 개발할 때만 쓰는 기본 토큰이다. 소스에 그대로 적혀 있어 비밀이 아니다.
DEV_TOKEN = "dev-token"

# 실제로 확인할 토큰이다. 환경변수로 주지 않으면 개발용 값을 쓴다.
SERVICE_TOKEN = env("API_TOKEN", DEV_TOKEN)

# 운영에서 기본값을 그대로 쓰면 아무나 통과하는 것과 같다.
if IS_PROD and SERVICE_TOKEN == DEV_TOKEN:
    # 그래서 서버가 뜨기 전에 멈춘다.
    raise RuntimeError(
        # 무엇이 문제인지 먼저 말한다.
        "APP_ENV=prod 인데 API_TOKEN 이 기본값이다. 이 값은 공개돼 있어 인증이 없는 것과 같다. "
        # 그리고 무엇을 해야 하는지 적는다.
        "앞단 서버만 아는 값으로 API_TOKEN 을 정할 것")


# 사용자 아이디로 받아 줄 최대 글자 수다.
MAX_USER_ID = 64

# HTTP 헤더에는 ASCII 글자만 실을 수 있다.
if not SERVICE_TOKEN.isascii():
    # 한글이나 이모지가 섞이면 요청 자체가 안 나가므로 뜰 때 잡는다.
    raise RuntimeError(
        # 무엇이 문제이고 어떻게 고쳐야 하는지 한 줄로 알려 준다.
        "API_TOKEN 에 ASCII 아닌 글자가 있다. HTTP 헤더로 보낼 수 없다. 영문·숫자로 바꿀 것")


# 서비스 토큰을 확인한다. 틀리면 401
def _check_token(authorization):
    # 헤더 자체가 없으면 인증을 시도하지도 않은 것이다.
    if not authorization:
        # 401 은 누구인지 밝히지 않았다는 뜻이다.
        raise HTTPException(
            # 상태 코드를 이름으로 적어 무슨 뜻인지 드러낸다.
            status_code=status.HTTP_401_UNAUTHORIZED,
            # 화면이나 호출한 쪽에 보일 설명이다.
            detail="서비스 토큰이 필요하다",
            # 어떤 방식으로 인증해야 하는지 알려 주는 표준 헤더다.
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 'Bearer 토큰값' 을 첫 빈칸에서 갈라 앞뒤를 나눈다.
    scheme, _, token = authorization.partition(" ")
    # 토큰 값 앞뒤의 공백을 떼어 낸다.
    token = token.strip()
    # 앞이 Bearer 가 아니거나 토큰이 비어 있으면 모양이 틀린 것이다.
    if scheme.lower() != "bearer" or not token:
        # 모양을 알려 주고 거절한다.
        raise HTTPException(
            # 인증이 안 됐다는 뜻의 상태 코드다.
            status_code=status.HTTP_401_UNAUTHORIZED,
            # 올바른 모양을 그대로 보여 준다.
            detail="Authorization 은 'Bearer <토큰>' 모양이어야 한다",
            # 인증 방식을 알려 주는 표준 헤더다.
            headers={"WWW-Authenticate": "Bearer"},
        )

    # compare_digest 는 글자가 몇 개까지 맞았는지 시간으로 새어 나가지 않게 비교한다.
    if not secrets.compare_digest(token, SERVICE_TOKEN):
        # 틀린 토큰이면 거절한다.
        raise HTTPException(
            # 인증이 안 됐다는 뜻의 상태 코드다.
            status_code=status.HTTP_401_UNAUTHORIZED,
            # 어디가 틀렸는지는 알려 주지 않는다.
            detail="서비스 토큰이 맞지 않는다",
            # 인증 방식을 알려 주는 표준 헤더다.
            headers={"WWW-Authenticate": "Bearer"},
        )


# 앞단이 말해 준 사용자 id. 없거나 모양이 이상하면 400
def _check_user_id(x_user_id):
    # 헤더가 없으면 빈 문자열로 두고 앞뒤 공백을 떼어 낸다.
    user_id = (x_user_id or "").strip()
    # 비어 있으면 누구의 요청인지 알 수 없다.
    if not user_id:
        # 400 은 보낸 요청 자체가 잘못됐다는 뜻이다.
        raise HTTPException(
            # 요청이 잘못됐다는 상태 코드다.
            status_code=status.HTTP_400_BAD_REQUEST,
            # 왜 필요한지까지 적어 준다.
            detail="X-User-Id 헤더가 필요하다. 앞단 서버가 누구를 대신해 부르는지 알려야 한다")
    # 너무 길거나, ASCII 가 아니거나, 눈에 안 보이는 글자가 섞이면 거절한다.
    if len(user_id) > MAX_USER_ID or not user_id.isascii() or not user_id.isprintable():
        # 기록의 열쇠로 쓰는 값이라 모양을 좁게 잡는다.
        raise HTTPException(
            # 요청이 잘못됐다는 상태 코드다.
            status_code=status.HTTP_400_BAD_REQUEST,
            # 허용 범위를 숫자까지 알려 준다.
            detail=f"X-User-Id 는 출력 가능한 ASCII {MAX_USER_ID}자 이내여야 한다")
    # 검사를 통과한 값을 돌려준다.
    return user_id


# 이 요청을 누구를 대신해 부르고 있나. 쿼터와 비용 기록이 이 값을 열쇠로 쓴다
def caller(authorization: str = Header(None),
           # Header(None) 은 이 헤더를 받되 없으면 None 으로 두라는 뜻이다.
           x_user_id: str = Header(None)) -> str:
    # 먼저 서비스 토큰이 맞는지 본다. 틀리면 여기서 멈춘다.
    _check_token(authorization)
    # 그다음 사용자 아이디를 확인해서 돌려준다.
    return _check_user_id(x_user_id)
