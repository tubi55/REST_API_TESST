# SQLite에 벡터를 저장하고 NumPy로 비슷한 항목을 검색하는 저장소다.

# 벡터를 SQLite에 넣을 수 있는 JSON 문자열로 바꿀 때 사용한다.
import json

# SQLite 테이블이 없을 때 발생하는 오류를 처리할 때 사용한다.
import sqlite3

# 벡터를 행렬로 만들고 유사도 점수를 계산하거나 정렬할 때 사용한다.
import numpy as np

# 벡터의 각 숫자를 소수점 몇 자리까지 저장할지 정한 설정값이다.
from app.core.config import EMBED_DECIMALS

# DB 연결, 단일 실행, 여러 행 실행, 조회를 담당하는 공통 함수들이다.
from app.core.db import connection, execute, executemany, query

# kind별로 (벡터 테이블명, 기본 키 컬럼명, 원본 테이블명)을 연결한다.
TABLES = {
    # 상품 설명을 잘라 놓은 문서 조각의 벡터다.
    "chunk": ("chunk_vectors", "chunk_id", "chunks"),
    # 상품 하나를 통째로 나타내는 벡터다.
    "product": ("product_vectors", "product_id", "products"),
    # 고객의 취향을 나타내는 벡터다.
    "customer": ("customer_vectors", "customer_id", "customers"),
    # 후기 벡터다. 후기는 구매 행에 딸려 있어 키 이름만 purchase_id로 다르다.
    "review": ("review_vectors", "purchase_id", "purchases"),
}

# 간단한 타입 이름을 실제 SQLite 컬럼 타입으로 바꿀 때 사용한다.
SQL_TYPE = {"int": "INTEGER", "text": "TEXT", "float": "REAL"}


# JSON 문자열로 저장된 벡터를 읽어 (아이디 목록, NumPy 행렬)로 반환한다.
def _load_vectors(table, key):
    # ids에는 각 행의 아이디를, rows에는 숫자 벡터를 차례대로 담는다.
    ids, rows = [], []
    # 선택된 키 컬럼과 vector 컬럼을 해당 테이블에서 조회한다.
    for row_id, vector in connection().execute(f"SELECT {key}, vector FROM {table}"):
        # 아이디는 DB에 들어 있는 형태 그대로 담아 둔다.
        ids.append(row_id)
        # '[1.0, 2.0]' 같은 JSON 문자열을 파이썬 리스트로 되돌린다.
        rows.append(json.loads(vector))
    # float32는 벡터 계산 정밀도를 유지하면서 메모리 사용량을 줄인다.
    return ids, np.array(rows, dtype="float32")


# 숫자 벡터를 SQLite에 저장할 수 있는 JSON 문자열로 변환한다.
def vector_to_text(vector):
    # 숫자를 float로 통일하고 설정된 소수 자릿수로 반올림한다.
    return json.dumps([round(float(x), EMBED_DECIMALS) for x in vector])


