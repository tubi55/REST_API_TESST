"""문장에서 전화번호와 이메일 같은 개인정보를 가린다."""

# 글에서 정해진 모양을 찾아 바꾸기 위해 사용한다.
import re

# 휴대전화 번호다. 가운데 구분 기호가 없거나 하이픈, 점, 공백이어도 잡는다.
PHONE = re.compile(r"01[016-9][-.\s]?\d{3,4}[-.\s]?\d{4}")

# 이메일 주소다. 골뱅이 앞뒤와 점 뒤의 글자를 각각 잡는다.
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]{2,}")

# '카톡' 이 들어간 문장 하나를 통째로 잡는다. 아이디까지 같이 지우기 위해서다.
KAKAO = re.compile(r"[^.!?]*카톡[^.!?]*[.!?]?")

# 연락을 유도하는 낱말이 든 문장을 통째로 잡는다.
CONTACT = re.compile(r"[^.!?]*(문자|연락|공구|디엠|DM)[^.!?]*[.!?]?")


# 도시 목록으로 주소 정규식을 만든다. 목록이 비면 None
def build_address_pattern(cities):
    # 도시 목록이 없으면 만들 수 있는 것이 없다.
    if not cities:
        # 부르는 쪽이 None 인지 보고 건너뛴다.
        return None
    # 중복을 없애고 긴 이름부터 놓는다. 짧은 이름이 먼저 걸리면 뒤가 잘린다.
    ordered = sorted(set(cities), key=len, reverse=True)
    # 도시 이름 뒤에 동·구·읍·면·로·길 이 붙으면 거기까지 함께 잡는다.
    return re.compile(r"(?:%s)(?:\s?[가-힣]+(?:동|구|읍|면|로|길))?" % "|".join(ordered))


# 가리고 나면 생기는 연속 공백을 정리한다
def _tidy(text):
    # 공백이 두 개 이상 이어지면 하나로 줄이고 앞뒤 공백을 떼어 낸다.
    return re.sub(r"\s{2,}", " ", text).strip()


# 개인정보를 지운다. 되돌릴 수 없으므로 나가는 글에만 쓴다
def mask(text, *, names=(), address=None):
    # 빈 글이면 손댈 것이 없다.
    if not text:
        # 받은 값을 그대로 돌려준다.
        return text
    # 카톡 아이디가 든 문장을 통째로 지운다.
    text = KAKAO.sub(" ", text)
    # 연락을 유도하는 문장도 통째로 지운다.
    text = CONTACT.sub(" ", text)
    # 전화번호는 자리만 남기고 표시로 바꾼다.
    text = PHONE.sub("[연락처]", text)
    # 이메일도 표시로 바꾼다.
    text = EMAIL.sub("[메일]", text)
    # 주소 정규식을 만들어 넘겼을 때만 주소를 가린다.
    if address is not None:
        # 도시 이름과 그 뒤의 동·구까지 한꺼번에 바꾼다.
        text = address.sub("[주소]", text)
    # 이름 사전으로 가린다. 긴 이름부터 봐야 짧은 이름이 먼저 걸리지 않는다.
    for name in sorted({n for n in names if n}, key=len, reverse=True):
        # 글 안에 그 이름이 있을 때만 바꾼다.
        if name in text:
            # 정규식이 아니라 글자 그대로 바꾼다.
            text = text.replace(name, "[이름]")
    # 지우고 남은 빈 자리를 정리해서 돌려준다.
    return _tidy(text)
