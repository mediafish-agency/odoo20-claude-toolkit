"""Extract Odoo model structure from Python sources with ``ast``."""
from __future__ import annotations

import ast
import json
import re

MODEL_BASES = {"Model", "AbstractModel", "TransientModel", "CachedModel", "BaseModel"}
MODEL_ATTRS = {
    "_name", "_inherit", "_inherits", "_description", "_order", "_rec_name", "_rec_names_search",
    "_table", "_auto", "_log_access", "_parent_name", "_parent_store", "_active_name", "_check_company_auto",
    "_fold_name", "_translate", "_register", "_abstract", "_transient", "_clear_cache_name",
    "_clear_cache_on_fields", "_explanation", "_allow_sudo_commands", "_table_query", "_sequence",
}
RELATIONAL = {"Many2one", "One2many", "Many2many"}
CONSTRAINT_TYPES = {"Constraint", "Index", "UniqueIndex"}

_REF_CALL = re.compile(
    r"\b(?:ref|has_group|_xmlid_to_res_id|_xmlid_lookup|_xmlid_to_res_model_res_id|_get_id)\(\s*"
    r"['\"]([a-z0-9_]+\.[A-Za-z0-9_.]+)['\"]"
)
_GROUPS_KW = re.compile(r"\bgroups\s*=\s*['\"]([a-z0-9_.,!\- ]+)['\"]")


def _literal(node: ast.AST, limit: int = 160):
    try:
        return ast.literal_eval(node)
    except Exception:  # noqa: BLE001
        text = ast.unparse(node)
        return {"expr": text if len(text) <= limit else text[:limit] + "…"}


def _as_list(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [v for v in value if isinstance(v, str)]
    return []


def _base_names(cls: ast.ClassDef) -> list[str]:
    names = []
    for base in cls.bases:
        if isinstance(base, ast.Attribute):
            names.append(base.attr)
        elif isinstance(base, ast.Name):
            names.append(base.id)
    return names


def _calls_super(fn: ast.AST) -> bool:
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "super":
            return True
    return False


def _field_call(value: ast.AST) -> tuple[str, str] | None:
    """Return (namespace, ctor) for ``fields.X(...)`` / ``models.Constraint(...)`` calls."""
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) and isinstance(value.func.value, ast.Name):
        return value.func.value.id, value.func.attr
    return None


def extract(module: str, rel: str, text: str) -> dict[str, list]:
    out: dict[str, list] = {"models": [], "fields": [], "methods": [], "constraints": [], "refs": [], "errors": []}
    for m in _REF_CALL.finditer(text):
        out["refs"].append((module, m.group(1), "py.ref", "py", rel, text.count("\n", 0, m.start()) + 1))
    for m in _GROUPS_KW.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        for grp in m.group(1).split(","):
            grp = grp.strip().lstrip("!-")
            if "." in grp:
                out["refs"].append((module, grp, "py.groups", "py", rel, line))
    try:
        tree = ast.parse(text, filename=rel)
    except SyntaxError as exc:
        out["errors"].append((module, rel, exc.lineno or 0, f"SyntaxError: {exc.msg}"))
        return out

    for cls in tree.body:
        if not isinstance(cls, ast.ClassDef):
            continue
        bases = _base_names(cls)
        attrs: dict = {}
        fields: list = []
        constraints: list = []
        methods: list = []
        for stmt in cls.body:
            targets: list[str] = []
            value = None
            if isinstance(stmt, ast.Assign) and all(isinstance(t, ast.Name) for t in stmt.targets):
                targets, value = [t.id for t in stmt.targets], stmt.value  # also `_name = _description = 'x'`
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None:
                targets, value = [stmt.target.id], stmt.value
            for target in targets:
                if target in MODEL_ATTRS:
                    attrs[target] = _literal(value)
                    continue
                call = _field_call(value)
                if call and call[0] == "fields" and call[1][:1].isupper():
                    fields.append((target, call[1], value, stmt.lineno))
                elif call and call[0] == "models" and call[1] in CONSTRAINT_TYPES:
                    constraints.append((target, call[1], ast.unparse(value)[:300], stmt.lineno))
            if targets:
                continue
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(stmt)

        base_kind = next((b for b in bases if b in MODEL_BASES), None)
        name = attrs.get("_name") if isinstance(attrs.get("_name"), str) else None
        inherit = _as_list(attrs.get("_inherit"))
        if not name and not inherit:
            continue  # abstract framework class or plain helper class
        model = name or inherit[0]
        kind = "define" if name and name not in inherit else "extend"
        parents = [p for p in inherit if p != model]
        inherits = attrs.get("_inherits") if isinstance(attrs.get("_inherits"), dict) else {}
        model_type = base_kind or (bases[0] if bases else "")
        plain_attrs = {k: v for k, v in attrs.items() if k not in {"_name", "_inherit", "_inherits"}}
        out["models"].append((
            module, model, kind, json.dumps(parents), json.dumps(inherits), model_type,
            json.dumps(plain_attrs, default=str), rel, cls.lineno, cls.name,
        ))
        for fname, ftype, call, line in fields:
            comodel = None
            fattrs: dict = {}
            if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
                if ftype in RELATIONAL:
                    comodel = call.args[0].value
                else:
                    fattrs["string"] = call.args[0].value
            if ftype in {"Many2one", "One2many", "Many2many"} and len(call.args) > 1:
                second = call.args[1]
                if isinstance(second, ast.Constant) and isinstance(second.value, str):
                    fattrs["inverse_name" if ftype == "One2many" else "string"] = second.value
            for kw in call.keywords:
                if kw.arg is None:
                    continue
                if kw.arg == "comodel_name" and isinstance(kw.value, ast.Constant):
                    comodel = kw.value.value
                fattrs[kw.arg] = _literal(kw.value)
            out["fields"].append((
                module, model, fname, ftype, comodel, json.dumps(fattrs, default=str), rel, line, kind,
            ))
        for cname, ctype, definition, line in constraints:
            out["constraints"].append((module, model, cname, ctype, definition, rel, line))
        for fn in methods:
            decorators = [ast.unparse(d) for d in fn.decorator_list]
            out["methods"].append((
                module, model, fn.name, json.dumps(decorators), ast.unparse(fn.args)[:300],
                int(_calls_super(fn)), rel, fn.lineno, fn.end_lineno or fn.lineno,
            ))
    return out
