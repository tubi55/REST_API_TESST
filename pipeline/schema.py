"""CSV 파일을 읽어 SQLite 테이블과 데이터를 만든다."""

import csv
import re
import sqlite3
import sys
from pathlib import Path

from app.core.config import DATA_DIR, DB_PATH


# CSV 한 장을 읽어 (컬럼 이름 목록, 행 목록) 을 돌려준다
def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


# 정수인가. 앞자리가 0 이면 숫자가 아니라 번호라서 아니라고 본다
def looks_int(text):
    body = text[1:] if text.startswith("-") else text

    if not body.isdigit():
        return False

    return not (len(body) > 1 and body.startswith("0"))


# 소수인가. 점이 있고 float 으로 바뀌어야 한다
def looks_real(text):
    if "." not in text:
        return False
    try:
        float(text)
    except ValueError:
        return False
    return True


# 2026-08-17 모양인가. 모양만 보고 실제로 있는 날짜인지는 안 본다
def looks_date(text):
    return re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) is not None


# 한 컬럼의 값들을 보고 타입 하나를 고른다. 빈 칸은 판단에서 뺀다
def infer_type(values):
    seen = [v for v in values if v != ""]

    if not seen:
        return "TEXT"
    if all(looks_int(v) for v in seen):
        return "INTEGER"
    if all(looks_real(v) or looks_int(v) for v in seen):
        return "REAL"
    if all(looks_date(v) for v in seen):
        return "DATE"
    return "TEXT"


# 기본키를 찾는다. 이름이 _id 로 끝나고 값이 전부 다르며 빈 칸이 없어야 한다
def infer_pk(columns, rows):
    for col in columns:
        if not col.endswith("_id"):
            continue

        values = [r[col] for r in rows]
        if "" in values:
            continue
        if len(set(values)) == len(values):
            return col
    return None


# product_id 라는 컬럼의 주인 표를 찾는다. 없으면 None
def owner_of(column, tables):
    stem = column[:-3]
    for candidate in (stem, stem + "s", stem + "es"):
        if candidate in tables:
            return candidate
    return None


# 추론한 정보를 CREATE TABLE 문으로 조립한다. 실행하지는 않는다
def build_create(name, table):
    lines = []
    for col in table["columns"]:
        piece = f"    {col} {table['types'][col]}"
        if col == table["pk"]:
            piece += " PRIMARY KEY"
        lines.append(piece)

    for col, owner in table["fks"]:
        lines.append(f"    FOREIGN KEY ({col}) REFERENCES {owner}({col})")

    return f"CREATE TABLE {name} (\n" + ",\n".join(lines) + "\n)"


# 표를 만들 순서를 정한다. 참조당하는 표가 먼저다
def sort_by_dependency(tables):
    done = set()
    order = []

    while len(order) < len(tables):
        moved = False

        for name, table in tables.items():
            if name in done:
                continue
            if all(owner in done for _, owner in table["fks"]):
                order.append(name)
                done.add(name)
                moved = True

        if not moved:
            order += [n for n in tables if n not in done]
            break

    return order


# CSV 에서 복원되지 않는 행을 지우기 전에 뜬다. (상품 행, 사용량 행)
def rescue(path):
    if not path.exists():
        return [], []
    old_con = sqlite3.connect(path)
    saved_products, saved_usage = [], []
    try:
        names = [row[1] for row in old_con.execute("PRAGMA table_info(products)")]
        if "source" in names:
            saved_products = old_con.execute(
                "SELECT * FROM products WHERE source = 'app'").fetchall()
        saved_usage = old_con.execute("SELECT * FROM usage_log").fetchall()
    except sqlite3.OperationalError:
        pass
    finally:
        old_con.close()
    return saved_products, saved_usage


# CSV 에서 읽은 문자열을 선언한 타입에 맞춰 파이썬 값으로 바꾼다
def convert(value, kind):
    if value == "":
        return None
    if kind == "INTEGER":
        return int(value)
    if kind == "REAL":
        return float(value)
    return value


# CSV 를 전부 읽어 타입 · 기본키 · 외래키를 알아내고 화면에 찍는다
def infer_all(data_dir):
    print("=" * 72)
    print("1. 타입 · 기본키 · 외래키를 추론한다")
    print("=" * 72)

    tables = {}

    for path in sorted(data_dir.glob("*.csv")):
        columns, rows = read_csv(path)

        tables[path.stem] = {
            "columns": columns,
            "rows": rows,
            "types": {col: infer_type([r[col] for r in rows]) for col in columns},
            "pk": infer_pk(columns, rows),
        }

    for name, table in tables.items():
        fks = []
        for col in table["columns"]:
            if not col.endswith("_id"):
                continue
            owner = owner_of(col, tables)
            if not owner:
                continue
            if owner == name:
                continue
            if tables[owner]["pk"] != col:
                continue
            fks.append((col, owner))
        table["fks"] = fks

    for name, table in tables.items():
        marks = []
        if table["pk"]:
            marks.append(f"PK={table['pk']}")
        for col, owner in table["fks"]:
            marks.append(f"FK={col}→{owner}")

        print(f"\n  {name:16s} {'  '.join(marks) or '(열쇠 없음)'}")
        for column in table["columns"]:
            example = next((r[column] for r in table["rows"] if r[column] != ""), "")
            print(f"      {column:16s} {table['types'][column]:8s} 예: {example[:36]}")

    print()
    print("  ▸ phone 이 TEXT 로 남은 것을 보라. 010-4786-2358 은 숫자처럼 생겼지만 번호다")
    print("  ▸ product_details 의 product_id 는 기본키이면서 동시에 외래키다  ")
    print("    값이 전부 다르니 열쇠이고, products 의 열쇠와 이름이 같으니 참조다")

    return tables


