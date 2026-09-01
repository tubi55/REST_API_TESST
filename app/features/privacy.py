"""DB의 고객 정보와 개인정보 마스킹 규칙을 연결한다."""

# 개인정보를 가리는 순수 함수들이 모여 있는 모듈이다.
from app.domain import masking

# 고객 표에 닿는 저장소를 얻는 함수다.
from app.repositories import get_customer_repo

# 이 파일에서 계속 쓸 고객 저장소를 한 번만 잡아 둔다.
customer_repo = get_customer_repo()

# 아직 이름 사전을 안 읽었다는 뜻으로 None 을 넣어 둔다.
_names = None

# 아직 주소 정규식을 안 만들었다는 뜻으로 None 을 넣어 둔다.
_address = None


# 이름·도시 사전을 한 번만 읽어 둔다
def _load():
    # 함수 안에서 모듈 전역 변수에 값을 넣기 위해 global 을 사용한다.
    global _names, _address
    # 이미 읽었으면 다시 읽지 않는다.
    if _names is not None:
        # 그대로 끝낸다.
        return
    # 고객 이름을 중복 없이 모아 사전으로 삼는다.
    _names = customer_repo.distinct_names()
    # 도시 목록으로 주소를 찾는 정규식을 만들어 둔다.
    _address = masking.build_address_pattern(customer_repo.distinct_cities())


# 사전을 붙여 개인정보를 지운다. 앱은 이 함수만 부른다
def mask_text(text):
    # 아직 안 읽었으면 여기서 읽는다.
    _load()
    # 사전 없이 부르면 이름과 주소가 안 가려지므로 반드시 이 함수를 거친다.
    return masking.mask(text, names=_names, address=_address)


# 밖으로 내보내는 이름은 이것 하나다. 사전 없는 mask 를 직접 부르지 않게 한다.
__all__ = ["mask_text"]
