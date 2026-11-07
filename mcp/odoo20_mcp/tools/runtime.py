"""Runtime tools: upgrade_code sandbox, scaffold, databases, tests, jobs, dev server, shell, JSON-2."""
from __future__ import annotations

import difflib
import json
import shlex
import shutil
import tempfile
import time
import urllib.error
import urllib.request
from functools import cache
from pathlib import Path

from .. import context as ctx
from ..index.scanner import MANIFEST
from ..runtime.jobs import Job, JobManager
from ..runtime.odoo import OdooRuntime
from ..util import ToolError, did_you_mean, render, truncate

READ_METHODS = {"search_read", "search", "search_count", "read", "fields_get", "read_group", "formatted_read_group",
                "web_read_group", "web_search_read", "web_read", "get_views", "name_search", "default_get",
                "has_access", "check_access", "context_get", "get_record_default_action", "onchange"}


@cache
def runtime() -> OdooRuntime:
    return OdooRuntime(ctx.config())


@cache
def jobs() -> JobManager:
    return JobManager(ctx.config().jobs_dir)


def _module_dirs(path: Path) -> list[Path]:
    if (path / MANIFEST).is_file():
        return [path]
    mods = sorted(d for d in path.iterdir() if (d / MANIFEST).is_file()) if path.is_dir() else []
    if not mods:
        raise ToolError(f"{path} is neither an Odoo module nor a folder of modules")
    return mods


def _job_text(job: Job, wait_note: bool = False) -> str:
    s = job.summary or {}
    lines = [f"## Job `{job.id}` — {job.title}",
             f"- status: **{job.status}** · elapsed {job.elapsed()}s · exit {job.returncode}" + (f" · db `{job.db}`" if job.db else ""),
             f"- log: `{job.log_path}`"]
    if job.kind == "server" and job.status == "running":
        lines.append(f"- {job.note}")
    if s:
        if s.get("tests") or s.get("failed") or s.get("errors"):
            lines.append(f"- tests: {s.get('tests', 0)} run, {s.get('failed', 0)} failed, {s.get('errors', 0)} error(s)")
        if s.get("skipped"):
            lines.append(f"- **{len(s['skipped'])} test(s) SKIPPED** (not a pass):")
            lines += [f"  - {name}: {why}" for name, why in s["skipped"][:10]]
        for block in s.get("error_blocks", [])[:6]:
            lines += ["", "```", truncate(block, 3000), "```"]
    if job.note and job.kind != "server":
        lines.append(f"- note: {job.note.strip()}")
    if wait_note and job.status == "running":
        lines.append(f"\nStill running — poll with odoo_job(job_id=\"{job.id}\").")
    return "\n".join(lines)


def _wait(job: Job, seconds: int) -> None:
    deadline = time.time() + max(0, seconds)
    while job.status == "running" and time.time() < deadline:
        time.sleep(1)


# ---------------------------------------------------------------------------
# upgrade_code (sandboxed)
# ---------------------------------------------------------------------------

