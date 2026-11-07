"""Runtime configuration.

Values come from environment variables that the plugin's ``.mcp.json`` fills
from ``userConfig`` (``${user_config.*}``). An empty value, or a placeholder
that was not substituted, means "use the default". The same ``ODOO20_*``
variables configure the server when it runs outside Claude Code.
"""
from __future__ import annotations

import fnmatch
import os
import pwd
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

DEFAULT_ODOO_PYTHON = "~/.venvs/odoo20/bin/python"
DEFAULT_DB_ALLOW = "odoo20_*"
STANDALONE_DATA_DIR = "~/.claude/plugins/data/odoo20-standalone"
TEMPLATE_DB = "odoo20_tmpl"
# Placeholder used when no Odoo 20 tree is configured or detected: it never exists and never contains a path.
UNSET_ROOT = Path("/nonexistent/odoo20-root-not-configured")
ROOT_HELP = (
    "No Odoo 20 source tree configured. Set the plugin option odoo_root to the folder that contains odoo-bin "
    "(claude plugin configure odoo20@mediafish-odoo), or set ODOO20_ROOT when running the server standalone."
)
# odoo.conf keys copied from the user's own config (plugin option odoo_config) into the generated one.
DB_CONF_KEYS = ("db_host", "db_port", "db_user", "db_password", "db_sslmode", "pg_path")


# Hooks receive plugin options as CLAUDE_PLUGIN_OPTION_<KEY>; the MCP server gets ODOO20_* from .mcp.json.
_OPTION_FALLBACK = {
    "ODOO20_ROOT": "ODOO_ROOT", "ODOO20_EXTRA_ADDONS": "EXTRA_ADDONS_PATHS", "ODOO20_PYTHON": "ODOO_PYTHON",
    "ODOO20_DB_ALLOW": "DB_ALLOW", "ODOO20_ALLOW_WRITES": "ALLOW_WRITES", "ODOO20_LIVE_URL": "LIVE_URL",
    "ODOO20_LIVE_DB": "LIVE_DB", "ODOO20_LIVE_API_KEY": "LIVE_API_KEY", "ODOO20_ODOO_CONFIG": "ODOO_CONFIG",
}


def _env(name: str, default: str = "") -> str:
    for key in (name, f"CLAUDE_PLUGIN_OPTION_{_OPTION_FALLBACK[name]}" if name in _OPTION_FALLBACK else None):
        if not key:
            continue
        value = os.environ.get(key, "").strip()
        if value and not value.startswith("${"):
            return value
    return default


def _bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _split_paths(value: str) -> list[Path]:
    parts: list[str] = []
    for chunk in value.replace("\n", ",").split(","):
        # accept both "a,b" and "a:b" (but keep Windows-like drive letters out of scope)
        parts.extend(p for p in chunk.split(":") if p.strip())
    return [Path(os.path.expanduser(p.strip())).resolve() for p in parts]


def odoo_major(root: Path) -> int | None:
    """Major version of the Odoo tree at ``root`` (from odoo/release.py), or None."""
    try:
        text = (root / "odoo" / "release.py").read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r"^version_info\s*=\s*\((\d+)", text, re.M)
    return int(m.group(1)) if m else None


def _is_odoo20(path: Path) -> bool:
    return (path / "odoo-bin").is_file() and odoo_major(path) == 20


def detect_odoo_root() -> Path | None:
    """Find an Odoo 20 tree near the project: the project dir or one of its 2 parents, or a child ``odoo*``
    folder of those (layouts like ``project/{odoo,enterprise,custom}``). Only Odoo 20 trees qualify."""
    starts = []
    for raw in (os.environ.get("CLAUDE_PROJECT_DIR"), os.getcwd()):
        if raw and (path := Path(raw).resolve()) not in starts:
            starts.append(path)
    for start in starts:
        for base in (start, *list(start.parents)[:2]):
            if _is_odoo20(base):
                return base
            try:
                children = sorted(c for c in base.iterdir() if c.is_dir() and c.name.lower().startswith("odoo"))
            except OSError:
                continue
            for child in children:
                if _is_odoo20(child):
                    return child
    return None


def real_home() -> Path:
    """Home of the real user; HOME may be overridden (eval sandboxes, sudo, containers)."""
    try:
        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    except (KeyError, OSError):
        return Path.home()


def existing_runtime_dir() -> Path | None:
    """First odoo20 plugin data dir (under HOME, then the real home) that already holds an installed runtime."""
    for home in dict.fromkeys((Path.home(), real_home())):
        for candidate in sorted((home / ".claude" / "plugins" / "data").glob("odoo20-*")):
            if (candidate / "venv" / "bin" / "python").exists():
                return candidate
    return None


def default_data_dir() -> Path:
    """Where the venv, index, generated odoo.conf and job logs live (same order as odoo20_data_dir in
    scripts/lib.sh): explicit ODOO20_DATA_DIR, our plugin data dir when it holds a runtime, any installed
    odoo20 runtime dir, our plugin data dir, the standalone dir."""
    if explicit := _env("ODOO20_DATA_DIR"):
        return Path(os.path.expanduser(explicit))
    ours = Path(plugin_dir) if (plugin_dir := _plugin_data_dir()) else None
    if ours and (ours / "venv" / "bin" / "python").exists():
        return ours
    return existing_runtime_dir() or ours or Path(os.path.expanduser(STANDALONE_DATA_DIR))


