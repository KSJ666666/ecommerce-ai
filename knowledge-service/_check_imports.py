"""静态校验 knowledge 包内所有 `from knowledge.x import y`：
模块是否存在、导入的符号是否真的定义在该模块里。不执行被导入模块的副作用。
"""
import ast
from pathlib import Path

ROOT = Path(r"D:\code\shopkeeper_brain")
PKG = ROOT / "knowledge"
SKIP = {"__pycache__", "temp_data", "temp_dir"}


def module_path(mod: str) -> Path | None:
    parts = mod.split(".")
    if parts[0] != "knowledge":
        return None
    p = PKG.joinpath(*parts[1:])
    if p.with_suffix(".py").exists():
        return p.with_suffix(".py")
    if (p / "__init__.py").exists():
        return p / "__init__.py"
    return None


def defined_names(path: Path) -> set[str]:
    names: set[str] = set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return names
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                names.add(a.asname or a.name)
        elif isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.asname or a.name.split(".")[0])
    return names


problems = []
for py in sorted(PKG.rglob("*.py")):
    if any(p in SKIP for p in py.parts):
        continue
    try:
        tree = ast.parse(py.read_text(encoding="utf-8"))
    except SyntaxError as e:
        problems.append(f"[语法错误] {py.relative_to(ROOT)}: {e}")
        continue
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        mod = node.module or ""
        if not mod.startswith("knowledge."):
            continue
        target = module_path(mod)
        if target is None:
            problems.append(f"[模块不存在] {py.relative_to(ROOT)} -> {mod}")
            continue
        available = defined_names(target)
        for alias in node.names:
            if alias.name == "*":
                continue
            if alias.name not in available and target.name != "__init__.py":
                problems.append(f"[符号缺失] {py.relative_to(ROOT)} import {alias.name} from {mod}")

if problems:
    print(f"发现 {len(problems)} 个问题：")
    for p in problems:
        print("  " + p)
else:
    print("全部 import 校验通过")
