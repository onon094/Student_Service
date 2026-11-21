"""
架构适应度函数（Architecture Fitness Functions）
------------------------------------------------
用可执行的测试，检查以下规则有没有被破坏：

1. 跨模块禁止 import 其他模块的 internal；
2. 模块依赖图必须是无环图（DAG）；
3. 模块内依赖方向：router -> service -> repository；
4. shared 不能反向依赖业务模块。

运行：
    pytest tests/test_architecture.py -q
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"

MODULES = {
    "identity",
    "student",
    "psych",
    "employee",
    "catalog",
    "recommend",
    "nl2sql",
    "shared",
}

BUSINESS_MODULES = MODULES - {"shared"}


def py_files() -> list[Path]:
    """所有业务 Python 文件，排除缓存。"""
    return [
        path
        for path in APP_DIR.rglob("*.py")
        if "__pycache__" not in path.parts
    ]


def module_of_file(path: Path) -> str | None:
    """根据文件路径判断它属于哪个模块。"""
    relative = path.relative_to(APP_DIR)
    if not relative.parts:
        return None
    first = relative.parts[0]
    return first if first in MODULES else None


def iter_imports(path: Path):
    """遍历一个文件里的绝对 import（项目内统一用绝对导入）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                yield node.module


def module_of_dotted(dotted: str) -> str | None:
    """app.student.internal.service -> student"""
    parts = dotted.split(".")
    if len(parts) >= 2 and parts[0] == "app" and parts[1] in MODULES:
        return parts[1]
    return None


def test_no_cross_module_internal_imports() -> None:
    """
    规则一：模块封装。

    除了组合根 app/main.py，任何文件都不能 import 其他模块的 internal。
    """
    violations: list[str] = []

    for path in py_files():
        if path == APP_DIR / "main.py":
            continue

        source_module = module_of_file(path)
        if not source_module:
            continue

        for dotted in iter_imports(path):
            target_module = module_of_dotted(dotted)
            if (
                target_module
                and target_module != source_module
                and ".internal" in dotted
            ):
                violations.append(
                    f"{path.relative_to(APP_DIR)} -> {dotted}"
                )

    assert not violations, (
        "发现跨模块 internal 导入：\n" + "\n".join(violations)
    )


def test_module_dependencies_are_acyclic() -> None:
    """规则二：模块之间的静态依赖必须构成 DAG。"""
    graph: dict[str, set[str]] = defaultdict(set)

    for path in py_files():
        source_module = module_of_file(path)
        if not source_module:
            continue

        for dotted in iter_imports(path):
            target_module = module_of_dotted(dotted)
            if target_module and target_module != source_module:
                graph[source_module].add(target_module)

    visited: set[str] = set()
    stack: set[str] = set()
    cycles: list[str] = []

    def dfs(module: str, path: list[str]) -> None:
        visited.add(module)
        stack.add(module)
        path.append(module)

        for next_module in graph[module]:
            if next_module not in visited:
                dfs(next_module, path)
            elif next_module in stack:
                cycles.append(" -> ".join(path + [next_module]))

        stack.discard(module)
        path.pop()

    for module in MODULES:
        if module not in visited:
            dfs(module, [])

    assert not cycles, "发现循环依赖：\n" + "\n".join(cycles)


def test_layer_dependencies() -> None:
    """规则三：repository 不依赖 service/router；service 不依赖 router。"""
    violations: list[str] = []

    for path in py_files():
        relative = path.relative_to(APP_DIR).as_posix()

        if relative.endswith("internal/repository.py"):
            forbidden_markers = ("internal.service", "internal.router")
            # repository 也不能 import 其他模块的 api
            check_api = True
        elif relative.endswith("internal/service.py"):
            forbidden_markers = ("internal.router",)
            check_api = False
        elif relative.endswith("api.py"):
            forbidden_markers = ("internal.router",)
            check_api = False
        else:
            continue

        for dotted in iter_imports(path):
            if any(marker in dotted for marker in forbidden_markers):
                violations.append(f"{relative} -> {dotted}")

            if check_api and dotted.startswith("app.") and dotted.endswith(".api"):
                violations.append(f"{relative} -> {dotted}")

    assert not violations, "发现分层依赖违规：\n" + "\n".join(violations)


def test_shared_does_not_import_business_modules() -> None:
    """规则四：shared 是共享内核，不能反向依赖业务模块。"""
    violations: list[str] = []

    for path in (APP_DIR / "shared").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue

        for dotted in iter_imports(path):
            target_module = module_of_dotted(dotted)
            if target_module in BUSINESS_MODULES:
                violations.append(f"{path.relative_to(APP_DIR)} -> {dotted}")

    assert not violations, "shared 依赖了业务模块：\n" + "\n".join(violations)
