"""Small shared helpers: output shaping, suggestions, comment stripping."""
from __future__ import annotations

import difflib
import io
import json
import re
import tokenize
from collections.abc import Iterable, Sequence

MAX_OUTPUT_CHARS = 25_000


try:  # surface our errors as normal tool errors (no "unexpected exception" traceback)
    from mcp.server.mcpserver.exceptions import ToolError as _BaseToolError
except ImportError:  # the validator CLI (PostToolUse hook) may run without the MCP SDK
    _BaseToolError = Exception


class ToolError(_BaseToolError):
    """An error whose message is meant for the model (actionable, no traceback)."""


def truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    cut = text.rfind("\n", 0, limit)
    cut = cut if cut > limit * 0.8 else limit
    omitted = len(text) - cut
    return (
        text[:cut]
        + f"\n\n… output truncated ({omitted} more characters). "
        "Narrow the query (filters, `limit`/`offset`) to see the rest."
    )


def render(data, fmt: str = "markdown", md: str | None = None) -> str:
    """Return JSON when asked, else the provided markdown rendering."""
    if fmt == "json":
        return truncate(json.dumps(data, indent=1, default=str, ensure_ascii=False))
    return truncate(md if md is not None else json.dumps(data, indent=1, default=str))


def suggest(word: str, candidates: Iterable[str], n: int = 5) -> list[str]:
    candidates = list(candidates)
    close = difflib.get_close_matches(word, candidates, n=n, cutoff=0.6)
    if len(close) < n:
        needle = word.lower()
        close += [c for c in candidates if needle in c.lower() and c not in close][: n - len(close)]
    return close


def did_you_mean(kind: str, word: str, candidates: Iterable[str]) -> ToolError:
    hints = suggest(word, candidates)
    msg = f"{kind} {word!r} not found in the index."
    if hints:
        msg += " Did you mean: " + ", ".join(hints) + "?"
    else:
        msg += " Try odoo_search to discover the exact name."
    return ToolError(msg)


def md_table(headers: Sequence[str], rows: Iterable[Sequence]) -> str:
    def cell(v) -> str:
        s = "" if v is None else str(v)
        return s.replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


def page(items: Sequence, limit: int, offset: int) -> tuple[list, str]:
    total = len(items)
    chunk = list(items[offset: offset + limit])
    note = ""
    if offset + len(chunk) < total:
        note = f"\n\n_Showing {offset + 1}–{offset + len(chunk)} of {total}; use offset={offset + len(chunk)} for more._"
    return chunk, note


# --------------------------------------------------------------------------
# Comment stripping that keeps line/column positions (comments -> spaces)
# --------------------------------------------------------------------------

_XML_COMMENT = re.compile(r"<!--.*?-->", re.S)


def _blank(match: re.Match) -> str:
    return re.sub(r"[^\n]", " ", match.group(0))


def strip_xml_comments(text: str) -> str:
    return _XML_COMMENT.sub(_blank, text)


def strip_py_comments(text: str) -> str:
    """Blank out Python comments; strings are kept (they may hold model names)."""
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return re.sub(r"(?m)^\s*#.*$", lambda m: " " * len(m.group(0)), text)
    lines = text.splitlines(keepends=True)
    for tok in tokens:
        if tok.type == tokenize.COMMENT:
            (row, col), (_, ecol) = tok.start, tok.end
            line = lines[row - 1]
            lines[row - 1] = line[:col] + " " * (ecol - col) + line[ecol:]
    return "".join(lines)


def strip_js_comments(text: str) -> str:
    """Blank out // and /* */ comments in JS while respecting strings and templates.

    Regex literals are not tokenized; a `/*` or `//` inside a regex literal is
    rare in Odoo code and only makes the stripper blank a bit too much.
    """
    out = list(text)
    i, n = 0, len(text)
    state = None  # None | "'" | '"' | "`"
    while i < n:
        c = text[i]
        if state:
            if c == "\\":
                i += 2
                continue
            if c == state:
                state = None
            elif state == "`" and c == "$" and i + 1 < n and text[i + 1] == "{":
                # skip template expression roughly (balanced braces)
                depth, i = 1, i + 2
                while i < n and depth:
                    if text[i] == "{":
                        depth += 1
                    elif text[i] == "}":
                        depth -= 1
                    i += 1
                continue
            i += 1
            continue
        if c in "'\"`":
            state = c
            i += 1
            continue
        if c == "/" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "/":
                j = text.find("\n", i)
                j = n if j == -1 else j
                for k in range(i, j):
                    out[k] = " "
                i = j
                continue
            if nxt == "*":
                j = text.find("*/", i + 2)
                j = n if j == -1 else j + 2
                for k in range(i, j):
                    if out[k] != "\n":
                        out[k] = " "
                i = j
                continue
        i += 1
    return "".join(out)


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1
