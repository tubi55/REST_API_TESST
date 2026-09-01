"""상품 데이터를 조회하고 등록, 수정, 삭제한다."""

# 벡터를 못 만든 것 같은 문제를 남기기 위해 사용한다.
import logging

# 벡터 저장소 객체를 얻는 함수다.
from app.adapters.stores import get_store

# 상품 한 건을 검색용 문장 하나로 만드는 순수 함수다.
from app.domain.embedding_text import product_text

# 글의 지문을 만드는 함수와 한 건만 벡터를 맞추는 함수다.
from app.features.embedding_sync import fingerprint, sync_one

# 받아 줄 카테고리와 피부 타입 목록이다.
from app.features.product_schemas import CATEGORIES, SKIN_TYPES

# 주의사항이 바뀌었을 때 금지 목록을 다시 읽게 하는 함수다.
from app.features.safety_filter import reset as reset_safety_filter

# 표에 닿는 저장소들과 여러 문장을 묶는 도구를 가져온다.
from app.repositories import (
    # 상세 문서 표에 닿는다.
    get_detail_repo,
    # 상품 표에 닿는다.
    get_product_repo,
    # 구매 표에 닿는다.
    get_purchase_repo,
    # 중간에 터지면 통째로 되돌린다.
    transaction,
)

# 이 파일에서 계속 쓸 상세 저장소를 한 번만 잡아 둔다.
detail_repo = get_detail_repo()

# 이 파일에서 계속 쓸 상품 저장소를 한 번만 잡아 둔다.
product_repo = get_product_repo()

# 이 파일에서 계속 쓸 구매 저장소를 한 번만 잡아 둔다.
purchase_repo = get_purchase_repo()

# 이 파일에서 남기는 기록에 모듈 이름을 붙여 준다.
log = logging.getLogger(__name__)

# 맨 앞의 product_id 를 뺀 나머지가 밖에서 고칠 수 있는 컬럼이다.
WRITABLE = product_repo.COLUMNS[1:]


# CRUD 가 거부한 이유. app/api/errors.py 가 이걸 HTTP 상태로 옮긴다
class ProductError(Exception):
    # 어떤 종류의 거부인지, 무슨 말을 보여 줄지, 어느 칸이 문제인지를 받는다.
    def __init__(self, kind, message, field=None):
        # 파이썬 기본 오류가 하던 일을 그대로 하게 둔다.
        super().__init__(message)
        # 'validation' · 'not_found' · 'conflict' 중 하나다.
        self.kind = kind
        # 화면에 보일 설명이다.
        self.message = message
        # 어느 칸 때문인지다. 없을 수도 있다.
        self.field = field


# 값이 우리가 허용한 목록 안에 있나
def _check_choices(values):
    # 값을 안 줬으면 검사하지 않는다. 부분 수정에서는 안 준 칸이 많다.
    if values.get("category") is not None and values["category"] not in CATEGORIES:
        # 쓸 수 있는 값을 전부 보여 줘야 화면에서 고칠 수 있다.
        raise ProductError("validation", f"category 는 {', '.join(CATEGORIES)} 중 하나다",
                           # 어느 칸이 문제인지 알려 준다.
                           "category")
    # 피부 타입도 같은 방식으로 본다.
    if values.get("skin_type") is not None and values["skin_type"] not in SKIN_TYPES:
        # 밖으로 나가는 이름은 화면이 쓰는 camelCase 로 적는다.
        raise ProductError("validation", f"skinType 은 {', '.join(SKIN_TYPES)} 중 하나다",
                           # 어느 칸이 문제인지 알려 준다.
                           "skinType")


