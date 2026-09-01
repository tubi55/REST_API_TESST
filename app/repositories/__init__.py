"""정형 데이터 저장소 객체를 만들고 다른 계층에 제공한다."""

# 여러 문장을 한 덩어리로 묶는 도구다. 여기서 다시 내보내 다른 계층이 쓴다.
from app.core.db import transaction


# 상품 표. 약속은 app/domain/ports.py 의 ProductRepository 다
def get_product_repo():
    # 실제로 필요할 때 불러 불필요한 초기 로딩과 순환 import 를 피한다.
    from app.repositories import products

    # 이 프로젝트의 저장소는 클래스가 아니라 모듈 하나다. 모듈을 그대로 돌려준다.
    return products


# 고객 표
def get_customer_repo():
    # 필요할 때 불러온다.
    from app.repositories import customers

    # 고객 질의가 모여 있는 모듈을 돌려준다.
    return customers


# 구매와 후기 표
def get_purchase_repo():
    # 필요할 때 불러온다.
    from app.repositories import purchases

    # 구매와 후기 질의가 모여 있는 모듈을 돌려준다.
    return purchases


# 상세에서 파생된 세 표. product_details · sections · chunks
def get_detail_repo():
    # 필요할 때 불러온다.
    from app.repositories import details

    # 상세 문서 질의가 모여 있는 모듈을 돌려준다.
    return details


# usage_log 표
def get_usage_repo():
    # 필요할 때 불러온다.
    from app.repositories import usage

    # 사용 기록 질의가 모여 있는 모듈을 돌려준다.
    return usage


# 표 모양의 버전
def get_schema_repo():
    # 필요할 때 불러온다.
    from app.repositories import schema

    # 표 모양 관리 질의가 모여 있는 모듈을 돌려준다.
    return schema


# 뜰 때 한 번 도는 표 모양 바꾸기. 아직 안 돈 것만 돌고 돌았다고 적는다.
def apply_migrations(now):
    # 어디까지 왔는지 적어 두는 모듈을 가져온다.
    schema = get_schema_repo()
    # 기록할 표 자체가 없으면 먼저 만든다.
    schema.ensure_version_table()

    # (번호, 이름, 실제로 할 일) 을 순서대로 적어 둔다.
    steps = (
        # 1번은 사용 기록 표를 만드는 일이다.
        (1, "usage_log 표", lambda: get_usage_repo().ensure_table()),
        # 2번은 상품 표에 source 컬럼을 더하는 일이다.
        (2, "products.source 컬럼", lambda: get_product_repo().ensure_source_column()),
    )

    # 이 DB 가 지금 몇 번까지 마쳤는지 읽는다.
    done = schema.current_version()
    # 이번에 실제로 돈 단계를 모아 둘 목록이다.
    applied = []
    # 적어 둔 단계를 번호 순서대로 본다.
    for version, name, run in steps:
        # 이미 마친 번호면 건너뛴다.
        if version <= done:
            # 다음 단계로 넘어간다.
            continue
        # 아직 안 돈 단계를 실제로 돌린다.
        run()
        # 돌았다고 표에 적어 다음에 또 돌지 않게 한다.
        schema.record_version(version, name, now)
        # 서버 기록에 남길 수 있게 이번에 돈 것을 모아 둔다.
        applied.append(f"{version} {name}")
    # 이번에 실제로 돈 단계 목록을 돌려준다. 없으면 빈 목록이다.
    return applied


# 이 모듈에서 밖으로 내보내는 이름들이다. 여기 없는 것은 내부용으로 본다.
__all__ = ["apply_migrations", "get_customer_repo", "get_detail_repo",
           # 이름 순서로 적어 두면 빠진 것을 찾기 쉽다.
           "get_product_repo", "get_purchase_repo", "get_schema_repo",
           # transaction 은 위에서 가져와 다시 내보내는 것이다.
           "get_usage_repo", "transaction"]
