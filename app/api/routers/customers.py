"""고객 조회, 유사 후기 검색, 상품 추천 API를 제공한다."""

# 라우터를 만들고, 의존성을 붙이고, 오류를 알리기 위해 사용한다.
from fastapi import APIRouter, Depends, HTTPException

# 인증 · 쿼터 관문 · 사용 기록 맥락을 붙이는 세 함수다.
from app.api.dependencies import caller, guard, meter

# 추천을 만드는 모듈과 조회를 모아 둔 모듈이다.
from app.features import recommending, retrieve

# 사전을 붙여 개인정보를 지우는 함수다.
from app.features.privacy import mask_text

# 응답의 모양을 정해 둔 네 가지다.
from app.features.schemas import CustomerBrief, Dashboard, Recommended, SimilarReviews

# 이 파일의 주소는 모두 /api/customers 로 시작한다.
router = APIRouter(prefix="/api/customers", tags=["고객"])


# 없는 고객이면 404. 세 엔드포인트가 같은 판정을 쓴다
def _board(customer_id):
    # 고객 한 명의 판을 읽는다. 없으면 None 이 온다.
    board = retrieve.dashboard(customer_id)
    # 없는 고객이면 여기서 멈춘다.
    if board is None:
        # 404 는 그런 자원이 없다는 뜻이다.
        raise HTTPException(status_code=404, detail="그런 고객이 없다")
    # 있으면 그 판을 그대로 돌려준다.
    return board


# 고객 목록
@router.get("", response_model=list[CustomerBrief])
def customers(user: str = Depends(caller)):
    # 목록은 모델을 안 부르므로 쿼터를 세지 않는다.
    return retrieve.customer_list()


# 고객 한 명의 판. 없으면 404
@router.get("/{customer_id}", response_model=Dashboard)
def customer(customer_id: str, user: str = Depends(caller)):
    # 위에서 만든 판정을 그대로 쓴다.
    return _board(customer_id)


# 이 고객의 최근 후기와 비슷한 불만을 쓴 다른 후기
@router.get("/{customer_id}/similar-reviews", response_model=SimilarReviews)
def similar_reviews(customer_id: str, user: str = Depends(caller)):
    # 임베딩을 부르므로 사용 기록에 남게 맥락을 붙인다.
    meter(user, "similar_reviews")
    # 없는 고객이면 여기서 404 로 끝난다.
    board = _board(customer_id)

    # 후기를 실제로 쓴 구매만 남긴다.
    written = [row for row in board["purchases"] if row["review"]]
    # 쓴 후기가 하나도 없으면 찾을 기준이 없다.
    if not written:
        # 빈 결과를 모양만 맞춰 돌려준다.
        return {"query": "", "product_name": "", "found": []}

    # 구매 이력이 최근 순이라 첫 줄이 가장 최근 후기다.
    latest = written[0]
    # 찾는 데 쓴 글은 밖으로 나가므로 가려서 보여 준다.
    return {"query": mask_text(latest["review"]),
            # 그 후기가 어느 상품의 것인지 같이 준다.
            "product_name": latest["name"],
            # 찾을 때는 원문을 쓴다. 가린 글로 찾으면 뜻이 달라진다.
            "found": retrieve.search_reviews(latest["review"], k=5,
                                             # 본인 후기는 결과에서 뺀다.
                                             exclude_customer_id=customer_id)}


# 추천. use_llm=false 로 두면 벡터 순위 그대로 나온다
@router.get("/{customer_id}/recommend", response_model=Recommended)
def recommend(customer_id: str, use_llm: bool = True, user: str = Depends(caller)):
    # 없는 고객이면 여기서 404 로 끝난다.
    board = _board(customer_id)

    # 모델을 부를 때만 쿼터를 센다.
    if use_llm:
        # 다 썼으면 여기서 429 로 끝난다.
        guard(user, "recommend")

    # 벡터로 후보를 뽑는다. 막힌 것과 쓴 필터 이름도 같이 받는다.
    cands, blocked, filter_used = retrieve.candidates(customer_id)
    # 모델을 안 불러도 이만큼은 돌려줄 수 있다.
    result = {"customer_id": customer_id, "picked": cands[:5], "blocked": blocked,
              # 어떤 필터를 걸었고 후보가 몇 개였는지 같이 준다.
              "filter_used": filter_used, "n_candidates": len(cands),
              # 아직 모델을 안 불렀다는 표시다.
              "llm_used": False, "retries": 0}
    # 모델을 안 쓰기로 했거나 후보가 없으면 여기서 끝낸다.
    if not use_llm or not cands:
        # 벡터 순위 그대로 돌려준다.
        return result

    # 후보 중에서 고르게 한다. 실패하면 picked 가 None 이다.
    picked, retries, error = recommending.recommend(cands, board)
    # 형식이 틀려 몇 번 다시 시켰는지 화면에도 알려 준다.
    result["retries"] = retries
    # 끝내 못 받았을 때다.
    if picked is None:
        # 왜 실패했는지 필터 이름 옆에 붙여 화면에서 보이게 한다.
        result["filter_used"] += f" (LLM 실패: {error[:60]})"
        # 그래도 벡터 순위는 그대로 돌려준다.
        return result

    # 모델이 고른 번호로 후보를 바로 찾을 수 있게 만든다.
    by_number = {row["number"]: row for row in cands}
    # 고른 후보에 모델이 쓴 이유를 붙여 넣는다.
    result["picked"] = [{**by_number[p.number], "reason": p.reason}
                        # 모델이 고른 순서를 그대로 지킨다.
                        for p in picked.picks]
    # 모델을 실제로 썼다고 표시한다.
    result["llm_used"] = True
    # 최종 결과를 돌려준다.
    return result
