"""API 요청과 응답에 사용하는 Pydantic 모델을 정의한다."""

# 모양을 정하는 BaseModel, 설정을 담는 ConfigDict, 칸마다 조건을 다는 Field,
# 칸 하나를 검사하는 field_validator, 다 채워진 뒤 검사하는 model_validator 다.
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# 질문 한 개의 최대 글자 수를 설정에서 가져온다.
from app.core.config import MAX_QUESTION_CHARS

# 추천 이유의 최소 글자 수와 최대 글자 수다.
MIN_REASON, MAX_REASON = 2, 200

# 한 번에 몇 개까지 고를 수 있는지 정한 값이다.
MAX_PICKS = 5


# LLM 이 처음 뱉는 추천 한 칸. 검사 전이라 값이 아무거나 올 수 있다
class PickDraft(BaseModel):
    # extra="forbid" 는 정해 둔 칸 말고 다른 칸이 오면 거절한다는 뜻이다.
    model_config = ConfigDict(extra="forbid")

    # description 은 모델에게 이 칸이 무엇인지 알려 주는 설명이다.
    number: int = Field(description="후보 목록의 번호")
    # 왜 골랐는지 한 문장이 들어올 자리다.
    reason: str = Field(description="왜 이 사람에게 맞는가")


# LLM 이 처음 뱉는 추천 묶음. 검사 전이다
class RecommendationDraft(BaseModel):
    # 정해 둔 칸 말고 다른 칸이 오면 거절한다.
    model_config = ConfigDict(extra="forbid")

    # 위 한 칸짜리 모양을 목록으로 담는다.
    picks: list[PickDraft]


# 추천 한 칸. 상품 이름 대신 후보 번호로 받아 범위를 코드가 막는다
class Pick(BaseModel):
    # 정해 둔 칸 말고 다른 칸이 오면 거절한다.
    model_config = ConfigDict(extra="forbid")

    # 후보 목록에서 몇 번인지다.
    number: int = Field(description="후보 목록의 번호")
    # 왜 골랐는지 한 문장이다.
    reason: str = Field(description="왜 이 사람에게 맞는가")

    # reason 칸 하나만 따로 검사한다.
    @field_validator("reason")
    # 이 검사는 객체가 아니라 클래스에 붙는다.
    @classmethod
    def check_reason(cls, value):
        # 앞뒤 공백을 떼고 길이를 잰다.
        value = value.strip()
        # 파이썬은 이렇게 두 조건을 한 줄로 이어 쓸 수 있다.
        if not MIN_REASON <= len(value) <= MAX_REASON:
            # 지금 몇 자인지까지 알려 줘야 모델이 다시 고칠 수 있다.
            raise ValueError(f"이유는 {MIN_REASON}~{MAX_REASON}자여야 한다 (지금 {len(value)}자)")
        # 공백을 떼어 낸 값을 그대로 쓰게 돌려준다.
        return value

    # mode="after" 는 칸을 다 채운 뒤에 전체를 보고 검사한다는 뜻이다.
    @model_validator(mode="after")
    def within_candidates(self, info):
        # 번호는 1 부터 시작한다.
        if self.number < 1:
            # 무엇을 골랐는지 같이 알려 준다.
            raise ValueError(f"번호는 1부터다 ({self.number} 을 골랐다)")
        # 후보가 몇 개였는지는 부르는 쪽이 context 로 넘겨 준다.
        limit = (info.context or {}).get("n_candidates")
        # 안 넘겨줬으면 범위 검사는 건너뛴다.
        if limit is not None and self.number > limit:
            # 올바른 범위를 숫자로 분명히 알려 준다.
            raise ValueError(f"후보는 1~{limit} 번인데 {self.number} 번을 골랐다")
        # 검사를 통과한 자기 자신을 돌려준다.
        return self


