"""설정에 맞는 LLM 클라이언트를 만들어 다른 기능에 제공한다."""

# 연결과 응답 대기 같은 단계별 제한 시간을 따로 정하려고 쓰는 HTTP 라이브러리다.
import httpx

# OpenAI 형식으로 대화하는 모델을 감싼 LangChain 클래스다.
from langchain_openai import ChatOpenAI

# 어느 모델을 어느 주소에서 어떤 열쇠로 부를지 미리 정해 둔 설정값이다.
from app.core.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

# 호출 기록을 남기는 도구 둘이다. writer는 사용량을 쌓고 tracer는 runs.jsonl에 한 줄씩 적는다.
from app.core.trace import tracer, writer

# 연결, 응답 읽기, 요청 쓰기, 연결 풀 대기의 최대 시간을 각각 설정한다.
TIMEOUT = httpx.Timeout(connect=5.0, read=300.0, write=30.0, pool=5.0)


# 정해진 형식의 답이 필요한 곳에서 쓰는 기본 클라이언트다. 추천 기능이 이걸 부른다.
chat = ChatOpenAI(
    # 부를 모델의 이름이다.
    model=LLM_MODEL,
    # 그 모델이 있는 서버 주소다. 로컬과 상용을 이 값 하나로 바꾼다.
    base_url=LLM_BASE_URL,
    # 그 서버에 자기를 밝히는 열쇠다.
    api_key=LLM_API_KEY,
    # temperature는 답변의 무작위성을 조절하며, 0이면 일관된 결과를 우선한다.
    temperature=0,
    # 위에서 만든 단계별 제한 시간을 그대로 쓴다.
    timeout=TIMEOUT,
    # 호출이 끝날 때마다 이 두 도구가 기록을 남긴다.
    callbacks=[writer, tracer],
)

# temperature를 0.3으로 높여 답변에 약간의 다양성을 주는 응답용 클라이언트다.
chat_answer = ChatOpenAI(
    # 위와 같은 모델을 쓴다. 성격만 다르게 잡은 두 번째 창구다.
    model=LLM_MODEL,
    # 서버 주소도 같다.
    base_url=LLM_BASE_URL,
    # 열쇠도 같다.
    api_key=LLM_API_KEY,
    # 0보다 크면 같은 질문에도 표현이 조금씩 달라진다.
    temperature=0.3,
    # 제한 시간도 위와 같은 값을 쓴다.
    timeout=TIMEOUT,
    # 기록을 남기는 도구도 같다.
    callbacks=[writer, tracer],
    # 답을 조금씩 흘려보내는 동안에도 토큰 사용량을 받아 오게 한다.
    stream_usage=True,
)
