"""모델 사용 기록을 저장하고 사용자별 사용량을 확인한다."""

# 오늘 날짜와 지금 시각을 얻기 위해 사용한다.
from datetime import datetime

# 하루에 몇 번까지 쓸 수 있는지 정한 설정값이다.
from app.core.config import DAILY_QUOTA

# 아직 저장소를 안 붙였다는 뜻으로 None 을 넣어 둔다.
_repo = None


# 어느 저장소에 쌓을지 정한다. 뜰 때 한 번 부른다
def use_repository(repo):
    # 함수 안에서 모듈 전역 변수에 값을 넣기 위해 global 을 사용한다.
    global _repo
    # 받은 저장소를 이 모듈이 계속 쓴다.
    _repo = repo


# 붙여 둔 저장소. 안 붙었으면 부르는 자리를 알려 주고 죽는다
def _store():
    # 아직 안 붙었으면 기록할 곳이 없다.
    if _repo is None:
        # 어디를 고쳐야 하는지 파일 이름까지 알려 준다.
        raise RuntimeError(
            # 어느 파일의 어느 함수가 붙여 주는지까지 적어 둔다.
            "usage 저장소가 안 붙었다. app/api/lifespan.py 가 use_repository() 를 부른다")
    # 붙여 둔 저장소를 돌려준다.
    return _repo

# 아래 단가를 확인한 날짜다. 값을 다시 볼 때 기준이 된다.
PRICING_AS_OF = "2026-08-28"
# 백만 토큰당 달러 단가다. in 은 입력, out 은 출력이다.
PRICING = {
    # 상용 대화 모델의 단가다.
    "gpt-4o-mini":            {"in": 0.15, "out": 0.60},
    # 상용 임베딩 모델의 단가다. 출력 토큰이 없어 0 이다.
    "text-embedding-3-small": {"in": 0.02, "out": 0.0},
    # 내 컴퓨터에서 도는 모델이라 돈이 들지 않는다.
    "qwen-cpu":               {"in": 0.0,  "out": 0.0},
}

# 하루 사용 횟수를 셀 때 세는 기능들이다. 나머지 기능은 쿼터를 안 쓴다.
QUOTA_FEATURES = ("ask", "recommend")


# 이 호출이 얼마짜리였나 (달러). 토큰 수를 모르면 0 이다
def cost_of(model, in_tokens, out_tokens):
    # 이름이 정확히 맞는 단가를 먼저 찾는다.
    price = PRICING.get(model)
    # 정확히 맞는 것이 없으면 앞부분만 맞는 것을 찾아본다.
    if price is None:
        # 긴 이름부터 보면 더 구체적인 쪽이 먼저 걸린다.
        for key in sorted(PRICING, key=len, reverse=True):
            # 모델 이름이 이 열쇠로 시작하는지 본다.
            if model.startswith(key):
                # 찾았으면 그 단가를 쓴다.
                price = PRICING[key]
                # 더 볼 필요가 없으므로 반복을 멈춘다.
                break
    # 단가를 모르거나 입력 토큰 수를 모르면 계산할 수 없다.
    if price is None or in_tokens is None:
        # 지어낸 숫자를 적지 않고 0 으로 둔다.
        return 0.0
    # 단가는 백만 토큰 기준이므로 100만으로 나눈다. 출력 토큰이 없으면 0 으로 친다.
    return (in_tokens * price["in"] + (out_tokens or 0) * price["out"]) / 1_000_000


# 지금 시각을 표에 적는 모양으로
def _now():
    # 초 단위까지만 남기고 '2026-08-28T21:03:11' 같은 문자열로 만든다.
    return datetime.now().isoformat(timespec="seconds")


# 쿼터를 한 칸 먼저 잡는다. 잡았으면 줄 번호, 다 썼으면 None.
def reserve(user_id, feature):
    # 실제 세는 일은 저장소가 한다. 여기서는 필요한 값만 모아 넘긴다.
    return _store().reserve_log(
        # 언제, 누가, 어느 기능인지를 적는다.
        at=_now(), user_id=user_id, feature=feature,
        # 하루 단위로 세므로 오늘 날짜를 함께 넘긴다.
        day=datetime.now().date().isoformat(),
        # 어떤 기능을 셀지와 하루 상한을 알려 준다.
        quota_features=QUOTA_FEATURES, limit=DAILY_QUOTA
    )


# 잡아 둔 칸에 실제로 든 것을 적는다. 돌아온 값은 이 호출의 원가다
def settle(log_id, *, model, in_tokens=None, out_tokens=None, seconds=None):
    # 토큰 수와 모델 이름으로 값을 계산한다.
    cost = cost_of(model, in_tokens, out_tokens)
    # 미리 잡아 둔 줄에 실제 값을 채워 넣는다.
    _store().settle_log(
        # 어느 줄인지와 어떤 모델이었는지 적는다.
        log_id, model=model, in_tokens=in_tokens,
        # 출력 토큰 수와 걸린 시간을 적는다.
        out_tokens=out_tokens, seconds=seconds, cost=cost
    )
    # 계산한 원가를 부른 쪽에도 돌려준다.
    return cost


# 요청 하나를 기록한다
def record(user_id, feature, *, model, in_tokens=None, out_tokens=None, seconds=None):
    # 토큰 수와 모델 이름으로 값을 계산한다.
    cost = cost_of(model, in_tokens, out_tokens)
    # 미리 잡아 두지 않고 한 줄을 바로 넣는다.
    _store().insert_log(
        # 언제, 누가, 어느 기능을, 어떤 모델로 불렀는지 적는다.
        at=_now(), user_id=user_id, feature=feature, model=model,
        # 입력과 출력 토큰 수를 적는다.
        in_tokens=in_tokens, out_tokens=out_tokens,
        # 걸린 시간과 계산한 값을 적는다.
        seconds=seconds, cost=cost
    )
    # 계산한 원가를 부른 쪽에도 돌려준다.
    return cost


# 오늘 이 사용자가 쿼터를 몇 번 썼나
def used_today(user_id):
    # 오늘 날짜와 셀 기능 목록을 함께 넘겨 저장소가 세게 한다.
    return _store().count_today(user_id, datetime.now().date().isoformat(), QUOTA_FEATURES)