# 추천 묶음. 개수와 중복까지 여기서 막는다
class Recommendation(BaseModel):
    # 정해 둔 칸 말고 다른 칸이 오면 거절한다.
    model_config = ConfigDict(extra="forbid")

    # 검사를 마친 한 칸짜리 모양을 목록으로 담는다.
    picks: list[Pick]

    # picks 목록 전체를 보고 검사한다.
    @field_validator("picks")
    # 이 검사는 객체가 아니라 클래스에 붙는다.
    @classmethod
    def check_picks(cls, picks):
        # 하나도 안 고르거나 너무 많이 고른 것을 막는다.
        if not 1 <= len(picks) <= MAX_PICKS:
            # 지금 몇 개인지까지 알려 준다.
            raise ValueError(f"1~{MAX_PICKS}개를 골라야 한다 (지금 {len(picks)}개)")
        # 고른 번호만 목록으로 모은다.
        numbers = [p.number for p in picks]
        # set 은 중복을 없애므로 개수가 줄었으면 같은 번호를 두 번 고른 것이다.
        if len(set(numbers)) != len(numbers):
            # 어떤 번호를 골랐는지 그대로 보여 준다.
            raise ValueError(f"같은 번호를 여러 번 골랐다: {numbers}")
        # 검사를 통과한 목록을 그대로 돌려준다.
        return picks


# 고객 목록 한 줄
class CustomerBrief(BaseModel):
    # 고객을 가리키는 아이디다.
    customer_id: str
    # 고객 이름이다.
    name: str
    # 나이다.
    age: int
    # 성별이다.
    gender: str
    # 피부 타입이다. 안전 필터가 이 값을 본다.
    skin_type: str
    # 사는 도시다.
    city: str
    # 구매 건수다. 안 주면 0 으로 둔다.
    n_purchases: int = 0


# 구매 이력 한 줄. rating 과 review 는 표가 NULL 을 허용해서 None 이 될 수 있다
class PurchaseRow(BaseModel):
    # 어떤 상품을 샀는지 가리키는 아이디다.
    product_id: str
    # 상품 이름이다.
    name: str
    # 상품 카테고리다.
    category: str
    # 가격이다.
    price: int
    # 언제 샀는지다.
    purchased_at: str
    # 세로 막대는 둘 중 하나라는 뜻이다. 별점이 없을 수 있다.
    rating: int | None = None
    # 후기 원문이다. 없을 수 있다.
    review: str | None = None
    # 개인정보를 가린 후기다. 밖으로는 이 값이 나간다.
    review_masked: str = ""


# 고객 한 명의 판. 요약과 구매 이력을 같이 담는다
class Dashboard(BaseModel):
    # 위에서 정한 고객 한 줄 모양을 그대로 쓴다.
    customer: CustomerBrief
    # 별점이 하나도 없으면 평균을 낼 수 없어 None 이 된다.
    avg_rating: float | None = None
    # 지금까지 쓴 금액의 합이다.
    total_spent: int = 0
    # 카테고리 이름을 열쇠로, 건수를 값으로 담는다.
    by_category: dict[str, int] = {}
    # 구매 이력 전체다.
    purchases: list[PurchaseRow] = []


# 추천 후보 한 칸. 뽑힌 근거를 같이 들고 다닌다
class Candidate(BaseModel):
    # 후보 목록에서 몇 번인지다. 모델이 이 번호로 고른다.
    number: int
    # 상품을 가리키는 아이디다.
    product_id: str
    # 상품 이름이다.
    name: str
    # 브랜드 이름이다.
    brand: str
    # 카테고리다.
    category: str
    # 가격이다.
    price: int
    # 어떤 피부 타입용인지다.
    skin_type: str
    # 주요 성분이다.
    ingredient: str
    # 어떤 고민에 맞는지다.
    concern: str
    # 벡터로 잰 가까운 정도다. 클수록 가깝다.
    score: float
    # 모델이 쓴 추천 이유다. 아직 없으면 빈 글자다.
    reason: str = ""
    # 안전 필터에 막혔는지 여부다.
    blocked: bool = False
    # 막혔다면 그 근거 문장이다.
    blocked_reason: str = ""


