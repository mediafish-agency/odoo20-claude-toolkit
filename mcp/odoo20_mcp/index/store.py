"""SQLite index: schema, incremental (per-module) builds in a background thread."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from ..config import ROOT_HELP, Config
from .extract import TABLE_KEYS, extract_module
from .scanner import find_modules, list_files

SCHEMA_VERSION = "11"

SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE modules(name TEXT PRIMARY KEY, path TEXT, root TEXT, signature TEXT, manifest TEXT, depends TEXT,
    auto_install TEXT, installable INT, application INT, license TEXT, version TEXT, summary TEXT, category TEXT,
    n_files INT, error TEXT);
CREATE TABLE files(module TEXT, rel TEXT, kind TEXT, size INT);
CREATE TABLE models(module TEXT, model TEXT, kind TEXT, parents TEXT, inherits TEXT, model_type TEXT, attrs TEXT,
    file TEXT, line INT, class_name TEXT);
CREATE TABLE fields(module TEXT, model TEXT, name TEXT, ftype TEXT, comodel TEXT, attrs TEXT, file TEXT, line INT,
    class_kind TEXT);
CREATE TABLE methods(module TEXT, model TEXT, name TEXT, decorators TEXT, signature TEXT, calls_super INT,
    file TEXT, line INT, end_line INT);
CREATE TABLE constraints(module TEXT, model TEXT, name TEXT, ctype TEXT, definition TEXT, file TEXT, line INT);
CREATE TABLE records(module TEXT, xmlid TEXT, model TEXT, tag TEXT, fields TEXT, noupdate INT, file TEXT, line INT);
CREATE TABLE views(module TEXT, xmlid TEXT, kind TEXT, model TEXT, vtype TEXT, inherit_id TEXT, mode TEXT,
    priority TEXT, name TEXT, arch_fields TEXT, specs TEXT, buttons TEXT, groups TEXT, file TEXT, line INT);
CREATE TABLE refs(module TEXT, ref TEXT, via TEXT, lang TEXT, file TEXT, line INT);
CREATE TABLE access(module TEXT, xmlid TEXT, name TEXT, model TEXT, model_ref TEXT, group_ref TEXT, operation TEXT,
    domain TEXT, active INT, source TEXT, file TEXT, line INT);
CREATE TABLE templates(module TEXT, name TEXT, inherit TEXT, mode TEXT, file TEXT, line INT);
CREATE TABLE js_modules(module TEXT, path TEXT, alias TEXT, file TEXT, exports TEXT);
CREATE TABLE js_imports(module TEXT, file TEXT, line INT, source TEXT, names TEXT);
CREATE TABLE js_registry(module TEXT, category TEXT, key TEXT, value TEXT, file TEXT, line INT);
CREATE TABLE js_patches(module TEXT, target TEXT, file TEXT, line INT);
CREATE TABLE js_classes(module TEXT, name TEXT, extends TEXT, template TEXT, file TEXT, line INT);
CREATE TABLE assets(module TEXT, bundle TEXT, seq INT, directive TEXT, target TEXT, path TEXT);
CREATE TABLE errors(module TEXT, file TEXT, line INT, message TEXT);
"""

INDEXES = """
CREATE INDEX i_files ON files(module);
CREATE INDEX i_models ON models(model);
CREATE INDEX i_models_mod ON models(module);
CREATE INDEX i_fields ON fields(model, name);
CREATE INDEX i_methods ON methods(model, name);
CREATE INDEX i_records ON records(xmlid);
CREATE INDEX i_records_model ON records(model);
CREATE INDEX i_views ON views(xmlid);
CREATE INDEX i_views_inh ON views(inherit_id);
CREATE INDEX i_views_model ON views(model);
CREATE INDEX i_refs ON refs(ref);
CREATE INDEX i_access ON access(model);
CREATE INDEX i_templates ON templates(name);
CREATE INDEX i_jsmod ON js_modules(path);
CREATE INDEX i_jsreg ON js_registry(category, key);
CREATE INDEX i_jspatch ON js_patches(target);
CREATE INDEX i_assets ON assets(bundle);
CREATE VIRTUAL TABLE symbols USING fts5(name, kind UNINDEXED, module UNINDEXED, loc UNINDEXED, detail UNINDEXED, tokenize='trigram');
"""

SYMBOLS_FILL = """
INSERT INTO symbols SELECT name, 'module', name, path, summary FROM modules;
INSERT INTO symbols SELECT DISTINCT model, 'model', module, file || ':' || line, kind FROM models;
INSERT INTO symbols SELECT model || '.' || name, 'field', module, file || ':' || line, ftype FROM fields;
INSERT INTO symbols SELECT model || '.' || name || '()', 'method', module, file || ':' || line, signature FROM methods;
INSERT INTO symbols SELECT xmlid, 'xmlid', module, file || ':' || line, model FROM records WHERE xmlid IS NOT NULL AND tag != 'csv';
INSERT INTO symbols SELECT name, 'owl_template', module, file || ':' || line, inherit FROM templates;
INSERT INTO symbols SELECT category || ':' || key, 'js_registry', module, file || ':' || line, value FROM js_registry;
INSERT INTO symbols SELECT path, 'js_module', module, file, exports FROM js_modules WHERE path IS NOT NULL;
INSERT INTO symbols SELECT name, 'js_class', module, file || ':' || line, extends FROM js_classes;
INSERT INTO symbols SELECT DISTINCT bundle, 'asset_bundle', module, '__manifest__.py', NULL FROM assets;
"""


def connect(path: Path, readonly: bool = True) -> sqlite3.Connection:
    if readonly:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False, timeout=30)
    else:
        con = sqlite3.connect(path, check_same_thread=False, timeout=30)
    con.row_factory = sqlite3.Row
    return con


