"""계층이 한 방향으로만 흐르나. import 그래프를 떠서 본다."""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

LAYER = {
    "app.domain": 0,
    "app.core": 1,
    "app.repositories": 2,
    "app.adapters": 2,
    "app.features": 3,
    "app.api": 4,
}


# 파일 경로를 app.core.db 같은 모듈 이름으로 바꾼다
def module_name(path):
    return str(path.relative_to(ROOT).with_suffix("")).replace("\\", ".").replace(
        "/", ".").removesuffix(".__init__")


# 그 모듈이 몇 층인가. 못 찾으면 (None, None)
def layer_of(module):
    for prefix, number in LAYER.items():
        if module == prefix or module.startswith(prefix + "."):
            return number, prefix
    return None, None


# app/ 안의 (부르는 쪽, 불리는 쪽) 전부
def edges():
    out = []
    for path in sorted((ROOT / "app").rglob("*.py")):
        source = module_name(path)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module and node.module.startswith("app"):
                    out.append((source, node.module))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("app"):
                        out.append((source, alias.name))
    return out


def test_아래층이_위층을_가리키지_않는다():
    broken = []
    for source, target in edges():
        up, source_layer = layer_of(source)
        down, target_layer = layer_of(target)
        if up is None or down is None:
            continue
        if source_layer == target_layer:
            continue
        if down > up:
            broken.append(f"{source} -> {target}  ({source_layer} -> {target_layer})")

    assert not broken, "아래층이 위층을 가리킨다:\n  " + "\n  ".join(broken)


def test_domain_은_아무_층도_안_가리킨다():
    outward = [f"{s} -> {t}" for s, t in edges()
               if s.startswith("app.domain") and not t.startswith("app.domain")]

    assert not outward, "domain 이 밖을 본다:\n  " + "\n  ".join(outward)


@pytest.mark.parametrize("module", sorted(LAYER))
def test_층마다_파일이_실제로_있다(module):
    folder = ROOT / module.replace(".", "/")
    assert folder.is_dir(), f"{module} 폴더가 없다. LAYER 표가 낡았다"
