"""상품 데이터를 조회하고 등록, 수정, 삭제한다."""

# 중복 키 오류와 DB 를 읽고 쓰는 공통 함수들을 가져온다.
from app.core.db import IntegrityError, dicts, execute, one, query

# 임베딩 문장을 만들 때 쓰는 컬럼 이름과 순서다. 한 곳에서만 정한다.
from app.domain.embedding_text import PRODUCT_FIELDS

# 화면에 돌려줄 컬럼들이다. 임베딩용 컬럼에 아이디와 용량을 앞뒤로 더한다.
COLUMNS = ("product_id",) + PRODUCT_FIELDS + ("volume",)

# 추천 후보 카드에 필요한 컬럼만 따로 모아 둔다.
CARD_COLUMNS = ("product_id", "name", "brand", "category", "price",
                # 뒤 셋은 피부 타입과 성분, 고민이다.
                "skin_type", "ingredient", "concern")

# 밖에서 온 정렬 이름을 실제 컬럼 이름으로 바꾼다. 여기 없는 이름은 안 받는다.
SORTABLE = {"name": "name", "price": "price", "createdAt": "product_id",
            # 화면이 쓰는 camelCase 이름도 같이 받아 준다.
            "productId": "product_id"}


# source 컬럼이 없으면 만든다. 서버가 뜰 때 한 번 부른다
def ensure_source_column():
    # PRAGMA table_info 는 표의 컬럼을 한 줄씩 주고 row[1] 이 이름이다.
    names = [row[1] for row in query("PRAGMA table_info(products)")]
    # 이미 있으면 다시 만들지 않는다.
    if "source" not in names:
        # 기존 행은 CSV 에서 온 것이므로 기본값을 'csv' 로 둔다.
        execute("ALTER TABLE products ADD COLUMN source TEXT NOT NULL DEFAULT 'csv'")


# 한 건. 없으면 None
def find_by_id(product_id):
    # 컬럼 이름을 쉼표로 이어 SELECT 문에 넣는다.
    rows = dicts(
        # 값인 상품 아이디는 '?' 자리로 넘긴다.
        f"SELECT {', '.join(COLUMNS)}, source FROM products WHERE product_id = ?",
        # 값이 하나여도 튜플이어야 하므로 뒤에 쉼표를 붙인다.
        (product_id,))
    # 한 건만 찾는 질의이므로 첫 줄만 준다. 없으면 None 이다.
    return rows[0] if rows else None


# 목록 한 쪽과 전체 건수. (행 목록, 전체 건수) 를 돌려준다
def find_page(*, keyword=None, category=None, skin_type=None,
              # 몇 쪽의 몇 건을, 무엇을 기준으로 어느 방향으로 줄 세울지 정한다.
              page=0, size=20, sort="name", order="asc"):
    # 조건 문장과 그 값을 따로 모은다. 값은 끝까지 '?' 로 간다.
    where, params = [], []
    # 검색어를 받았을 때만 조건을 더한다.
    if keyword:
        # 이름, 브랜드, 성분 중 하나라도 맞으면 걸리게 한다.
        where.append("(name LIKE ? OR brand LIKE ? OR ingredient LIKE ?)")
        # '?' 가 셋이므로 같은 값을 세 번 넣는다. 앞뒤 % 는 부분 일치를 뜻한다.
        params += [f"%{keyword}%"] * 3
    # 카테고리를 받았을 때만 조건을 더한다.
    if category:
        # 정확히 같은 카테고리만 고른다.
        where.append("category = ?")
        # 그 값을 '?' 자리 목록에 더한다.
        params.append(category)
    # 피부 타입을 받았을 때만 조건을 더한다.
    if skin_type:
        # 정확히 같은 피부 타입만 고른다.
        where.append("skin_type = ?")
        # 그 값을 '?' 자리 목록에 더한다.
        params.append(skin_type)
    # 조건이 하나도 없으면 WHERE 자체를 안 붙인다.
    clause = ("WHERE " + " AND ".join(where)) if where else ""

    # 같은 조건으로 전체가 몇 건인지 먼저 센다. 쪽 나누기에 필요하다.
    total = one(f"SELECT COUNT(*) FROM products {clause}", tuple(params))[0]

    # 허용 목록에 없는 이름이 오면 조용히 이름 순으로 둔다.
    column = SORTABLE.get(sort, "name")
    # 내림차순 요청일 때만 DESC 로 두고 나머지는 오름차순이다.
    direction = "DESC" if order == "desc" else "ASC"
    # 정렬 기준과 방향은 위에서 허용된 값으로 좁혀 뒀으므로 SQL 에 직접 넣는다.
    rows = dicts(
        # 앞의 조건과 같은 조건으로 이번 쪽만 읽는다.
        f"SELECT {', '.join(COLUMNS)}, source FROM products {clause} "
        # LIMIT 은 몇 건을, OFFSET 은 몇 건을 건너뛸지다.
        f"ORDER BY {column} {direction} LIMIT ? OFFSET ?",
        # 조건 값 뒤에 건수와 건너뛸 수를 '?' 순서대로 이어 붙인다.
        tuple(params) + (size, page * size))
    # 이번 쪽의 행들과 전체 건수를 함께 돌려준다.
    return rows, total


