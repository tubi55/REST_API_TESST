"""DB와 모델이 실제 요청을 처리할 준비가 되었는지 확인한다."""

# 점검이 실패한 이유를 남기기 위해 사용한다.
import logging

# 벡터 저장소 객체를 얻는 함수다.
from app.adapters.stores import get_store

# 임베딩기가 올라왔는지 묻기 위해 모듈째 가져온다.
from app.core import embedder

# 표 모양 버전을 읽는 저장소를 얻는 함수다.
from app.repositories import get_schema_repo

# 이 파일에서 남기는 기록에 모듈 이름을 붙여 준다.
log = logging.getLogger(__name__)

# 저장소가 살아 있는지 볼 때 찔러 보는 종류다.
PROBE_KIND = "product"


# 정형 데이터에 닿나. 이름 붙은 질의 하나로 본다
def _db_ok():
    # 버전이 0보다 크면 표가 만들어졌고 질의도 통했다는 뜻이다.
    return get_schema_repo().current_version() > 0


# 벡터 저장소가 섰나.
def _vector_store_ok():
    # 빈 아이디는 없으니 답은 늘 거짓이다. 노린 것은 답이 아니라 표를 실제로 읽어 보는 일이다.
    get_store().has(PROBE_KIND, "")
    # 위 줄이 오류 없이 지나갔으면 저장소가 선 것이다.
    return True


# 임베딩기가 올라왔나
def _embedder_ok():
    # 여기서 만들지 않는다. 확인만 하려다 449MB 모델을 올리면 안 된다.
    return embedder.is_loaded()


# 점검할 항목의 이름과 실제로 볼 함수를 짝지어 둔다.
CHECKS = (("db", _db_ok), ("vectors", _vector_store_ok), ("embedder", _embedder_ok))


# 각 항목이 준비됐나. {이름: 참거짓} 과 전체 판정을 돌려준다
def check():
    # 항목마다 결과를 담을 딕셔너리다.
    result = {}
    # 위에 적어 둔 점검을 하나씩 돌린다.
    for name, probe in CHECKS:
        # 한 항목이 터져도 나머지 점검은 계속 돌아야 한다.
        try:
            # bool 로 감싸 항상 참거짓으로 맞춘다.
            result[name] = bool(probe())
        # 어떤 오류든 잡아 그 항목만 실패로 본다.
        except Exception as exc:
            # 무엇이 왜 실패했는지 기록에 남긴다.
            log.warning("준비 점검 실패 (%s): %s", name, exc)
            # 이 항목은 준비가 안 된 것으로 적는다.
            result[name] = False
    # 항목별 결과와, 전부 참인지 여부를 함께 돌려준다.
    return result, all(result.values())