@dataclass(frozen=True)
class Config:
    odoo_root: Path
    extra_addons: tuple[Path, ...]
    odoo_python: Path
    db_allow: tuple[str, ...]
    allow_writes: bool
    live_url: str
    live_db: str
    live_api_key: str
    data_dir: Path
    odoo_config: Path | None = None
    odoo_root_source: str = "option"  # option | detected | unset | invalid
    invalid_root_option: Path | None = None  # odoo_root option that has no odoo-bin (detection used instead)

    # -- derived -----------------------------------------------------------
    @property
    def core_addons(self) -> tuple[Path, ...]:
        return (self.odoo_root / "odoo" / "addons", self.odoo_root / "addons")

    @property
    def addons_paths(self) -> tuple[Path, ...]:
        """Addons directories in resolution order (first match wins)."""
        seen: list[Path] = []
        for path in (*self.core_addons, *self.extra_addons):
            if path.is_dir() and path not in seen:
                seen.append(path)
        return tuple(seen)

    @property
    def odoo_bin(self) -> Path:
        return self.odoo_root / "odoo-bin"

    @property
    def has_odoo_root(self) -> bool:
        return self.odoo_bin.is_file()

    def root_problem(self) -> str | None:
        """Why there is no usable Odoo tree (None when there is one)."""
        if self.has_odoo_root:
            return None
        if self.odoo_root_source == "unset":
            return ROOT_HELP
        return (f"The plugin option odoo_root is {self.odoo_root}, which has no odoo-bin. Set it to the folder "
                "that contains odoo-bin (claude plugin configure odoo20@mediafish-odoo), then /reload-plugins.")

    @property
    def index_path(self) -> Path:
        return self.data_dir / "index.sqlite3"

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    @property
    def odoo_conf(self) -> Path:
        return self.data_dir / "odoo20.conf"

    def db_allowed(self, db: str) -> bool:
        return bool(db) and any(fnmatch.fnmatchcase(db, pat) for pat in self.db_allow)

    def is_core_path(self, path: str | Path) -> bool:
        try:
            Path(path).resolve().relative_to(self.odoo_root.resolve())
        except ValueError:
            return False
        return True

    def in_known_roots(self, path: str | Path) -> bool:
        resolved = Path(path).resolve()
        for root in (self.odoo_root, *self.extra_addons):
            try:
                resolved.relative_to(root.resolve())
                return True
            except ValueError:
                continue
        return False

    def describe(self) -> dict:
        """Configuration summary safe to show (no secrets)."""
        return {
            "odoo_root": str(self.odoo_root) if self.odoo_root_source != "unset" else None,
            "odoo_root_source": self.odoo_root_source,
            "invalid_root_option": str(self.invalid_root_option) if self.invalid_root_option else None,
            "addons_paths": [str(p) for p in self.addons_paths],
            "odoo_python": str(self.odoo_python),
            "odoo_python_exists": self.odoo_python.exists(),
            "db_allow": list(self.db_allow),
            "allow_writes": self.allow_writes,
            "live_url": self.live_url or None,
            "live_db": self.live_db or None,
            "live_api_key": "set" if self.live_api_key else "unset",
            "odoo_config": str(self.odoo_config) if self.odoo_config else None,
            "data_dir": str(self.data_dir),
        }


def _plugin_data_dir() -> str:
    """CLAUDE_PLUGIN_DATA, but only when it is this plugin's (another plugin's hook env may leak it)."""
    value = _env("CLAUDE_PLUGIN_DATA")
    return value if value and Path(value).name.startswith("odoo20-") else ""


@cache
def get_config() -> Config:
    data_dir = default_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    invalid = None
    if raw_root := _env("ODOO20_ROOT"):
        odoo_root, source = Path(os.path.expanduser(raw_root)).resolve(), "option"
        if not (odoo_root / "odoo-bin").is_file():
            # a mistyped or stale option: use an Odoo 20 tree found near the project, and say so
            invalid = odoo_root
            detected = detect_odoo_root()
            odoo_root, source = (detected, "detected") if detected else (odoo_root, "invalid")
    elif detected := detect_odoo_root():
        odoo_root, source = detected, "detected"
    else:
        odoo_root, source = UNSET_ROOT, "unset"
    raw_conf = _env("ODOO20_ODOO_CONFIG")
    return Config(
        odoo_root=odoo_root,
        odoo_root_source=source,
        invalid_root_option=invalid,
        odoo_config=Path(os.path.expanduser(raw_conf)).resolve() if raw_conf else None,
        extra_addons=tuple(_split_paths(_env("ODOO20_EXTRA_ADDONS"))),
        odoo_python=Path(os.path.expanduser(_env("ODOO20_PYTHON", DEFAULT_ODOO_PYTHON))),
        db_allow=tuple(p.strip() for p in _env("ODOO20_DB_ALLOW", DEFAULT_DB_ALLOW).split(",") if p.strip()),
        allow_writes=_bool(_env("ODOO20_ALLOW_WRITES", "false")),
        live_url=_env("ODOO20_LIVE_URL").rstrip("/"),
        live_db=_env("ODOO20_LIVE_DB"),
        live_api_key=_env("ODOO20_LIVE_API_KEY"),
        data_dir=data_dir,
    )
