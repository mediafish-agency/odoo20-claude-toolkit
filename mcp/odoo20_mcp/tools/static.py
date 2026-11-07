"""Static (source index) tools. Each function returns the tool's text output."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .. import context as ctx
from ..config import ROOT_HELP
from ..query import core as q
from ..util import ToolError, did_you_mean, md_table, page, render, suggest
from . import grep as grep_mod

FIELD_KEY_ATTRS = ("compute", "related", "store", "required", "readonly", "index", "groups", "tracking",
                   "default", "selection", "aggregator", "translate", "company_dependent", "compute_sql")


def _con():
    try:
        return ctx.index().db()
    except RuntimeError as exc:
        raise ToolError(str(exc)) from exc


def _loc(g, module: str, rel: str, line: int | None = None) -> str:
    path = q.display_path(g, module, rel, ctx.config().odoo_root)
    return f"{path}:{line}" if line else path


def _short(value, limit: int = 60) -> str:
    text = value.get("expr") if isinstance(value, dict) and "expr" in value else value
    text = json.dumps(text) if not isinstance(text, str) else text
    return text if len(text) <= limit else text[: limit - 1] + "…"


# ---------------------------------------------------------------------------
def status(refresh: bool = False, fmt: str = "markdown") -> str:
    cfg, im = ctx.config(), ctx.index()
    if refresh:
        im.ensure_started()
    st = im.status()
    data = {"odoo_version": ctx.odoo_version(), "config": cfg.describe(), "index": st}
    if cfg.odoo_root_source == "unset":
        root_line = "- Odoo root: NOT CONFIGURED — " + ROOT_HELP
    else:
        root_line = f"- Odoo root: `{cfg.odoo_root}`" + (
            " (auto-detected near the project; set the plugin option odoo_root to pin it)"
            if cfg.odoo_root_source == "detected" else "")
    lines = [
        f"## Odoo {data['odoo_version']} workspace",
        root_line,
        "- Addons paths: " + ", ".join(f"`{p}`" for p in cfg.addons_paths),
        f"- Runtime interpreter (odoo-bin): `{cfg.odoo_python}` "
        + ("(found)" if cfg.odoo_python.exists()
           else "(MISSING — run the /odoo20:setup skill or scripts/setup_odoo_runtime.sh)"),
        f"- Databases tools may touch: {', '.join(cfg.db_allow)} · writes allowed: {cfg.allow_writes}",
        f"- Live JSON-2: {cfg.live_url + ' db=' + (cfg.live_db or '?') if cfg.live_url else 'not configured'}"
        + (" (API key set)" if cfg.live_api_key else ""),
    ]
    if cfg.odoo_config:
        lines.append(f"- Database connection settings from: `{cfg.odoo_config}`")
    if not data["odoo_version"].startswith(("20.", "unknown")):
        lines.append(f"- WARNING: this toolkit targets Odoo 20; the configured tree is Odoo {data['odoo_version']}")
    if st.get("ready"):
        stats = st.get("stats", {})
        lines.append(f"- Index: ready, built {st.get('built_at')} — {stats.get('modules')} modules, "
                     f"{stats.get('models')} model classes, {stats.get('fields')} fields, {stats.get('views')} views, "
                     f"{stats.get('js_registry')} JS registry entries")
    else:
        lines.append("- Index: not ready")
    if st.get("state") == "scanning":
        lines.append("- Index refresh: checking for changed files…")
    elif st.get("state") not in {"idle", None}:
        lines.append(f"- Indexing: {st['state']} {st.get('done')}/{st.get('total')} {st.get('message', '')}")
    elif st.get("message"):
        lines.append(f"- Last refresh: {st['message']}")
    if st.get("shadowed_modules"):
        lines.append("- Shadowed modules (same name in several paths): " + "; ".join(st["shadowed_modules"][:5]))
    return render(data, fmt, "\n".join(lines))


# ---------------------------------------------------------------------------
def search(query: str, kind: str | None, module: str | None, limit: int, offset: int, fmt: str) -> str:
    con = _con()
    query = query.strip()
    if not query:
        raise ToolError("query is empty")
    params: list = []
    if len(query) >= 3:
        where = "symbols MATCH ?"
        params.append('"' + query.replace('"', '""') + '"')  # only `name` is indexed
    else:
        where = "name LIKE ?"
        params.append(f"%{query}%")
    if kind:
        where += " AND kind = ?"
        params.append(kind)
    if module:
        where += " AND module = ?"
        params.append(module)
    rows = con.execute(
        f"SELECT name, kind, module, loc, detail FROM symbols WHERE {where} "
        "ORDER BY (lower(name) = lower(?)) DESC, (name LIKE ?) DESC, length(name) LIMIT ? OFFSET ?",
        (*params, query, f"{query}%", limit + 1, offset),
    ).fetchall()
    more = len(rows) > limit
    rows = rows[:limit]
    g = q.graph(con)
    items = [dict(r) for r in rows]
    if not items:
        pool: list[str] = []
        if kind in (None, "model"):
            pool += q.known_models(con)
        if kind in (None, "module"):
            pool += list(g.paths)
        if kind == "asset_bundle":
            pool += [r[0] for r in con.execute("SELECT DISTINCT bundle FROM assets")]
        hints = suggest(query, pool)
        if hints:
            return f"No symbol contains {query!r}. Did you mean: " + ", ".join(f"`{h}`" for h in hints) + "?"
        return f"No symbol matches {query!r}" + (f" (kind={kind})" if kind else "") + \
            ". Kinds: module, model, field, method, xmlid, owl_template, js_registry, js_module, js_class, asset_bundle. " \
            "For free text use odoo_grep."
    table = md_table(["name", "kind", "module", "location", "detail"], [
        (r["name"], r["kind"], r["module"],
         _loc(g, r["module"], r["loc"].rsplit(":", 1)[0], int(r["loc"].rsplit(":", 1)[1]))
         if ":" in (r["loc"] or "") and r["loc"].rsplit(":", 1)[1].isdigit() else r["loc"],
         _short(r["detail"] or "", 50)) for r in items])
    note = f"\n\n_More results: use offset={offset + limit}._" if more else ""
    return render(items, fmt, table + note)


def grep(pattern: str, regex: bool, ignore_case: bool, module: str | None, glob: str | None, context: int,
         limit: int, include_vendor: bool) -> str:
    cfg = ctx.config()
    roots = list(cfg.addons_paths)
    subpaths: list[str] = []
    if module:
        con = _con()
        g = q.graph(con)
        if module not in g.paths:
            raise did_you_mean("Module", module, g.paths)
        mpath = Path(g.paths[module])
        roots = [mpath.parent]
        subpaths = [mpath.name]
    else:
        # search the whole Odoo source (framework included) plus extra addons
        roots = [cfg.odoo_root, *cfg.extra_addons]
    lines, n = grep_mod.grep(roots, pattern, regex=regex, ignore_case=ignore_case, subpaths=subpaths, glob=glob,
                             context=context, limit=limit, include_vendor=include_vendor)
    if not lines:
        return f"No match for {pattern!r}" + (f" in module {module}" if module else "") + (f" ({glob})" if glob else "")
    head = f"{n} matching line(s)" + (" (limit reached — narrow with module/glob)" if n >= limit else "")
    return head + "\n```\n" + "\n".join(lines) + "\n```"


# ---------------------------------------------------------------------------
def module_info(name: str, fmt: str) -> str:
    con = _con()
    g = q.graph(con)
    row = con.execute("SELECT * FROM modules WHERE name=?", (name,)).fetchone()
    if row is None:
        raise did_you_mean("Module", name, g.paths)
    manifest = json.loads(row["manifest"] or "{}")
    kinds = Counter(r["kind"] for r in con.execute("SELECT kind FROM files WHERE module=?", (name,)))
    models = con.execute("SELECT model, kind, file, line FROM models WHERE module=? ORDER BY kind, model", (name,)).fetchall()
    views = Counter((r["kind"], r["vtype"]) for r in con.execute("SELECT kind, vtype FROM views WHERE module=?", (name,)))
    records = Counter(r["model"] for r in con.execute("SELECT model FROM records WHERE module=?", (name,)))
    assets = Counter(r["bundle"] for r in con.execute("SELECT bundle FROM assets WHERE module=?", (name,)))
    tests = [r["rel"] for r in con.execute("SELECT rel FROM files WHERE module=? AND (rel LIKE 'tests/test_%.py' OR rel LIKE 'static/tests/%.test.js')", (name,))]
    special = sorted({r["rel"].split("/")[0] for r in con.execute(
        "SELECT rel FROM files WHERE module=? AND (rel LIKE 'migrations/%' OR rel LIKE 'upgrades/%' OR rel LIKE 'populate/%' OR rel LIKE 'i18n/%')", (name,))})
    install = g.install_closure(name)
    data = {
        "name": name, "path": row["path"], "manifest": manifest, "depends": json.loads(row["depends"]),
        "dependency_closure": sorted(g.closure(name)), "install_closure_extra": sorted(install - g.closure(name)),
        "dependents": sorted(g.dependents(name)), "load_order": g.order.get(name),
        "files_by_kind": dict(kinds), "models": [dict(m) for m in models], "views": {f"{k[0]}:{k[1]}": v for k, v in views.items()},
        "records_by_model": dict(records.most_common(25)), "assets": dict(assets), "tests": tests, "special_dirs": special,
    }
    defined = [m["model"] for m in models if m["kind"] == "define"]
    extended = sorted({m["model"] for m in models if m["kind"] == "extend"})
    md = [
        f"## Module `{name}` — {manifest.get('name') or ''}",
        f"- Path: `{row['path']}` · version {manifest.get('version') or '-'} · license {manifest.get('license') or '(unset)'}"
        f" · application {bool(manifest.get('application'))} · auto_install {manifest.get('auto_install', False)}",
        f"- Summary: {manifest.get('summary') or '-'}",
        f"- depends: {', '.join(data['depends']) or '(base)'}",
        f"- Dependency closure: {len(data['dependency_closure'])} modules; auto-installed with it: "
        f"{', '.join(data['install_closure_extra'][:15]) or 'none'}",
        f"- Direct dependents ({len(data['dependents'])}): {', '.join(data['dependents'][:30])}{' …' if len(data['dependents']) > 30 else ''}",
        f"- Load order position: {data['load_order']}",
        "- Files: " + ", ".join(f"{k} {v}" for k, v in kinds.most_common()),
        f"- Models defined ({len(defined)}): {', '.join(defined[:40]) or '-'}",
        f"- Models extended ({len(extended)}): {', '.join(extended[:40]) or '-'}",
        "- Views: " + (", ".join(f"{t or '?'}×{c}" for (_k, t), c in views.most_common()) or "-"),
        "- Data records: " + (", ".join(f"{m}×{c}" for m, c in records.most_common(12)) or "-"),
        "- Assets: " + (", ".join(f"{b} ({c})" for b, c in assets.most_common()) or "-"),
        f"- Tests: {len(tests)} file(s)" + (f" e.g. {', '.join(tests[:5])}" if tests else ""),
        f"- Special dirs: {', '.join(special) or '-'}",
    ]
    if row["error"]:
        md.append(f"- **Manifest error:** {row['error']}")
    return render(data, fmt, "\n".join(md))


# ---------------------------------------------------------------------------
def model_info(model: str, scope_module: str | None, include_tests: bool, field: str | None,
               include: str, limit: int, offset: int, fmt: str) -> str:
    con = _con()
    g = q.graph(con)
    scope = q.scope_modules(con, scope_module, include_tests)
    info = q.model_info(con, model, scope)
    fields = info["fields"]
    scope_note = f"scope: install closure of `{scope_module}`" if scope_module else \
        ("scope: all indexed modules" + ("" if include_tests else " except test modules"))
    if field:
        if field not in fields:
            raise did_you_mean(f"Field on {model}", field, fields)
        f = fields[field]
        rows = [(d["module"], _loc(g, d["module"], d["file"], d["line"]), d["type"],
                 ", ".join(f"{k}={_short(v, 40)}" for k, v in d["attrs"].items())) for d in f["defs"]]
        usage = con.execute(
            "SELECT xmlid, module, file, line FROM views WHERE model=? AND arch_fields LIKE ? LIMIT 30",
            (model, f'%"{field}"%')).fetchall()
        md = [f"## `{model}.{field}` ({f['type']}{' → ' + f['comodel'] if f.get('comodel') else ''})",
              f"_{scope_note}_", "",
              f"Origin: {f.get('origin') or 'declared on the model'}", "",
              "**Merged attributes** (later definitions override earlier ones):",
              ", ".join(f"`{k}`={_short(v, 80)}" for k, v in f["attrs"].items()) or "-", "",
              "**Definitions in load order:**", md_table(["module", "location", "type", "attributes"], rows)]
        if usage:
            md += ["", "**Referenced in views (direct, not inherited):**"] + \
                  [f"- {u['xmlid']} — {_loc(g, u['module'], u['file'], u['line'])}" for u in usage]
        return render({"model": model, "field": field, **f}, fmt, "\n".join(md))

    parts = {p.strip() for p in include.split(",")} if include else {"all"}
    want = lambda k: "all" in parts or k in parts  # noqa: E731
    md = [f"## Model `{model}`", f"_{scope_note}_", ""]
    attrs = info["attrs"]
    if attrs:
        md.append("Attributes: " + ", ".join(f"`{k}`={_short(v, 50)}" for k, v in attrs.items()))
    if info["parents"]:
        md.append("Inherits (mixins/parents): " + ", ".join(f"`{p}`" for p in info["parents"]))
    if info["inherits"]:
        md.append("Delegation `_inherits`: " + ", ".join(f"`{k}` via `{v}`" for k, v in info["inherits"].items()))
    if want("inheritance"):
        md += ["", f"**Contributing classes in load order ({len(info['contributions'])}):**",
               md_table(["module", "kind", "class", "location"],
                        [(c["module"], c["kind"], c["class_name"], _loc(g, c["module"], c["file"], c["line"]))
                         for c in info["contributions"]])]
    if want("fields"):
        names = sorted(fields)
        chunk, note = page(names, limit, offset)
        rows = []
        for name in chunk:
            f = fields[name]
            mods = [d["module"] for d in f["defs"]]
            key = ", ".join(f"{k}={_short(f['attrs'][k], 30)}" for k in FIELD_KEY_ATTRS if k in f["attrs"])
            origin = f.get("origin") or (mods[0] if mods else "")
            rows.append((name, f["type"] + (f"→{f['comodel']}" if f.get("comodel") else ""), origin,
                         ", ".join(mods[1:]) if len(mods) > 1 else "", key))
        md += ["", f"**Fields ({len(fields)}):**", md_table(["field", "type", "defined in", "overridden in", "key attributes"], rows) + note]
    if want("methods"):
        by_name: dict[str, list[str]] = {}
        for m in info["methods"]:
            by_name.setdefault(m["name"], []).append(m["module"])
        public = sorted(n for n in by_name if not n.startswith("_"))
        md += ["", f"**Methods on the model ({len(by_name)}; public: {len(public)}):** "
               + ", ".join(f"`{n}`({len(by_name[n])})" for n in public[:80])
               + ("" if len(public) <= 80 else " …"), "_Use odoo_method for the override chain of one method._"]
    if want("constraints") and info["constraints"]:
        md += ["", "**Constraints / indexes:**"] + [f"- `{c['name']}` {c['ctype']}: `{c['definition']}` ({c['module']})"
                                                    for c in info["constraints"]]
    data = {**info, "fields": {k: {kk: vv for kk, vv in v.items() if kk != "defs"} for k, v in fields.items()},
            "methods": [dict(m) for m in info["methods"]]}
    return render(data, fmt, "\n".join(md))


def method_info(model: str, method: str, scope_module: str | None, include_code: bool, fmt: str) -> str:
    con = _con()
    g = q.graph(con)
    scope = q.scope_modules(con, scope_module)
    if not q.contributions(con, model, scope):
        raise did_you_mean("Model", model, q.known_models(con))
    chain = q.method_chain(con, model, method, scope)
    base = method in _basemodel_methods()
    if not chain and not base:
        names = {r[0] for r in con.execute("SELECT DISTINCT name FROM methods WHERE model=?", (model,))}
        raise did_you_mean(f"Method on {model}", method, names)
    md = [f"## `{model}.{method}()` — call order (first row runs first; `super()` continues down)", ""]
    rows = []
    for c in chain:
        decos = json.loads(c["decorators"] or "[]")
        rows.append((c["module"], c["via"], _loc(g, c["module"], c["file"], c["line"]), " ".join(f"@{d}" for d in decos),
                     f"({c['signature']})", "yes" if c["calls_super"] else "**no**"))
    if rows:
        md.append(md_table(["module", "class model", "location", "decorators", "signature", "calls super()"], rows))
    if base:
        md.append(f"\nBase implementation: `BaseModel.{method}` in `odoo/orm/models.py`.")
    if include_code:
        for c in chain[:8]:
            path = Path(g.paths[c["module"]]) / c["file"]
            try:
                src = path.read_text(encoding="utf-8").splitlines()[c["line"] - 1: min(c["end_line"], c["line"] + 80)]
            except OSError:
                continue
            md += ["", f"**{c['module']}** — {_loc(g, c['module'], c['file'], c['line'])}", "```python", *src, "```"]
    return render({"model": model, "method": method, "chain": chain, "basemodel": base}, fmt, "\n".join(md))


def _basemodel_methods() -> frozenset[str]:
    from ..validate.semantic import basemodel_methods
    return basemodel_methods(str(ctx.config().odoo_root))


# ---------------------------------------------------------------------------
def xmlid_info(xmlid: str, limit: int, fmt: str) -> str:
    con = _con()
    g = q.graph(con)
    if "." not in xmlid:
        raise ToolError("xmlid must be fully qualified: module.name (e.g. sale.view_order_form)")
    defs = q.xmlid_definitions(con, xmlid)
    access = con.execute("SELECT * FROM access WHERE xmlid=?", (xmlid,)).fetchall()
    refs = q.xmlid_references(con, xmlid, limit)
    if not defs and not access and not refs:
        name = xmlid.split(".", 1)[1]
        cands = [r[0] for r in con.execute("SELECT DISTINCT xmlid FROM records WHERE xmlid LIKE ? LIMIT 400", (f"%{name[:12]}%",))]
        raise did_you_mean("XML id", xmlid, cands)
    md = [f"## `{xmlid}`", ""]
    if defs or access:
        md.append("**Defined / updated in:**")
        for d in defs:
            vals = json.loads(d["fields"] or "{}")
            keys = ", ".join(f"{k}={_short(v, 40)}" for k, v in list(vals.items())[:8])
            md.append(f"- `{d['model']}` ({d['tag']}) — {_loc(g, d['module'], d['file'], d['line'])}"
                      + (" · noupdate" if d["noupdate"] else "") + (f" — {keys}" if keys else ""))
        for a in access:
            md.append(f"- `ir.access` — {_loc(g, a['module'], a['file'], a['line'])} — {a['model'] or a['model_ref']} "
                      f"group={a['group_ref'] or '(restriction)'} op={a['operation']}")
    else:
        md.append("_No XML/CSV definition found (may be created by Python code or auto-generated)._")
    if refs:
        md += ["", f"**Referenced from ({len(refs)}{'+' if len(refs) >= limit else ''}):**"]
        md += [f"- {_loc(g, r['module'], r['file'], r['line'])} ({r['via']})" for r in refs]
    md.append("\n_JS/Python string usages: odoo_grep with the xmlid._")
    return render({"definitions": [dict(d) for d in defs], "access": [dict(a) for a in access],
                   "references": [dict(r) for r in refs]}, fmt, "\n".join(md))


def views_info(xmlid: str | None, model: str | None, view_type: str | None, fmt: str) -> str:
    con = _con()
    g = q.graph(con)
    if xmlid:
        tree = q.view_tree(con, xmlid)
        lines = [f"## View inheritance for `{xmlid}`", ""]
        if tree["ancestors"]:
            lines.append("Ancestors (up to the primary view): " + " ← ".join(f"`{a}`" for a in tree["ancestors"]))

        def walk(node, depth):
            v = node["view"]
            focus = " ◀" if v["xmlid"] == tree["focus"] else ""
            specs = json.loads(v["specs"] or "[]")
            spec_txt = "; ".join(s["spec"] if isinstance(s, dict) else s for s in specs[:4])
            lines.append(f"{'  ' * depth}- `{v['xmlid']}` [{v['mode']}, prio {v['priority'] or 16}"
                         f"{', groups ' + v['groups'] if v['groups'] else ''}] {v['vtype'] or ''} "
                         f"{('model ' + v['model']) if v['model'] and depth == 0 else ''} — "
                         f"{_loc(g, v['module'], v['file'], v['line'])}{focus}"
                         + (f"\n{'  ' * depth}  ↳ {spec_txt}" if spec_txt else ""))
            for child in node["children"]:
                walk(child, depth + 1)
        walk(tree["root"], 0)
        if tree["truncated"]:
            lines.append("\n_(tree truncated)_")
        callers = q.template_callers(con, xmlid, 30)
        if callers:
            lines += ["", f"**Called with t-call from ({len(callers)}):**"] + \
                     [f"- {_loc(g, c['module'], c['file'], c['line'])}" for c in callers]
        lines.append("\n_Order is static (priority, load order); the exact combined arch needs resolve=\"db\"._")
        return render(tree, fmt, "\n".join(lines))
    if not model:
        raise ToolError("give either `xmlid`, or `model` (optionally with `view_type`)")
    sql = "SELECT * FROM views WHERE model=? AND mode='primary'"
    params: list = [model]
    if view_type:
        sql += " AND vtype=?"
        params.append(view_type)
    rows = con.execute(sql + " ORDER BY vtype, CAST(coalesce(priority, 16) AS INT), xmlid", params).fetchall()
    if not rows:
        if not q.contributions(con, model, None):
            raise did_you_mean("Model", model, q.known_models(con))
        return f"No primary {view_type or ''} view for `{model}` (Odoo generates a default one)."
    table = md_table(["xmlid", "type", "priority", "extensions", "location"], [
        (r["xmlid"], r["vtype"], r["priority"] or 16,
         con.execute("SELECT count(*) FROM views WHERE inherit_id=?", (r["xmlid"],)).fetchone()[0],
         _loc(g, r["module"], r["file"], r["line"])) for r in rows])
    return render([dict(r) for r in rows], fmt, f"## Primary views of `{model}`\n\n{table}\n\n_Use odoo_views(xmlid=…) for the inheritance tree._")


# ---------------------------------------------------------------------------
def access_info(model: str, fmt: str) -> str:
    con = _con()
    g = q.graph(con)
    rows = q.access_rows(con, model)
    if not rows and not q.contributions(con, model, None):
        raise did_you_mean("Model", model, q.known_models(con))
    perms = [r for r in rows if r["group_ref"]]
    restrictions = [r for r in rows if not r["group_ref"]]
    md = [f"## Access for `{model}` (ir.access)", "",
          "Effective domain per operation = OR(permissions of the user's groups) AND AND(restrictions). "
          "No permission row = no access. Source: odoo/orm/models.py `_access_domain`.", ""]
    md.append(f"**Permissions ({len(perms)}):**")
    md.append(md_table(["group", "op", "domain", "active", "module", "location"], [
        (r["group_ref"], r["operation"], _short(r["domain"] or "", 70), "yes" if r["active"] else "no", r["module"],
         _loc(g, r["module"], r["file"], r["line"])) for r in perms]) if perms else "_none — nobody can access this model_")
    md += ["", f"**Restrictions ({len(restrictions)}):**"]
    md.append(md_table(["op", "domain", "active", "module", "location"], [
        (r["operation"], _short(r["domain"] or "", 80), "yes" if r["active"] else "no", r["module"],
         _loc(g, r["module"], r["file"], r["line"])) for r in restrictions]) if restrictions else "_none_")
    try:
        fields = q.merged_fields(con, model, q.scope_modules(con, None))
        guarded = [(n, f["attrs"]["groups"]) for n, f in sorted(fields.items()) if "groups" in f["attrs"]]
    except ToolError:
        guarded = []
    if guarded:
        md += ["", "**Field-level `groups`:** " + ", ".join(f"`{n}` ({_short(gr, 50)})" for n, gr in guarded[:60])]
    return render({"permissions": [dict(r) for r in perms], "restrictions": [dict(r) for r in restrictions],
                   "field_groups": guarded}, fmt, "\n".join(md))


# ---------------------------------------------------------------------------
def js_info(registry: str | None, key: str | None, patches_of: str | None, module_path: str | None,
            template: str | None, js_class: str | None, limit: int, offset: int, fmt: str) -> str:
    con = _con()
    g = q.graph(con)
    if registry is not None:
        if registry == "":
            cats = con.execute("SELECT category, count(*) n FROM js_registry GROUP BY category ORDER BY n DESC").fetchall()
            return render([dict(c) for c in cats], fmt, "## JS registry categories\n\n" +
                          md_table(["category", "entries"], [(c["category"], c["n"]) for c in cats]))
        sql, params = "SELECT * FROM js_registry WHERE category=?", [registry]
        if key:
            sql += " AND key=?"
            params.append(key)
        rows = con.execute(sql + " ORDER BY key", params).fetchall()
        if not rows:
            cats = [r[0] for r in con.execute("SELECT DISTINCT category FROM js_registry")]
            if registry not in cats:
                raise did_you_mean("Registry category", registry, cats)
            raise did_you_mean(f"Key in {registry}", key or "", [r[0] for r in con.execute(
                "SELECT key FROM js_registry WHERE category=?", (registry,))])
        chunk, note = page(rows, limit, offset)
        return render([dict(r) for r in rows], fmt, f"## registry.category(\"{registry}\") — {len(rows)} entries\n\n" +
                      md_table(["key", "value", "module", "location"],
                               [(r["key"], _short(r["value"] or "", 40), r["module"], _loc(g, r["module"], r["file"], r["line"]))
                                for r in chunk]) + note)
    if patches_of:
        rows = con.execute("SELECT * FROM js_patches WHERE target=? OR target=? ORDER BY module",
                           (patches_of, patches_of + ".prototype")).fetchall()
        if not rows:
            targets = [r[0] for r in con.execute("SELECT DISTINCT target FROM js_patches")]
            raise did_you_mean("Patch target", patches_of, targets)
        cls = con.execute("SELECT * FROM js_classes WHERE name=?", (patches_of.removesuffix(".prototype"),)).fetchall()
        md = [f"## patch({patches_of}) — {len(rows)} patches"]
        md += ["Class defined in: " + ", ".join(_loc(g, c["module"], c["file"], c["line"]) for c in cls)] if cls else []
        md += [f"- {r['module']} — {_loc(g, r['module'], r['file'], r['line'])}" for r in rows[:limit]]
        return render([dict(r) for r in rows], fmt, "\n".join(md))
    if module_path:
        row = con.execute("SELECT * FROM js_modules WHERE path=? OR alias=?", (module_path, module_path)).fetchone()
        if row is None:
            raise did_you_mean("JS module", module_path, [r[0] for r in con.execute("SELECT path FROM js_modules WHERE path IS NOT NULL")])
        importers = con.execute("SELECT module, file, line FROM js_imports WHERE source=? LIMIT ?", (module_path, limit)).fetchall()
        md = [f"## `{module_path}`", f"File: {_loc(g, row['module'], row['file'])}",
              "Exports: " + ", ".join(f"`{e}`" for e in json.loads(row["exports"] or "[]")),
              "", f"Imported by ({len(importers)}{'+' if len(importers) >= limit else ''}):"]
        md += [f"- {_loc(g, i['module'], i['file'], i['line'])}" for i in importers]
        return render({"module": dict(row), "importers": [dict(i) for i in importers]}, fmt, "\n".join(md))
    if template:
        defs = con.execute("SELECT * FROM templates WHERE name=? OR inherit=? ORDER BY module", (template, template)).fetchall()
        comps = con.execute("SELECT * FROM js_classes WHERE template=?", (template,)).fetchall()
        if not defs:
            raise did_you_mean("OWL template", template, [r[0] for r in con.execute("SELECT name FROM templates")])
        md = [f"## OWL template `{template}`"]
        for d in defs:
            role = "definition" if d["name"] == template and not d["inherit"] else \
                f"t-inherit ({d['mode'] or 'extension'}) as `{d['name']}`" if d["inherit"] == template else f"inherits {d['inherit']}"
            md.append(f"- {role} — {d['module']} — {_loc(g, d['module'], d['file'], d['line'])}")
        md += [f"- used by component `{c['name']}` — {_loc(g, c['module'], c['file'], c['line'])}" for c in comps]
        return render([dict(d) for d in defs], fmt, "\n".join(md))
    if js_class:
        rows = con.execute("SELECT * FROM js_classes WHERE name=?", (js_class,)).fetchall()
        if not rows:
            raise did_you_mean("JS class", js_class, [r[0] for r in con.execute("SELECT DISTINCT name FROM js_classes")])
        subs = con.execute("SELECT * FROM js_classes WHERE extends=? LIMIT ?", (js_class, limit)).fetchall()
        patches = con.execute("SELECT * FROM js_patches WHERE target IN (?, ?)", (js_class, js_class + ".prototype")).fetchall()
        md = [f"## JS class `{js_class}`"] + [
            f"- defined in {_loc(g, r['module'], r['file'], r['line'])} extends `{r['extends']}` template `{r['template']}`" for r in rows]
        md += ["", f"Subclasses ({len(subs)}): " + ", ".join(f"`{s['name']}` ({s['module']})" for s in subs)]
        md += [f"Patched in ({len(patches)}): " + ", ".join(f"{p['module']}" for p in patches)]
        return render({"class": [dict(r) for r in rows], "subclasses": [dict(s) for s in subs]}, fmt, "\n".join(md))
    raise ToolError("give one of: registry (\"\" lists categories), patches_of, module_path, template, js_class")


def assets_info(bundle: str, scope_module: str | None, limit: int, offset: int, fmt: str) -> str:
    con = _con()
    scope = q.scope_modules(con, scope_module, include_tests=True) if scope_module else None
    rows = q.asset_entries(con, bundle, scope)
    if not rows:
        bundles = [r[0] for r in con.execute("SELECT DISTINCT bundle FROM assets")]
        raise did_you_mean("Asset bundle", bundle, bundles)
    chunk, note = page(rows, limit, offset)
    includes = sorted({r["path"] for r in rows if r["directive"] == "include"})
    md = [f"## Bundle `{bundle}` — {len(rows)} directives from {len({r['module'] for r in rows})} modules (module load order)",
          f"_{'scope: install closure of ' + scope_module if scope_module else 'all indexed modules (an actual DB only has installed ones)'}_", "",
          md_table(["#", "module", "directive", "target", "path/glob"],
                   [(i + offset, r["module"], r["directive"], r["target"] or "", r["path"]) for i, r in enumerate(chunk)]) + note]
    if includes:
        md += ["", "Included bundles: " + ", ".join(f"`{i}`" for i in includes)]
    md.append("\n_Directive semantics: odoo/addons/base/models/ir_asset.py. Real file list: resolve=\"db\" (runtime)._")
    return render(rows, fmt, "\n".join(md))


def suggest_models(con, name: str) -> list[str]:
    return suggest(name, q.known_models(con))
