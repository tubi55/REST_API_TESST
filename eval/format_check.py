"""LLM이 요청한 JSON 응답 형식을 지키는지 측정한다."""

import json
import sys
import time

sys.stdout.reconfigure(errors="replace")

from langchain_core.prompts import ChatPromptTemplate
from pydantic import ValidationError

from app.adapters.llm import chat
from app.core.config import LLM_MODEL
from app.domain.prompting import candidate_block, customer_block
from app.features.retrieve import candidates, dashboard
from app.features.schemas import Recommendation, RecommendationDraft
from app.repositories import customers as customer_repo

SYSTEM = ("너는 화장품 회사의 마케팅 담당자다. 관리자에게 보고하듯 한국어로 답한다. "
          "반드시 아래 후보 목록의 번호 중에서만 고른다. 목록에 없는 상품은 절대 만들지 않는다.")


# 모델이 JSON 앞뒤에 말을 붙이는 일이 있다. 중괄호 구간만 떼어 낸다
def extract_json(text):
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        text = text[4:] if text.startswith("json") else text
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if start != -1 and end != -1 else text

N = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 30
CUSTOMERS = customer_repo.all_ids()[:N]

CONDITIONS = [
    ("예시없음", False, False),
    ("프롬프트만", True, False),
    ("스키마 강제", True, True),
]
WANTED = [c for c in CONDITIONS
          if len(sys.argv) < 3 or c[0] in sys.argv[2:]]


# 한 번만 부른다. 재시도 없이 '처음에 어떻게 냈나'를 봐야 형식 사고가 보인다
def ask_once(cands, board, with_example, force_schema):
    tail = ('{{"picks": [{{"number": 번호, "reason": "이유"}}]}} 형태의 JSON 만 출력한다.'
            if with_example else
            "결과는 picks 라는 목록에 번호(number)와 이유(reason)를 담아 JSON 으로만 답한다.")
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM),
        ("human", "{customer}\n\n[후보]\n{candidates}\n\n"
                  "이 고객에게 맞는 상품 5개를 후보 번호로 고르고, 각각 한 문장으로 이유를 써라.\n"
                  + tail),
    ])
    variables = {"customer": customer_block(board),
                 "candidates": candidate_block(cands)}

    if force_schema:
        structured = chat.with_structured_output(
            RecommendationDraft, method="json_schema", include_raw=True)
        got = (prompt | structured).invoke(variables)
        return got["raw"].content if got["raw"] is not None else ""
    return (prompt | chat).invoke(variables).content or ""


# 낸 답을 뜯어본다. 몇 개 냈나 · 범위를 벗어났나를 센다
def judge(answer, n_candidates):
    out = {"json_ok": False, "n_picks": 0, "out_of_range": 0,
           "duplicated": False, "schema_ok": False}
    try:
        data = json.loads(extract_json(answer))
    except (json.JSONDecodeError, ValueError):
        return out

    out["json_ok"] = True
    picks = data.get("picks", []) if isinstance(data, dict) else []
    numbers = [p.get("number") for p in picks if isinstance(p, dict)]
    out["n_picks"] = len(picks)
    out["out_of_range"] = sum(
        1 for x in numbers if not isinstance(x, int) or not 1 <= x <= n_candidates)
    out["duplicated"] = len(set(numbers)) != len(numbers)

    try:
        Recommendation.model_validate(data, context={"n_candidates": n_candidates})
        out["schema_ok"] = True
    except ValidationError:
        pass
    return out


print(f"모델 {LLM_MODEL} · 고객 {N}명 · 조건 {len(WANTED)}개 "
      f"({' / '.join(c[0] for c in WANTED)})")
print("재시도는 끄고 첫 응답만 본다\n")

results = {c[0]: [] for c in WANTED}
started = time.perf_counter()

for i, cid in enumerate(CUSTOMERS, start=1):
    cands, _blocked, _used = candidates(cid)
    board = dashboard(cid)
    if not cands:
        continue
    for label, with_example, force in WANTED:
        answer = ask_once(cands, board, with_example, force)
        results[label].append(judge(answer, len(cands)))
    done = time.perf_counter() - started
    print(f"  {i:>3}/{N}  ({done / i:.0f}초/명 · 남은 시간 {(N - i) * done / i / 60:.0f}분)",
          end="\r")

print(" " * 70, end="\r")
print("=" * 74)
print(f"{'':14s} {'JSON 파싱':>9s} {'5개를 다 냄':>11s} {'후보 밖 번호':>12s} "
      f"{'중복':>6s} {'스키마 통과':>11s}")
for label, rows in results.items():
    n = len(rows)
    total_numbers = sum(r["n_picks"] for r in rows)
    print(f"  {label:12s} {sum(r['json_ok'] for r in rows):>6}/{n:<3} "
          f"{sum(r['n_picks'] == 5 for r in rows):>8}/{n:<3} "
          f"{sum(r['out_of_range'] for r in rows):>8}/{total_numbers:<4} "
          f"{sum(r['duplicated'] for r in rows):>4}   "
          f"{sum(r['schema_ok'] for r in rows):>8}/{n}")

print(f"\n총 {time.perf_counter() - started:.0f}초")
print("이 숫자를 docs/measurements.md 에 잰 날짜 · 표본과 함께 옮겨 적는다.")