# 후보 카드 여럿을 한 번에. 아이디 하나마다 SELECT 하지 않는다
def find_cards(product_ids):
    # 아이디가 없으면 DB 를 건드리지 않는다.
    if not product_ids:
        # 빈 목록을 준다.
        return []
    # 아이디 개수만큼 IN 절의 '?' 를 만든다.
    marks = ", ".join("?" * len(product_ids))
    # 카드에 필요한 컬럼만 읽는다.
    return dicts(
        # 카드용 컬럼 이름을 쉼표로 이어 붙인다.
        f"SELECT {', '.join(CARD_COLUMNS)} FROM products "
        # 준 아이디에 드는 상품만 한 번에 읽는다.
        f"WHERE product_id IN ({marks})", tuple(product_ids))


# 임베딩 문장을 만들 재료. 없으면 None
def find_embedding_source(product_id):
    # 문장을 만드는 데 필요한 컬럼만 읽는다.
    rows = dicts(
        # 컬럼 순서가 임베딩 문장 순서와 같아야 한다.
        f"SELECT {', '.join(PRODUCT_FIELDS)} FROM products WHERE product_id = ?",
        # 상품 아이디를 '?' 자리로 넘긴다.
        (product_id,))
    # 한 건만 찾는 질의이므로 첫 줄만 준다. 없으면 None 이다.
    return rows[0] if rows else None


# 이름 한 개. 없으면 None
def find_name(product_id):
    # 이름 한 칸만 필요하므로 one 으로 한 줄만 읽는다.
    row = one("SELECT name FROM products WHERE product_id = ?", (product_id,))
    # 줄이 있으면 첫 칸인 이름을, 없으면 None 을 준다.
    return row[0] if row else None


# 다음 상품 번호. P001 다음은 P002 다
def next_id():
    # 'P' 로 시작하는 아이디 중 가장 큰 것을 찾는다.
    last = one("SELECT MAX(product_id) FROM products WHERE product_id LIKE 'P%'")[0]
    # 앞의 'P' 를 떼고 숫자로 바꿔 하나 더한다. 아무것도 없으면 1 부터 시작한다.
    number = int(last[1:]) + 1 if last else 1
    # 03d 는 세 자리로 맞추고 빈자리를 0 으로 채우라는 뜻이다.
    return f"P{number:03d}"


# 새 행을 넣는다. 그 번호를 다른 요청이 먼저 가져갔으면 False
def insert(product_id, values):
    # 아이디를 맨 앞에, source 를 맨 뒤에 두어 컬럼 순서를 정한다.
    columns = ["product_id"] + list(values) + ["source"]
    # 컬럼 개수만큼 '?' 를 만든다.
    marks = ", ".join("?" * len(columns))
    # 같은 아이디가 이미 있으면 DB 가 오류를 내므로 감싼다.
    try:
        # 컬럼 이름은 SQL 에 넣고 값은 '?' 자리로 넘긴다.
        execute(f"INSERT INTO products ({', '.join(columns)}) VALUES ({marks})",
                # 화면에서 넣은 행이라는 표시로 source 에 'app' 을 적는다.
                (product_id,) + tuple(values.values()) + ("app",))
    # 그 번호를 다른 요청이 먼저 가져간 경우다.
    except IntegrityError:
        # 부르는 쪽이 번호를 다시 받아 시도하도록 False 를 준다.
        return False
    # 여기까지 왔으면 잘 들어간 것이다.
    return True


# 준 컬럼만 고친다. 고친 행은 source 를 app 으로 바꾼다
def update(product_id, fields):
    # 고칠 것이 없으면 SQL 을 만들지 않는다.
    if not fields:
        # 그대로 끝낸다.
        return
    # 'name = ?, price = ?' 처럼 SET 절을 만든다. 값은 '?' 로 간다.
    assignments = ", ".join(f"{name} = ?" for name in fields)
    # 한 번이라도 고친 행은 CSV 원본과 달라지므로 source 를 함께 바꾼다.
    execute(f"UPDATE products SET {assignments}, source = 'app' WHERE product_id = ?",
            # SET 의 값들이 먼저, WHERE 의 아이디가 뒤다.
            tuple(fields.values()) + (product_id,))


# 한 건을 지운다
def delete(product_id):
    # 상품 행만 지운다. 상세와 벡터는 부르는 쪽이 따로 지운다.
    execute("DELETE FROM products WHERE product_id = ?", (product_id,))
