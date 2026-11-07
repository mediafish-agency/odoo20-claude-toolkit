"""Extract module paths, imports/exports, registries, patches and classes from Odoo JS.

Works on comment-stripped text so multi-line chains such as::

    registry
        .category("fields")
        .add("char", charField);

and per-file variables (``const fieldRegistry = registry.category("fields")``)
are both found.
"""
from __future__ import annotations

import json
import re

from ..util import line_of, strip_js_comments

_STR = r"""(["'`])((?:(?!\1)[^\\]|\\.)*)\1"""
_IMPORT = re.compile(r"\bimport\s+(?:([\w*${}\s,]+?)\s+from\s+)?[\"']([^\"']+)[\"']", re.S)
_EXPORT_DECL = re.compile(r"\bexport\s+(?:default\s+)?(?:async\s+)?(?:function\*?|class|const|let|var)\s+([\w$]+)")
_EXPORT_LIST = re.compile(r"\bexport\s*\{([^}]*)\}")
_EXPORT_DEFAULT = re.compile(r"\bexport\s+default\b")
_EXPORT_STAR = re.compile(r"\bexport\s*\*\s*(?:as\s+([\w$]+)\s+)?from\b")
_CATEGORY_CHAIN = re.compile(
    r"(?:\b(?:const|let|var)\s+([\w$]+)\s*=\s*)?\bregistry((?:\s*\.\s*category\(\s*[\"'`][^\"'`]+[\"'`]\s*\))+)"
)
_CATEGORY = re.compile(r"category\(\s*[\"'`]([^\"'`]+)[\"'`]\s*\)")
_ADD_AFTER = re.compile(r"\s*\.\s*add\(\s*(?:" + _STR + r"|([\w$.]+))\s*(?:,\s*([^,)\n]{0,80}))?")
_PATCH = re.compile(r"\bpatch\(\s*([\w$.]+(?:\.prototype)?)")
_CLASS = re.compile(r"\bclass\s+([\w$]+)(?:\s+extends\s+([\w$.]+(?:\([^)]*\))?))?\s*\{")
_STATIC_TEMPLATE = re.compile(r"\bstatic\s+template\s*=\s*[\"'`]([^\"'`]+)[\"'`]")
_SERVICES_ADD = re.compile(r"\bservices\s*\.\s*add\(\s*([\w$]+)")
ALIAS = re.compile(r"@odoo-module\s+alias=([\w@/.\-]+)")


def module_path(addon: str, rel: str) -> str | None:
    """Odoo's transpiler naming: static/src/a/b.js -> @addon/a/b; static/tests -> @addon/../tests/..."""
    rel = rel.replace("\\", "/")
    if not rel.endswith(".js"):
        return None
    stem = rel[:-3]
    if stem.startswith("static/src/"):
        path = f"@{addon}/{stem[len('static/src/'):]}"
    elif stem.startswith("static/"):
        path = f"@{addon}/../{stem[len('static/'):]}"
    else:
        return None
    # odoo/tools/js_transpiler.py remove_index: a folder holding index.js is importable by its name
    return path[: -len("/index")] if path.endswith("/index") else path


def extract(module: str, rel: str, raw: str) -> dict[str, list]:
    out: dict[str, list] = {"js_modules": [], "js_imports": [], "js_registry": [], "js_patches": [], "js_classes": []}
    alias_m = ALIAS.search(raw[:400])
    text = strip_js_comments(raw)
    exports = set(_EXPORT_DECL.findall(text))
    for m in _EXPORT_LIST.finditer(text):
        for part in m.group(1).split(","):
            part = part.strip()
            if part:
                exports.add(part.split(" as ")[-1].strip())
    if _EXPORT_DEFAULT.search(text):
        exports.add("default")
    for m in _EXPORT_STAR.finditer(text):
        exports.add(m.group(1) or "*")  # `export * from` re-exports names we do not resolve
    path = module_path(module, rel)
    out["js_modules"].append((module, path, alias_m.group(1) if alias_m else None, rel, json.dumps(sorted(exports))))

    imported_services = False
    for m in _IMPORT.finditer(text):
        names = re.sub(r"\s+", " ", (m.group(1) or "").strip())
        source = m.group(2)
        out["js_imports"].append((module, rel, line_of(text, m.start()), source, names))
        if source == "@web/core/services" and "services" in names:
            imported_services = True

    variables: dict[str, str] = {}
    for m in _CATEGORY_CHAIN.finditer(text):
        category = ".".join(_CATEGORY.findall(m.group(2)))
        if m.group(1):
            variables[m.group(1)] = category
        add = _ADD_AFTER.match(text, m.end())
        if add:
            key = add.group(2) if add.group(1) else add.group(3)
            value = (add.group(4) or "").strip()
            out["js_registry"].append((module, category, key, value, rel, line_of(text, m.start())))
    for var, category in variables.items():
        for m in re.finditer(r"\b" + re.escape(var) + r"(?=\s*\.\s*add\()", text):
            add = _ADD_AFTER.match(text, m.end())
            if add:
                key = add.group(2) if add.group(1) else add.group(3)
                value = (add.group(4) or "").strip()
                out["js_registry"].append((module, category, key, value, rel, line_of(text, m.start())))
    if imported_services:
        for m in _SERVICES_ADD.finditer(text):
            out["js_registry"].append((module, "services (plugins)", m.group(1), m.group(1), rel, line_of(text, m.start())))

    for m in _PATCH.finditer(text):
        out["js_patches"].append((module, m.group(1), rel, line_of(text, m.start())))

    classes = list(_CLASS.finditer(text))
    for i, m in enumerate(classes):
        end = classes[i + 1].start() if i + 1 < len(classes) else len(text)
        tpl = _STATIC_TEMPLATE.search(text, m.end(), end)
        out["js_classes"].append((
            module, m.group(1), (m.group(2) or "").split("(")[0] or None, tpl.group(1) if tpl else None,
            rel, line_of(text, m.start()),
        ))
    return out
