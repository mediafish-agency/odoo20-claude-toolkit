"""Read-side queries over the index (pure functions of a sqlite connection)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ..util import did_you_mean

MAGIC_FIELDS = {
    "id": "Id", "display_name": "Char", "create_uid": "Many2one", "create_date": "Datetime",
    "write_uid": "Many2one", "write_date": "Datetime",
}


# ---------------------------------------------------------------------------
# modules & load order
# ---------------------------------------------------------------------------

class Graph:
    """Dependency graph and Odoo's load order: sort by (phase, depth, order_name),
    see odoo/modules/module_graph.py (test_* modules load right after their last dependency)."""

    def __init__(self, con: sqlite3.Connection):
        self.paths: dict[str, str] = {}
        self.deps: dict[str, list[str]] = {}
        self.auto: dict[str, object] = {}
        for row in con.execute("SELECT name, path, depends, auto_install FROM modules"):
            self.paths[row["name"]] = row["path"]
            deps = json.loads(row["depends"] or "[]")
            self.deps[row["name"]] = deps or ([] if row["name"] == "base" else ["base"])
            self.auto[row["name"]] = json.loads(row["auto_install"] or "false")
        self._depth: dict[str, int] = {}
        self._oname: dict[str, str] = {}
        self.rdeps: dict[str, list[str]] = {}
        for name, deps in self.deps.items():
            for d in deps:
                self.rdeps.setdefault(d, []).append(name)
        order = sorted(self.deps, key=lambda m: (0 if m == "base" else 1, self.depth(m), self.order_name(m)))
        self.order = {name: i for i, name in enumerate(order)}

    def _known_deps(self, name: str) -> list[str]:
        return [d for d in self.deps.get(name, []) if d in self.deps]

    def _last_dep(self, name: str) -> str | None:
        deps = self._known_deps(name)
        return max(deps, key=lambda d: (self.depth(d), self.order_name(d))) if deps else None

    def depth(self, name: str, _stack: frozenset = frozenset()) -> int:
        if name in self._depth:
            return self._depth[name]
        if name in _stack:
            return 0
        deps = self._known_deps(name)
        if name.startswith("test_") and deps:
            value = self.depth(self._last_dep(name), _stack | {name})
        else:
            value = max((self.depth(d, _stack | {name}) for d in deps), default=-1) + 1
        self._depth[name] = value
        return value

    def order_name(self, name: str) -> str:
        if name in self._oname:
            return self._oname[name]
        value = name
        if name.startswith("test_"):
            last = self._last_dep(name)
            if last:
                value = self.order_name(last) + " " + name
        self._oname[name] = value
        return value

    def closure(self, name: str) -> set[str]:
        seen: set[str] = set()
        stack = [name]
        while stack:
            cur = stack.pop()
            if cur in seen or cur not in self.deps:
                continue
            seen.add(cur)
            stack.extend(self.deps[cur])
        return seen

    def install_closure(self, name: str) -> set[str]:
        """Modules present once ``name`` is installed: its dependencies plus every auto_install module whose
        trigger modules are all present (fixpoint), as Odoo's module installer does."""
        scope = self.closure(name)
        changed = True
        while changed:
            changed = False
            for mod, auto in self.auto.items():
                if mod in scope or not auto:
                    continue
                trigger = self.deps.get(mod, []) if auto is True else [d for d in auto if isinstance(d, str)]
                if all(t in scope for t in trigger):
                    scope |= self.closure(mod)
                    changed = True
        return scope

    def dependents(self, name: str, recursive: bool = False) -> set[str]:
        direct = set(self.rdeps.get(name, []))
        if not recursive:
            return direct
        seen: set[str] = set()
        stack = list(direct)
        while stack:
            cur = stack.pop()
            if cur not in seen:
                seen.add(cur)
                stack.extend(self.rdeps.get(cur, []))
        return seen


_GRAPH_CACHE: dict[str, Graph] = {}


def graph(con: sqlite3.Connection) -> Graph:
    key = con.execute("SELECT value FROM meta WHERE key='built_at'").fetchone()[0]
    if key not in _GRAPH_CACHE:
        _GRAPH_CACHE.clear()
        _GRAPH_CACHE[key] = Graph(con)
    return _GRAPH_CACHE[key]


def scope_modules(con: sqlite3.Connection, scope_module: str | None, include_tests: bool = False) -> set[str] | None:
    g = graph(con)
    if scope_module:
        if scope_module not in g.deps:
            raise did_you_mean("Module", scope_module, g.deps)
        return g.install_closure(scope_module)
    if include_tests:
        return None
    return {m for m in g.deps if not m.startswith("test_") and "_test" not in m}


