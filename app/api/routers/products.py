"""상품 조회, 등록, 수정, 삭제 API를 제공한다."""

# 라우터를 만들고, 의존성을 붙이고, 오류를 알리고, 조건에 범위를 다는 도구다.
from fastapi import APIRouter, Depends, HTTPException, Query

# 인증 · 사용 기록 맥락 · 쓰기 스위치를 보는 세 함수다.
from app.api.dependencies import caller, meter, writable

# 내부 오류를 HTTP 오류로 옮기는 함수다.
from app.api.errors import product_http

# 상품 CRUD 가 모여 있는 모듈이다.
from app.features import products

# 요청과 응답의 모양을 정해 둔 다섯 가지다.
from app.features.product_schemas import (
    # 목록 한 쪽의 모양이다.
    Page,
    # 밖으로 나가는 상품 한 건의 모양이다.
    Product,
    # 새로 만들 때 받는 값의 모양이다.
    ProductDraft,
    # 폼의 선택 목록 모양이다.
    ProductOptions,
    # 부분 수정에서 받는 값의 모양이다.
    ProductPatch,
)

# 이 파일의 주소는 모두 /api/products 로 시작한다.
router = APIRouter(prefix="/api/products", tags=["상품"])


# 폼의 선택 목록. 화면이 값을 하드코딩하지 않게 서버가 준다.
@router.get("/options", response_model=ProductOptions)
def product_options(user: str = Depends(caller)):
    # 기본값이 곧 목록이라 만들기만 하면 된다.
    return ProductOptions()


# 상품 목록 한 쪽. 검색어 · 분류 · 피부 타입으로 좁힌다
@router.get("", response_model=Page[Product])
def product_list(
    # 이름 · 브랜드 · 성분에서 찾을 검색어다. 안 줘도 된다.
    keyword: str | None = None,
    # 카테고리로 좁힌다. 안 줘도 된다.
    category: str | None = None,
    # 화면이 camelCase 로 보내므로 여기서도 그 이름 그대로 받는다.
    skinType: str | None = None,
    # ge=0 은 0 이상만 받는다는 뜻이다.
    page: int = Query(default=0, ge=0),
    # 한 번에 100건을 넘게 요청하지 못하게 막는다.
    size: int = Query(default=20, ge=1, le=100),
    # 무엇을 기준으로 줄 세울지다. 허용 목록은 저장소가 들고 있다.
    sort: str = "name",
    # 오름차순인지 내림차순인지다.
    order: str = "asc",
    # Depends(caller) 가 토큰을 확인하고 사용자 아이디를 넣어 준다.
    user: str = Depends(caller),
):
    # 받은 조건을 그대로 넘긴다. 이 층에는 SQL 도 표 이름도 없다.
    return products.list_products(keyword=keyword, category=category,
                                  # 밖의 camelCase 이름을 안쪽 snake_case 로 옮긴다.
                                  skin_type=skinType, page=page, size=size,
                                  # 정렬 기준과 방향을 넘긴다.
                                  sort=sort, order=order)


# 상품 한 건. 없으면 404
@router.get("/{product_id}", response_model=Product)
def product_get(product_id: str, user: str = Depends(caller)):
    # 한 건을 읽는다. 없으면 None 이 온다.
    row = products.get_product(product_id)
    # 없는 상품이면 여기서 멈춘다.
    if row is None:
        # 404 는 그런 자원이 없다는 뜻이다.
        raise HTTPException(status_code=404, detail="그런 상품이 없다")
    # 있으면 그대로 돌려준다.
    return row


# 새 상품. 만드는 즉시 그 한 건만 임베딩한다
@router.post("", response_model=Product, status_code=201,
             # 쓰기 문이 닫혀 있으면 이 자리에서 405 로 막힌다.
             dependencies=[Depends(writable)])
def product_create(draft: ProductDraft, user: str = Depends(caller)):
    # 임베딩을 부르므로 사용 기록에 남게 맥락을 붙인다.
    meter(user, "product_create")
    # 허용 목록에 없는 값이면 아래에서 오류가 온다.
    try:
        # model_dump 는 받은 값을 평범한 딕셔너리로 바꾼다.
        return products.create_product(draft.model_dump())
    # 상품 쪽이 거부한 경우다.
    except products.ProductError as exc:
        # 거부 종류에 맞는 HTTP 상태로 바꿔 다시 던진다.
        raise product_http(exc) from exc


# 부분 수정. 검색용 문장이 바뀌면 그 한 건만 다시 임베딩한다
@router.patch("/{product_id}", response_model=Product,
              # 쓰기 문이 닫혀 있으면 이 자리에서 405 로 막힌다.
              dependencies=[Depends(writable)])
def product_update(product_id: str, patch: ProductPatch,
                   # Depends(caller) 가 토큰을 확인하고 사용자 아이디를 넣어 준다.
                   user: str = Depends(caller)):
    # 임베딩을 부를 수 있으므로 사용 기록에 남게 맥락을 붙인다.
    meter(user, "product_update")
    # 없는 상품이거나 허용 목록 밖의 값이면 아래에서 오류가 온다.
    try:
        # exclude_unset 은 실제로 보낸 칸만 남긴다. 안 보낸 칸은 안 고친다.
        return products.update_product(product_id, patch.model_dump(exclude_unset=True))
    # 상품 쪽이 거부한 경우다.
    except products.ProductError as exc:
        # 거부 종류에 맞는 HTTP 상태로 바꿔 다시 던진다.
        raise product_http(exc) from exc


# 상품을 지운다. 구매 이력이 걸려 있으면 features 가 막는다
@router.delete("/{product_id}", status_code=204,
               # 쓰기 문이 닫혀 있으면 이 자리에서 405 로 막힌다.
               dependencies=[Depends(writable)])
def product_delete(product_id: str, user: str = Depends(caller)):
    # 없는 상품이거나 구매 이력이 있으면 아래에서 오류가 온다.
    try:
        # 204 는 잘 됐고 돌려줄 내용이 없다는 뜻이라 결과를 반환하지 않는다.
        products.delete_product(product_id)
    # 상품 쪽이 거부한 경우다.
    except products.ProductError as exc:
        # 거부 종류에 맞는 HTTP 상태로 바꿔 다시 던진다.
        raise product_http(exc) from exc


# 이 상품의 벡터를 지금 글에 맞춘다. 쓰기 스위치를 안 탄다.
@router.post("/{product_id}/reindex", response_model=Product)
def product_reindex(product_id: str, user: str = Depends(caller)):
    # 임베딩을 부르므로 사용 기록에 남게 맥락을 붙인다.
    meter(user, "product_reindex")
    # 없는 상품이면 아래에서 오류가 온다.
    try:
        # 상품 원본은 안 건드리고 벡터만 맞추므로 쓰기 문과 상관이 없다.
        return products.reindex_product(product_id)
    # 상품 쪽이 거부한 경우다.
    except products.ProductError as exc:
        # 거부 종류에 맞는 HTTP 상태로 바꿔 다시 던진다.
        raise product_http(exc) from exc