def upgrade_code(path_str: str, from_version: str, include_owl3: bool, script: str | None, apply: bool,
                 max_diff_lines: int) -> str:
    cfg = ctx.config()
    path = Path(path_str).expanduser().resolve()
    if not path.exists():
        raise ToolError(f"path not found: {path}")
    if cfg.is_core_path(path):
        raise ToolError("refusing to run on the Odoo source tree itself; point to your own addon(s)")
    modules = _module_dirs(path)
    steps: list[dict] = [{"script": script}] if script else [{"from_version": from_version}]
    has_static = any((m / "static").is_dir() for m in modules)
    if include_owl3 and not script and has_static:
        steps.append({"script": "owl3-migration"})
    warnings = []
    for m in modules:
        if (m / "security" / "ir.access.csv").exists() and not script:
            warnings.append(f"{m.name} already has security/ir.access.csv: the 19.4-00-ir-access script is not "
                            "idempotent; review its diff carefully")
    with tempfile.TemporaryDirectory(prefix="odoo20-upgrade-") as tmp:
        sandbox = Path(tmp) / "addons"
        sandbox.mkdir()
        for m in modules:
            shutil.copytree(m, sandbox / m.name, ignore=shutil.ignore_patterns(".git", "__pycache__", "node_modules"))
        ro_paths = [str(p) for p in cfg.addons_paths if not any(p == m.parent for m in modules)]
        result = runtime().run_helper("upgrade_runner.py", {"addons_dir": str(sandbox), "steps": steps,
                                                           "ro_paths": ro_paths}, timeout=900)
        diffs, changed = [], []
        for m in modules:
            new_root = sandbox / m.name
            old_files = {p.relative_to(m) for p in m.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
            new_files = {p.relative_to(new_root) for p in new_root.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
            for rel in sorted(old_files | new_files):
                old_p, new_p = m / rel, new_root / rel
                old = old_p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True) if rel in old_files else []
                new = new_p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True) if rel in new_files else []
                if old == new:
                    continue
                changed.append((m, rel, rel in new_files))
                diff = list(difflib.unified_diff(old, new, f"a/{m.name}/{rel}", f"b/{m.name}/{rel}", n=2))
                if len(diff) > max_diff_lines:
                    diff = diff[:max_diff_lines] + [f"... ({len(diff) - max_diff_lines} more diff lines)\n"]
                diffs.append("".join(diff))
        if apply:
            for m, rel, exists in changed:
                target = m / rel
                if exists:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(sandbox / m.name / rel, target)
                elif target.exists():
                    target.unlink()
    step_txt = ", ".join(s.get("script") or f"versions {s['from_version']} -> 20.0" for s in steps)
    head = [f"## upgrade_code on {', '.join(m.name for m in modules)} ({step_txt})",
            f"{len(changed)} file(s) {'changed and WRITTEN' if apply else 'would change (dry run; nothing written)'}."]
    script_lines = []
    for r in result.get("results", []):
        if r.get("error"):
            script_lines.append(f"- {r['script']}: **failed** — {r['error']}" + (f" (likely cause: {r['hint']})" if r.get("hint") else ""))
        else:
            note = f" ({r['ignored_outside']} change(s) to other addons discarded)" if r.get("ignored_outside") else ""
            script_lines.append(f"- {r['script']}: {str(r.get('files', 0)) + ' file(s) changed' if r['changed'] else 'no change'}{note}")
    head += ["", "Scripts:"] + script_lines
    head += [f"- warning: {w}" for w in warnings]
    if not changed:
        head.append("Nothing to rewrite. Run odoo_validate for what the scripts do not cover.")
    else:
        head.append("Next: " + ("odoo_validate the module, then odoo_test." if apply else
                                "review the diff, then re-run with apply=true (or apply it by hand)."))
    body = "\n".join(head) + ("\n\n```diff\n" + "\n".join(diffs) + "\n```" if diffs else "")
    return truncate(body)


# ---------------------------------------------------------------------------
# databases, tests, jobs, server
# ---------------------------------------------------------------------------

def db_tool(action: str, name: str | None, modules: str, with_demo: bool, wait: int) -> str:
    rt = runtime()
    cfg = ctx.config()
    if action == "list":
        dbs = rt.list_databases()
        allowed = [d for d in dbs if cfg.db_allowed(d)]
        return (f"## Databases ({len(dbs)})\n- allowlisted for the tools ({', '.join(cfg.db_allow)}): "
                + (", ".join(f"`{d}`" for d in allowed) or "none")
                + f"\n- template `{rt.template_db}`: {'present' if rt.template_db in dbs else 'missing (create_template)'}"
                + f"\n- other databases (never touched): {len(dbs) - len(allowed)}")
    name = name or (rt.template_db if action == "create_template" else None)
    if not name:
        raise ToolError(f"action {action!r} needs `name`")
    rt.require_db(name)
    mods = ",".join(m.strip() for m in modules.split(",") if m.strip())
    exists = rt.db_exists(name)
    if action in {"create", "create_template"}:
        if exists:
            raise ToolError(f"database {name!r} already exists (drop it first, or use it)")
        steps = []
        if action == "create" and rt.db_exists(rt.template_db):
            steps.append(rt.cmd("db", "duplicate", rt.template_db, name))
        else:
            steps.append(rt.cmd("db", "init", name, *(["--with-demo"] if with_demo else [])))
        if mods:
            steps.append(rt.cmd("module", "install", "-d", name, *mods.split(",")))
        script = " && ".join(shlex.join(s) for s in steps)
        job = jobs().start("db", f"{action} {name}" + (f" + {mods}" if mods else ""), ["bash", "-c", script], db=name,
                           timeout=3600, cwd=str(cfg.odoo_root))
        _wait(job, wait)
        return _job_text(job, wait_note=True)
    if not exists:
        raise ToolError(f"database {name!r} does not exist")
    if action == "drop":
        cmd = rt.cmd("db", "drop", name)
    elif action == "neutralize":
        cmd = rt.cmd("neutralize", "-d", name)
    elif action in {"install", "upgrade"}:
        if not mods:
            raise ToolError("`modules` is required for install/upgrade")
        cmd = rt.cmd("module", action, "-d", name, *mods.split(","))
    else:
        raise ToolError(f"unknown action {action!r}")
    job = jobs().start("db", f"{action} {name} {mods}".strip(), cmd, db=name, timeout=3600, cwd=str(cfg.odoo_root))
    _wait(job, wait)
    return _job_text(job, wait_note=True)


