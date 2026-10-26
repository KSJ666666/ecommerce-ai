"""校验 app/ 下所有 py 文件的相对导入：模块是否存在、导入的符号是否真的定义在该模块里。
只做静态检查（不执行被导入模块的副作用），用完可删。
"""
import ast
import re
from pathlib import Path

ROOT = Path(r"D:\code\spzx-parent\spzx-parent\customer-service-backend")
APP = ROOT / "app"

problems = []

def module_path(mod: str) -> Path | None:
    """app.domain.state -> app/domain/state.py"""
    parts = mod.split(".")
    if parts[0] != "app":
        return None
    p = APP.joinpath(*parts[1:])
    if (p.with_suffix(".py")).exists():
        return p.with_suffix(".py")
    if (p / "__init__.py").exists():
        return p / "__init__.py"
    return None

def defined_names(path: Path) -> set[str]:
    """收集模块顶层定义的类名/函数名/变量名 + 可能的别名赋值"""
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
        elif isinstance(node, ast.ImportFrom):  # from x import y as z 也导出
            for a in node.names:
                names.add(a.asname or a.name)
        elif isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.asname or a.name.split(".")[0])
    return names

for py in sorted(APP.rglob("*.py")):
    if "__pycache__" in py.parts:
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
        if not mod.startswith("app."):
            continue
        target = module_path(mod)
        if target is None:
            problems.append(f"[模块不存在] {py.relative_to(ROOT)}  ->  {mod}")
            continue
        available = defined_names(target)
        for alias in node.names:
            if alias.name == "*":
                continue
            if alias.name not in available:
                problems.append(
                    f"[符号缺失] {py.relative_to(ROOT)}  import {alias.name} from {mod}"
                )

if problems:
    print(f"发现 {len(problems)} 个问题：")
    for p in problems:
        print("  " + p)
else:
    print("全部 import 校验通过")