def display_path(con_or_graph, module: str, rel: str, odoo_root: Path) -> str:
    g = con_or_graph if isinstance(con_or_graph, Graph) else graph(con_or_graph)
    base = g.paths.get(module)
    if not base:
        return rel
    full = Path(base) / rel
    try:
        return str(full.relative_to(odoo_root))
    except ValueError:
        return str(full)


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------

def known_models(con: sqlite3.Connection) -> list[str]:
    return [r[0] for r in con.execute("SELECT DISTINCT model FROM models")]


def contributions(con: sqlite3.Connection, model: str, scope: set[str] | None) -> list[sqlite3.Row]:
    g = graph(con)
    rows = [r for r in con.execute("SELECT * FROM models WHERE model=?", (model,)) if scope is None or r["module"] in scope]
    rows.sort(key=lambda r: (g.order.get(r["module"], 10**6), r["file"], r["line"]))
    return rows


def merged_fields(con: sqlite3.Connection, model: str, scope: set[str] | None, _stack: frozenset = frozenset()) -> dict:
    """Fields of ``model`` merged in load order. Each value: {type, comodel, attrs, defs:[...], origin}."""
    if model in _stack:
        return {}
    stack = _stack | {model}
    contribs = contributions(con, model, scope)
    result: dict[str, dict] = {}
    log_access = True
    for c in contribs:
        for parent in json.loads(c["parents"] or "[]"):
            for fname, info in merged_fields(con, parent, scope, stack).items():
                if fname not in result:
                    result[fname] = {**info, "origin": info.get("origin") or parent}
        attrs = json.loads(c["attrs"] or "{}")
        if attrs.get("_log_access") is False or attrs.get("_auto") is False:
            log_access = attrs.get("_log_access", True) is not False and attrs.get("_auto", True) is not False
        frows = con.execute(
            "SELECT * FROM fields WHERE model=? AND module=? AND file=? AND line>=? ORDER BY line",
            (model, c["module"], c["file"], c["line"]),
        ).fetchall()
        # only fields declared in this class body (stop at the next class in the same file)
        next_cls = con.execute(
            "SELECT min(line) FROM models WHERE module=? AND file=? AND line>?", (c["module"], c["file"], c["line"])
        ).fetchone()[0]
        for f in frows:
            if next_cls and f["line"] > next_cls:
                break
            fattrs = json.loads(f["attrs"] or "{}")
            entry = result.get(f["name"])
            d = {"module": f["module"], "file": f["file"], "line": f["line"], "type": f["ftype"], "attrs": fattrs}
            if entry is None or entry.get("origin"):
                result[f["name"]] = {"type": f["ftype"], "comodel": f["comodel"], "attrs": dict(fattrs), "defs": [d], "origin": None}
            else:
                entry["attrs"].update(fattrs)
                entry["type"] = f["ftype"] or entry["type"]
                entry["comodel"] = f["comodel"] or entry["comodel"]
                entry["defs"].append(d)
        for parent_model, fk in json.loads(c["inherits"] or "{}").items():
            for fname, info in merged_fields(con, parent_model, scope, stack).items():
                if fname not in result and fname not in MAGIC_FIELDS:
                    result[fname] = {**info, "origin": f"{parent_model} (_inherits via {fk})"}
    if contribs:
        for fname, ftype in MAGIC_FIELDS.items():
            if fname in {"id", "display_name"} or log_access:
                result.setdefault(fname, {"type": ftype, "comodel": "res.users" if fname.endswith("_uid") else None,
                                          "attrs": {}, "defs": [], "origin": "magic"})
    return result


def model_info(con: sqlite3.Connection, model: str, scope: set[str] | None) -> dict:
    contribs = contributions(con, model, scope)
    if not contribs:
        raise did_you_mean("Model", model, known_models(con))
    fields = merged_fields(con, model, scope)
    parents: list[str] = []
    inherits: dict = {}
    attrs: dict = {}
    for c in contribs:
        for p in json.loads(c["parents"] or "[]"):
            if p not in parents:
                parents.append(p)
        inherits.update(json.loads(c["inherits"] or "{}"))
        attrs.update(json.loads(c["attrs"] or "{}"))
    methods = con.execute(
        "SELECT name, module, decorators FROM methods WHERE model=? ORDER BY name", (model,)
    ).fetchall()
    methods = [m for m in methods if scope is None or m["module"] in scope]
    constraints = [dict(r) for r in con.execute("SELECT * FROM constraints WHERE model=?", (model,))
                   if scope is None or r["module"] in scope]
    return {
        "model": model,
        "contributions": [dict(c) for c in contribs],
        "parents": parents,
        "inherits": inherits,
        "attrs": attrs,
        "fields": fields,
        "methods": methods,
        "constraints": constraints,
    }