def test_tool(modules: str, test_tags: str | None, db: str | None, keep_db: bool, install: bool, timeout: int,
              wait: int, js_tests: bool = False) -> str:
    rt = runtime()
    cfg = ctx.config()
    mods = [m.strip() for m in modules.split(",") if m.strip()]
    if not mods:
        raise ToolError("give at least one module")
    con = ctx.index().db()
    known = {r[0] for r in con.execute("SELECT name FROM modules")}
    for m in mods:
        if m not in known:
            raise did_you_mean("Module", m, known)
    tags = test_tags or ",".join(f"/{m}" for m in mods)
    port = rt.free_port()
    steps: list[str] = []
    throwaway = db is None
    if throwaway:
        db = f"odoo20_test_{mods[0][:30]}_{time.strftime('%H%M%S')}"
        rt.require_db(db)
        if not rt.db_exists(rt.template_db):
            steps.append(shlex.join(rt.cmd("db", "init", rt.template_db)))
        steps.append(shlex.join(rt.cmd("db", "duplicate", rt.template_db, db)))
    else:
        rt.require_db(db)
        if not rt.db_exists(db):
            raise ToolError(f"database {db!r} does not exist (omit `db` to use a throwaway copy of {rt.template_db})")
    mode = "-i" if (install or throwaway) else "-u"
    run = rt.cmd("-d", db, mode, ",".join(mods), "--test-tags", tags, "--stop-after-init", "--http-port", str(port),
                 "--log-level", "test")
    if js_tests:
        # Hoot suites live in web's WebSuite (a CrossModule test scoped by the /module tag); post-install tests
        # are only collected from modules updated in this run, so web must be updated too.
        run += ["-u", "web"]
    steps.append(shlex.join(run))
    script = "set -o pipefail; " + " && ".join(steps)
    if throwaway and not keep_db:
        # always drop the throwaway database, keep the test exit code
        script = f"{script}; rc=$?; {shlex.join(rt.cmd('db', 'drop', db))} >/dev/null 2>&1; exit $rc"
    job = jobs().start("test", f"tests {tags} on {db}{' (throwaway)' if throwaway else ''}", ["bash", "-c", script],
                       db=db, timeout=timeout, cwd=str(cfg.odoo_root))
    if throwaway and keep_db:
        job.note = f"database {db} kept for inspection"
    _wait(job, wait)
    return _job_text(job, wait_note=True)


def job_tool(job_id: str | None, action: str, lines: int, grep: str | None) -> str:
    jm = jobs()
    if not job_id:
        if not jm.jobs:
            return "No jobs in this session."
        rows = [f"- `{j.id}` {j.kind} **{j.status}** {j.elapsed()}s — {j.title}" for j in jm.jobs.values()]
        return "## Jobs\n" + "\n".join(rows[-30:])
    if action == "cancel":
        return _job_text(jm.cancel(job_id))
    if action == "log":
        return f"```\n{truncate(jm.tail(job_id, lines, grep), 20000)}\n```"
    return _job_text(jm.get(job_id), wait_note=True)


def server_tool(action: str, db: str | None, port: int, dev: str, update: str) -> str:
    rt = runtime()
    jm = jobs()
    servers = [j for j in jm.jobs.values() if j.kind == "server" and j.status == "running"]
    if action == "status":
        if not servers:
            return "No dev server started by this session."
        return "\n".join(_job_text(j) for j in servers)
    if action in {"stop", "logs"}:
        target = [j for j in servers if not db or j.db == db]
        if not target:
            raise ToolError("no running dev server" + (f" on {db}" if db else ""))
        if action == "stop":
            return "\n".join(_job_text(jm.cancel(j.id)) for j in target)
        return f"```\n{truncate(jm.tail(target[0].id, 120), 20000)}\n```"
    if action != "start":
        raise ToolError(f"unknown action {action!r}")
    rt.require_db(db or "")
    if not rt.db_exists(db):
        raise ToolError(f"database {db!r} does not exist (create it with odoo_db)")
    if rt.free_port(port) != port:
        raise ToolError(f"port {port} is busy; pick another `port`")
    args = ["-d", db, "--http-port", str(port), "--db-filter", f"^{db}$"]
    if dev:
        args += ["--dev", dev]
    if update:
        args += ["-u", update]
    job = jm.start("server", f"dev server {db} :{port}", rt.cmd(*args), db=db, timeout=None,
                   cwd=str(ctx.config().odoo_root))
    job.note = f"URL: http://127.0.0.1:{port}/odoo (login admin / admin on toolkit-created databases)"
    _wait(job, 8)
    return _job_text(job)


