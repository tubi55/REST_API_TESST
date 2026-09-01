"""요청별 실행 과정과 모델 사용 기록을 서로 섞이지 않게 관리한다."""

# 요청마다 값을 따로 두어 서로 섞이지 않게 하는 도구다.
import contextvars

# 기록 한 줄을 JSON 문자열로 만들 때 사용한다.
import json

# 파일을 밀지 못하는 등의 문제를 남길 때 사용한다.
import logging

# LangSmith 설정을 환경변수로 넘기기 위해 사용한다.
import os

# 호출에 걸린 시간을 재기 위해 사용한다.
import time

# 기록에 남길 지금 시각을 얻기 위해 사용한다.
from datetime import datetime

# 기록 파일 경로를 다루기 위해 사용한다.
from pathlib import Path

# 모델 호출의 시작과 끝에 끼어들 수 있게 해 주는 LangChain 기반 클래스다.
from langchain_core.callbacks import BaseCallbackHandler

# 사용량을 실제로 쌓는 모듈이다.
from app.core import usage

# 기록 파일 위치와 LangSmith 스위치를 설정에서 가져온다.
from app.core.config import (
    # 프롬프트와 답 전문까지 보낼지 정하는 스위치다.
    LANGSMITH_SEND_BODY,
    # LangSmith 를 켤지 정하는 스위치다.
    LANGSMITH_TRACING,
    # 호출 기록을 쌓을 파일 위치다.
    RUNS_PATH,
)

# 이 파일에서 남기는 기록에 모듈 이름을 붙여 준다.
log = logging.getLogger(__name__)

# 지금 처리 중인 요청이 누구의 어느 기능인지 담는 상자다. 요청마다 따로 존재한다.
CURRENT = contextvars.ContextVar("usage_context", default=None)


# 기록 파일이 이 크기를 넘으면 한 세대 밀어 둔다. 10MB 다.
MAX_RUNS_BYTES = 10 * 1024 * 1024


# 엔드포인트가 시작할 때 부른다. 아래 콜백이 이 값을 보고 사용량을 남긴다.
def set_context(user_id, feature, log_id=None):
    # 누구의 어느 기능인지, 미리 잡아 둔 줄 번호가 있는지를 담는다.
    CURRENT.set({"user_id": user_id, "feature": feature, "log_id": log_id})


# 응답에서 입력 토큰, 출력 토큰, 모델 이름을 꺼낸다
def tokens_of(response):
    # 응답에 붙는 사용량 정보다. 없으면 빈 딕셔너리로 둔다.
    token_usage = (response.llm_output or {}).get("token_usage") or {}
    # 실제 생성된 답이다. 없을 수도 있으므로 확인하고 꺼낸다.
    generation = response.generations[0][0] if response.generations else None
    # 모델마다 사용량이 붙는 자리가 달라 두 번째 자리도 본다.
    meta = getattr(getattr(generation, "message", None), "usage_metadata", None) or {}
    # 앞자리가 비면 뒷자리 값을 쓰는 식으로 셋을 모아 돌려준다.
    return (token_usage.get("prompt_tokens") or meta.get("input_tokens"),
            # 출력 토큰 수도 두 자리 중 값이 있는 쪽을 쓴다.
            token_usage.get("completion_tokens") or meta.get("output_tokens"),
            # 모델 이름은 응답 정보에만 붙어 있다.
            (response.llm_output or {}).get("model_name"))


# 맥락을 찾아 사용량을 남기는 판. 시작 시각을 run_id 로 나눠 담는다
class UsageWriter(BaseCallbackHandler):
    # 호출마다 시작 시각을 담아 둘 딕셔너리를 만든다.
    def __init__(self):
        # 열쇠는 run_id 이고 값은 시작 시각이다.
        self.started = {}

    # 모델 호출이 시작될 때 LangChain 이 이 함수를 부른다.
    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
        # 이 호출의 시작 시각을 run_id 로 구분해 담는다.
        self.started[run_id] = time.perf_counter()

    # 모델 호출이 끝나면 LangChain 이 이 함수를 부른다.
    def on_llm_end(self, response, *, run_id, **kwargs):
        # 담아 둔 시작 시각을 꺼내면서 지운다. 없으면 None 이다.
        started = self.started.pop(run_id, None)
        # 지금 요청의 맥락을 꺼낸다.
        ctx = CURRENT.get()
        # 요청 밖에서 부른 경우라 맥락이 없으면 남길 곳이 없다.
        if ctx is None:
            # 기록을 건너뛰고 끝낸다.
            return
        # 응답에서 토큰 수와 모델 이름을 꺼낸다.
        in_tokens, out_tokens, model = tokens_of(response)
        # 시작 시각을 못 받았으면 시간은 비워 둔다.
        seconds = round(time.perf_counter() - started, 2) if started else None

        # 쿼터 때문에 미리 잡아 둔 줄이 있는지 본다.
        log_id = ctx.get("log_id")
        # 있으면 새 줄을 넣지 않고 그 줄을 채운다.
        if log_id is not None:
            # 한 번만 채우도록 맥락에서 지운다. 같은 요청의 두 번째 호출은 새 줄로 간다.
            ctx["log_id"] = None
            # 모델 이름이 안 오면 로컬 모델로 본다.
            usage.settle(log_id, model=model or "qwen-cpu", in_tokens=in_tokens,
                         # 출력 토큰 수와 걸린 시간을 함께 적는다.
                         out_tokens=out_tokens, seconds=seconds)
            # 여기서 끝낸다. 아래 줄로 내려가면 두 번 적힌다.
            return

        # 미리 잡아 둔 줄이 없으면 새 줄로 남긴다.
        usage.record(ctx["user_id"], ctx["feature"], model=model or "qwen-cpu",
                     # 토큰 수와 걸린 시간을 함께 적는다.
                     in_tokens=in_tokens, out_tokens=out_tokens, seconds=seconds)

    # 호출이 실패했을 때 LangChain 이 이 함수를 부른다.
    def on_llm_error(self, error, *, run_id, **kwargs):
        # 담아 둔 시작 시각만 치운다. 안 치우면 계속 쌓인다.
        self.started.pop(run_id, None)


