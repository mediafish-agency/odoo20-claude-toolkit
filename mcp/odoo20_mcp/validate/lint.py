"""External linters: ruff with Odoo's ruff.toml; ESLint with Odoo's tooling config when installed."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from .engine import Finding


def _ruff_binary() -> str | None:
    local = Path(sys.executable).parent / "ruff"
    if local.exists():
        return str(local)
    return shutil.which("ruff")


def ruff(paths: list[Path], odoo_root: Path, display_base: Path | None = None, timeout: int = 120) -> list[Finding]:
    binary = _ruff_binary()
    if not binary or not paths:
        return []
    config = odoo_root / "ruff.toml"
    cmd = [binary, "check", "--output-format", "json", "--no-cache", "--exit-zero"]
    if config.is_file():
        cmd += ["--config", str(config)]
    cmd += [str(p) for p in paths]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        items = json.loads(proc.stdout or "[]")
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
        return [Finding("RUFF", "info", str(paths[0]), 0, f"ruff could not run: {exc}")]
    findings = []
    for item in items:
        file = Path(item.get("filename", ""))
        disp = str(file.relative_to(display_base)) if display_base and file.is_relative_to(display_base) else str(file)
        code = item.get("code") or "ruff"
        severity = "error" if code.startswith(("F", "E9")) else "warning"
        fix = (item.get("fix") or {}).get("message") or ""
        findings.append(Finding(f"RUFF:{code}", severity, disp, (item.get("location") or {}).get("row", 0),
                                item.get("message", ""), fix, "ruff.toml"))
    return findings


def eslint(paths: list[Path], odoo_root: Path, timeout: int = 180) -> list[Finding]:
    """Run ESLint only when Odoo's tooling was enabled (addons/web/tooling/enable.sh installs it)."""
    for base in (odoo_root, odoo_root / "addons" / "web" / "tooling"):
        binary = base / "node_modules" / ".bin" / "eslint"
        if binary.exists():
            break
    else:
        return []
    try:
        proc = subprocess.run([str(binary), "-f", "json", *map(str, paths)], capture_output=True, text=True,
                              timeout=timeout, cwd=str(odoo_root), check=False)
        items = json.loads(proc.stdout or "[]")
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return []
    findings = []
    for item in items:
        for msg in item.get("messages", []):
            findings.append(Finding(f"ESLINT:{msg.get('ruleId')}", "error" if msg.get("severity") == 2 else "warning",
                                    item.get("filePath", ""), msg.get("line", 0), msg.get("message", "")))
    return findings
