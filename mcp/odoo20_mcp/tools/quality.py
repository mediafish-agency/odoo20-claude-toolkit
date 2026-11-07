"""odoo_validate: legacy patterns + RNG + index-backed semantic checks + linters."""
from __future__ import annotations

import ast
from pathlib import Path

from .. import context as ctx
from ..index.scanner import MANIFEST
from ..util import ToolError, render
from ..validate import engine, lint, rng
from ..validate.engine import SEVERITY_ORDER, Finding, module_root_of

ALL_CHECKS = ("legacy", "rng", "semantic", "lint")


def _display_base(path: Path) -> Path | None:
    cfg = ctx.config()
    return cfg.odoo_root if cfg.is_core_path(path) else None


def _manifest_files(mod: Path) -> list[Path]:
    try:
        text = (mod / MANIFEST).read_text(encoding="utf-8")
        manifest = ast.literal_eval(text[text.find("{"):])
    except (OSError, ValueError, SyntaxError):
        return []
    out = []
    for key in ("data", "demo"):
        for entry in manifest.get(key) or []:
            if entry.endswith(".xml") and (mod / entry).is_file():
                out.append(mod / entry)
    return out


def _disp(path: Path, base: Path | None) -> str:
    return str(path.relative_to(base)) if base and path.is_relative_to(base) else str(path)


def validate_module(mod: Path, checks: set[str], notes: list[str]) -> list[Finding]:
    cfg = ctx.config()
    base = _display_base(mod)
    findings: list[Finding] = []
    if "legacy" in checks:
        findings += engine.check_tree(mod, base)
    if "rng" in checks:
        for data_file in _manifest_files(mod):
            findings += rng.check_data_file(data_file, _disp(data_file, base), cfg.odoo_root)
    if "semantic" in checks:
        if not cfg.in_known_roots(mod):
            notes.append(f"semantic checks skipped for `{mod.name}`: it is outside the indexed addons paths "
                         "(add its parent folder to the plugin option extra_addons_paths)")
        else:
            from ..validate.semantic import check_module
            im = ctx.index()
            im.build()  # incremental: re-extracts only modules whose files changed
            findings += check_module(im.db(), cfg.odoo_root, mod.name)
    if "lint" in checks:
        py_files = [p for p, rel in engine.iter_module_files(mod) if p.suffix == ".py"]
        findings += lint.ruff(py_files, cfg.odoo_root, base)
        js_files = [p for p, rel in engine.iter_module_files(mod) if p.suffix == ".js" and "/static/" in str(p)]
        findings += lint.eslint(js_files, cfg.odoo_root) if js_files else []
    return findings


def validate(path_str: str, checks: str, min_severity: str, limit: int, fmt: str) -> str:
    path = Path(path_str).expanduser()
    if not path.is_absolute():
        path = (ctx.config().odoo_root / path) if (ctx.config().odoo_root / path).exists() else path.resolve()
    if not path.exists():
        raise ToolError(f"path not found: {path}")
    selected = {c.strip() for c in checks.split(",") if c.strip()} if checks and checks != "all" else set(ALL_CHECKS)
    unknown = selected - set(ALL_CHECKS)
    if unknown:
        raise ToolError(f"unknown checks {sorted(unknown)}; choose from {ALL_CHECKS}")
    notes: list[str] = []
    findings: list[Finding] = []
    if path.is_file():
        base = _display_base(path)
        disp = _disp(path, base)
        if "legacy" in selected:
            findings += engine.check_file(path, disp)
        mod = module_root_of(path)
        if "rng" in selected and path.suffix == ".xml" and mod and "/static/" not in str(path):
            findings += rng.check_data_file(path, disp, ctx.config().odoo_root)
        if "lint" in selected and path.suffix == ".py":
            findings += lint.ruff([path], ctx.config().odoo_root, base)
        if "semantic" in selected and mod:
            notes.append(f"semantic checks run per module: call odoo_validate on `{mod}` for cross-file checks")
        target = f"file `{disp}`"
    else:
        if (path / MANIFEST).is_file():
            modules = [path]
        else:
            modules = sorted(d for d in path.iterdir() if (d / MANIFEST).is_file())
            if not modules:
                raise ToolError(f"{path} is neither a module (no __manifest__.py) nor a folder of modules")
            if len(modules) > 60:
                raise ToolError(f"{len(modules)} modules under {path}; validate one module (or a smaller folder)")
        for mod in modules:
            findings += validate_module(mod, selected, notes)
        target = f"module `{modules[0].name}`" if len(modules) == 1 else f"{len(modules)} modules in `{path}`"

    floor = SEVERITY_ORDER.get(min_severity, 2)
    findings = [f for f in engine.sort_findings(findings) if SEVERITY_ORDER.get(f.severity, 9) <= floor]
    counts = {s: sum(1 for f in findings if f.severity == s) for s in ("error", "warning", "info")}
    shown = findings[:limit]
    md = [f"## Validation of {target}: {counts['error']} error(s), {counts['warning']} warning(s), {counts['info']} info",
          f"_checks: {', '.join(sorted(selected))}_"]
    md += [f"- note: {n}" for n in notes]
    current = None
    for f in shown:
        if f.severity != current:
            current = f.severity
            md.append(f"\n### {current.capitalize()}s")
        line = f"- `{f.file}:{f.line}` **[{f.rule}]** {f.message}"
        if f.snippet:
            line += f"\n  `{f.snippet[:140]}`"
        if f.fix:
            line += f"\n  fix: {f.fix}"
        if f.fixed_by:
            line += f" (automatable: odoo_upgrade_code script `{f.fixed_by}`)"
        md.append(line)
    if len(findings) > limit:
        md.append(f"\n_{len(findings) - limit} more finding(s) not shown; raise `limit` or `min_severity`._")
    if not findings:
        md.append("\nNo findings. (Static checks only: also install the module and run its tests: odoo_test.)")
    return render({"counts": counts, "notes": notes, "findings": [f.as_dict() for f in findings[:limit]]}, fmt, "\n".join(md))
