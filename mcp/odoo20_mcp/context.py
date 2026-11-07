"""Process-wide singletons shared by the tools."""
from __future__ import annotations

import re
from functools import cache

from .config import Config, get_config
from .index.store import IndexManager


@cache
def config() -> Config:
    return get_config()


@cache
def index() -> IndexManager:
    return IndexManager(config())


def odoo_version() -> str:
    if not config().has_odoo_root:
        return "unknown (no usable Odoo source tree)"
    try:
        text = (config().odoo_root / "odoo" / "release.py").read_text(encoding="utf-8")
        m = re.search(r"^version_info\s*=\s*\((\d+),\s*(\d+)", text, re.M)
        return f"{m.group(1)}.{m.group(2)}" if m else "unknown"
    except OSError:
        return "unknown (odoo/release.py not found)"