def shell_tool(db: str, code: str, commit: bool, timeout: int) -> str:
    rt = runtime()
    rt.require_db(db)
    if commit:
        rt.require_writes("odoo_shell(commit=true)")
    result = rt.run_helper("shell_runner.py", {"db": db, "code": code, "commit": commit}, timeout=timeout)
    md = [f"## odoo_shell on `{db}` — {'committed' if result.get('committed') else 'rolled back'}"]
    if result.get("stdout"):
        md += ["**stdout:**", "```", result["stdout"].rstrip(), "```"]
    if result.get("result") is not None:
        md += ["**result:**", "```", result["result"], "```"]
    if result.get("exception"):
        md += ["**exception:**", "```", result["exception"].rstrip(), "```"]
    return truncate("\n".join(md))


# ---------------------------------------------------------------------------
# resolve="db" variants of static tools
# ---------------------------------------------------------------------------

def _default_db(db: str | None) -> str:
    db = db or ctx.config().live_db or runtime().template_db
    runtime().require_db(db)
    return db


def views_db(xmlid: str, db: str | None, fmt: str) -> str:
    db = _default_db(db)
    r = runtime().run_helper("odoo_query.py", {"op": "combined_arch", "db": db, "xmlid": xmlid})
    md = f"## Combined arch of `{r['root']}` ({r['type']}, model `{r['model']}`) from database `{db}`\n\n```xml\n{r['arch']}\n```"
    return render(r, fmt, md)


def assets_db(bundle: str, db: str | None, fmt: str) -> str:
    db = _default_db(db)
    r = runtime().run_helper("odoo_query.py", {"op": "asset_paths", "db": db, "bundle": bundle})
    md = [f"## `{bundle}` in database `{db}`: {len(r['paths'])} files (installed modules only, final order)"]
    md += [f"{i}. {p[0]}" for i, p in enumerate(r["paths"])]
    return render(r, fmt, "\n".join(md))


def model_db(model: str, db: str | None, fmt: str) -> str:
    db = _default_db(db)
    r = runtime().run_helper("odoo_query.py", {"op": "fields_get", "db": db, "model": model})
    rows = []
    for name, f in sorted(r["fields"].items()):
        flags = [k for k in ("required", "readonly", "store") if f.get(k)]
        rows.append(f"| {name} | {f.get('type')}{'→' + f['relation'] if f.get('relation') else ''} | {f.get('string', '')} | "
                    f"{' '.join(flags)} | {f.get('groups') or ''} |")
    md = (f"## `{model}` fields in database `{db}` ({len(rows)})\n\n| field | type | label | flags | groups |\n|---|---|---|---|---|\n"
          + "\n".join(rows))
    return render(r, fmt, md)


# ---------------------------------------------------------------------------
# JSON-2 live call
# ---------------------------------------------------------------------------

def _is_readonly_method(model: str, method: str) -> bool:
    if method in READ_METHODS:
        return True
    try:
        con = ctx.index().db()
    except RuntimeError:
        return False
    from ..query import core as q
    for item in q.method_chain(con, model, method, None):
        if any(d in {"api.readonly", "readonly"} for d in json.loads(item["decorators"] or "[]")):
            return True
    return False


def live_call(model: str, method: str, ids: list[int] | None, kwargs: dict | None, context: dict | None,
              timeout: int) -> str:
    cfg = ctx.config()
    if not (cfg.live_url and cfg.live_db and cfg.live_api_key):
        raise ToolError("live access is not configured: set the plugin options live_url, live_db and live_api_key "
                        "(an API key with scope rpc for that database)")
    if not cfg.db_allowed(cfg.live_db):
        raise ToolError(f"live_db {cfg.live_db!r} is not in the allowlist {list(cfg.db_allow)}")
    if not _is_readonly_method(model, method) and not cfg.allow_writes:
        raise ToolError(f"{model}.{method} is not a read method; calling it needs the plugin option allow_writes=true")
    body = {**(kwargs or {})}
    if ids:
        body["ids"] = ids
    if context:
        body["context"] = context
    req = urllib.request.Request(
        f"{cfg.live_url}/json/2/{model}/{method}", data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {cfg.live_api_key}", "X-Odoo-Database": cfg.live_db,
                 "Content-Type": "application/json; charset=utf-8", "User-Agent": "odoo20-mcp"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - URL comes from the user's config
            payload = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:3000]
        raise ToolError(f"JSON-2 {model}.{method} -> HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ToolError(f"cannot reach {cfg.live_url}: {exc.reason} (is the server running? odoo_server start)") from exc
    try:
        data = json.loads(payload)
        text = json.dumps(data, indent=1, ensure_ascii=False, default=str)
    except json.JSONDecodeError:
        text = payload
    return truncate(f"## {model}.{method} -> HTTP {status}\n```json\n{text}\n```")
