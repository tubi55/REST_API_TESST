"""질문 종류를 판단하고 검색 결과를 이용해 답변을 생성한다."""

# 모델의 답에서 글자만 꺼내 주는 도구다.
from langchain_core.output_parsers import StrOutputParser

# 시스템 지시와 사용자 질문을 담는 프롬프트 틀이다.
from langchain_core.prompts import ChatPromptTemplate

# 답변용으로 만들어 둔 LLM 클라이언트다.
from app.adapters.llm import chat_answer

# 이 호출에 든 토큰과 시간을 받아 담아 주는 판이다.
from app.core.trace import UsageCollector

# 고객·후보·자료를 프롬프트 한 덩어리로 만드는 함수다.
from app.domain.prompting import build_context

# 이 낱말이 질문에 들어 있으면 상품 문서를 찾아야 하는 질문으로 본다.
PRODUCT_WORDS = ("성분", "사용법", "주의", "배송", "교환", "반품", "용량", "보관",
                 # 뒤쪽 낱말들도 상품 문서에 답이 있는 것들이다.
                 "부작용", "임산부", "유통기한", "환불", "몇 번", "언제 바르")

# 모델에게 줄 지시와 질문의 틀이다.
ANSWER_PROMPT = ChatPromptTemplate.from_messages([
    # system 은 모델의 역할과 지켜야 할 규칙을 정하는 자리다.
    ("system",
     # 자료 밖의 내용을 지어내지 못하게 못 박는다.
     "너는 화장품 회사의 상담 담당자다. 주어진 '자료' 안에 있는 내용만 근거로 한국어로 답한다. "
     # 모르면 모른다고 말하게 하고 길이도 정해 둔다.
     "자료에 없으면 '자료에 없다'고 말한다. 지어내지 않는다. 3~5문장으로 짧게 쓴다."),
    # human 은 실제 질문 자리다. 중괄호 두 곳에 값이 들어간다.
    ("human", "{context}\n\n[질문]\n{question}"),
])

# 세로 막대는 앞의 결과를 뒤로 넘긴다. 틀 → 모델 → 글자 꺼내기 순으로 이어진다.
ANSWER_CHAIN = ANSWER_PROMPT | chat_answer | StrOutputParser()


# 상품 질문인가 고객 분석인가
def route(question):
    # 위 낱말 중 하나라도 들어 있으면 상품 질문으로 본다.
    return "product" if any(word in question for word in PRODUCT_WORDS) else "customer"


# 답을 글자 조각으로 흘려보낸다
def stream(question, sources=None, board=None, blocked=None, cands=None, meter=None):
    # 담을 그릇을 받았을 때만 사용량을 재는 판을 붙인다.
    config = {"callbacks": [UsageCollector(meter)]} if meter is not None else {}
    # yield from 은 모델이 흘려보내는 조각을 그대로 다시 흘려보낸다.
    yield from ANSWER_CHAIN.stream({
        # 자료가 없으면 빈 목록으로 두고 나머지도 있는 것만 넣는다.
        "context": build_context(sources or [], board, blocked, cands),
        # 사용자가 실제로 물어본 문장이다.
        "question": question,
        # 위에서 만든 설정을 같이 넘긴다. 그릇이 없으면 빈 설정이라 아무 일도 안 한다.
    }, config=config)
