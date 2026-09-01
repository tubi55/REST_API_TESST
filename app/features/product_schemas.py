"""상품 API에서 사용하는 요청과 응답 형식을 정의한다."""

# 목록 안에 들어갈 종류를 나중에 정하는 틀을 만들기 위해 사용한다.
from typing import Generic, TypeVar

# 모양을 정하는 BaseModel, 설정을 담는 ConfigDict, 칸마다 조건을 다는 Field 다.
from pydantic import BaseModel, ConfigDict, Field

# snake_case 이름을 camelCase 로 바꿔 주는 함수다.
from pydantic.alias_generators import to_camel

# 자리를 비워 둔 종류 이름이다. Page 를 만들 때 실제 종류가 정해진다.
T = TypeVar("T")

# 상품 카테고리로 받아 줄 값들이다. 여기 없는 값은 거절한다.
CATEGORIES = ("로션", "토너", "클렌징오일", "미스트", "앰플", "에센스",
              # 뒤쪽 여섯 개도 같은 목록의 일부다.
              "아이크림", "클렌징폼", "크림", "세럼", "선크림", "마스크팩")
# 피부 타입으로 받아 줄 값들이다.
SKIN_TYPES = ("건성", "지성", "복합성", "민감성", "모든 피부")


# JSON 은 camelCase, 파이썬은 snake_case 로 주고받는다
class CamelModel(BaseModel):
    # populate_by_name 은 파이썬 이름으로도 값을 채울 수 있게 한다.
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# 목록 한 쪽. 내용과 전체 건수를 같이 준다
class Page(CamelModel, Generic[T]):
    # 이번 쪽에 담긴 항목들이다. 종류는 쓰는 쪽이 정한다.
    content: list[T]
    # 조건에 맞는 전체 건수다. 쪽 나누기에 필요하다.
    total_elements: int
    # 지금 몇 번째 쪽인지다.
    number: int
    # 한 쪽에 몇 건인지다.
    size: int


# 만들거나 고칠 때 받는 값. product_id 는 서버가 정한다
class ProductDraft(CamelModel):
    # 이름은 비울 수 없고 60자까지다.
    name: str = Field(min_length=1, max_length=60)
    # 브랜드도 비울 수 없고 40자까지다.
    brand: str = Field(min_length=1, max_length=40)
    # 값 검사는 features/products.py 가 목록과 대조해 따로 한다.
    category: str
    # ge 는 이 값 이상, le 는 이 값 이하라는 뜻이다.
    price: int = Field(ge=0, le=10_000_000)
    # 안 주면 빈 글자로 둔다.
    volume: str = Field(default="", max_length=20)
    # 값 검사는 features/products.py 가 목록과 대조해 따로 한다.
    skin_type: str
    # 주요 성분이다. 안 줘도 된다.
    ingredient: str = Field(default="", max_length=60)
    # 어떤 고민에 맞는지다. 안 줘도 된다.
    concern: str = Field(default="", max_length=60)
    # 검색에 쓰는 태그다. 안 줘도 된다.
    tags: str = Field(default="", max_length=120)
    # 상품 설명이다. 안 줘도 된다.
    description: str = Field(default="", max_length=2000)


# 부분 수정. 준 것만 바뀐다
class ProductPatch(CamelModel):
    # 세로 막대는 둘 중 하나라는 뜻이다. None 이면 안 고친다는 뜻이다.
    name: str | None = Field(default=None, min_length=1, max_length=60)
    # 브랜드도 안 주면 안 고친다.
    brand: str | None = Field(default=None, min_length=1, max_length=40)
    # 카테고리도 안 주면 안 고친다.
    category: str | None = None
    # 가격도 안 주면 안 고친다.
    price: int | None = Field(default=None, ge=0, le=10_000_000)
    # 용량도 안 주면 안 고친다.
    volume: str | None = Field(default=None, max_length=20)
    # 피부 타입도 안 주면 안 고친다.
    skin_type: str | None = None
    # 성분도 안 주면 안 고친다.
    ingredient: str | None = Field(default=None, max_length=60)
    # 고민도 안 주면 안 고친다.
    concern: str | None = Field(default=None, max_length=60)
    # 태그도 안 주면 안 고친다.
    tags: str | None = Field(default=None, max_length=120)
    # 설명도 안 주면 안 고친다.
    description: str | None = Field(default=None, max_length=2000)


# 밖으로 나가는 상품 한 건
class Product(CamelModel):
    # 상품을 가리키는 아이디다. 서버가 정한다.
    product_id: str
    # 상품 이름이다.
    name: str
    # 브랜드 이름이다.
    brand: str
    # 카테고리다.
    category: str
    # 가격이다.
    price: int
    # 용량이다. 없으면 빈 글자다.
    volume: str = ""
    # 어떤 피부 타입용인지다.
    skin_type: str
    # 주요 성분이다.
    ingredient: str = ""
    # 어떤 고민에 맞는지다.
    concern: str = ""
    # 검색에 쓰는 태그다.
    tags: str = ""
    # 상품 설명이다.
    description: str = ""
    # CSV 에서 온 행인지 화면에서 넣은 행인지 표시다.
    source: str = "csv"
    # 이 상품의 벡터가 있는지다.
    has_vector: bool = False
    # 지금 글로 벡터를 다시 만들어야 하는지다.
    needs_embedding: bool = False


# 폼의 선택 목록. 화면이 값을 하드코딩하지 않게 서버가 준다
class ProductOptions(CamelModel):
    # 위에 정해 둔 카테고리를 목록으로 바꿔 내보낸다.
    categories: list[str] = list(CATEGORIES)
    # 피부 타입도 같은 방식으로 내보낸다.
    skin_types: list[str] = list(SKIN_TYPES)