class IndexManager:
    """Owns the index file; builds/refreshes it in a background thread."""

    def __init__(self, config: Config):
        self.config = config
        self.path = config.index_path
        self.lock = threading.Lock()
        self.build_lock = threading.Lock()
        self.thread: threading.Thread | None = None
        self.progress = {"state": "idle", "done": 0, "total": 0, "message": "", "last_build": None}
        self.duplicates: list[str] = []

    # -- status ------------------------------------------------------------
    @property
    def ready(self) -> bool:
        return self.path.exists() and self._meta("schema_version") == SCHEMA_VERSION

    def _meta(self, key: str) -> str | None:
        try:
            con = connect(self.path)
            row = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
            con.close()
            return row[0] if row else None
        except sqlite3.Error:
            return None

    def status(self) -> dict:
        info = dict(self.progress)
        info["ready"] = self.ready
        info["path"] = str(self.path)
        if info["ready"]:
            info["built_at"] = self._meta("built_at")
            info["stats"] = json.loads(self._meta("stats") or "{}")
        if self.duplicates:
            info["shadowed_modules"] = self.duplicates[:20]
        return info

    def db(self) -> sqlite3.Connection:
        if not self.config.has_odoo_root and not self.ready:
            raise RuntimeError(ROOT_HELP)
        if not self.ready:
            self.ensure_started()
            p = self.progress
            raise RuntimeError(
                f"The Odoo source index is being built ({p['done']}/{p['total']} modules, state={p['state']}). "
                "Retry in a few seconds, or call odoo_status to watch progress."
            )
        return connect(self.path)

    # -- building ----------------------------------------------------------
    def ensure_started(self, force: bool = False) -> None:
        with self.lock:
            if self.thread and self.thread.is_alive():
                return
            self.thread = threading.Thread(target=self._run, args=(force,), daemon=True, name="odoo20-index")
            self.thread.start()

    def wait(self, timeout: float | None = None) -> None:
        if self.thread:
            self.thread.join(timeout)

    def _run(self, force: bool) -> None:
        try:
            self.progress.update(state="scanning", done=0, total=0, message="")
            self.build(force=force)
            self.progress.update(state="idle", last_build=time.strftime("%Y-%m-%d %H:%M:%S"))
        except Exception as exc:  # noqa: BLE001
            self.progress.update(state="error", message=f"{type(exc).__name__}: {exc}")

    def build(self, force: bool = False) -> dict:
        with self.build_lock:
            return self._build(force)

    def _build(self, force: bool = False) -> dict:
        if not self.config.has_odoo_root:
            raise RuntimeError(ROOT_HELP)
        t0 = time.time()
        modules, self.duplicates = find_modules(self.config.addons_paths)
        for entry in modules.values():
            list_files(entry)
        old = {}
        if not force and self.ready:
            con = connect(self.path)
            old = {r["name"]: r["signature"] for r in con.execute("SELECT name, signature FROM modules")}
            con.close()
        changed = [m for m in modules.values() if old.get(m.name) != m.signature]
        removed = set(old) - set(modules)
        if not changed and not removed and old:
            self.progress.update(message="index up to date")
            return {"changed": 0}

        self.progress.update(state="indexing", total=len(changed), done=0)
        tmp = self.path.with_suffix(".building")
        if tmp.exists():
            tmp.unlink()
        con = connect(tmp, readonly=False)
        con.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;" + SCHEMA)
        unchanged = [name for name in modules if name in old and old[name] == modules[name].signature]
        if unchanged:
            con.execute("ATTACH DATABASE ? AS old", (str(self.path),))
            con.execute("CREATE TEMP TABLE keep(name TEXT PRIMARY KEY)")
            con.executemany("INSERT INTO keep VALUES (?)", [(n,) for n in unchanged])
            con.execute("INSERT INTO modules SELECT * FROM old.modules WHERE name IN (SELECT name FROM keep)")
            for table in TABLE_KEYS:
                con.execute(f"INSERT INTO {table} SELECT * FROM old.{table} WHERE module IN (SELECT name FROM keep)")
            con.commit()
            con.execute("DETACH DATABASE old")

        workers = max(1, min(os.cpu_count() or 2, 12) - 1)
        args = [(m.name, str(m.path), str(m.root), m.signature, m.files) for m in changed]
        if len(args) <= 3:
            results = (extract_module(*a) for a in args)
            self._store(con, results)
        else:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(extract_module, *a) for a in args]
                self._store(con, (f.result() for f in as_completed(futures)))

        con.executescript(INDEXES + SYMBOLS_FILL)
        stats = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("modules", *TABLE_KEYS)}
        con.executemany("INSERT INTO meta VALUES (?, ?)", [
            ("schema_version", SCHEMA_VERSION),
            ("built_at", time.strftime("%Y-%m-%d %H:%M:%S")),
            ("roots", json.dumps([str(p) for p in self.config.addons_paths])),
            ("stats", json.dumps(stats)),
            ("duration_s", f"{time.time() - t0:.1f}"),
        ])
        con.commit()
        con.close()
        os.replace(tmp, self.path)
        self.progress.update(message=f"indexed {len(changed)} changed modules in {time.time() - t0:.1f}s")
        return {"changed": len(changed), "removed": len(removed), "seconds": round(time.time() - t0, 1)}

    def _store(self, con: sqlite3.Connection, results) -> None:
        for res in results:
            con.execute(f"INSERT INTO modules VALUES ({','.join('?' * 15)})", res["module"])
            for table, rows in res["rows"].items():
                if rows:
                    con.executemany(f"INSERT INTO {table} VALUES ({','.join('?' * len(rows[0]))})", rows)
            self.progress["done"] += 1
        con.commit()
