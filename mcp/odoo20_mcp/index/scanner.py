"""Discover addons, read manifests, list files and compute change signatures."""
from __future__ import annotations

import ast
import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path

MANIFEST = "__manifest__.py"
SKIP_DIRS = {"__pycache__", "node_modules", ".git", ".idea", ".vscode"}

TEXT_KINDS = {
    ".py": "py", ".js": "js", ".ts": "ts", ".xml": "xml", ".scss": "scss", ".css": "css",
    ".csv": "csv", ".po": "po", ".pot": "po", ".sql": "sql", ".rng": "rng", ".json": "json",
    ".md": "md", ".rst": "md", ".html": "html", ".txt": "txt", ".yml": "yaml", ".yaml": "yaml",
}


@dataclass
class ModuleEntry:
    name: str
    path: Path
    root: Path
    files: list[tuple[str, str, int, int]] = field(default_factory=list)  # rel, kind, size, mtime_ns
    signature: str = ""


def file_kind(rel: str) -> str:
    """Classify a module-relative path; static XML is OWL/client QWeb, static/lib is vendored."""
    rel_posix = rel.replace(os.sep, "/")
    ext = os.path.splitext(rel_posix)[1].lower()
    if rel_posix == MANIFEST:
        return "manifest"
    if rel_posix.startswith("static/lib/") or "/static/lib/" in rel_posix:
        return "lib"
    kind = TEXT_KINDS.get(ext, "other")
    if kind == "xml" and rel_posix.startswith("static/"):
        return "owl_xml"
    return kind


def read_manifest(path: Path) -> dict:
    try:
        text = (path / MANIFEST).read_text(encoding="utf-8")
        value = ast.literal_eval(_strip_header(text))
        return value if isinstance(value, dict) else {"__error__": "manifest is not a dict"}
    except Exception as exc:  # noqa: BLE001 - report any manifest problem
        return {"__error__": f"{type(exc).__name__}: {exc}"}


def _strip_header(text: str) -> str:
    # manifests are a single dict literal, optionally preceded by comments/encoding lines
    start = text.find("{")
    return text[start:] if start >= 0 else text


def find_modules(addons_paths: tuple[Path, ...]) -> tuple[dict[str, ModuleEntry], list[str]]:
    """Return modules by name (first addons path wins, like Odoo) and duplicate warnings."""
    modules: dict[str, ModuleEntry] = {}
    duplicates: list[str] = []
    for root in addons_paths:
        try:
            names = sorted(os.listdir(root))
        except OSError:
            continue
        for name in names:
            path = root / name
            if not (path / MANIFEST).is_file():
                continue
            if name in modules:
                duplicates.append(f"{name}: {path} shadowed by {modules[name].path}")
                continue
            modules[name] = ModuleEntry(name=name, path=path, root=root)
    return modules, duplicates


def list_files(entry: ModuleEntry) -> ModuleEntry:
    """Walk a module (i18n/*.po are listed but not stat'ed deeply) and compute its signature."""
    files: list[tuple[str, str, int, int]] = []
    digest = hashlib.blake2b(digest_size=16)
    base = str(entry.path)
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        rel_dir = os.path.relpath(dirpath, base)
        rel_dir = "" if rel_dir == "." else rel_dir.replace(os.sep, "/") + "/"
        is_i18n = rel_dir.startswith("i18n/")
        for fname in sorted(filenames):
            rel = rel_dir + fname
            kind = file_kind(rel)
            if is_i18n:
                # translations do not affect the index; avoid stat'ing thousands of .po files
                files.append((rel, kind, 0, 0))
                continue
            try:
                st = os.stat(os.path.join(dirpath, fname))
            except OSError:
                continue
            files.append((rel, kind, st.st_size, st.st_mtime_ns))
            digest.update(f"{rel}\0{st.st_size}\0{st.st_mtime_ns}\n".encode())
    entry.files = files
    entry.signature = digest.hexdigest()
    return entry
