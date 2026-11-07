"""Verify the odoo20 skills against the Odoo 20 source.

Checks every markdown file of our skills (not Odoo's official ones):
  1. relative links resolve to existing files;
  2. cited Odoo paths (`odoo/...`, `addons/...`, with optional :line) exist in the Odoo tree;
  3. Python `from odoo.x import a, b` lines in code blocks import names that exist in that module;
  4. JS `import { a } from "@addon/path"` lines in code blocks import names the module exports (via the index).

    ODOO20_ROOT=/path/to/odoo python scripts/check_skill_refs.py [--quiet]   (root auto-detected when unset)
Exit code 1 when something is broken.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp"))
# data dir / Odoo root: same resolution as the MCP server (ODOO20_DATA_DIR, ODOO20_ROOT, auto-detection)

OFFICIAL = {"odoo-git", "odoo-guidelines", "odoo-review", "odoo-security", "odoo-web-guidelines"}
LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
SRC_PATH = re.compile(r"(?<![\w/.])((?:odoo|addons)/[\w./@-]+?\.(?:json|js|py|xml|scss|csv|rng|txt|ts|md|sql)(?:\.template)?)(?![\w.])(?::\d+(?:-\d+)?)?")
# paths the docs name on purpose because they do NOT exist in Odoo 20
KNOWN_ABSENT = {"odoo/__init__.py"}
INLINE_CODE = re.compile(r"`[^`\n]*`")
CODE_BLOCK = re.compile(r"```(\w*)\n(.*?)```", re.S)
PY_IMPORT = re.compile(r"^\s*from\s+(odoo[\w.]*)\s+import\s+(?:\(([\w ,\n]+)\)|([\w ,]+))", re.M)
JS_IMPORT = re.compile(r"import\s*\{([^}]*)\}\s*from\s*[\"'](@[\w./-]+)[\"']")


def _module_file(odoo_root: Path, module: str) -> tuple[Path | None, Path | None]:
    """(file, package_dir) for a dotted odoo module; odoo.addons.X resolves in both addons folders."""
    parts = module.split(".")
    bases = [odoo_root]
    if parts[:2] == ["odoo", "addons"] and len(parts) > 2:
        bases = [odoo_root / "odoo" / "addons", odoo_root / "addons"]
        parts = parts[2:]
    for base in bases:
        rel = base.joinpath(*parts)
        for cand in (rel.with_suffix(".py"), rel / "__init__.py"):
            if cand.is_file():
                return cand, rel if rel.is_dir() else None
        if rel.is_dir():
            return None, rel
    return None, None


def py_names(odoo_root: Path, module: str, _depth: int = 0) -> set[str] | None:
    import ast
    path, pkg = _module_file(odoo_root, module)
    if path is None and pkg is None:
        return None
    names: set[str] = set()
    if pkg is not None:
        names |= {p.stem for p in pkg.iterdir() if p.suffix == ".py" or p.is_dir()}
    if path is None:
        return names | {"*"}  # namespace package
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return names | {"*"}
    stack = list(tree.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name == "*" and isinstance(node, ast.ImportFrom) and node.level and _depth < 3:
                    sub = ".".join(module.split(".")[: len(module.split(".")) - (node.level - 1)] + ([node.module] if node.module else []))
                    names |= py_names(odoo_root, sub, _depth + 1) or set()
                else:
                    names.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, (ast.If, ast.Try, ast.With)):
            stack.extend(node.body)
            stack.extend(getattr(node, "orelse", []))
            stack.extend(getattr(node, "finalbody", []))
            for handler in getattr(node, "handlers", []):
                stack.extend(handler.body)
        elif isinstance(node, ast.FunctionDef) is False and isinstance(node, ast.Expr):
            pass
    if any(isinstance(n, ast.FunctionDef) and n.name == "__getattr__" for n in tree.body):
        names.add("*")
    return names


def main() -> int:
    from odoo20_mcp import context
    odoo_root = context.config().odoo_root
    im = context.index()
    im.build()  # incremental: seconds when the index is current, ~20 s from scratch
    con = im.db()
    exports: dict[str, set[str]] = {}
    import json
    for r in con.execute("SELECT path, alias, exports FROM js_modules"):
        names = set(json.loads(r["exports"] or "[]"))
        for key in (r["path"], r["alias"]):
            if key:
                exports[key] = names
    quiet = "--quiet" in sys.argv
    problems: list[str] = []
    files = [p for p in (ROOT / "skills").rglob("*.md") if p.relative_to(ROOT / "skills").parts[0] not in OFFICIAL]
    for md in sorted(files):
        text = md.read_text(encoding="utf-8")
        rel = md.relative_to(ROOT)
        prose = INLINE_CODE.sub("", CODE_BLOCK.sub("", text))
        for target in LINK.findall(prose):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (md.parent / target).resolve().exists():
                problems.append(f"{rel}: broken link -> {target}")
        for path in set(SRC_PATH.findall(text)):
            if path in KNOWN_ABSENT:
                continue
            if not (odoo_root / path).exists() and "<" not in path and "*" not in path:
                problems.append(f"{rel}: cited path not in Odoo tree -> {path}")
        for lang, block in CODE_BLOCK.findall(text):
            if lang in {"python", "py", ""}:
                for module, paren_names, line_names in PY_IMPORT.findall(block):
                    names = paren_names or line_names
                    available = py_names(odoo_root, module)
                    if available is None:
                        problems.append(f"{rel}: python module not found -> {module}")
                        continue
                    if "*" in available:
                        continue
                    for part in names.replace("\n", " ").split(","):
                        name = part.strip().split(" as ")[0].strip()
                        if name and name not in available:
                            problems.append(f"{rel}: `from {module} import {name}` - name not found in {module}")
            if lang in {"javascript", "js", ""}:
                for names, source in JS_IMPORT.findall(block):
                    norm = re.sub(r"/index$", "", source)
                    available = exports.get(source) or exports.get(norm)
                    if source.startswith(("@odoo/owl", "@odoo/hoot")) or source.startswith("@my_module") or \
                            source.startswith("@odoo20_") or "your" in source or "my_" in source:
                        continue
                    if available is None:
                        problems.append(f"{rel}: JS module not found -> {source}")
                        continue
                    if "*" in available or not available:
                        continue
                    for part in names.split(","):
                        name = part.strip().split(" as ")[0].strip()
                        if name and name not in available:
                            problems.append(f"{rel}: `import {{ {name} }} from \"{source}\"` - not exported")
    for p in problems:
        print(p)
    if not quiet:
        print(f"\nchecked {len(files)} files: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
