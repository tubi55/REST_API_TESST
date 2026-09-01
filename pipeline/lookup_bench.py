"""반복 DB 조회와 메모리 조회의 처리 시간을 비교한다."""

import sqlite3
import sys
import time

sys.stdout.reconfigure(errors="replace")

from app.core.config import DB_PATH

con = sqlite3.connect(DB_PATH)

keys = con.execute("SELECT product_id, section FROM chunks ORDER BY chunk_id").fetchall()

print("=" * 74)
print("같은 것을 두 번 찾지 않는다. 매번 SELECT vs 담아 두기")
print("=" * 74)
print(f"  조각 {len(keys):,}건에 대해 section_id 를 찾는다\n")


started = time.perf_counter()
a_result = []
for product_id, section in keys:
    row = con.execute(
        "SELECT section_id FROM sections WHERE product_id = ? AND section = ?",
        (product_id, section)).fetchone()
    a_result.append(row[0])
a_elapsed = time.perf_counter() - started


started = time.perf_counter()
section_id_lookup = {(product_id, section): section_id for section_id, product_id, section
                     in con.execute("SELECT section_id, product_id, section FROM sections")}
b_result = [section_id_lookup[key] for key in keys]
b_elapsed = time.perf_counter() - started


assert a_result == b_result, "두 방식의 답이 다르다. 재기 전에 이것부터 고쳐야 한다"

print(f"  (A) 조각마다 SELECT      {a_elapsed:>8.4f}초   (질의 {len(keys):,}번)")
print(f"  (B) 담아 두고 꺼내 쓰기   {b_elapsed:>8.4f}초   "
      f"(질의 1번 + 딕셔너리 조회 {len(keys):,}번)")
print(f"\n  {a_elapsed / b_elapsed:>8.1f}배   답은 {len(a_result):,}건 모두 같다\n")

print("=" * 74)
print("이 숫자를 어떻게 읽나")
print("=" * 74)
print("  배수는 크지만 절대 시간은 둘 다 작다. 이 규모(1,560건)에서는")
print("     둘 중 무엇을 써도 사람은 차이를 못 느낀다. 그러니 「빨라서 딕셔너리를 쓴다」")
print("     는 이 숫자만으로는 약한 근거다.")
print()
print("  진짜 이유는 따로 있다. 그 시점이 지나면 번호가 사라진다.")
print("     section_id 는 INSERT 하는 순간 cur.lastrowid 로 한 번 나온다.")
print("     그 자리에서 안 받아 두면 되찾는 방법이 (A) 밖에 없다.")
print("     딕셔너리는 「빠르게 하려고」가 아니라 「없어지기 전에 받아 두려고」 쓴다.")
print()
print("  그리고 데이터가 10배 100배가 되면 (A) 는 그만큼 늘고 (B) 는 거의 그대로다.")
print("  지금 안 아픈 것과 나중에 안 아픈 것은 다르다.")

con.close()
