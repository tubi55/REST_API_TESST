"""서버 시작 시 DB와 모델을 사용할 수 있도록 미리 준비한다."""

# 미리 읽지 못한 것을 기록으로 남기기 위해 사용한다.
import logging

# 뜰 때와 내려갈 때를 한 함수로 묶기 위해 사용한다.
from contextlib import asynccontextmanager

# 표 모양을 바꾼 시각을 적기 위해 사용한다.
from datetime import datetime

# 벡터 저장소 객체를 얻는 함수다.
from app.adapters.stores import get_store

# 임베딩기를 미리 올리는 embedder 와 사용량을 쌓는 usage 다.
from app.core import embedder, usage

# 표 모양을 맞추는 함수와 사용 기록 저장소를 얻는 함수다.
from app.repositories import apply_migrations, get_usage_repo

# 이 파일에서 남기는 기록에 모듈 이름을 붙여 준다.
log = logging.getLogger(__name__)

# 뜰 때 미리 읽어 둘 벡터 종류들이다.
WARM_KINDS = ("chunk", "product", "customer", "review")


# 뜰 때 표 모양을 맞추고 벡터와 임베딩기를 미리 올린다
@asynccontextmanager
async def lifespan(app):
    # usage 모듈이 어느 표에 쌓을지 여기서 붙여 준다.
    usage.use_repository(get_usage_repo())

    # 아직 안 돈 표 모양 바꾸기만 돌린다.
    applied = apply_migrations(datetime.now().isoformat(timespec="seconds"))
    # 실제로 뭔가 돌았을 때만 기록을 남긴다.
    if applied:
        # 무엇이 돌았는지 이름을 이어 붙여 남긴다.
        log.info("표 모양을 맞췄다: %s", ", ".join(applied))

    # 벡터 저장소를 얻는다.
    store = get_store()
    # 네 종류를 하나씩 미리 읽는다.
    for kind in WARM_KINDS:
        # 한 종류가 실패해도 서버는 떠야 한다.
        try:
            # 빈 아이디라 답은 늘 거짓이다. 노린 것은 표를 메모리에 올리는 일이다.
            store.has(kind, "")
        # 표가 아직 없는 등의 이유로 실패할 수 있다.
        except Exception as exc:
            # 왜 못 읽었는지 남기고 넘어간다.
            log.warning("%s 벡터를 미리 읽지 못했다: %s", kind, exc)

    # 모델도 첫 요청 밖에서 올려 둔다.
    try:
        # 안 그러면 449MB 짜리 모델을 첫 요청 안에서 올리게 된다.
        embedder.warm_up()
    # 모델을 못 올려도 서버는 떠야 한다.
    except Exception as exc:
        # 왜 못 올렸는지 남기고 넘어간다.
        log.warning("임베딩기를 미리 올리지 못했다: %s", exc)
    # 여기서 서버가 실제로 요청을 받는다. 내려갈 때 이 줄 다음이 이어진다.
    yield
