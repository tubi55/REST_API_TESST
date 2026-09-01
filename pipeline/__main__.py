"""python -m pipeline 명령으로 각 데이터 준비 단계를 실행"""

import runpy
import sys

STEPS = (
    ("schema", "CSV -> DB"),
    ("chunk", "상세 청킹"),
    ("embed", "임베딩 (--full 로 전량)"),
    ("verify", "점검"),
)

EXTRAS = (
    ("lookup_bench", "조회 방식 비교"),
)

ALL = dict(STEPS + EXTRAS)


# 단계 목록을 찍는다
def usage():
    print("사용법:  python -m pipeline <단계> [인자]")
    print()
    print("  순서대로:")
    for name, what in STEPS:
        print(f"    {name:14s} {what}")
    print()
    print("  곁가지:")
    for name, what in EXTRAS:
        print(f"    {name:14s} {what}")


# 인자로 받은 단계 하나를 찾아 돌린다
def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        usage()
        return 0

    name = argv[0]
    if name not in ALL:
        print(f"모르는 단계다: {name}")
        print()
        usage()
        return 2

    sys.argv = [f"pipeline/{name}.py", *argv[1:]]
    runpy.run_module(f"pipeline.{name}", run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
