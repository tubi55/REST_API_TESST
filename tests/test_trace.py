"""사용량 콜백 시험. DB 도 모델도 없이 돈다."""

import pytest

from app.core import trace, usage


# LangChain 이 주는 응답 중 tokens_of 가 보는 부분만 흉내 낸다
class FakeResponse:
    llm_output = {"token_usage": {"prompt_tokens": 10, "completion_tokens": 5},
                  "model_name": "시험모델"}
    generations = []


# 맥락은 ContextVar 다. 시험이 끝나면 되돌려야 다음 시험에 안 새어 나간다
@pytest.fixture
def context():
    def use(value):
        token = trace.CURRENT.set(value)
        tokens.append(token)

    tokens = []
    yield use
    for token in reversed(tokens):
        trace.CURRENT.reset(token)


# usage.record 를 가로채 남은 기록을 목록으로 준다
@pytest.fixture
def recorded(monkeypatch, context):
    rows = []
    monkeypatch.setattr(usage, "record",
                        lambda user_id, feature, **kw: rows.append({**kw, "who": user_id}))
    context({"user_id": "사람", "feature": "recommend"})
    return rows


def test_동시에_온_두_호출의_시간이_안_섞인다(recorded, monkeypatch):
    ticks = iter([100.0, 100.5, 103.0, 103.25])
    monkeypatch.setattr(trace.time, "perf_counter", lambda: next(ticks))

    writer = trace.UsageWriter()
    writer.on_chat_model_start(None, [], run_id="가")
    writer.on_chat_model_start(None, [], run_id="나")
    writer.on_llm_end(FakeResponse(), run_id="가")
    writer.on_llm_end(FakeResponse(), run_id="나")

    assert [row["seconds"] for row in recorded] == [3.0, 2.75]


def test_맥락이_없으면_안_남기고_자리도_안_남긴다(context):
    context(None)
    writer = trace.UsageWriter()

    writer.on_chat_model_start(None, [], run_id="가")
    writer.on_llm_end(FakeResponse(), run_id="가")

    assert writer.started == {}


def test_실패해도_자리를_치운다():
    writer = trace.UsageWriter()

    writer.on_chat_model_start(None, [], run_id="가")
    writer.on_llm_error(RuntimeError("끊겼다"), run_id="가")

    assert writer.started == {}


def test_토큰과_모델을_응답에서_꺼낸다():
    assert trace.tokens_of(FakeResponse()) == (10, 5, "시험모델")


def test_runs_jsonl_이_상한을_넘으면_한_세대_밀린다(tmp_path, monkeypatch):
    monkeypatch.setattr(trace, "MAX_RUNS_BYTES", 200)
    tracer = trace.JsonlTracer(tmp_path / "runs.jsonl")

    for n in range(20):
        tracer._write({"n": n, "덧": "자리를 채운다" * 3})

    assert (tmp_path / "runs.1.jsonl").exists()
    assert (tmp_path / "runs.jsonl").stat().st_size < 200
    assert '"n": 19' in (tmp_path / "runs.jsonl").read_text(encoding="utf-8")


def test_파일이_없으면_밀_것도_없다(tmp_path):
    tracer = trace.JsonlTracer(tmp_path / "runs.jsonl")

    tracer._write({"n": 0})

    assert (tmp_path / "runs.jsonl").exists()
    assert not (tmp_path / "runs.1.jsonl").exists()