# 벡터가 있나, 그리고 그 벡터가 지금 글로 만든 것인가를 붙여 준다
def _with_vector_flag(rows):
    # 볼 행이 없으면 그대로 돌려준다.
    if not rows:
        # 빈 목록을 그대로 준다.
        return rows
    # ids= 를 붙여 이 행들의 지문만 읽는다. 표를 통째로 읽지 않는다.
    known = get_store().hashes("product",
                               # 저장소가 아이디를 글자로 다루므로 여기서도 글자로 맞춘다.
                               ids=[str(row["product_id"]) for row in rows])
    # 행을 하나씩 보면서 두 값을 붙인다.
    for row in rows:
        # 저장된 지문을 꺼낸다. 없으면 None 이다.
        mark = known.get(str(row["product_id"]))
        # 지문이 있으면 벡터도 있는 것이다.
        row["has_vector"] = mark is not None
        # 지금 글로 만든 지문과 다르면 다시 만들어야 한다는 뜻이다.
        row["needs_embedding"] = mark != fingerprint(product_text(row))
    # 두 값이 붙은 행들을 돌려준다.
    return rows


# 이 상품의 검색용 문장을 만들어 벡터를 맞춘다. 실패해도 던지지 않는다
def _resync(product_id):
    # 문장을 만들 재료를 읽는다.
    row = product_repo.find_embedding_source(product_id)
    # 임베딩은 밖에 있는 모델을 부르는 일이라 실패할 수 있다.
    try:
        # 지문이 같으면 sync_one 이 알아서 건너뛴다.
        return sync_one("product", product_id, product_text(row))
    # 어떤 오류든 잡는다.
    except Exception as exc:
        # 벡터를 못 만들었다고 기록만 남긴다.
        log.warning("상품 %s 의 벡터를 못 만들었다: %s", product_id, exc)
        # 상품 저장 자체는 이미 끝났으므로 요청을 실패로 만들지 않는다.
        return None


# 조각 표에 베껴 둔 상품 이름을 맞춘다. 조각 글은 안 바뀌므로 벡터는 그대로다
def _resync_chunk_names(product_id):
    # 지금 이름을 읽는다.
    name = product_repo.find_name(product_id)
    # 상품이 없으면 고칠 것도 없다.
    if name is None:
        # 그대로 끝낸다.
        return
    # 곁 값만 고치는 자리라 벡터도 캐시도 건드리지 않는다.
    get_store().set_payload("chunk", detail_repo.chunk_ids_for_product(product_id),
                            # 이 컬럼을 이 이름으로 바꾼다.
                            "product_name", name)


# 이 상품의 벡터를 지금 글에 맞춘다. 이미 맞으면 아무것도 안 한다.
def reindex_product(product_id):
    # 없는 상품이면 여기서 멈춘다.
    if get_product(product_id) is None:
        # api/errors.py 가 이 종류를 404 로 옮긴다.
        raise ProductError("not_found", "그런 상품이 없다")
    # 상품 벡터를 지금 글에 맞춘다.
    _resync(product_id)
    # 조각에 베껴 둔 이름도 맞춘다.
    _resync_chunk_names(product_id)
    # 맞춘 뒤의 상태를 다시 읽어 돌려준다.
    return get_product(product_id)


# 목록. Spring Data 의 Page 모양으로 돌려준다
def list_products(keyword=None, category=None, skin_type=None,
                  # 몇 쪽의 몇 건을, 무엇을 기준으로 어느 방향으로 줄 세울지다.
                  page=0, size=20, sort="name", order="asc"):
    # 조건과 쪽 정보를 그대로 저장소에 넘긴다. SQL 은 저장소에만 있다.
    rows, total = product_repo.find_page(keyword=keyword, category=category,
                                         # 피부 타입과 쪽 정보를 넘긴다.
                                         skin_type=skin_type, page=page, size=size,
                                         # 정렬 기준과 방향을 넘긴다.
                                         sort=sort, order=order)
    # 화면이 기대하는 이름으로 담아 돌려준다.
    return {"content": _with_vector_flag(rows), "total_elements": total,
            # 지금 쪽 번호와 한 쪽 건수도 같이 준다.
            "number": page, "size": size}


