"""후보 상품에서 규칙에 맞는 최종 추천 상품을 고른다."""

# 모델이 한 말과 사람이 한 말을 나타내는 메시지 종류다.
from langchain_core.messages import AIMessage, HumanMessage

# 프롬프트 틀과, 나중에 메시지를 끼워 넣을 자리를 만드는 도구다.
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# 값이 정해 둔 모양과 다를 때 나는 오류다.
from pydantic import ValidationError

# 정해진 형식의 답을 받을 때 쓰는 LLM 클라이언트다.
from app.adapters.llm import chat

# 후보 목록과 고객 정보를 프롬프트용 글로 만드는 함수들이다.
from app.domain.prompting import candidate_block, customer_block

# 모델의 답이 지켜야 할 모양을 정해 둔 두 가지다.
from app.features.schemas import Recommendation, RecommendationDraft

# 형식이 틀렸을 때 몇 번까지 다시 시켜 볼지 정한 값이다.
MAX_RETRIES = 2

# 모델에게 줄 지시와 질문의 틀이다.
RECOMMEND_PROMPT = ChatPromptTemplate.from_messages([
    # system 은 모델의 역할과 지켜야 할 규칙을 정하는 자리다.
    ("system",
     # 누구에게 보고하는 글인지 정해 준다.
     "너는 화장품 회사의 마케팅 담당자다. 관리자에게 보고하듯 한국어로 답한다. "
     # 후보 밖의 상품을 지어내지 못하게 못 박는다.
     "반드시 아래 후보 목록의 번호 중에서만 고른다. 목록에 없는 상품은 절대 만들지 않는다."),
    # human 은 실제 요청 자리다.
    ("human",
     # 고객 정보와 후보 목록을 칸을 나눠 넣는다.
     "{customer}\n\n[후보]\n{candidates}\n\n"
     # 몇 개를 고르고 무엇을 써야 하는지 분명히 적는다.
     "이 고객에게 맞는 상품 {n_pick}개를 후보 번호로 고르고, 각각 한 문장으로 이유를 써라.\n"
     # 중괄호 두 개는 값을 넣는 자리가 아니라 글자 그대로의 중괄호를 뜻한다.
     '{{"picks": [{{"number": 번호, "reason": "이유"}}]}} 형태의 JSON 만 출력한다.'),
    # 형식이 틀렸을 때 주고받은 말을 여기에 끼워 넣는다. 없으면 빈 자리로 둔다.
    MessagesPlaceholder("corrections", optional=True),
])


# 모델에게 되돌려 줄 오류 문장
def readable(exc):
    # 모양이 안 맞는 오류는 항목마다 설명이 따로 붙는다.
    if isinstance(exc, ValidationError):
        # 설명만 모아 세미콜론으로 잇는다.
        return "; ".join(e.get("msg", "") for e in exc.errors())
    # 그 밖의 오류는 첫 줄만 쓴다. 뒤는 모델에게 쓸모가 없다.
    return str(exc).split("\n")[0]


# 후보에서 n_pick 개를 고르게 한다. (결과 또는 None, 재시도 횟수, 마지막 오류)
def recommend(candidates, board, n_pick=5):
    # 정해 둔 모양대로만 답하게 묶는다.
    structured = chat.with_structured_output(
        # include_raw 를 켜면 모델의 원본 답까지 같이 받는다.
        RecommendationDraft, method="json_schema", include_raw=True)
    # 세로 막대는 앞의 결과를 뒤로 넘긴다. 틀 → 모델 순으로 이어진다.
    chain = RECOMMEND_PROMPT | structured

    # 프롬프트의 중괄호 자리에 넣을 값들이다.
    variables = {"customer": customer_block(board),
                 # 후보 목록을 번호가 붙은 글로 만든다.
                 "candidates": candidate_block(candidates),
                 # 몇 개를 고를지 알려 준다.
                 "n_pick": n_pick}
    # 형식이 틀렸을 때 주고받은 말을 여기에 쌓는다.
    corrections = []
    # 마지막으로 무엇이 틀렸는지 담아 둔다.
    last_error = ""

    # 처음 한 번과 다시 시켜 보는 횟수를 합쳐 돈다.
    for attempt in range(MAX_RETRIES + 1):
        # 모델 호출 자체가 실패할 수 있으므로 감싼다.
        try:
            # 지금까지 쌓인 지적을 같이 넣어 부른다.
            got = chain.invoke({**variables, "corrections": corrections})
        # 네트워크나 모델 쪽 문제다.
        except Exception as exc:
            # 기록에 남기기 좋게 첫 줄만 120글자까지 남긴다.
            last_error = str(exc).split("\n")[0][:120]
            # 마지막 시도였으면 더 볼 것이 없다.
            if attempt == MAX_RETRIES:
                # 반복을 빠져나간다.
                break
            # 아직 기회가 남았으면 다시 시도한다.
            continue

        # 원본 답, 읽어 낸 값, 읽다가 난 오류를 각각 꺼낸다.
        raw, parsed, error = got["raw"], got["parsed"], got["parsing_error"]
        # 여기서부터는 답의 내용이 규칙에 맞는지 본다.
        try:
            # JSON 자체를 못 읽었으면 아래 검사도 못 한다.
            if error is not None or parsed is None:
                # 아래 except 가 잡도록 오류를 낸다.
                raise ValueError(f"JSON 을 못 읽었다: {str(error)[:80]}")
            # 후보 개수를 같이 넘겨 번호가 범위 안인지까지 검사하게 한다.
            checked = Recommendation.model_validate(
                # model_dump 는 값들을 평범한 딕셔너리로 바꾼다.
                parsed.model_dump(), context={"n_candidates": len(candidates)})
            # 통과했으면 결과와 몇 번 만에 됐는지를 돌려준다.
            return checked, attempt, ""
        # 모양이 안 맞거나 위에서 낸 오류를 잡는다.
        except (ValidationError, ValueError) as exc:
            # 무엇이 틀렸는지 사람이 읽을 수 있는 문장으로 바꾼다.
            last_error = readable(exc)
            # 마지막 시도였으면 더 볼 것이 없다.
            if attempt == MAX_RETRIES:
                # 반복을 빠져나간다.
                break
            # 다음 시도에 무엇이 틀렸는지 알려 주려고 주고받은 말을 쌓는다.
            corrections += [
                # 모델이 실제로 뭐라고 했는지 그대로 되돌려 준다.
                AIMessage(content=raw.content if raw is not None else ""),
                # 그리고 무엇이 틀렸는지와 올바른 범위를 알려 준다.
                HumanMessage(content=f"형식이 틀렸다: {last_error}\n"
                                     # 번호 범위를 숫자로 분명히 적어 준다.
                                     f"후보는 1~{len(candidates)}번이다. 다시 골라라."),
            ]

    # 끝까지 못 받았으면 결과 자리를 None 으로 두고 마지막 오류를 알려 준다.
    return None, MAX_RETRIES, last_error
