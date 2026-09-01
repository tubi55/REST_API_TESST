"""나눈 문서 조각을 SQLite 테이블에 저장한다."""


# 섹션과 조각을 새로 만들어 넣는다. 조각 벡터도 같이 지운다
def save_sections_and_chunks(con, sections, chunks):
    con.execute("DROP TABLE IF EXISTS chunk_vectors")
    con.execute("DROP TABLE IF EXISTS chunks")
    con.execute("DROP TABLE IF EXISTS sections")
    con.execute("""
        CREATE TABLE sections (
            section_id INTEGER PRIMARY KEY,
            product_id TEXT NOT NULL,
            section    TEXT NOT NULL,
            text       TEXT NOT NULL,
            n_tokens   INTEGER NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        )
    """)
    con.execute("""
        CREATE TABLE chunks (
            chunk_id    INTEGER PRIMARY KEY,
            section_id  INTEGER NOT NULL,
            product_id  TEXT NOT NULL,
            section     TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            text        TEXT NOT NULL,
            body        TEXT NOT NULL,
            n_tokens    INTEGER NOT NULL,
            FOREIGN KEY (section_id) REFERENCES sections(section_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        )
    """)
    con.execute("CREATE INDEX idx_chunks_product_id ON chunks(product_id)")
    con.execute("CREATE INDEX idx_chunks_section ON chunks(section)")
    con.execute("CREATE INDEX idx_sections_product_id ON sections(product_id)")

    section_id_lookup = {}
    for section in sections:
        cur = con.execute(
            "INSERT INTO sections (product_id, section, text, n_tokens) VALUES (?, ?, ?, ?)",
            (section["product_id"], section["section"], section["text"], section["n_tokens"]),
        )
        section_id_lookup[(section["product_id"], section["section"])] = cur.lastrowid

    for chunk in chunks:
        con.execute("""
            INSERT INTO chunks (section_id, product_id, section, chunk_index, text, body, n_tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (section_id_lookup[(chunk["product_id"], chunk["section"])],
              chunk["product_id"], chunk["section"], chunk["chunk_index"],
              chunk["text"], chunk["body"], chunk["n_tokens"]))

    con.commit()