# 한 건. 없으면 None
def get_product(product_id):
    # 상품 한 건을 읽는다.
    row = product_repo.find_by_id(product_id)
    # 목록용 함수를 한 건에도 쓰려고 목록에 담았다가 다시 꺼낸다.
    return _with_vector_flag([row])[0] if row else None


# 새 상품을 만들고 그 자리에서 벡터를 만든다
def create_product(draft):
    # 카테고리와 피부 타입이 허용 목록 안인지 먼저 본다.
    _check_choices(draft)
    # 고칠 수 있는 컬럼만 골라 담는다. 안 준 칸은 빈 글자로 둔다.
    values = {name: draft.get(name, "") for name in WRITABLE}

    # 번호를 다른 요청이 먼저 가져갈 수 있어 몇 번 다시 시도한다.
    for _attempt in range(5):
        # 지금 쓸 수 있는 다음 번호를 받는다.
        product_id = product_repo.next_id()
        # 잘 들어갔으면 참이 온다.
        if product_repo.insert(product_id, values):
            # 성공했으니 반복을 멈춘다.
            break
    # for 에 붙는 else 는 break 없이 다 돌았을 때만 실행된다.
    else:
        # 다섯 번을 다 실패했으면 부르는 쪽이 다시 시도하게 한다.
        raise ProductError("conflict", "상품 번호를 못 정했다. 다시 시도할 것")

    # 넣자마자 검색에 걸리도록 그 자리에서 벡터를 만든다.
    _resync(product_id)
    # 만들어진 상품을 다시 읽어 돌려준다.
    return get_product(product_id)


# 준 값만 고치고 벡터를 맞춘다
def update_product(product_id, patch):
    # 없는 상품이면 여기서 멈춘다.
    if get_product(product_id) is None:
        # api/errors.py 가 이 종류를 404 로 옮긴다.
        raise ProductError("not_found", "그런 상품이 없다")
    # 준 값이 허용 목록 안인지 본다.
    _check_choices(patch)

    # 실제로 준 칸만 골라 넘긴다.
    product_repo.update(product_id,
                        # None 은 안 고친다는 뜻이므로 여기서 걸러 낸다.
                        {name: value for name, value in patch.items()
                         # 값이 있는 것만 남긴다.
                         if value is not None})
    # 글이 바뀌었을 수 있으니 벡터를 맞춘다.
    _resync(product_id)
    # 조각에 베껴 둔 이름도 맞춘다.
    _resync_chunk_names(product_id)
    # 고친 뒤의 상태를 다시 읽어 돌려준다.
    return get_product(product_id)


# 상품과 그에 딸린 것을 전부 지운다. 구매 이력이 있으면 거부한다
def delete_product(product_id):
    # 없는 상품이면 여기서 멈춘다.
    if get_product(product_id) is None:
        # api/errors.py 가 이 종류를 404 로 옮긴다.
        raise ProductError("not_found", "그런 상품이 없다")

    # 산 사람이 있는 상품을 지우면 구매 이력이 가리킬 곳을 잃는다.
    used = purchase_repo.count_for_product(product_id)
    # 한 건이라도 있으면 지우지 않는다.
    if used:
        # 몇 건이 있는지까지 알려 준다.
        raise ProductError("conflict", f"구매 이력이 {used}건 있어 지울 수 없다")

    # 여러 표를 지우는 동안 중간에 터지면 통째로 되돌린다.
    with transaction():
        # 벡터 저장소를 얻는다.
        store = get_store()
        # 이 상품에 딸린 조각 벡터를 먼저 지운다.
        store.delete("chunk", detail_repo.chunk_ids_for_product(product_id))
        # 상품 벡터도 지운다.
        store.delete("product", [product_id])

        # 상세 · 섹션 · 조각 표의 행을 지운다.
        detail_repo.delete_for_product(product_id)
        # 마지막으로 상품 행을 지운다.
        product_repo.delete(product_id)

    # 주의사항이 사라졌으니 금지 목록을 다시 읽게 한다.
    reset_safety_filter()