# 부른 쪽이 준 그릇에 사용량을 담아 주는 판. 맥락을 안 본다
class UsageCollector(BaseCallbackHandler):
    # 결과를 담을 딕셔너리를 밖에서 받아 둔다.
    def __init__(self, into):
        # 이 딕셔너리에 값을 채워 주면 부른 쪽이 바로 읽는다.
        self.into = into
        # 아직 시작하지 않았다는 뜻으로 None 을 둔다.
        self.started = None

    # 모델 호출이 시작될 때 부른다.
    def on_chat_model_start(self, serialized, messages, **kwargs):
        # 한 번에 하나만 다루므로 run_id 로 나누지 않는다.
        self.started = time.perf_counter()

    # 모델 호출이 끝나면 부른다.
    def on_llm_end(self, response, **kwargs):
        # 응답에서 토큰 수와 모델 이름을 꺼낸다.
        in_tokens, out_tokens, model = tokens_of(response)
        # 입력 토큰 수를 그릇에 담는다.
        self.into["in"] = in_tokens
        # 출력 토큰 수를 그릇에 담는다.
        self.into["out"] = out_tokens
        # 모델 이름을 그릇에 담는다.
        self.into["model"] = model
        # 시작 시각을 받았을 때만 걸린 시간을 담는다.
        if self.started:
            # 초 단위로 소수점 둘째 자리까지 남긴다.
            self.into["seconds"] = round(time.perf_counter() - self.started, 2)


