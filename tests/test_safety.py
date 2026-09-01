"""안전 필터 규칙 시험. DB 없이 돈다."""

from app.domain.safety import blocked_for, extract_bans, reason_for

SECTIONS = [
    ("P001", "고농도 비타민C 유도체가 함유되어 있습니다. "
             "민감성 피부에는 따가움이 느껴질 수 있으므로 사용을 권하지 않습니다."),
    ("P002", "민감성 피부도 편안하게 쓰실 수 있습니다."),
    ("P003", "자극이 있을 수 있으니 주의하세요."),
    ("P004", "건성 피부에는 사용을 권하지 않습니다."),
]
BANS = extract_bans(SECTIONS)


def test_금지_문장이_있는_상품만_잡는다():
    assert set(BANS) == {"P001"}


def test_주의하세요_는_금지가_아니다():
    assert "P003" not in BANS


def test_민감성이_아닌_금지는_안_잡는다():
    assert "P004" not in BANS


def test_민감성_고객만_막힌다():
    assert blocked_for("민감성", BANS) == {"P001"}
    assert blocked_for("건성", BANS) == set()
    assert blocked_for(None, BANS) == set()


def test_근거_문장을_돌려준다():
    assert "사용을 권하지 않습니다" in reason_for("P001", BANS)
    assert reason_for("P002", BANS) == ""


def test_빈_글이_섞여도_안_터진다():
    assert extract_bans([("P100", ""), ("P101", None)]) == {}
