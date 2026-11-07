"""Run the legacy-pattern catalogue on files (fast, no index needed)."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from ..index.scanner import MANIFEST, SKIP_DIRS, file_kind
from ..util import strip_js_comments, strip_py_comments, strip_xml_comments
from .rules import NEEDLES, RULES_BY_ID, Rule, rules_for

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
_IGNORE = re.compile(r"odoo20-ignore(?::\s*([\w, ]+))?")


@dataclass
class Finding:
    rule: str
    severity: str
    file: str
    line: int
    message: str
    fix: str = ""
    source: str = ""
    fixed_by: str | None = None
    snippet: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def module_root_of(path: Path) -> Path | None:
    cur = path if path.is_dir() else path.parent
    for _ in range(10):
        if (cur / MANIFEST).is_file():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def kind_of(path: Path) -> str:
    root = module_root_of(path)
    if root is None:
        ext = path.suffix.lower()
        return {".py": "py", ".xml": "xml", ".js": "js", ".scss": "scss", ".csv": "csv"}.get(ext, "other")
    rel = path.resolve().relative_to(root.resolve()).as_posix()
    return file_kind(rel)


def _prepare(kind: str, text: str) -> str:
    if kind in {"py", "manifest"}:
        return strip_py_comments(text)
    if kind in {"xml", "owl_xml"}:
        return strip_xml_comments(text)
    if kind in {"js", "scss", "css"}:
        return strip_js_comments(text)
    return text


def _may_match(rule: Rule, text: str) -> bool:
    needles = NEEDLES.get(rule.id)
    if needles and not any(n in text for n in needles):
        return False
    return rule.regex().search(text) is not None


def _suppressed(lines: list[str], line: int, rule_id: str) -> bool:
    for idx in (line - 1, line - 2):
        if 0 <= idx < len(lines):
            m = _IGNORE.search(lines[idx])
            if m and (not m.group(1) or rule_id in {r.strip() for r in m.group(1).split(",")}):
                return True
    return False


def check_text(text: str, kind: str, display: str, rules: list[Rule] | None = None) -> list[Finding]:
    if kind == "manifest":
        rules = rules if rules is not None else rules_for("manifest")
    else:
        rules = rules if rules is not None else rules_for(kind)
    if not rules:
        return []
    # Cheap pass on the raw text first; comments are stripped only when something matched.
    candidates = [
        r for r in rules
        if (r.check is not None and (r.hint is None or re.search(r.hint, text)))
        or (r.check is None and _may_match(r, text))
    ]
    if not candidates:
        return []
    prepared = _prepare(kind, text)
    lines = text.splitlines()
    findings: list[Finding] = []
    for rule in candidates:
        hits: list[tuple[int, str]] = []
        regex = rule.regex()
        if regex is not None:
            for m in regex.finditer(prepared):
                hits.append((prepared.count("\n", 0, m.start()) + 1, m.group(0)))
        elif rule.check is not None:
            hits.extend(rule.check(prepared, display))
        seen_lines: set[int] = set()
        for line, extra in hits:
            if line in seen_lines or _suppressed(lines, line, rule.id):
                continue
            seen_lines.add(line)
            snippet = lines[line - 1].strip()[:180] if 0 < line <= len(lines) else extra[:180]
            findings.append(Finding(rule.id, rule.severity, display, line, rule.title, rule.fix, rule.source,
                                    rule.fixed_by, snippet))
    return findings


_MIGRATION_DIRS = ("migrations/", "upgrades/")
_VENDORED = re.compile(r"(?:^|/)(?:static/lib|static/src/libs|o_spreadsheet)/")
_TEMPLATE_RULES_SKIPPED_IN_TESTS = {"OWL001", "OWL002", "OWL003", "OWL004", "OWL005", "OWL006", "JS015", "JS017"}


def applicable_rules(kind: str, rel: str) -> list[Rule]:
    """Rules for a file kind, minus the ones that do not make sense at this module-relative path."""
    if rel.startswith(_MIGRATION_DIRS) or _VENDORED.search(rel):
        return []  # migration scripts handle older schemas by design; vendored code is not ours
    rules = rules_for(kind)
    if rel.endswith(".test.js"):
        rules = [r for r in rules if r.id not in _TEMPLATE_RULES_SKIPPED_IN_TESTS]
    return rules


def check_file(path: Path, display: str | None = None, text: str | None = None,
               module_root: Path | None = None, rel: str | None = None) -> list[Finding]:
    if rel is None:
        root = module_root or module_root_of(path)
        rel = path.resolve().relative_to(root.resolve()).as_posix() if root else path.name
        if root is None:
            kind = kind_of(path)
        else:
            kind = file_kind(rel)
    else:
        kind = file_kind(rel)
    if path.name == MANIFEST:
        kind = "manifest"
    if kind in {"lib", "other", "po", "md", "json", "txt", "html", "yaml", "rng", "sql", "ts"}:
        return []
    rules = applicable_rules(kind, rel)
    if not rules:
        return []
    if text is None:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return [Finding("IO", "error", display or str(path), 0, f"cannot read file: {exc}")]
    return check_text(text, kind, display or str(path), rules)


def iter_module_files(root: Path):
    """Yield (path, module-relative posix path) for the files worth checking."""
    import os
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
        rel_dir = "" if rel_dir == "." else rel_dir + "/"
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS
                             and not (rel_dir + d).startswith(("i18n", "static/lib")))
        for fname in sorted(filenames):
            yield Path(dirpath) / fname, rel_dir + fname


def check_tree(root: Path, display_base: Path | None = None) -> list[Finding]:
    findings: list[Finding] = []
    for path, rel in iter_module_files(root):
        disp = str(path.relative_to(display_base)) if display_base else str(path)
        findings.extend(check_file(path, disp, module_root=root, rel=rel))
    return findings


def sort_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.file, f.line, f.rule))


def rule_doc(rule_id: str) -> Rule | None:
    return RULES_BY_ID.get(rule_id)
