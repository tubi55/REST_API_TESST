"""상품 주의사항에서 판매하면 안 되는 조건을 찾는다."""

# 글에서 정해진 표현을 찾기 위해 사용한다.
import re

# 사용을 말리는 표현들이다. 세로 막대는 이 중 하나라도 맞으면 된다는 뜻이다.
BAN = re.compile(r"(사용을 권하지 않|사용하지 마|사용을 피하|사용을 삼가|사용 금지)")

# 지금 막는 대상은 민감성 피부 하나다.
SENSITIVE = "민감성"


# 주의사항 섹션들에서 {상품id: [금지 문장]} 을 만든다
def extract_bans(sections):
    # 상품 아이디별로 금지 문장을 모아 둘 딕셔너리다.
    bans = {}
    # 주의사항 글을 상품 아이디와 함께 하나씩 꺼낸다.
    for product_id, text in sections:
        # 마침표·느낌표·물음표 뒤나 줄바꿈에서 글을 문장으로 자른다.
        for sentence in re.split(r"(?<=[.!?])\s+|\n", text or ""):
            # 말리는 표현과 민감성이 같은 문장 안에 있을 때만 금지로 본다.
            if BAN.search(sentence) and SENSITIVE in sentence:
                # setdefault 는 그 아이디가 처음이면 빈 목록을 만들어 준다.
                bans.setdefault(product_id, []).append(sentence.strip())
    # 상품 아이디마다 금지 문장 목록이 담긴 딕셔너리를 돌려준다.
    return bans


# 이 피부 타입 고객에게 추천하면 안 되는 상품 아이디들
def blocked_for(skin_type, bans):
    # 민감성 고객일 때만 막는다.
    if skin_type == SENSITIVE:
        # 딕셔너리를 set 으로 감싸면 열쇠, 곧 상품 아이디만 남는다.
        return set(bans)
    # 다른 피부 타입은 막지 않으므로 빈 집합이다.
    return set()


# 왜 막혔는지 근거 문장. 근거 없는 차단은 사람이 못 고친다
def reason_for(product_id, bans):
    # 그 상품의 금지 문장 목록을 꺼낸다. 없으면 빈 목록이다.
    sentences = bans.get(product_id, [])
    # 첫 문장 하나만 근거로 보여 준다. 없으면 빈 글자다.
    return sentences[0] if sentences else ""
