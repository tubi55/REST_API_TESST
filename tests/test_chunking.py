"""청킹 시험. 데이터베이스 없이 돈다."""

import ast
from pathlib import Path

from pipeline.prep import chunking
from pipeline.prep.options import RESPLIT_OVER

DETAILS = [
    ("P001", "비타민C 필링 로션",
     "## 상품 소개\n비타민C 가 들어 있습니다.\n\n"
     "## 주의사항\n민감성 피부에는 사용을 권하지 않습니다."),
    ("P002", "수분 크림",
     "머리말입니다.\n\n## 사용법\n아침 저녁으로 바릅니다."),
]


def test_헤더로_갈린다():
    sections = chunking.split_sections(DETAILS)

    assert len(sections) == 4
    assert [s["section"] for s in sections] == [
        "상품 소개", "주의사항", "(머리말)", "사용법"]
    assert sections[0]["product_id"] == "P001"


def test_헤더_없는_앞토막은_머리말이_된다():
    sections = chunking.split_sections([DETAILS[1]])

    assert sections[0]["section"] == "(머리말)"
    assert "머리말입니다." in sections[0]["text"]


def test_헤더_줄은_본문에서_빠진다():
    sections = chunking.split_sections(DETAILS)

    assert "##" not in sections[0]["text"]
    assert "상품 소개" not in sections[0]["text"]


def test_접두어가_붙는다():
    _sections, chunks, _n = chunking.split_details(DETAILS)

    warning = next(c for c in chunks if c["section"] == "주의사항")
    assert warning["text"].startswith("[비타민C 필링 로션 > 주의사항] ")
    assert warning["body"] == "민감성 피부에는 사용을 권하지 않습니다."
    assert not warning["body"].startswith("[")


def test_짧은_섹션은_다시_안_자른다():
    sections, chunks, n_resplit = chunking.split_details(DETAILS)

    assert n_resplit == 0
    assert len(chunks) == len(sections)
    assert {c["chunk_index"] for c in chunks} == {0}


def test_긴_섹션은_다시_잘린다():
    long_detail = [("P003", "긴 상품", "## 긴 섹션\n" + ("가나다라마바사. " * RESPLIT_OVER))]
    sections, chunks, n_resplit = chunking.split_details(long_detail)

    assert n_resplit == 1
    assert len(sections) == 1
    assert len(chunks) > 1
    assert [c["chunk_index"] for c in chunks] == list(range(len(chunks)))
    for chunk in chunks:
        assert chunk["n_tokens"] <= RESPLIT_OVER + chunking.count_tokens("[긴 상품 > 긴 섹션] ")


def test_토큰_수를_같이_들고_나온다():
    sections, chunks, _n = chunking.split_details(DETAILS)

    for section in sections:
        assert section["n_tokens"] == chunking.count_tokens(section["text"])
    for chunk in chunks:
        assert chunk["n_tokens"] == chunking.count_tokens(chunk["text"])


def test_청커는_데이터베이스를_모른다():
    source = (Path(__file__).resolve().parent.parent
              / "pipeline" / "prep" / "chunking.py").read_text(encoding="utf-8")

    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert "sqlite3" not in imported
    assert "pipeline" in imported
