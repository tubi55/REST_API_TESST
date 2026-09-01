"""텍스트를 벡터로 바꾸는 임베딩기를 만들어 함께 사용한다."""

# 임베딩에 걸린 시간을 재기 위해 사용한다.
import time

# 지금 어느 요청인지 알려 주는 trace 와 사용량을 쌓는 usage 를 가져온다.
from app.core import trace, usage

# 어떤 임베딩기를 어디에 어떤 열쇠로 붙일지 정한 설정값들이다.
from app.core.config import EMBED_BACKEND, EMBED_MODEL, LLM_API_KEY, LLM_BASE_URL

# 아직 임베딩기를 만들지 않았다는 뜻으로 None 을 넣어 둔다.
_embeddings = None


# 임베딩 호출을 usage_log 에 남기는 껍데기. 값은 한 글자도 안 바꾼다
class _Metered:
    # 감쌀 진짜 임베딩기를 받아 안에 넣어 둔다.
    def __init__(self, inner):
        # 이 뒤로 모든 일은 이 객체에게 넘긴다.
        self._inner = inner

    # 임베딩기가 토큰 수를 안 돌려준다. 모르는 것은 채우지 않는다.
    def _record(self, n_texts, seconds):
        # 지금 어느 사용자의 어느 기능인지 담긴 맥락을 꺼낸다.
        ctx = trace.CURRENT.get()
        # 요청 밖에서 부른 경우라 맥락이 없으면 남길 곳이 없다.
        if ctx is None:
            # 기록만 건너뛰고 조용히 끝낸다.
            return
        # 기록이 실패해도 본래 작업이 멈추면 안 되므로 감싼다.
        try:
            # 어느 기능에서 부른 임베딩인지 이름 앞에 embed: 를 붙인다.
            usage.record(ctx["user_id"], f"embed:{ctx['feature']}", model=EMBED_MODEL,
                         # 입력 토큰은 알 수 없어 비우고, 출력 자리에 글 개수를 적는다.
                         in_tokens=None, out_tokens=n_texts, seconds=seconds)
        # 어떤 오류가 나든 기록 때문에 요청을 깨뜨리지 않는다.
        except Exception:
            # 아무것도 하지 않고 넘어간다.
            pass

    # 글 하나를 벡터로 바꾼다.
    def embed_query(self, text):
        # 시작 시각을 재 둔다.
        started = time.perf_counter()
        # 진짜 임베딩기에게 그대로 넘긴다.
        got = self._inner.embed_query(text)
        # 글 한 개를 처리한 시간과 함께 기록한다.
        self._record(1, round(time.perf_counter() - started, 2))
        # 받은 값을 손대지 않고 그대로 돌려준다.
        return got

    # 글 여러 개를 한 번에 벡터로 바꾼다.
    def embed_documents(self, texts):
        # 시작 시각을 재 둔다.
        started = time.perf_counter()
        # 진짜 임베딩기에게 그대로 넘긴다.
        got = self._inner.embed_documents(texts)
        # 처리한 글 개수와 걸린 시간을 함께 기록한다.
        self._record(len(texts), round(time.perf_counter() - started, 2))
        # 받은 값을 손대지 않고 그대로 돌려준다.
        return got

    # 나머지는 그대로 넘긴다. 껍데기가 인터페이스를 좁히면 안 된다.
    def __getattr__(self, name):
        # 여기 없는 이름을 물으면 안에 든 진짜 객체에게 물어본다.
        return getattr(self._inner, name)


# 진짜 임베딩기를 만든다. 로컬이든 상용이든 LangChain Embeddings 하나를 돌려준다
def _build():
    # 내 컴퓨터에서 모델을 돌리는 경우다.
    if EMBED_BACKEND == "local":
        # 진행 막대를 끄는 함수다.
        from huggingface_hub.utils import disable_progress_bars

        # 모델 내려받기 쪽 기록 설정이다.
        from huggingface_hub.utils import logging as hub_logging

        # 모델 라이브러리 쪽 기록 설정이다.
        from transformers import logging as hf_logging

        # 오류만 남기고 잔소리를 줄인다.
        hf_logging.set_verbosity_error()
        # 진행 막대를 끈다.
        hf_logging.disable_progress_bar()
        # 내려받기 쪽도 오류만 남긴다.
        hub_logging.set_verbosity_error()
        # 내려받기 진행 막대도 끈다.
        disable_progress_bars()

        # 로컬 모델을 감싼 LangChain 클래스다. 위 설정을 마친 뒤 불러온다.
        from langchain_huggingface import HuggingFaceEmbeddings

        # 설정에 적힌 모델로 임베딩기를 만든다.
        return HuggingFaceEmbeddings(
            # 어떤 모델을 쓸지 이름으로 정한다.
            model_name=EMBED_MODEL,
            # 그래픽카드 없이 CPU 로 돌린다.
            model_kwargs={"device": "cpu"},
            # 벡터 길이를 1로 맞추고 64개씩 묶어 처리한다.
            encode_kwargs={"normalize_embeddings": True, "batch_size": 64},
        )

    # 여기까지 왔으면 상용 API 를 쓰는 경우다.
    from langchain_openai import OpenAIEmbeddings

    # 설정에 적힌 주소와 열쇠로 API 임베딩기를 만든다.
    return OpenAIEmbeddings(model=EMBED_MODEL, base_url=LLM_BASE_URL,
                            # 그 서버에 자기를 밝히는 열쇠다.
                            api_key=LLM_API_KEY)


# 사용량을 세는 임베딩기 하나
def get_embeddings():
    # 함수 안에서 모듈 전역 변수에 값을 넣기 위해 global 을 사용한다.
    global _embeddings
    # 아직 안 만들었을 때만 만든다.
    if _embeddings is None:
        # 진짜 임베딩기를 만들어 기록용 껍데기로 감싼다.
        _embeddings = _Metered(_build())
    # 이후 호출에서는 같은 객체를 그대로 돌려준다.
    return _embeddings


# 이미 올라왔나. 준비 점검이 묻는다. 안 올라왔으면 만들지 않는다
def is_loaded():
    # 여기서 get_embeddings 를 부르면 확인만 하려다 모델을 올리게 된다.
    return _embeddings is not None


# 뜰 때 미리 올린다. 안 그러면 449MB 짜리 모델을 첫 요청 안에서 올린다
def warm_up():
    # 아무 글이나 한 번 넣어 모델을 실제로 올려 둔다.
    get_embeddings().embed_query("워밍업")
