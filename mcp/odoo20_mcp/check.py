"""Fast single-file Odoo 20 legacy check, used by the PostToolUse hook and usable from the shell.

Hook mode (no argument): read the PostToolUse JSON on stdin, check ``tool_input.file_path`` when it belongs
to an Odoo addon, and print ``hookSpecificOutput.additionalContext`` when errors/warnings are found.

CLI mode: ``python -m odoo20_mcp.check FILE [FILE...]`` prints findings and exits 1 on errors.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .validate.engine import check_file, module_root_of

CHECKED_SUFFIXES = {".py", ".xml", ".js", ".scss", ".csv"}
MAX_REPORTED = 15


def _findings(path: Path):
    return [f for f in check_file(path, str(path)) if f.severity in {"error", "warning"}]


def _format(path: Path, findings) -> str:
    lines = [f"odoo20 check: {len(findings)} Odoo 20 issue(s) in {path.name} (fix before moving on):"]
    for f in findings[:MAX_REPORTED]:
        line = f"- line {f.line} [{f.rule}] {f.severity}: {f.message} -> {f.fix}"
        if f.fixed_by:
            line += f" (automatable: odoo_upgrade_code script {f.fixed_by})"
        lines.append(line)
    if len(findings) > MAX_REPORTED:
        lines.append(f"- … {len(findings) - MAX_REPORTED} more: run odoo_validate on the module")
    lines.append("Suppress a deliberate case with a comment containing `odoo20-ignore: RULE_ID` on that line.")
    return "\n".join(lines)


def hook() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    file_path = (payload.get("tool_input") or {}).get("file_path")
    if not file_path:
        return 0
    path = Path(file_path)
    if path.suffix not in CHECKED_SUFFIXES and path.name != "__manifest__.py":
        return 0
    if not path.is_file() or module_root_of(path) is None:
        return 0  # not inside an Odoo addon
    findings = _findings(path)
    if not findings:
        return 0
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                             "additionalContext": _format(path, findings)[:9500]}}))
    return 0


def cli(paths: list[str]) -> int:
    status = 0
    for raw in paths:
        path = Path(raw)
        for f in check_file(path, str(path)):
            print(f"{f.file}:{f.line}: {f.severity} [{f.rule}] {f.message}\n    fix: {f.fix}")
            status = 1 if f.severity == "error" else status
    return status


def main() -> None:
    sys.exit(cli(sys.argv[1:]) if len(sys.argv) > 1 else hook())


if __name__ == "__main__":
    main()
