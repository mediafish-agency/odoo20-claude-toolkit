"""Extract everything for one module (runs in a worker process)."""
from __future__ import annotations

import json
from pathlib import Path

from . import csv_extract, js_extract, py_extract, xml_extract
from .scanner import read_manifest

TABLE_KEYS = (
    "files", "models", "fields", "methods", "constraints", "records", "views", "refs", "access",
    "templates", "js_modules", "js_imports", "js_registry", "js_patches", "js_classes", "assets", "errors",
)


def _merge(acc: dict[str, list], part: dict[str, list]) -> None:
    for key, rows in part.items():
        acc.setdefault(key, []).extend(rows)


def _read(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def extract_module(name: str, path: str, root: str, signature: str, files: list[tuple[str, str, int, int]]) -> dict:
    mod_path = Path(path)
    manifest = read_manifest(mod_path)
    rows: dict[str, list] = {key: [] for key in TABLE_KEYS}
    rows["files"] = [(name, rel, kind, size) for rel, kind, size, _ in files]

    for bundle_name, entries in (manifest.get("assets") or {}).items() if isinstance(manifest.get("assets"), dict) else []:
        for seq, entry in enumerate(entries or []):
            if isinstance(entry, str):
                rows["assets"].append((name, bundle_name, seq, "append", None, entry))
            elif isinstance(entry, (list, tuple)) and entry:
                directive = entry[0]
                if directive in {"before", "after", "replace"} and len(entry) >= 3:
                    rows["assets"].append((name, bundle_name, seq, directive, entry[1], entry[2]))
                elif len(entry) >= 2:
                    rows["assets"].append((name, bundle_name, seq, directive, None, entry[1]))

    for rel, kind, _size, _mtime in files:
        if kind == "lib" and rel.endswith(".js"):
            # vendored libraries are importable (`@web/../lib/hoot/hoot`) but not analysed
            head = (_read(mod_path / rel) or b"")[:400].decode("utf-8", "replace")
            alias = js_extract.ALIAS.search(head)
            rows["js_modules"].append((name, js_extract.module_path(name, rel), alias.group(1) if alias else None, rel, "[]"))
            continue
        if kind not in {"py", "xml", "owl_xml", "csv", "js"}:
            continue
        data = _read(mod_path / rel)
        if data is None:
            continue
        try:
            if kind == "py":
                _merge(rows, py_extract.extract(name, rel, data.decode("utf-8", "replace")))
            elif kind == "xml":
                _merge(rows, xml_extract.extract_server(name, rel, data))
            elif kind == "owl_xml":
                _merge(rows, xml_extract.extract_static(name, rel, data))
            elif kind == "csv":
                _merge(rows, csv_extract.extract(name, rel, data.decode("utf-8-sig", "replace")))
            elif kind == "js" and rel.startswith("static/"):
                _merge(rows, js_extract.extract(name, rel, data.decode("utf-8", "replace")))
        except Exception as exc:  # noqa: BLE001 - one bad file must not kill the index
            rows["errors"].append((name, rel, 0, f"extractor crashed: {type(exc).__name__}: {exc}"))

    depends = manifest.get("depends") or []
    module_row = (
        name, path, root, signature, json.dumps(manifest, default=str),
        json.dumps(depends if isinstance(depends, list) else []),
        json.dumps(manifest.get("auto_install", False)),
        int(bool(manifest.get("installable", True))), int(bool(manifest.get("application", False))),
        manifest.get("license"), manifest.get("version"), manifest.get("summary") or manifest.get("name"),
        manifest.get("category"), len(files), manifest.get("__error__"),
    )
    return {"module": module_row, "rows": rows}