def method_chain(con: sqlite3.Connection, model: str, method: str, scope: set[str] | None,
                 _stack: frozenset = frozenset()) -> list[dict]:
    """Definitions of ``method`` reachable from ``model`` in approximate MRO (call) order."""
    if model in _stack:
        return []
    stack = _stack | {model}
    g = graph(con)
    contribs = contributions(con, model, scope)
    chain: list[dict] = []
    for c in reversed(contribs):
        rows = con.execute(
            "SELECT * FROM methods WHERE model=? AND module=? AND file=? AND name=? AND line>=? ORDER BY line",
            (model, c["module"], c["file"], method, c["line"]),
        ).fetchall()
        next_cls = con.execute(
            "SELECT min(line) FROM models WHERE module=? AND file=? AND line>?", (c["module"], c["file"], c["line"])
        ).fetchone()[0]
        for r in rows:
            if next_cls and r["line"] > next_cls:
                break
            chain.append({**dict(r), "via": model, "order": g.order.get(r["module"])})
    seen_parents: list[str] = []
    for c in reversed(contribs):
        for p in reversed(json.loads(c["parents"] or "[]")):
            if p not in seen_parents:
                seen_parents.append(p)
    for p in seen_parents:
        for item in method_chain(con, p, method, scope, stack):
            if item not in chain:
                chain.append(item)
    return chain


# ---------------------------------------------------------------------------
# xmlids, views, templates
# ---------------------------------------------------------------------------

def xmlid_definitions(con: sqlite3.Connection, xmlid: str) -> list[sqlite3.Row]:
    return con.execute("SELECT * FROM records WHERE xmlid=?", (xmlid,)).fetchall()


def xmlid_references(con: sqlite3.Connection, xmlid: str, limit: int = 200) -> list[sqlite3.Row]:
    return con.execute("SELECT * FROM refs WHERE ref=? LIMIT ?", (xmlid, limit)).fetchall()


def view_children(con: sqlite3.Connection, xmlid: str) -> list[sqlite3.Row]:
    g = graph(con)
    rows = con.execute("SELECT * FROM views WHERE inherit_id=?", (xmlid,)).fetchall()

    def prio(r):
        try:
            return int(r["priority"] or 16)
        except ValueError:
            return 16
    return sorted(rows, key=lambda r: (prio(r), g.order.get(r["module"], 10**6), r["xmlid"] or ""))


def view_tree(con: sqlite3.Connection, xmlid: str, max_nodes: int = 400) -> dict:
    rows = con.execute("SELECT * FROM views WHERE xmlid=?", (xmlid,)).fetchall()
    if not rows:
        cands = [r[0] for r in con.execute("SELECT xmlid FROM views WHERE xmlid LIKE ?", (f"%{xmlid.split('.')[-1]}%",))]
        raise did_you_mean("View/template", xmlid, cands or [r[0] for r in con.execute("SELECT xmlid FROM views LIMIT 2000")])
    node = rows[0]
    ancestors = []
    cur = node
    while cur is not None and cur["inherit_id"] and cur["mode"] != "primary":
        parent = con.execute("SELECT * FROM views WHERE xmlid=?", (cur["inherit_id"],)).fetchone()
        if parent is None:
            break
        ancestors.append(parent)
        cur = parent
    root = ancestors[-1] if ancestors else node
    count = 0

    def build(row, depth=0):
        nonlocal count
        count += 1
        kids = [] if count > max_nodes else [build(k, depth + 1) for k in view_children(con, row["xmlid"])]
        return {"view": dict(row), "children": kids}
    return {"root": build(root), "focus": node["xmlid"], "ancestors": [a["xmlid"] for a in ancestors], "truncated": count > max_nodes}


def template_callers(con: sqlite3.Connection, name: str, limit: int = 100) -> list[sqlite3.Row]:
    return con.execute("SELECT * FROM refs WHERE ref=? AND via IN ('xml.t-call','owl.t-call') LIMIT ?", (name, limit)).fetchall()


# ---------------------------------------------------------------------------
# security
# ---------------------------------------------------------------------------

def access_rows(con: sqlite3.Connection, model: str) -> list[sqlite3.Row]:
    model_xmlid_suffix = "%.model_" + model.replace(".", "_")
    return con.execute(
        "SELECT * FROM access WHERE model=? OR model_ref LIKE ? ORDER BY module, file, line",
        (model, model_xmlid_suffix),
    ).fetchall()


# ---------------------------------------------------------------------------
# assets
# ---------------------------------------------------------------------------

def asset_entries(con: sqlite3.Connection, bundle: str, scope: set[str] | None) -> list[dict]:
    g = graph(con)
    rows = [dict(r) for r in con.execute("SELECT * FROM assets WHERE bundle=?", (bundle,)) if scope is None or r["module"] in scope]
    rows.sort(key=lambda r: (g.order.get(r["module"], 10**6), r["seq"]))
    return rows

