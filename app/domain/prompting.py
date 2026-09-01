"""LLM에 전달할 프롬프트 문장을 입력 데이터로부터 만든다."""

# 프롬프트에 넣을 구매 이력의 최대 건수다. 너무 길면 모델이 앞을 잊는다.
MAX_HISTORY = 8


# 고객 한 명을 프롬프트용 글로. 나가는 것은 이미 가려진 글이다
def customer_block(board):
    # 고객 정보만 따로 꺼내 둔다.
    customer = board["customer"]
    # 줄 단위로 모았다가 마지막에 하나로 잇는다.
    lines = [
        # 첫 줄은 나이, 성별, 피부 타입, 사는 곳이다.
        f"고객: {customer['age']}세 {customer['gender']} · "
        # 같은 줄에 이어 붙는다. 따옴표만 끊었을 뿐 줄바꿈이 아니다.
        f"{customer['skin_type']} 피부 · {customer['city']} 거주",
        # 둘째 줄은 몇 건을 샀고 평균 별점이 얼마인지다.
        f"구매 {customer['n_purchases']}건 · 평균 별점 {board['avg_rating']}",
    ]
    # 구매 이력은 앞에서부터 정해 둔 건수만 넣는다.
    for row in board["purchases"][:MAX_HISTORY]:
        # 이력 한 건을 한 줄로 만들어 덧붙인다.
        lines.append(
            # 쉼표를 넣은 :, 는 1,000 처럼 세 자리마다 쉼표를 찍으라는 뜻이다.
            f"- {row['name']} ({row['category']}, {row['price']:,}원, "
            # 후기가 없을 수도 있으므로 get 으로 꺼내 빈 글자를 기본값으로 둔다.
            f"별점 {row['rating']}) {row.get('review_masked', '')}")
    # 모아 둔 줄들을 줄바꿈으로 이어 하나의 글로 만든다.
    return "\n".join(lines)


# 후보 상품을 번호가 붙은 글로. 이 번호가 모델이 답으로 돌려줄 이름표다
def candidate_block(candidates):
    # 후보마다 한 줄씩 만들어 줄바꿈으로 잇는다.
    return "\n".join(
        # 맨 앞의 번호가 모델이 답으로 가리킬 이름표다.
        f"{row['number']}. {row['name']} · {row['brand']} · {row['category']} · "
        # 가격과 피부 타입, 성분, 고민을 같은 줄에 이어 붙인다.
        f"{row['price']:,}원 · {row['skin_type']}용 · {row['ingredient']} · {row['concern']}"
        # 후보 목록을 하나씩 꺼내 위 모양으로 만든다.
        for row in candidates)


# 프롬프트의 자료 칸을 만든다. 들어온 것만 이어 붙인다
def build_context(sources, board=None, blocked=None, cands=None):
    # 만들어진 칸을 순서대로 모아 둘 목록이다.
    parts = []
    # 고객 정보를 받았을 때만 넣는다.
    if board:
        # 대괄호로 칸 이름을 달아 모델이 구분하게 한다.
        parts.append(f"[고객]\n{customer_block(board)}")
    # 추천 후보를 받았을 때만 넣는다.
    if cands:
        # 칸 이름에 지켜야 할 규칙을 같이 적어 둔다.
        parts.append("[추천 가능한 상품 - 이 목록 밖은 말하지 않는다]\n"
                     # 위에서 만든 번호 붙은 목록을 이어 붙인다.
                     + candidate_block(cands))
    # 근거 자료를 받았을 때만 넣는다.
    if sources:
        # 자료 사이는 빈 줄 하나로 갈라 둔다.
        parts.append("[자료]\n" + "\n\n".join(
            # 괄호 안의 번호가 답에서 근거를 가리킬 때 쓰는 이름표다.
            f"({i}) {s['product_name']} > {s['section']}\n{s['text']}"
            # start=1 이라 번호가 0 이 아니라 1 부터 시작한다.
            for i, s in enumerate(sources, start=1)))
    # 막아야 할 상품이 있을 때만 넣는다.
    if blocked:
        # 무엇을 하지 말아야 하는지 문장으로 분명히 적는다.
        parts.append("[주의] 아래 상품은 이 고객의 피부 타입에 권하지 않는다. 추천하지 마라.\n"
                     # 상품 이름과 막힌 이유를 한 줄씩 적는다.
                     + "\n".join(f"- {row['name']}: {row['blocked_reason']}"
                                 # 막힌 상품을 하나씩 꺼낸다.
                                 for row in blocked))
    # 만들어진 칸들을 빈 줄로 갈라 하나의 글로 잇는다.
    return "\n\n".join(parts)