# LLM 을 부를 때마다 runs.jsonl 에 한 줄씩 적는다. run_id 로 짝을 맞춘다
class JsonlTracer(BaseCallbackHandler):
    # 어느 파일에 적을지 정하고 시작 시각 상자를 만든다.
    def __init__(self, path=RUNS_PATH):
        # 문자열로 온 경로를 다루기 쉬운 형태로 바꾼다.
        self.path = Path(path)
        # 열쇠는 run_id 이고 값은 (시작 시각, 프롬프트 글자 수) 다.
        self.started = {}

    # 모델 호출이 시작될 때 부른다.
    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
        # 주고받은 메시지 중 글자로 된 것만 모아 하나로 잇는다.
        text = "\n".join(m.content for turn in messages for m in turn
                         # 그림 같은 다른 형식이 섞여 있으면 건너뛴다.
                         if isinstance(m.content, str))
        # 시작 시각과 프롬프트 글자 수를 run_id 로 구분해 담는다.
        self.started[run_id] = (time.perf_counter(), len(text))

    # 모델 호출이 끝나면 부른다.
    def on_llm_end(self, response, *, run_id, **kwargs):
        # 담아 둔 값을 꺼내면서 지운다. 없으면 기본값을 쓴다.
        started, n_prompt = self.started.pop(run_id, (None, 0))
        # 실제 생성된 답이다. 없을 수도 있다.
        generation = response.generations[0][0] if response.generations else None
        # 모델 이름은 여기서 안 쓰므로 밑줄 이름으로 받는다.
        in_tokens, out_tokens, _model = tokens_of(response)
        # 성공한 호출 한 줄을 만들어 적는다.
        self._write({
            # 언제 끝났는지 초 단위까지 적는다.
            "at": datetime.now().isoformat(timespec="seconds"),
            # 같은 호출을 나중에 찾을 수 있게 식별자를 적는다.
            "run_id": str(run_id),
            # 시작 시각을 못 받았으면 시간은 비워 둔다.
            "seconds": round(time.perf_counter() - started, 2) if started else None,
            # 보낸 프롬프트의 글자 수다.
            "prompt_chars": n_prompt,
            # 받은 답의 글자 수다. 답이 없으면 0 이다.
            "output_chars": len(generation.text) if generation else 0,
            # 입력 토큰 수다.
            "prompt_tokens": in_tokens,
            # 출력 토큰 수다.
            "completion_tokens": out_tokens,
            # 성공했다는 표시다.
            "ok": True,
        })

    # 호출이 실패했을 때 부른다.
    def on_llm_error(self, error, *, run_id, **kwargs):
        # 담아 둔 값을 꺼내면서 지운다.
        started, n_prompt = self.started.pop(run_id, (None, 0))
        # 실패한 호출도 한 줄로 남긴다.
        self._write({
            # 언제 실패했는지 적는다.
            "at": datetime.now().isoformat(timespec="seconds"),
            # 같은 호출을 찾을 수 있게 식별자를 적는다.
            "run_id": str(run_id),
            # 실패까지 걸린 시간이다.
            "seconds": round(time.perf_counter() - started, 2) if started else None,
            # 보낸 프롬프트의 글자 수다.
            "prompt_chars": n_prompt,
            # 실패했다는 표시다.
            "ok": False,
            # 오류 내용이 길 수 있으므로 앞 200글자만 남긴다.
            "error": str(error)[:200],
        })

    # 한 줄에 JSON 하나. 덧붙이기만 하니 도중에 죽어도 앞부분은 남는다
    def _write(self, row):
        # 적기 전에 파일이 너무 커졌는지 본다.
        self._rotate()
        # 'a' 는 덧붙이기다. 기존 내용을 지우지 않는다.
        with open(self.path, "a", encoding="utf-8") as f:
            # 한글이 그대로 보이게 두고 줄바꿈을 붙여 한 줄로 만든다.
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # 상한을 넘으면 한 세대 밀어 둔다. 안 밀면 이 파일이 끝없이 자란다
    def _rotate(self):
        # 파일이 없거나 권한 문제가 있을 수 있으므로 감싼다.
        try:
            # 아직 상한 아래면 밀 필요가 없다.
            if self.path.stat().st_size < MAX_RUNS_BYTES:
                # 그대로 두고 끝낸다.
                return
            # 이름 끝을 .1.jsonl 로 바꿔 한 세대 밀어 둔다.
            self.path.replace(self.path.with_suffix(".1.jsonl"))
        # 파일이 아직 없으면 밀 것도 없다.
        except FileNotFoundError:
            # 그대로 끝낸다.
            return
        # 권한 같은 다른 문제는 기록만 남기고 넘어간다.
        except OSError as exc:
            # 기록을 못 민다고 요청을 깨뜨리지는 않는다.
            log.warning("runs.jsonl 을 밀지 못했다: %s", exc)


# LangSmith 를 켠다. 끄면 아무 일도 안 한다
def setup_langsmith():
    # 설정이 꺼져 있으면 아무것도 내보내지 않는다.
    if not LANGSMITH_TRACING:
        # 라이브러리가 보는 환경변수도 확실히 꺼 둔다.
        os.environ["LANGSMITH_TRACING"] = "false"
        # 상태를 글자로 돌려준다.
        return "꺼짐"

    # 켜기로 했는데 열쇠가 비어 있으면 보낼 수 없다.
    if not os.environ.get("LANGSMITH_API_KEY", "").strip():
        # 실패를 반복하지 않도록 꺼 둔다.
        os.environ["LANGSMITH_TRACING"] = "false"
        # 설정이 어긋났다는 것을 알려 준다.
        log.warning("LANGSMITH_TRACING=true 인데 LANGSMITH_API_KEY 가 비어 있다")
        # 상태를 글자로 돌려준다.
        return "키 없음"

    # 여기까지 왔으면 실제로 켠다.
    os.environ["LANGSMITH_TRACING"] = "true"

    # 본문을 보낼 때는 가리지 않고, 안 보낼 때는 가린다.
    hide = "false" if LANGSMITH_SEND_BODY else "true"
    # 입력 본문을 가릴지 정한다.
    os.environ["LANGSMITH_HIDE_INPUTS"] = hide
    # 출력 본문을 가릴지 정한다.
    os.environ["LANGSMITH_HIDE_OUTPUTS"] = hide

    # 환경변수를 바꾼 뒤에 불러온다.
    from langsmith import utils as ls_utils
    # 라이브러리가 이미 읽어 둔 옛 값을 버리게 한다.
    ls_utils.get_env_var.cache_clear()

    # 본문까지 보내는지 여부를 상태 글자에 담아 돌려준다.
    return "켜짐 (본문 포함)" if LANGSMITH_SEND_BODY else "켜짐 (지표만)"


# 이 파일을 불러올 때 한 번 돌려 상태를 정해 둔다.
LANGSMITH_STATE = setup_langsmith()

# 사용량을 쌓는 판 하나를 만들어 둔다.
writer = UsageWriter()
# 호출 기록을 파일에 적는 판 하나를 만들어 둔다.
tracer = JsonlTracer()
