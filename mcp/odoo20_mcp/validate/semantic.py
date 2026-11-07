"""Index-backed checks for one module: manifest, views, access, references, imports, models."""
from __future__ import annotations

import ast
import glob
import json
import re
import sqlite3
from functools import cache
from pathlib import Path

from ..query import core as q
from ..util import suggest
from .engine import Finding

VALID_OPERATIONS = {"crud", "cru", "crd", "cud", "rud", "cr", "cu", "cd", "ru", "rd", "ud", "c", "r", "u", "d"}
EXTERNAL_GROUPS = {"base.group_portal", "base.group_public", "base.group_everyone"}
JS_EXTERNAL = re.compile(r"^@odoo/(?:owl|hoot(?:-dom|-mock)?|o-spreadsheet)$")
IMPLICIT_XMLID = re.compile(r"\.(?:model_|field_|module_|module_category_|selection__)|_product_template$")
DATA_DIRS = ("views/", "data/", "security/", "report/", "reports/", "wizard/", "wizards/", "demo/")
REF_VIAS = ("xml.ref", "xml.inherit_id", "xml.%d", "xml.eval", "xml.parent", "xml.action", "xml.groups",
            "xml.t-call", "csv.group_id")


@cache
def basemodel_methods(odoo_root: str) -> frozenset[str]:
    """Public and private method names of BaseModel (odoo/orm/models.py)."""
    path = Path(odoo_root) / "odoo" / "orm" / "models.py"
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return frozenset()
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name in {"BaseModel", "Model", "AbstractModel", "TransientModel"}:
            names |= {n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return frozenset(names)


class ModuleChecker:
    def __init__(self, con: sqlite3.Connection, odoo_root: Path, module: str):
        self.con = con
        self.root = odoo_root
        self.g = q.graph(con)
        self.module = module
        row = con.execute("SELECT * FROM modules WHERE name=?", (module,)).fetchone()
        self.row = row
        self.path = Path(row["path"]) if row else None
        self.scope = self.g.install_closure(module) if row else set()
        self.findings: list[Finding] = []
        self._fields_cache: dict[str, dict] = {}

    # -- helpers -------------------------------------------------------------
    def add(self, rule: str, severity: str, rel: str, line: int, message: str, fix: str = "") -> None:
        file = q.display_path(self.g, self.module, rel, self.root) if rel else str(self.path)
        self.findings.append(Finding(rule, severity, file, line, message, fix))

    def model_scope_state(self, model: str, exclude_self: bool = False) -> tuple[bool, list[str]]:
        """(defined in dependency closure?, modules defining it anywhere)."""
        rows = self.con.execute("SELECT module FROM models WHERE model=?", (model,)).fetchall()
        mods = sorted({r["module"] for r in rows if not (exclude_self and r["module"] == self.module)})
        return any(m in self.scope for m in mods), mods

    def fields_of(self, model: str) -> dict:
        if model not in self._fields_cache:
            self._fields_cache[model] = q.merged_fields(self.con, model, self.scope)
        return self._fields_cache[model]

    def missing_dep_hint(self, modules: list[str]) -> str:
        defining = [m for m in modules if not m.startswith("test_")][:3] or modules[:3]
        return f"add one of {defining} to `depends` in __manifest__.py" if defining else ""

    # -- checks --------------------------------------------------------------
    def run(self) -> list[Finding]:
        if self.row is None:
            return [Finding("IDX001", "error", self.module, 0,
                            f"Module {self.module!r} is not in the index. Add its parent folder to the plugin "
                            "option extra_addons_paths, then retry.")]
        self.check_manifest()
        self.check_python_models()
        self.check_views()
        self.check_access()
        self.check_refs()
        self.check_js_imports()
        for err in self.con.execute("SELECT * FROM errors WHERE module=?", (self.module,)):
            self.add("PARSE", "error", err["file"], err["line"], err["message"])
        return self.findings

    def check_manifest(self) -> None:
        manifest = json.loads(self.row["manifest"] or "{}")
        if manifest.get("__error__"):
            self.add("MAN100", "error", "__manifest__.py", 1, f"manifest cannot be parsed: {manifest['__error__']}")
            return
        for dep in manifest.get("depends") or []:
            if dep not in self.g.deps:
                hints = suggest(dep, self.g.deps)
                self.add("MAN101", "error", "__manifest__.py", 1, f"depends on unknown module {dep!r}",
                         f"did you mean {hints}?" if hints else "check the addons paths")
        listed: set[str] = set()
        data = manifest.get("data") or []
        for key in ("data", "demo"):
            for entry in manifest.get(key) or []:
                listed.add(entry)
                if not (self.path / entry).is_file():
                    self.add("MAN102", "error", "__manifest__.py", 1, f"{key} file not found: {entry}")
        listed |= set(manifest.get("other_files") or [])
        access = [d for d in data if d.endswith("ir.access.csv")]
        if access and data[-1] != access[-1]:
            self.add("MAN103", "info", "__manifest__.py", 1, "security/ir.access.csv is usually listed last in `data`",
                     "groups and models must exist before the rows referencing them are loaded")
        if not manifest.get("license"):
            self.add("MAN104", "warning", "__manifest__.py", 1, "no `license` key (defaults to LGPL-3 with a warning)")
        version = str(manifest.get("version") or "")
        if re.match(r"^\d+\.\d+\.\d+\.\d+", version) and not version.startswith("20.0."):
            self.add("MAN105", "error", "__manifest__.py", 1,
                     f"version {version!r} is for another Odoo major version: Odoo 20 marks the module "
                     "installable=False (odoo/modules/module.py)", "use '20.0.x.y.z' or a short 'x.y' version")
        if not manifest.get("author"):
            self.add("MAN108", "info", "__manifest__.py", 1, "no `author` key (Odoo logs a warning)")
        for rel, _kind, _size in self.con.execute(
                "SELECT rel, kind, size FROM files WHERE module=? AND kind IN ('xml','csv')", (self.module,)):
            if rel.startswith(DATA_DIRS) and not rel.startswith("data/template/") and rel not in listed:
                self.add("MAN106", "warning", rel, 1, "data file is not listed in the manifest (it is never loaded)",
                         "add it to `data` (or `demo`)")
        for a in self.con.execute("SELECT * FROM assets WHERE module=?", (self.module,)):
            if a["directive"] == "include":
                if not self.con.execute("SELECT 1 FROM assets WHERE bundle=? LIMIT 1", (a["path"],)).fetchone():
                    self.add("MAN107", "warning", "__manifest__.py", 1,
                             f"assets[{a['bundle']!r}] includes unknown bundle {a['path']!r}")
                continue
            if a["directive"] == "remove":
                continue
            target = a["path"] or ""
            if target.startswith(("http://", "https://", "/")):
                continue
            owner, _, rest = target.partition("/")
            base = self.g.paths.get(owner)
            if base and rest and not glob.glob(str(Path(base) / rest), recursive=True):
                self.add("MAN107", "warning", "__manifest__.py", 1,
                         f"assets[{a['bundle']!r}] pattern matches no file: {target}")
        # python packages imported?
        for pkg in ("models", "controllers", "wizard", "wizards", "report"):
            pkg_dir = self.path / pkg
            if not (pkg_dir / "__init__.py").is_file():
                continue
            init = (pkg_dir / "__init__.py").read_text(encoding="utf-8", errors="replace")
            for py in sorted(pkg_dir.glob("*.py")):
                if py.name != "__init__.py" and not re.search(rf"\b{re.escape(py.stem)}\b", init):
                    self.add("PYI001", "warning", f"{pkg}/__init__.py", 1,
                             f"{pkg}/{py.name} is never imported (its classes are not registered)",
                             f"add `from . import {py.stem}`")
            root_init = (self.path / "__init__.py")
            if root_init.is_file() and not re.search(rf"\b{pkg}\b", root_init.read_text(errors="replace")):
                self.add("PYI001", "warning", "__init__.py", 1, f"package {pkg}/ is never imported",
                         f"add `from . import {pkg}`")

    def check_python_models(self) -> None:
        for m in self.con.execute("SELECT * FROM models WHERE module=?", (self.module,)):
            targets = json.loads(m["parents"] or "[]")
            if m["kind"] == "extend":
                targets = [m["model"], *targets]
            for target in targets:
                ok, mods = self.model_scope_state(target, exclude_self=(target == m["model"]))
                own = self.con.execute(
                    "SELECT 1 FROM models WHERE model=? AND module=? AND kind='define'", (target, self.module)).fetchone()
                if ok or own:
                    continue
                if mods:
                    self.add("PYM001", "error", m["file"], m["line"],
                             f"{m['class_name']} inherits {target!r}, defined only outside the dependencies ({mods[:3]})",
                             self.missing_dep_hint(mods))
                else:
                    self.add("PYM001", "error", m["file"], m["line"], f"{m['class_name']} inherits unknown model {target!r}")
        for f in self.con.execute("SELECT * FROM fields WHERE module=? AND comodel IS NOT NULL", (self.module,)):
            ok, mods = self.model_scope_state(f["comodel"])
            if ok:
                continue
            if mods:
                self.add("PYM002", "error", f["file"], f["line"],
                         f"field {f['model']}.{f['name']} points to {f['comodel']!r}, defined outside the dependencies",
                         self.missing_dep_hint(mods))
            else:
                self.add("PYM002", "error", f["file"], f["line"],
                         f"field {f['model']}.{f['name']} points to unknown model {f['comodel']!r}")

    def _view_model(self, view) -> str | None:
        seen = set()
        cur = view
        while cur is not None and cur["xmlid"] not in seen:
            seen.add(cur["xmlid"])
            if cur["model"]:
                return cur["model"]
            if not cur["inherit_id"]:
                return None
            cur = self.con.execute("SELECT * FROM views WHERE xmlid=?", (cur["inherit_id"],)).fetchone()
        return None

    def check_views(self) -> None:
        base_methods = basemodel_methods(str(self.root))
        for v in self.con.execute("SELECT * FROM views WHERE module=? AND kind='view'", (self.module,)):
            model = self._view_model(v)
            if not model:
                continue
            ok, mods = self.model_scope_state(model)
            if not ok:
                self.add("VIEW001", "error", v["file"], v["line"],
                         f"view {v['xmlid']} is on model {model!r}, not defined in the dependencies",
                         self.missing_dep_hint(mods) if mods else "check the model name")
                continue
            fields = self.fields_of(model)
            specs = json.loads(v["specs"] or "[]")
            if specs and isinstance(specs[0], dict):
                # inheriting view: only check specs anchored on this model (others edit an x2many sub-view)
                groups = [(s["fields"], s["buttons"]) for s in specs
                          if not s.get("subview") and (s.get("anchor") is None or s["anchor"] in fields)]
            else:
                groups = [(json.loads(v["arch_fields"] or "[]"), json.loads(v["buttons"] or "[]"))]
            for names, buttons in groups:
                for name in names:
                    if name not in fields:
                        hints = suggest(name, fields)
                        self.add("VIEW002", "error", v["file"], v["line"],
                                 f"view {v['xmlid']}: field {name!r} does not exist on {model!r} (in this module's dependencies)",
                                 f"did you mean {hints}?" if hints else "add the field or the missing dependency")
                for meth in buttons:
                    if meth.startswith("_"):
                        self.add("VIEW003", "error", v["file"], v["line"],
                                 f"view {v['xmlid']}: button type=object calls private method {meth!r} (not callable from the UI)")
                        continue
                    if meth in base_methods:
                        continue
                    if not q.method_chain(self.con, model, meth, self.scope):
                        self.add("VIEW004", "error", v["file"], v["line"],
                                 f"view {v['xmlid']}: button method {meth!r} not found on {model!r}")

    def check_access(self) -> None:
        defined = {
            r["model"]: r for r in self.con.execute(
                "SELECT * FROM models WHERE module=? AND kind='define'", (self.module,))
        }
        covered: set[str] = set()
        for a in self.con.execute("SELECT * FROM access WHERE module=?", (self.module,)):
            rel, line = a["file"], a["line"]
            op = (a["operation"] or "").strip()
            overrides_other = a["xmlid"] and a["xmlid"].split(".", 1)[0] != self.module
            if not op and overrides_other:
                pass  # updating another module's row (e.g. active=False): operation unchanged
            elif op not in VALID_OPERATIONS:
                self.add("SEC101", "error", rel, line, f"ir.access {a['xmlid']}: invalid operation {op!r}",
                         "use an ordered c-r-u-d subset: crud, cru, crd, cud, rud, cr, cu, cd, ru, rd, ud, c, r, u, d")
            model = a["model"]
            if not model and a["model_ref"]:
                ref = a["model_ref"].split(".", 1)[-1]
                model = ref[len("model_"):].replace("_", ".") if ref.startswith("model_") else None
            if a["model"] and a["model"].startswith("model_"):
                self.add("SEC102", "error", rel, line,
                         f"ir.access {a['xmlid']}: model_id must be the technical model name (e.g. sale.order), "
                         f"not an ir.model xmlid ({a['model']})")
            elif a["model"]:
                ok, mods = self.model_scope_state(a["model"])
                if not ok:
                    self.add("SEC102", "error", rel, line, f"ir.access {a['xmlid']}: model {a['model']!r} is not "
                             "defined in the dependencies", self.missing_dep_hint(mods) if mods else "")
            if model and a["group_ref"]:
                covered.add(model)
            if a["group_ref"]:
                self._check_xmlid(a["group_ref"], rel, line, f"ir.access {a['xmlid']} group")
                if a["group_ref"] in EXTERNAL_GROUPS and set(op) & set("cud"):
                    self.add("SEC105", "warning", rel, line,
                             f"ir.access {a['xmlid']} grants {op!r} to {a['group_ref']} (portal/public/everyone)",
                             "grant the minimum; see odoo-security 'Access control'")
            if a["domain"]:
                try:
                    ast.parse(a["domain"], mode="eval")
                except SyntaxError as exc:
                    self.add("SEC104", "error", rel, line, f"ir.access {a['xmlid']}: domain is not valid Python ({exc.msg})")
        for model, row in defined.items():
            if row["model_type"] == "AbstractModel" or model in covered:
                continue
            attrs = json.loads(row["attrs"] or "{}")
            if attrs.get("_auto") is False and row["model_type"] != "Model":
                continue
            has_any = self.con.execute(
                "SELECT 1 FROM access WHERE (model=? OR model_ref LIKE ?) AND group_ref IS NOT NULL LIMIT 1",
                (model, "%.model_" + model.replace(".", "_"))).fetchone()
            if not has_any:
                self.add("SEC106", "warning", row["file"], row["line"],
                         f"model {model!r} has no ir.access permission row: nobody can access it (default deny)",
                         "add a row to security/ir.access.csv, e.g. "
                         f"access_{model.replace('.', '_')}_user,{model} user,{model},base.group_user,crud,")

    def _check_xmlid(self, xmlid: str, rel: str, line: int, what: str) -> None:
        if not xmlid or "." not in xmlid:
            return
        owner = xmlid.split(".", 1)[0]
        if owner not in self.g.deps:
            self.add("REF002", "error", rel, line, f"{what}: {xmlid!r} belongs to unknown module {owner!r}")
            return
        if owner not in self.scope:
            self.add("REF001", "error", rel, line,
                     f"{what}: {xmlid!r} comes from module {owner!r}, which is not a dependency",
                     f"add {owner!r} to `depends`")
            return
        if IMPLICIT_XMLID.search(xmlid):
            return
        found = self.con.execute("SELECT 1 FROM records WHERE xmlid=? LIMIT 1", (xmlid,)).fetchone() or \
            self.con.execute("SELECT 1 FROM access WHERE xmlid=? LIMIT 1", (xmlid,)).fetchone()
        if not found:
            self.add("REF003", "info", rel, line, f"{what}: xmlid {xmlid!r} not found in {owner!r}",
                     "check spelling (records created in Python or by other means cannot be verified statically)")

    def check_refs(self) -> None:
        placeholders = ",".join("?" * len(REF_VIAS))
        seen: set[tuple] = set()
        for r in self.con.execute(
                f"SELECT * FROM refs WHERE module=? AND via IN ({placeholders})", (self.module, *REF_VIAS)):
            key = (r["ref"], r["file"], r["line"])
            if key in seen or r["file"].startswith(("migrations/", "upgrades/", "tests/", "populate/")):
                continue
            seen.add(key)
            self._check_xmlid(r["ref"], r["file"], r["line"], r["via"].split(".", 1)[1])

    def _check_import_names(self, imp, key: str, exports: dict) -> None:
        available = exports.get(key)
        if not available or "*" in available:
            return  # unknown export list (vendored lib, `export *`): cannot judge
        for name in _imported_names(imp["names"] or ""):
            if name not in available:
                hints = suggest(name, available)
                self.add("JSI003", "error", imp["file"], imp["line"],
                         f"{name!r} is not exported by {imp['source']!r}",
                         f"exports include {hints}" if hints else f"check the export list (odoo_js module_path={imp['source']!r})")

    def check_js_imports(self) -> None:
        known = {r["path"]: r["module"] for r in self.con.execute("SELECT path, module FROM js_modules WHERE path IS NOT NULL")}
        known.update({r["alias"]: r["module"] for r in self.con.execute("SELECT alias, module FROM js_modules WHERE alias IS NOT NULL")})
        exports = {}
        for r in self.con.execute("SELECT path, alias, file, exports FROM js_modules"):
            names = set(json.loads(r["exports"] or "[]"))
            for key in (r["path"], r["alias"]):
                if key:
                    exports[key] = names
        for imp in self.con.execute("SELECT * FROM js_imports WHERE module=?", (self.module,)):
            src = imp["source"]
            if not src.startswith("@") or JS_EXTERNAL.match(src):
                continue
            norm = re.sub(r"/index(?:\.js)?/?$", "", src.removesuffix(".js"))  # js_transpiler.remove_index
            owner = known.get(src) or known.get(norm)
            if owner is None:
                hints = suggest(src, known)
                self.add("JSI001", "error", imp["file"], imp["line"], f"import {src!r} does not resolve to any module file",
                         f"did you mean {hints[:3]}?" if hints else "check the path (@addon/path relative to static/src)")
            else:
                self._check_import_names(imp, src if src in exports else norm, exports)
            if owner is not None and owner not in self.scope and not imp["file"].startswith("static/tests/"):
                self.add("JSI002", "warning", imp["file"], imp["line"],
                         f"import {src!r} comes from module {owner!r}, which is not a dependency",
                         f"add {owner!r} to `depends`")


def _imported_names(spec: str) -> list[str]:
    """Names an import statement pulls from the target: `a`, `{ b, c as d }`, `* as ns` (none)."""
    spec = spec.strip()
    if not spec or spec.startswith("* as") or spec.startswith("*"):
        return []
    names = []
    brace = re.search(r"\{([^}]*)\}", spec)
    default = spec.split("{", 1)[0].split(",", 1)[0].strip()
    if default and not default.startswith("*"):
        names.append("default")
    if brace:
        for part in brace.group(1).split(","):
            part = part.strip()
            if part:
                names.append(part.split(" as ")[0].strip())
    return [n for n in names if n]


def check_module(con: sqlite3.Connection, odoo_root: Path, module: str) -> list[Finding]:
    return ModuleChecker(con, odoo_root, module).run()