# 추천 결과. 고른 것과 막힌 것을 같이 돌려준다
class Recommended(BaseModel):
    # 누구에게 추천한 것인지다.
    customer_id: str
    # 최종적으로 고른 상품들이다.
    picked: list[Candidate]
    # 안전 필터에 막혀 뺀 상품들이다. 왜 없는지 화면이 보여 줄 수 있다.
    blocked: list[Candidate] = []
    # 어떤 필터를 걸었는지 이름이다.
    filter_used: str = ""
    # 후보가 몇 개였는지다.
    n_candidates: int = 0
    # 모델을 실제로 불렀는지 여부다. 실패하면 거짓이다.
    llm_used: bool = False
    # 형식이 틀려 몇 번 다시 시켰는지다.
    retries: int = 0


# 질문 요청. 글자 수와 빈 값을 여기서 막는다
class AskRequest(BaseModel):
    # 고객을 지정하지 않고 물을 수도 있다.
    customer_id: str | None = None
    # 너무 짧거나 긴 질문을 여기서 막는다.
    question: str = Field(min_length=2, max_length=MAX_QUESTION_CHARS)

    # question 칸 하나만 따로 검사한다.
    @field_validator("question")
    # 이 검사는 객체가 아니라 클래스에 붙는다.
    @classmethod
    def not_blank(cls, value):
        # 공백만 잔뜩 보내면 길이 검사는 통과하지만 질문이 아니다.
        if not value.strip():
            # 그래서 여기서 따로 막는다.
            raise ValueError("질문이 비었다")
        # 앞뒤 공백을 떼어 낸 값을 쓰게 돌려준다.
        return value.strip()


# 답변 아래 붙는 출처. 어느 상품 어느 섹션에서 나왔나
class Source(BaseModel):
    # 어느 상품의 자료인지다.
    product_id: str
    # 화면에 보일 상품 이름이다.
    product_name: str
    # 그 상품 문서의 어느 섹션인지다.
    section: str
    # 질문과 얼마나 가까웠는지다.
    score: float
    # 실제 근거가 된 글이다.
    text: str


# 살아 있나. 지금 무슨 모델로 도는지 같이 준다
class HealthInfo(BaseModel):
    # 서버가 답할 수 있는 상태인지다.
    ok: bool
    # 상용 API 인지 로컬인지다.
    backend: str
    # 지금 쓰는 대화 모델 이름이다.
    llm: str
    # 지금 쓰는 임베딩 모델 이름이다.
    embed: str
    # 지금 보는 DB 파일 위치다.
    db: str


# 받을 준비가 됐나. 아직이면 503 으로 나간다
class ReadyInfo(BaseModel):
    # 전부 준비됐는지에 대한 한마디 답이다.
    ready: bool
    # 항목 이름과 그 항목이 준비됐는지를 담는다.
    checks: dict[str, bool] = {}


# 지금 설정. 화면이 표시한다
class ConfigInfo(BaseModel):
    # 지금 쓰는 대화 모델 이름이다.
    llm: str
    # 지금 쓰는 임베딩 모델 이름이다.
    embed: str
    # 상용 API 인지 로컬인지다.
    backend: str
    # 지금 보는 DB 파일 위치다.
    db: str


# 오늘 쓴 양과 하루 한도
class UsageInfo(BaseModel):
    # 오늘 이 사용자가 몇 번 썼는지다.
    used_today: int
    # 하루에 몇 번까지 쓸 수 있는지다.
    quota: int


# 비슷한 후기 한 줄
class SimilarReview(BaseModel):
    # 어느 구매의 후기인지 가리키는 번호다.
    purchase_id: str
    # 어떤 상품의 후기인지다.
    product_name: str
    # 별점이 없을 수 있다.
    rating: int | None = None
    # 찾을 때 쓴 글과 얼마나 가까웠는지다.
    score: float
    # 개인정보를 가린 후기 글이다.
    review: str


# 비슷한 후기 묶음. 무엇으로 찾았는지 같이 준다
class SimilarReviews(BaseModel):
    # 무슨 글로 찾았는지 그대로 담는다.
    query: str
    # 그 글이 어느 상품의 후기였는지다.
    product_name: str
    # 찾아낸 비슷한 후기들이다.
    found: list[SimilarReview] = []
