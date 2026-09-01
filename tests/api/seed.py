"""진짜 DB 가 없을 때 시험이 쓸 최소 데이터를 만든다."""

import sqlite3

SCHEMA = """
CREATE TABLE products (
    product_id TEXT PRIMARY KEY,
    name TEXT, brand TEXT, category TEXT, price INTEGER, volume TEXT,
    skin_type TEXT, ingredient TEXT, concern TEXT, tags TEXT, description TEXT,
    source TEXT NOT NULL DEFAULT 'csv'
);
CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY,
    name TEXT, gender TEXT, age INTEGER, skin_type TEXT,
    phone TEXT, email TEXT, city TEXT, joined_at DATE
);
CREATE TABLE purchases (
    purchase_id TEXT PRIMARY KEY,
    customer_id TEXT, product_id TEXT, purchased_at DATE,
    quantity INTEGER, rating INTEGER, review TEXT, is_holdout INTEGER,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
CREATE TABLE product_details (
    product_id TEXT PRIMARY KEY, detail TEXT,
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
CREATE TABLE sections (
    section_id INTEGER PRIMARY KEY, product_id TEXT NOT NULL,
    section TEXT NOT NULL, text TEXT NOT NULL, n_tokens INTEGER NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
CREATE TABLE chunks (
    chunk_id INTEGER PRIMARY KEY, section_id INTEGER NOT NULL,
    product_id TEXT NOT NULL, section TEXT NOT NULL, chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL, body TEXT NOT NULL, n_tokens INTEGER NOT NULL,
    FOREIGN KEY (section_id) REFERENCES sections(section_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
"""

PRODUCTS = [
    ("P001", "수분 크림", "가브랜드", "크림", 32000, "50ml", "건성",
     "히알루론산", "보습", "수분·보습", "건조한 피부를 위한 크림"),
    ("P002", "진정 토너", "나브랜드", "토너", 18000, "200ml", "민감성",
     "판테놀", "진정", "진정·저자극", "자극받은 피부를 달래는 토너"),
    ("P003", "비타민 세럼", "다브랜드", "세럼", 45000, "30ml", "복합성",
     "비타민C", "미백", "미백·톤업", "칙칙한 톤을 밝히는 세럼"),
]

CUSTOMERS = [
    ("C001", "김하늘", "여", 29, "건성", "010-1234-5678",
     "sky@example.com", "서울", "2024-03-01"),
    ("C002", "박서준", "남", 35, "민감성", "010-8765-4321",
     "jun@example.com", "부산", "2024-05-11"),
]

PURCHASES = [
    ("PU001", "C001", "P001", "2025-01-10", 1, 5, "겨울에 안 당겨서 좋다", 0),
    ("PU002", "C001", "P003", "2025-02-14", 1, 4, "톤이 밝아진 느낌이다", 0),
    ("PU003", "C002", "P001", "2025-03-02", 2, 3, "무겁게 발린다", 0),
    ("PU004", "C001", "P002", "2025-04-20", 1, 5, "숨겨 둔 정답", 1),
]

SECTIONS = [
    (1, "P001", "사용법", "세안 후 적당량을 덜어 얼굴 전체에 펴 바릅니다. "
                          "배송은 결제 후 2~3일 걸립니다."),
    (2, "P002", "주의사항", "상처 부위에는 바르지 마세요. "
                            "민감성 피부는 사용을 권하지 않습니다."),
    (3, "P003", "사용법", "아침 저녁으로 3~4방울을 얼굴에 바릅니다."),
]


# 표를 만들고 시험이 기대하는 최소 데이터를 넣는다
def build(path):
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)

    con.executemany(
        "INSERT INTO products (product_id, name, brand, category, price, volume, "
        "skin_type, ingredient, concern, tags, description) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", PRODUCTS)
    con.executemany(
        "INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", CUSTOMERS)
    con.executemany("INSERT INTO purchases VALUES (?, ?, ?, ?, ?, ?, ?, ?)", PURCHASES)
    con.executemany(
        "INSERT INTO product_details VALUES (?, ?)",
        [(pid, f"{pid} 상세 원문") for pid, *_ in PRODUCTS])

    con.executemany(
        "INSERT INTO sections (section_id, product_id, section, text, n_tokens) "
        "VALUES (?, ?, ?, ?, ?)",
        [(sid, pid, name, text, len(text)) for sid, pid, name, text in SECTIONS])
    con.executemany(
        "INSERT INTO chunks (chunk_id, section_id, product_id, section, chunk_index, "
        "text, body, n_tokens) VALUES (?, ?, ?, ?, 0, ?, ?, ?)",
        [(sid, sid, pid, name, f"{name}: {text}", text, len(text))
         for sid, pid, name, text in SECTIONS])

    con.commit()
    con.close()
