"""DB의 상품 주의사항에 안전 필터 규칙을 적용한다."""

# 금지 문장을 찾아내는 순수 함수들이 모여 있는 모듈이다.
from app.domain import safety

# 상세 문서 표에 닿는 저장소를 얻는 함수다.
from app.repositories import get_detail_repo

# 이 파일에서 계속 쓸 상세 저장소를 한 번만 잡아 둔다.
detail_repo = get_detail_repo()

# 아직 금지 목록을 안 만들었다는 뜻으로 None 을 넣어 둔다.
_bans = None


# 주의사항 섹션을 한 번만 읽어 금지 목록을 만든다
def _load():
    # 함수 안에서 모듈 전역 변수에 값을 넣기 위해 global 을 사용한다.
    global _bans
    # 이미 만들어 뒀으면 다시 읽지 않는다.
    if _bans is not None:
        # 그대로 끝낸다.
        return
    # 주의사항 글을 전부 읽어 상품별 금지 문장 목록으로 바꾼다.
    _bans = safety.extract_bans(detail_repo.caution_sections())


# 다음에 물어보면 다시 읽는다. 주의사항 글이 바뀐 뒤에 부른다
def reset():
    # 함수 안에서 모듈 전역 변수에 값을 넣기 위해 global 을 사용한다.
    global _bans
    # None 으로 되돌리면 다음 _load 가 DB 를 다시 읽는다.
    _bans = None


# 이 피부 타입 고객에게 추천하면 안 되는 상품 아이디들
def blocked_for(skin_type):
    # 아직 안 읽었으면 여기서 읽는다.
    _load()
    # 실제 판단은 순수 함수가 한다. 이 파일은 DB 를 붙여 줄 뿐이다.
    return safety.blocked_for(skin_type, _bans)


# 왜 막혔는지. 화면에 그대로 띄운다
def reason_for(product_id):
    # 아직 안 읽었으면 여기서 읽는다.
    _load()
    # 근거 문장 하나를 그대로 돌려준다. 없으면 빈 글자다.
    return safety.reason_for(product_id, _bans)