# 만들 순서를 정하고 CREATE TABLE 문을 찍는다. 실행은 아직 안 한다
def show_sql(tables):
    print()
    print("=" * 72)
    print("2. 만든 CREATE TABLE 문. 실행하기 전에 눈으로 본다")
    print("=" * 72)
    print("  자동으로 만들되, 무엇을 만들었는지는 사람이 봐야 한다.")
    print("  안 보고 실행하면 틀려도 모른다\n")

    order = sort_by_dependency(tables)
    print(f"  만드는 순서: {' → '.join(order)}")
    print("  (참조당하는 표가 먼저다)\n")

    for name in order:
        print(build_create(name, tables[name]) + ";\n")

    return order


# 건질 것을 건지고 기존 파일을 지운 뒤 빈 DB 를 새로 연다
def open_fresh_db(db_file):
    saved_products, saved_usage = rescue(db_file)
    if saved_products or saved_usage:
        print(f"  (지우기 전에 떠 둔다: 화면에서 만든 상품 {len(saved_products)}행 · "
              f"사용량 기록 {len(saved_usage)}행)")

    if db_file.exists():
        try:
            db_file.unlink()
            print(f"  (기존 {db_file.name} 을 지우고 새로 만든다)")
        except PermissionError:
            print(f"\n  {db_file.name} 을 지울 수 없다. 다른 프로그램이 쓰고 있다.")
            print("  DB 브라우저를 열어 뒀으면 닫고 다시 실행한다.")
            sys.exit(1)

    con = sqlite3.connect(db_file)
    con.execute("PRAGMA foreign_keys = ON")

    return con, saved_products, saved_usage


# 표를 만들고 값을 넣는다. 앞에서 찍은 문장을 이번에는 실제로 실행한다
def load_data(con, tables, order, saved_products, saved_usage):
    print("=" * 72)
    print("3. 표를 만들고 데이터를 넣는다")
    print("=" * 72)

    for name in order:
        table = tables[name]

        con.execute(build_create(name, table))

        columns = table["columns"]

        placeholders = ", ".join("?" for _ in columns)

        values = [
            tuple(convert(row[col], table["types"][col]) for col in columns)
            for row in table["rows"]
        ]

        con.executemany(
            f"INSERT INTO {name} ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )

        for col, _owner in table["fks"]:
            con.execute(f"CREATE INDEX idx_{name}_{col} ON {name}({col})")

        print(f"  {name:16s} {len(values):>6,}행 적재"
              + (f"  · 인덱스 {len(table['fks'])}개" if table["fks"] else ""))

    con.execute("ALTER TABLE products ADD COLUMN source TEXT NOT NULL DEFAULT 'csv'")

    if saved_products:
        marks = ", ".join("?" * len(saved_products[0]))
        con.executemany(f"INSERT OR REPLACE INTO products VALUES ({marks})", saved_products)
        print(f"\n화면에서 만든 상품 {len(saved_products)}행을 되돌려 놓았다")

    if saved_usage:
        marks = ", ".join("?" * len(saved_usage[0]))
        con.execute("""
            CREATE TABLE IF NOT EXISTS usage_log (
                id          INTEGER PRIMARY KEY,
                at          TEXT NOT NULL,
                user_id     TEXT NOT NULL,
                feature     TEXT NOT NULL,
                model       TEXT NOT NULL,
                in_tokens   INTEGER,
                out_tokens  INTEGER,
                seconds     REAL,
                cost_usd    REAL NOT NULL
            )
        """)
        con.executemany(f"INSERT OR REPLACE INTO usage_log VALUES ({marks})", saved_usage)
        print(f"  사용량 기록 {len(saved_usage)}행을 되돌려 놓았다")

    con.commit()


# 넣은 만큼 들어갔는지 세어 본다. 여기서는 아무것도 만들지 않는다
def report_counts(con, order, db_file):
    print()
    print("=" * 72)
    print("4. 확인. 넣은 만큼 들어갔나")
    print("=" * 72)

    for name in order:
        n = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        print(f"  SELECT COUNT(*) FROM {name:16s} -> {n:>6,}")

    broken = con.execute("PRAGMA foreign_key_check").fetchall()
    print(f"\n  FK 위반: {len(broken)}건" + ("  ← 0 이어야 한다" if not broken else ""))

    print(f"\n  {db_file.name} ({db_file.stat().st_size / 1024:,.0f}KB) 생성 완료")
    print("  다음: python -m pipeline chunk")


# 단계를 순서대로 부른다
def main():
    sys.stdout.reconfigure(errors="replace")

    db_file = Path(DB_PATH)

    tables = infer_all(DATA_DIR)
    order = show_sql(tables)
    con, saved_products, saved_usage = open_fresh_db(db_file)
    load_data(con, tables, order, saved_products, saved_usage)
    report_counts(con, order, db_file)
    con.close()


if __name__ == "__main__":
    main()