# 벡터의 저장, 조회, 검색 기능을 SQLite와 NumPy로 구현한다.
# VectorStore는 Protocol이므로 상속하지 않아도 같은 메서드를 제공하면 된다.
class SqliteVectorStore:
    # 벡터 조회 결과를 저장할 메모리 캐시를 초기화한다
    def __init__(self):
        # kind별로 (아이디 목록, 벡터 행렬, 아이디별 행 번호)를 보관한다.
        self._cache = {}

    # kind에 해당하는 벡터를 최초 한 번만 DB에서 읽고 이후에는 캐시를 반환한다.
    def _get(self, kind):
        # 아직 이 kind를 읽은 적이 없을 때만 DB를 조회한다.
        if kind not in self._cache:
            # _parent는 여기서 사용하지 않으므로 밑줄 이름으로 표시한다.
            table, key, _parent = TABLES[kind]
            # 이 한 줄에서 해당 테이블을 통째로 읽어 행렬로 만든다.
            ids, matrix = _load_vectors(table, key)
            # 숫자와 문자열 아이디가 섞이지 않도록 모두 문자열로 통일한다.
            ids = [str(v) for v in ids]
            # range(len(ids))는 ids의 위치 번호인 0, 1, 2, ...를 만든다.
            # lambda i: ids[i]는 각 위치의 아이디 값을 기준으로 위치 번호를 정렬한다.
            # 예: ids가 ["30", "10", "20"]이면 order는 [1, 2, 0]이 된다.
            order = sorted(range(len(ids)), key=lambda i: ids[i])
            # 아이디와 벡터 행렬을 반드시 같은 순서로 재배치한다.
            if order:
                # 정렬된 위치 번호대로 아이디를 다시 나열한다.
                ids = [ids[i] for i in order]
                # 행렬의 행도 같은 순서로 옮겨 아이디와 짝을 유지한다.
                matrix = matrix[order]
            # 마지막 딕셔너리는 아이디로 행렬 위치를 빠르게 찾기 위한 색인이다.
            self._cache[kind] = (ids, matrix, {v: i for i, v in enumerate(ids)})
        # (아이디 목록, 벡터 행렬, 아이디별 행 번호)를 반환한다.
        return self._cache[kind]

    # DB 내용이 바뀌었을 때 해당 kind의 오래된 메모리 캐시를 제거한다.
    def _invalidate(self, kind):
        # 두 번째 인수 None 덕분에 캐시가 없어도 오류가 발생하지 않는다.
        self._cache.pop(kind, None)

    # 해당 종류에 지정한 아이디의 벡터가 있는지 확인한다
    def has(self, kind, item_id):
        # 앞의 두 값은 필요 없고 아이디별 행 번호만 사용한다.
        _, _, row_of = self._get(kind)
        # 캐시의 아이디 형식과 맞추기 위해 문자열로 변환해 확인한다.
        return str(item_id) in row_of

    # 해당 종류와 아이디에 맞는 벡터를 가져온다
    def get_vector(self, kind, item_id):
        # 벡터 행렬과 아이디별 행 번호를 캐시에서 가져온다.
        _, matrix, row_of = self._get(kind)
        # get은 아이디가 없을 때 오류 대신 None을 돌려준다.
        i = row_of.get(str(item_id))
        # 아이디가 없으면 None, 있으면 행렬의 해당 벡터를 반환한다.
        return None if i is None else matrix[i]

    # 쿼리 벡터와 유사한 항목을 최대 k개 검색한다.
    # only_ids는 검색 대상을 제한하고 reverse=True는 낮은 점수부터 정렬한다.
    def search(self, kind, query_vector, k, *, only_ids=None, reverse=False):
        # 아이디 목록, 벡터 행렬, 아이디별 행 번호를 캐시에서 한 번에 받는다.
        ids, matrix, row_of = self._get(kind)
        # 저장된 벡터가 없으면 계산하지 않고 빈 목록을 반환한다.
        if len(ids) == 0:
            # 계산할 것이 없으므로 여기서 끝낸다.
            return []
        # only_ids가 None이면 해당 kind의 모든 벡터를 검색한다.
        if only_ids is None:
            # 전체 아이디와 전체 행렬을 그대로 검색 대상으로 삼는다.
            target_ids, rows = ids, matrix
        # only_ids를 받았으면 그 안에서만 찾는다.
        else:
            # 실제로 존재하는 아이디만 문자열로 통일하고 정렬한다.
            target_ids = sorted(i for i in map(str, only_ids) if i in row_of)
            # 걸러 낸 결과가 비면 계산할 대상이 없다.
            if not target_ids:
                # 빈 목록을 돌려주고 끝낸다.
                return []
            # 선택한 아이디에 해당하는 벡터 행만 꺼낸다.
            rows = matrix[[row_of[i] for i in target_ids]]

        # @ 연산자는 모든 저장 벡터와 query_vector의 내적 점수를 계산한다.
        scores = rows @ query_vector
        # 기본은 높은 점수순이고 reverse=True이면 낮은 점수순이다.
        # stable은 동점일 때 기존 아이디 순서를 유지하며 [:k]는 최대 k개만 고른다.
        order = np.argsort(scores if reverse else -scores, kind="stable")[:k]
        # NumPy 숫자를 일반 float로 바꿔 (아이디, 점수) 목록을 반환한다.
        return [(target_ids[i], float(scores[i])) for i in order]

    # 지정한 kind의 벡터 테이블을 삭제한 뒤 새로운 구조로 다시 만든다.
    # dim과 model은 공통 저장소 인터페이스를 맞추기 위한 값이며
    # 현재 SQLite 생성 SQL에서는 쓰지 않는다.
    # payload_columns는 {'컬럼명': 'int|text|float'} 형태의 추가 컬럼 설정이다.
    def recreate(self, kind, *, dim, model, payload_columns=None):
        # kind에 연결된 벡터 테이블, 키 컬럼, 원본 테이블을 찾는다.
        table, key, parent = TABLES[kind]
        # None이면 빈 딕셔너리로 바꿔 이후 반복 처리를 단순하게 한다.
        payload_columns = payload_columns or {}

        # PRAGMA table_info는 원본 테이블 구조를 조회하며 x[1]은 이름, x[2]는 타입이다.
        key_type = next(x[2] for x in query(f"PRAGMA table_info({parent})") if x[1] == key)

        # {'product_id': 'int'} 같은 설정을 'product_id INTEGER' SQL로 만든다.
        extra = "".join(
            # 컬럼 한 개짜리 SQL 조각을 만든다. 끝의 \n은 줄을 바꾸라는 표시다.
            f"    {name} {SQL_TYPE[kind_name]},\n"
            # 설정에 적힌 컬럼 이름과 타입 이름을 하나씩 꺼내 위 줄에 넣는다.
            for name, kind_name in payload_columns.items()
        )

        # IF EXISTS는 테이블이 아직 없어도 삭제 명령에서 오류가 나지 않게 한다.
        execute(f"DROP TABLE IF EXISTS {table}")
        # NOT NULL은 필수 값, PRIMARY KEY는 중복 불가 키를 뜻한다.
        # FOREIGN KEY는 벡터의 아이디가 원본 테이블의 실제 아이디를 가리키게 한다.
        execute(f"""
            CREATE TABLE {table} (
                {key} {key_type} PRIMARY KEY,
                {extra} dim INTEGER NOT NULL,
                model       TEXT NOT NULL,
                source_hash TEXT NOT NULL,
                vector      TEXT NOT NULL,
                FOREIGN KEY ({key}) REFERENCES {parent}({key})
            )
        """)
        # product_id로 청크를 자주 찾으므로 해당 추가 컬럼이 있을 때 색인을 만든다.
        if "product_id" in payload_columns:
            # 색인이 있으면 상품으로 청크를 찾는 조회가 빨라진다.
            execute(f"CREATE INDEX idx_{table}_product_id ON {table}(product_id)")
        # 테이블이 다시 만들어졌으므로 이전 캐시를 제거한다.
        self._invalidate(kind)

    # 여러 벡터와 관련 정보를 한 번에 추가하거나 기존 행을 갱신한다.
    # model과 hashes는 벡터 생성 정보이고 payloads는 함께 저장할 추가 컬럼 값이다.
    def upsert(self, kind, ids, vectors, *, model, hashes, payloads=None):
        # 저장할 벡터 테이블과 키 컬럼 이름을 찾는다.
        table, key, _parent = TABLES[kind]
        # payloads가 None이면 추가 컬럼이 없는 것으로 처리한다.
        payloads = payloads or {}
        # 딕셔너리 키를 SQL 컬럼 순서로 사용한다.
        names = list(payloads)

        # 기본 키, 추가 컬럼, 벡터 메타데이터 순으로 INSERT 컬럼을 구성한다.
        columns = [key] + names + ["dim", "model", "source_hash", "vector"]
        # '?'는 값을 SQL 문자열에 직접 넣지 않는 안전한 파라미터 자리 표시자다.
        marks = ", ".join("?" * len(columns))

        # 같은 position에 있는 아이디, 벡터, 해시, payload를 한 행으로 묶는다.
        rows = [
            # 첫 칸은 기본 키 값이다.
            (item_id,)
            # 그 뒤에 추가 컬럼 값들을 컬럼 순서대로 이어 붙인다.
            + tuple(payloads[name][position] for name in names)
            # 마지막에 벡터 관련 정보 네 개를 붙인다.
            + (
                # 차원은 인수로 받지 않고 벡터 길이를 직접 센다.
                len(vectors[position]),
                # 이 벡터를 만든 모델 이름이다.
                model,
                # 원본 글이 바뀌었는지 나중에 비교할 지문이다.
                hashes[position],
                # 숫자 벡터를 저장 가능한 문자열로 바꾼다.
                vector_to_text(vectors[position]),
            )
            # enumerate가 위치 번호와 아이디를 함께 주어 목록들의 같은 자리를 꺼내게 한다.
            for position, item_id in enumerate(ids)
        ]

        # INSERT OR REPLACE는 기본 키가 없으면 추가하고 이미 있으면 행을 교체한다.
        # executemany는 준비한 여러 행을 같은 SQL로 한 번에 처리한다.
        executemany(
            # 컬럼 이름은 SQL 문장에 넣고 값은 '?' 자리에 따로 넘긴다.
            f"INSERT OR REPLACE INTO {table} ({', '.join(columns)}) VALUES ({marks})",
            # 위에서 미리 만들어 둔 행 목록을 그대로 넘긴다.
            rows,
        )
        # DB 값이 달라졌으므로 다음 조회가 새 값을 읽도록 캐시를 제거한다.
        self._invalidate(kind)

    # 지정한 아이디에 해당하는 벡터들을 삭제한다
    def delete(self, kind, ids):
        # 삭제할 아이디가 없으면 불필요한 SQL 실행을 생략한다.
        if not ids:
            # 바뀐 것이 없으므로 캐시도 그대로 두고 끝낸다.
            return
        # 삭제할 벡터 테이블과 키 컬럼 이름을 찾는다.
        table, key, _parent = TABLES[kind]
        # 아이디 개수만큼 IN 절에 사용할 '?'를 만든다.
        marks = ", ".join("?" * len(ids))
        # tuple(ids)는 실제 값을 자리 표시자에 안전하게 전달한다.
        execute(f"DELETE FROM {table} WHERE {key} IN ({marks})", tuple(ids))
        # 삭제 전 데이터가 들어 있는 캐시를 제거한다.
        self._invalidate(kind)

    # 지정한 아이디들의 추가 정보 컬럼을 같은 값으로 변경한다.
    # column은 바꿀 컬럼명이고 value는 모든 대상 행에 넣을 값이다.
    def set_payload(self, kind, ids, column, value):
        # 수정할 아이디가 없으면 바로 끝낸다.
        if not ids:
            # 고칠 행이 없으므로 SQL을 만들지 않는다.
            return
        # 수정할 벡터 테이블과 키 컬럼 이름을 찾는다.
        table, key, _parent = TABLES[kind]
        # 실제 테이블 컬럼 목록을 읽어 허용되지 않은 컬럼명 사용을 막는다.
        columns = [row[1] for row in query(f"PRAGMA table_info({table})")]
        # 컬럼명은 '?'로 넘길 수 없어 SQL에 직접 들어가므로 미리 검사한다.
        if column not in columns:
            # 없는 컬럼이면 SQL을 만들기 전에 오류를 낸다.
            raise ValueError(f"{table} 에 {column} 컬럼이 없다")
        # IN 절에 아이디 개수만큼 안전한 자리 표시자를 만든다.
        marks = ", ".join("?" * len(ids))
        # 첫 번째 값은 SET의 value이고 나머지 값은 WHERE의 아이디들이다.
        execute(
            # SET에 '?' 하나, WHERE IN에 아이디 개수만큼의 '?'가 들어간다.
            f"UPDATE {table} SET {column} = ? WHERE {key} IN ({marks})",
            # '?'가 나오는 순서대로 값을 넘겨야 하므로 value가 앞에 온다.
            (value,) + tuple(ids),
        )

    # 여러 상품 아이디에 연결된 청크 아이디를 조회한다.
    # product_ids는 찾을 상품 아이디 목록이며 결과는 문자열 청크 아이디 목록이다.
    def chunk_ids_for_products(self, product_ids):
        # 상품 아이디가 없으면 DB를 조회하지 않는다.
        if not product_ids:
            # 찾을 대상이 없으므로 빈 목록을 돌려준다.
            return []
        # 청크 벡터 테이블과 청크 기본 키 이름을 가져온다.
        table, key, _parent = TABLES["chunk"]
        # 상품 아이디 개수만큼 IN 절의 파라미터 자리 표시자를 만든다.
        marks = ", ".join("?" * len(product_ids))
        # 조회 결과의 첫 번째 컬럼인 청크 아이디를 문자열로 통일한다.
        return [
            # row[0]은 조회한 첫 컬럼, 즉 청크 아이디다.
            str(row[0]) for row in query(
                # product_id는 청크 테이블에 함께 저장돼 있어 따로 이어 붙이지 않아도 된다.
                f"SELECT {key} FROM {table} WHERE product_id IN ({marks})",
                # 상품 아이디 값들을 '?' 자리에 안전하게 넘긴다.
                tuple(product_ids),
            )
        ]

    # 지정한 아이디들의 원하는 추가 정보 컬럼들을 조회한다.
    # columns는 가져올 컬럼명 목록이며 결과는 {아이디: {컬럼: 값}} 형태다.
    def fetch_payloads(self, kind, ids, columns):
        # 조회할 아이디가 없으면 빈 딕셔너리를 반환한다.
        if not ids:
            # 찾을 대상이 없으므로 여기서 끝낸다.
            return {}
        # 조회할 벡터 테이블과 키 컬럼 이름을 찾는다.
        table, key, _parent = TABLES[kind]
        # 테이블에 실제로 존재하는 컬럼 이름들을 가져온다.
        known = [row[1] for row in query(f"PRAGMA table_info({table})")]
        # 요청한 컬럼 중 테이블에 없는 이름을 찾는다.
        missing = [name for name in columns if name not in known]
        # 없는 이름이 하나라도 있으면 조회하지 않는다.
        if missing:
            # 빠진 이름을 모두 모아 한 번에 알려 준다.
            raise ValueError(f"{table} 에 {', '.join(missing)} 컬럼이 없다")
        # 아이디 개수에 맞춰 WHERE IN 절의 자리 표시자를 만든다.
        marks = ", ".join("?" * len(ids))
        # 키 컬럼과 사용자가 요청한 컬럼들만 조회한다.
        rows = query(
            # 키 컬럼을 맨 앞에 두고 요청한 컬럼들을 이어 붙인다.
            f"SELECT {key}, {', '.join(columns)} FROM {table} WHERE {key} IN ({marks})",
            # 아이디 값들을 '?' 자리에 안전하게 넘긴다.
            tuple(ids),
        )
        # zip으로 컬럼명과 각 행의 값을 짝지어 아이디별 딕셔너리로 만든다.
        return {str(row[0]): dict(zip(columns, row[1:])) for row in rows}

    # 원본 내용이 바뀌었는지 비교할 때 쓰는 source_hash를 조회한다.
    # ids=None이면 전체를 조회하고, 목록을 주면 해당 아이디만 조회한다.
    def hashes(self, kind, *, ids=None):
        # 조회할 벡터 테이블과 키 컬럼 이름을 찾는다.
        table, key, _parent = TABLES[kind]

        # None은 아이디 제한 없이 전체 행을 요청한다는 뜻이다.
        if ids is None:
            # WHERE 없이 테이블 전체를 읽는 SQL을 만든다.
            sql = f"SELECT {key}, source_hash FROM {table}"
            # SQL에 전달할 파라미터가 없으므로 빈 튜플을 사용한다.
            params = ()
        # 목록을 받았으면 그 아이디들만 조회한다.
        else:
            # DB 및 캐시와 같은 방식으로 비교하도록 아이디를 문자열로 통일한다.
            ids = [str(item_id) for item_id in ids]
            # 빈 목록이면 유효한 IN 절을 만들 수 없으므로 즉시 반환한다.
            if not ids:
                # 빈 목록은 전체가 아니라 대상 없음을 뜻한다.
                return {}
            # 아이디 개수만큼 IN 절의 자리 표시자를 만든다.
            marks = ", ".join("?" * len(ids))
            # 준 아이디들만 골라 읽는 SQL을 만든다.
            sql = f"SELECT {key}, source_hash FROM {table} WHERE {key} IN ({marks})"
            # '?' 자리에 넣을 아이디 값들을 준비한다.
            params = tuple(ids)

        # 벡터 테이블이 아직 없을 수 있으므로 조회를 try로 감싼다.
        try:
            # 조회된 각 행을 {문자열 아이디: 해시 값} 형태로 바꾼다.
            return {str(row[0]): row[1] for row in query(sql, params)}
        # 초기 실행 등으로 벡터 테이블이 아직 없으면 데이터가 없는 것으로 처리한다.
        except sqlite3.OperationalError:
            # 테이블이 없는 것은 저장된 지문이 하나도 없는 것과 같다.
            return {}
