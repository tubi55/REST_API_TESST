"""마스킹 규칙 시험. DB 도 인터넷도 모델도 없이 돈다."""

from app.domain.masking import build_address_pattern
from app.domain.masking import mask as mask_rule

NAMES = ["김서연", "박은수", "이수"]
ADDRESS = build_address_pattern(["성남", "천안", "서울"])


# 시험할 때마다 사전을 넘기기 번거로우니 짧게 감싼다
def mask(text):
    return mask_rule(text, names=NAMES, address=ADDRESS)


def test_전화번호_세_가지_모양을_모두_가린다():
    assert "010" not in mask("010-4786-2358 로 연락주세요")
    assert "010" not in mask("01047862358 로 연락주세요")
    assert "010" not in mask("010 4786 2358 로 연락주세요")


def test_하이픈만_잡는_정규식이면_놓쳤을_것():
    assert mask_rule("01047862358", names=(), address=None) == "[연락처]"


def test_전화번호처럼_생긴_다른_숫자는_안_건드린다():
    assert "2026-08-13" in mask("2026-08-13 에 샀어요")


def test_메일을_가린다():
    assert "@" not in mask("eunsu45@example.com 으로 보내주세요")


def test_카톡_문장은_통째로_버린다():
    result = mask("잘 썼어요. 카톡 아이디 seoyeon24 입니다.")
    assert "seoyeon24" not in result
    assert "잘 썼어요" in result


def test_긴_이름부터_지운다():
    both = ["박은", "박은수"]
    assert mask_rule("박은수 고객님", names=both, address=None) == "[이름] 고객님"
    assert mask_rule("박은수 고객님", names=both[::-1], address=None) == "[이름] 고객님"


def test_지금_데이터에는_겹치는_이름이_없다():
    assert not [(a, b) for a in NAMES for b in NAMES if a != b and a in b]


def test_사전에_없는_이름은_못_잡는다():
    assert "홍길동" in mask("홍길동 고객님")


def test_도시와_동네를_같이_가린다():
    assert "성남" not in mask("성남 정자동 살아요")
    assert "정자동" not in mask("성남 정자동 살아요")


def test_도시_사전이_비면_주소를_안_가린다():
    assert build_address_pattern([]) is None
    assert "성남" in mask_rule("성남 살아요", names=(), address=None)


def test_빈_값을_넣어도_안_터진다():
    assert mask("") == ""
    assert mask(None) is None


def test_앱_경로는_사전이_붙어_이름과_주소를_가린다():
    raw = "박은수님 010-1234-5678 로 연락주세요. 성남 분당동 삽니다."
    assert "성남" in mask_rule(raw)
    assert "성남" not in mask(raw)


def test_이름_사전에_None_이_섞여도_안_죽는다():
    got = mask_rule("박은수 고객님", names=["박은수", None, ""], address=None)
    assert got == "[이름] 고객님"
