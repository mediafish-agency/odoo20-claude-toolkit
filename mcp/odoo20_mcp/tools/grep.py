"""Code search: `git grep` where the root is a git work tree, a Python walk otherwise."""
from __future__ import annotations

import os
import re
import subprocess
from functools import cache
from pathlib import Path

from ..util import ToolError

EXCLUDES = ("**/i18n/**", "**/static/lib/**", "**/node_modules/**")


@cache
def _git_toplevel(root: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", root, "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                             timeout=10, check=False)
        return out.stdout.strip() or None if out.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def grep(roots: list[Path], pattern: str, *, regex: bool, ignore_case: bool, subpaths: list[str],
         glob: str | None, context: int, limit: int, include_vendor: bool) -> tuple[list[str], int]:
    """Return (output lines, number of matching lines). ``subpaths`` are paths relative to each root."""
    if regex:
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ToolError(f"invalid regular expression: {exc}") from exc
    lines: list[str] = []
    matches = 0
    for root in roots:
        top = _git_toplevel(str(root))
        if top:
            got, n = _git_grep(Path(top), root, pattern, regex, ignore_case, subpaths, glob, context,
                               limit - matches, include_vendor)
        else:
            got, n = _py_grep(root, pattern, regex, ignore_case, subpaths, glob, context, limit - matches,
                              include_vendor)
        lines += got
        matches += n
        if matches >= limit:
            break
    return lines, matches


def _git_grep(top: Path, root: Path, pattern, regex, ignore_case, subpaths, glob, context, limit, include_vendor):
    rel_root = os.path.relpath(root, top)
    rel_root = "" if rel_root == "." else rel_root + "/"
    specs = []
    for sub in subpaths or [""]:
        base = f"{rel_root}{sub}".rstrip("/")
        if glob:
            specs.append(f":(glob){base}/**/{glob}" if base else f":(glob)**/{glob}")
        else:
            specs.append(base or ".")
    if not include_vendor:
        specs += [f":(exclude,glob){e}" for e in EXCLUDES]
    cmd = ["git", "-C", str(top), "grep", "-n", "-I", "--no-color", "--untracked", "--full-name"]
    cmd += ["-i"] if ignore_case else []
    cmd += ["-P"] if regex else ["-F"]  # PCRE: same \b \d \w syntax as Python
    cmd += [f"-C{context}"] if context else []
    cmd += ["-e", pattern, "--", *specs]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False, errors="replace")
    except subprocess.TimeoutExpired as exc:
        raise ToolError("search timed out; narrow it with `module` or `glob`") from exc
    out, n = [], 0
    for line in proc.stdout.splitlines():
        if line == "--":
            out.append("--")
            continue
        m = re.match(r"^(.*?)([:-])(\d+)\2(.*)$", line)
        if not m:
            continue
        if m.group(2) == ":":
            n += 1
            if n > limit:
                break
        out.append(f"{m.group(1)}:{m.group(3)}{'' if m.group(2) == ':' else '-'} {m.group(4)[:300]}")
    return out, min(n, limit)


def _py_grep(root: Path, pattern, regex, ignore_case, subpaths, glob, context, limit, include_vendor):
    flags = re.I if ignore_case else 0
    rx = re.compile(pattern if regex else re.escape(pattern), flags)
    out, n = [], 0
    for sub in subpaths or [""]:
        base = root / sub
        files = base.rglob(glob or "*") if base.is_dir() else [base]
        for path in files:
            if not path.is_file() or (not include_vendor and any(p in path.parts for p in ("i18n", "lib", "node_modules"))):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="strict").splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            for i, line in enumerate(text):
                if rx.search(line):
                    n += 1
                    for j in range(max(0, i - context), min(len(text), i + context + 1)):
                        out.append(f"{path}:{j + 1}{'' if j == i else '-'} {text[j][:300]}")
                    if n >= limit:
                        return out, n
    return out, n
