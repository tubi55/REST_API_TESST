"""설정 읽기. 조용히 틀리는 자리를 막았는지 본다."""

import pytest

from app.core.config import env_bool


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "True", "yes", "on", "y"])
def test_참으로_읽는_말들(value, monkeypatch):
    monkeypatch.setenv("시험값", value)
    assert env_bool("시험값", "0") is True


@pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", "off", "n"])
def test_거짓으로_읽는_말들(value, monkeypatch):
    monkeypatch.setenv("시험값", value)
    assert env_bool("시험값", "1") is False


@pytest.mark.parametrize("value", ["treu", "2", "참", "yeah", "-1"])
def test_모르는_값은_조용히_넘기지_않는다(value, monkeypatch):
    monkeypatch.setenv("시험값", value)
    with pytest.raises(RuntimeError) as raised:
        env_bool("시험값", "0")
    assert "시험값" in str(raised.value)


def test_비어_있으면_기본값을_쓴다(monkeypatch):
    monkeypatch.setenv("시험값", "   ")
    assert env_bool("시험값", "1") is True
    monkeypatch.delenv("시험값")
    assert env_bool("시험값", "0") is False
