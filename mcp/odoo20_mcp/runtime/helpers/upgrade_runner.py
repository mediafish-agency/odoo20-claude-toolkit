"""Run Odoo's upgrade_code scripts on a sandbox addons directory (never on the Odoo tree).

* Only the sandbox files are registered in the FileManager, so scripts only rewrite the user's addon.
* All other addons (core + extra paths) are exposed read-only through FileManager._modules, so scripts that
  look up dependencies (e.g. 19.4-00-ir-access reading base.group_user) work; nothing outside the sandbox is
  ever saved.
* Scripts run one at a time with a fresh FileManager, saving after each, so a failing script is reported
  without discarding the others' changes.
"""
import contextlib
import importlib.util
import io
import json
import sys
import traceback
from pathlib import Path

payload = json.loads(sys.argv[1])
sys.path.insert(0, payload["odoo_root"])


def out(obj):
    print("@@ODOO20@@" + json.dumps(obj, default=str))


HINTS = {
    "'NoneType' object has no attribute 'encode'": "a file listed in __manifest__ 'data'/'demo' does not exist",
}


def main():
    from odoo import release
    from odoo.cli.upgrade_code import UPGRADE, FileManager
    from odoo.tools import parse_version

    sandbox = Path(payload["addons_dir"]).resolve()
    ro_modules = {}
    for apath in payload.get("ro_paths") or []:
        base = Path(apath)
        if not base.is_dir():
            continue
        for addon in base.iterdir():
            if addon.is_dir() and (addon / "__manifest__.py").exists():
                ro_modules.setdefault(addon.name, addon)

    def file_manager():
        fm = FileManager([str(sandbox)], payload.get("glob") or "**/*")
        for name, addon in ro_modules.items():
            fm._modules.setdefault(name, addon)  # sandbox modules keep precedence
        return fm

    def resolve(script):
        path = Path(script)
        if path.is_file():
            return path
        candidates = list(UPGRADE.glob(f"*{script.removesuffix('.py')}*.py"))
        if len(candidates) != 1:
            raise FileNotFoundError(f"script {script!r} matches {len(candidates)} files in {UPGRADE}")
        return candidates[0]

    scripts = []
    for step in payload["steps"]:
        if step.get("script"):
            scripts.append(resolve(step["script"]))
            continue
        from_v = parse_version(step["from_version"])
        to_v = parse_version(step.get("to_version") or release.version)
        for path in sorted(UPGRADE.glob("*.py")):
            prefix = path.name.partition("-")[0]
            if prefix[:1].isdigit() and from_v <= parse_version(prefix) <= to_v:
                scripts.append(path)

    # owl3-migration re-reads files from disk between its steps, so some rewrites only land on a second pass:
    # repeat it (max 3 passes) until it reaches a fixed point.
    expanded = []
    for script in scripts:
        expanded += [script] * (3 if script.name.startswith("owl3-migration") else 1)
    results = []
    log = io.StringIO()
    last_no_change = set()
    for script in expanded:
        if script.name in last_no_change:
            continue
        fm = file_manager()
        with contextlib.redirect_stdout(log):
            try:
                spec = importlib.util.spec_from_file_location(script.name, str(script))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.upgrade(fm)
                fm.print_summary()
            except Exception as exc:  # noqa: BLE001
                message = f"{type(exc).__name__}: {exc}"
                hint = next((h for k, h in HINTS.items() if k in message), "")
                results.append({"script": script.name, "error": message, "hint": hint,
                                "traceback": traceback.format_exc()[-1200:]})
                continue
        saved, ignored = 0, 0
        for file in fm:
            if not file.dirty:
                continue
            if Path(file.path).resolve().is_relative_to(sandbox):
                file._save()
                saved += 1
            else:
                ignored += 1  # a script touched a dependency in memory: never written
        if saved == 0:
            last_no_change.add(script.name)
        previous = next((r for r in results if r["script"] == script.name and "error" not in r), None)
        if previous is not None:  # repeated pass of the same script: accumulate
            previous["files"] += saved
            previous["changed"] = previous["changed"] or saved > 0
            previous["passes"] = previous.get("passes", 1) + 1
        else:
            results.append({"script": script.name, "changed": saved > 0, "files": saved, "ignored_outside": ignored})
    return {"results": results, "log": log.getvalue()[-8000:]}


try:
    out(main())
except Exception as exc:  # noqa: BLE001
    out({"error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()[-3000:]})
