"""생성한 답변이 검색 근거와 질문에 충실한지 측정한다."""

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(errors="replace")

from ragas import EvaluationDataset, SingleTurnSample, evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics._answer_relevance import ResponseRelevancy
from ragas.metrics._context_precision import LLMContextPrecisionWithoutReference
from ragas.metrics._faithfulness import Faithfulness

from app.adapters.llm import chat
from app.core.config import EMBED_MODEL, LLM_MODEL, USE_API
from app.core.embedder import get_embeddings
from app.features import answering
from app.features.retrieve import search_chunks

GOLDEN = json.loads((Path(__file__).parent / "qa_golden.json").read_text(encoding="utf-8"))

K = 3


# 앱이 실제로 하는 일을 그대로 한다. 여기서 갈라지면 딴것을 재는 셈이다
def answer_one(question):
    sources = search_chunks(question, k=K)
    answer = "".join(answering.stream(question, sources=sources))
    return answer, [s["text"] for s in sources]


# 골든 질문으로 ragas 점수를 내고 찍는다
def main(argv):
    if not USE_API:
        print("USE_API=1 로 돌려야 한다.")
        print()
        print("  ragas 는 LLM 을 심판으로 쓴다. 로컬 3B 는 구조화 출력이 17/30 이라")
        print("  (docs/measurements.md) 심판으로 못 쓴다. 못 믿을 심판이 낸 숫자는")
        print("  없는 것보다 나쁘다. 그 숫자를 나중에 믿게 되기 때문이다.")
        return 2

    limit = None
    if "--limit" in argv:
        limit = int(argv[argv.index("--limit") + 1])
    items = GOLDEN["items"][:limit]

    print("=" * 74)
    print(f"답변 품질 채점. 문항 {len(items)}개 · 근거 {K}개 · {LLM_MODEL}")
    print("=" * 74)
    print("  호출이 돈이 된다. 문항 하나에 답변 1번 + 심판 여러 번이다.")
    print()

    samples = []
    for n, item in enumerate(items, start=1):
        answer, contexts = answer_one(item["question"])
        print(f"  {n:>2}/{len(items)}  {item['question'][:44]}")
        samples.append(SingleTurnSample(
            user_input=item["question"],
            retrieved_contexts=contexts,
            response=answer,
        ))

    print()
    print("  심판을 부른다. 문항 수에 비례해 걸린다.")
    judge = LangchainLLMWrapper(chat)
    embedder = LangchainEmbeddingsWrapper(get_embeddings())
    result = evaluate(
        EvaluationDataset(samples=samples),
        metrics=[Faithfulness(), ResponseRelevancy(),
                 LLMContextPrecisionWithoutReference()],
        llm=judge,
        embeddings=embedder,
    )

    print()
    print("=" * 74)
    print("결과")
    print("=" * 74)
    for name, score in result._repr_dict.items():
        print(f"  {name:40s} {score:.3f}")

    print()
    print(f"  표본 {len(items)}문항 · 답변 {LLM_MODEL} · 임베딩 {EMBED_MODEL} · 근거 {K}개")
    print("  이 숫자를 docs/measurements.md 에 잰 날짜와 함께 옮겨 적는다.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
