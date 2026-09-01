"""질문을 받아 답변을 NDJSON 형식으로 한 줄씩 전송한다."""

# 한 줄짜리 JSON 을 만들기 위해 사용한다.
import json

# 스트리밍이 실패한 이유를 남기기 위해 사용한다.
import logging

# 라우터를 만들고 의존성을 붙이기 위해 사용한다.
from fastapi import APIRouter, Depends

# 답을 다 만들기 전에 조금씩 흘려보내는 응답 종류다.
from fastapi.responses import StreamingResponse

# 인증과 쿼터 관문이다.
from app.api.dependencies import caller, guard

# 사용량을 정산하는 모듈이다.
from app.core import usage

# 모델 이름이 안 왔을 때 대신 쓸 설정값이다.
from app.core.config import LLM_MODEL

# 답을 만드는 모듈과 조회를 모아 둔 모듈이다.
from app.features import answering, retrieve

# 요청의 모양을 정해 둔 것이다.
from app.features.schemas import AskRequest

# 이 파일에서 남기는 기록에 모듈 이름을 붙여 준다.
log = logging.getLogger(__name__)

# 이 파일의 주소는 /api 로 시작한다.
router = APIRouter(prefix="/api", tags=["질의응답"])


# 질문 하나를 받아 경로 · 출처 · 본문을 NDJSON 으로 흘려보낸다
@router.post("/ask")
def ask(request: AskRequest, user: str = Depends(caller)):
    # 쿼터를 한 칸 먼저 잡는다. 다 썼으면 여기서 429 로 끝난다.
    log_id = guard(user, "ask")

    # 고객을 지정했을 때만 그 고객의 판을 읽는다.
    board = retrieve.dashboard(request.customer_id) if request.customer_id else None
    # 상품 문서를 찾을 질문인지 고객 분석 질문인지 가른다.
    kind = answering.route(request.question)

    # 막힌 상품과 추천 후보를 담을 자리다. 상품 질문이면 비어 있다.
    blocked, cands = [], []
    # 상품 질문이면 문서 조각에서 근거를 찾는다.
    if kind == "product":
        # 전체 조각에서 가까운 셋을 찾는다.
        sources = retrieve.search_chunks(request.question, k=3)
    # 고객 분석 질문일 때다.
    else:
        # 고객을 안 지정했으면 근거 자료 없이 답한다.
        sources = []
        # 고객을 지정했을 때만 후보를 뽑는다.
        if request.customer_id:
            # 쓴 필터 이름은 여기서 안 쓰므로 밑줄 이름으로 받는다.
            picked, blocked, _used = retrieve.candidates(request.customer_id)
            # 프롬프트에 넣을 후보는 앞의 다섯 개로 자른다.
            cands = picked[:5]
            # 후보가 있을 때만 그 상품들로 자료를 좁혀 찾는다.
            if cands:
                # 후보와 상관없는 문서가 근거로 섞이지 않게 한다.
                sources = retrieve.search_chunks(
                    # 같은 질문으로 셋을 찾는다.
                    request.question, k=3,
                    # 이 상품들에 딸린 조각 안에서만 찾는다.
                    product_ids_only=[row["product_id"] for row in cands])

    # 모델이 쓴 토큰과 시간을 받아 담을 그릇이다.
    meter = {}

    # 이 안에서 yield 한 것이 한 줄씩 밖으로 나간다.
    def generate():
        # 첫 줄로 어느 경로를 탔는지 알려 준다. ensure_ascii=False 라야 한글이 그대로 간다.
        yield json.dumps({"type": "route", "kind": kind}, ensure_ascii=False) + "\n"
        # 둘째 줄로 근거 자료를 먼저 보낸다. 본문보다 앞서 화면에 뜬다.
        yield json.dumps({"type": "sources", "sources": sources},
                         # NDJSON 은 한 줄에 JSON 하나라 줄바꿈을 붙인다.
                         ensure_ascii=False) + "\n"
        # 모델 호출이 중간에 끊길 수 있다.
        try:
            # 모델이 흘려보내는 글자 조각을 하나씩 받는다.
            for piece in answering.stream(request.question, sources=sources, board=board,
                                    # 막힌 상품과 후보, 사용량 그릇을 같이 넘긴다.
                                    blocked=blocked, cands=cands, meter=meter):
                # 조각 하나를 한 줄짜리 JSON 으로 만들어 내보낸다.
                yield json.dumps({"type": "delta", "text": piece},
                                 # 한글이 그대로 나가게 하고 줄바꿈을 붙인다.
                                 ensure_ascii=False) + "\n"
        # 어떤 오류든 잡는다. 이미 응답이 나가기 시작해 상태 코드를 못 바꾼다.
        except Exception:
            # 무엇이 터졌는지는 서버 기록에만 남긴다.
            log.exception("답변 스트리밍이 실패했다 (user=%s)", user)
            # 화면에는 짧은 말만 보낸다.
            yield json.dumps({"type": "error", "message": "답을 만들지 못했다"},
                             # 한글이 그대로 나가게 하고 줄바꿈을 붙인다.
                             ensure_ascii=False) + "\n"

        # 정산이 실패해도 답은 이미 나갔으므로 요청을 깨뜨리지 않는다.
        try:
            # 모델 이름이 안 왔으면 설정값을 대신 쓴다.
            usage.settle(log_id, model=meter.get("model") or LLM_MODEL,
                         # 그릇에 담긴 토큰 수를 꺼낸다. 없으면 None 이다.
                         in_tokens=meter.get("in"), out_tokens=meter.get("out"),
                         # 걸린 시간도 같이 적는다.
                         seconds=meter.get("seconds"))
        # 어떤 오류든 잡는다.
        except Exception:
            # 어느 칸을 못 채웠는지 기록에 남긴다.
            log.exception("사용량 정산에 실패했다 (log_id=%s, user=%s)", log_id, user)

        # 마지막 줄로 다 끝났다고 알린다. 화면이 이 줄을 보고 마무리한다.
        yield json.dumps({"type": "done"}, ensure_ascii=False) + "\n"

    # 한 줄에 JSON 하나라는 뜻의 형식 이름을 붙여 내보낸다.
    return StreamingResponse(generate(), media_type="application/x-ndjson")
