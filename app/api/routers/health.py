"""서버 상태와 실제 요청을 처리할 준비가 되었는지 확인하는 API를 제공한다."""

# DB 파일 경로에서 파일 이름만 떼어 내기 위해 사용한다.
import os

# 라우터를 만들고, 의존성을 붙이고, 응답 상태를 바꾸기 위해 사용한다.
from fastapi import APIRouter, Depends, Response, status

# 토큰과 사용자 아이디를 확인하는 함수다.
from app.api.dependencies import caller

# 오늘 쓴 양을 세는 모듈이다.
from app.core import usage

# 지금 무슨 모델과 어느 DB 로 도는지 알려 줄 설정값들이다.
from app.core.config import DB_PATH, EMBED_MODEL, LLM_MODEL, USE_API

# 각 항목이 준비됐는지 보는 모듈이다.
from app.features import readiness

# 응답의 모양을 정해 둔 네 가지다.
from app.features.schemas import ConfigInfo, HealthInfo, ReadyInfo, UsageInfo

# 이 파일의 주소들을 묶는다. tags 는 자동 문서에서 묶어 보여 줄 이름이다.
router = APIRouter(tags=["상태"])


# 프로세스가 살아 있나. 감시 도구가 부르므로 토큰 없이 열어 둔다.
@router.get("/health", response_model=HealthInfo)
def health():
    # 답할 수 있다는 것 자체가 살아 있다는 뜻이다.
    return {
        # 상용 API 인지 로컬인지 같이 알려 준다.
        "ok": True, "backend": "api" if USE_API else "local",
        # 경로 전체가 아니라 파일 이름만 준다. 서버 폴더 구조를 밖에 흘리지 않는다.
        "llm": LLM_MODEL, "embed": EMBED_MODEL, "db": os.path.basename(DB_PATH)
    }


# 받을 준비가 됐나. 아직이면 503 이다. 감시 도구가 부르므로 토큰 없이 열어 둔다
@router.get("/ready", response_model=ReadyInfo)
def ready(response: Response):
    # 항목별 결과와 전체 판정을 함께 받는다.
    checks, ok = readiness.check()
    # 하나라도 준비가 안 됐으면 상태 코드를 바꾼다.
    if not ok:
        # 503 은 아직 받을 수 없다는 뜻이다. 배포 도구가 이걸 보고 기다린다.
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    # 무엇이 준비됐고 무엇이 안 됐는지 그대로 보여 준다.
    return {"ready": ok, "checks": checks}


# 오늘 이 사용자가 쓴 양과 하루 한도
@router.get("/api/usage", response_model=UsageInfo)
def my_usage(user: str = Depends(caller)):
    # Depends(caller) 가 토큰을 확인하고 사용자 아이디를 넣어 준다.
    return {"used_today": usage.used_today(user), "quota": usage.DAILY_QUOTA}


# 지금 무슨 모델과 어느 DB 로 도는지. 화면이 표시한다
@router.get("/api/config", response_model=ConfigInfo)
def config(user: str = Depends(caller)):
    # 화면 아래에 그대로 띄우는 값들이다.
    return {
        # 지금 쓰는 두 모델 이름이다.
        "llm": LLM_MODEL, "embed": EMBED_MODEL,
        # /health 와 달리 여기는 사람이 읽을 말로 준다.
        "backend": "상용 API" if USE_API else "로컬",
        # 경로 전체가 아니라 파일 이름만 준다.
        "db": os.path.basename(DB_PATH)
    }
