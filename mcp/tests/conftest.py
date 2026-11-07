import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

MCP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MCP_DIR))
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "addons"
CLEAN = FIXTURES / "odoo20_clean_demo"
LEGACY = FIXTURES / "odoo19_legacy_demo"


def _seed_from_installed_index(target: Path) -> None:
    """Start from the plugin's installed index when it covers the same Odoo tree (incremental build: fast)."""
    from odoo20_mcp import config
    runtime = config.existing_runtime_dir()
    installed = runtime / "index.sqlite3" if runtime else None
    if not installed or not installed.exists():
        return
    root = os.environ.get("ODOO20_ROOT")
    if root:
        try:
            con = sqlite3.connect(f"file:{installed}?mode=ro", uri=True)
            roots = json.loads(con.execute("SELECT value FROM meta WHERE key='roots'").fetchone()[0])
            con.close()
        except (sqlite3.Error, TypeError, ValueError):
            return
        if str(Path(root).expanduser().resolve() / "addons") not in roots:
            return
    shutil.copy(installed, target)


@pytest.fixture(scope="session")
def index(tmp_path_factory):
    """Index of the Odoo tree + the fixture addons (reuses the installed index as a starting point)."""
    data = tmp_path_factory.mktemp("odoo20data")
    from odoo20_mcp import config, context
    _seed_from_installed_index(data / "index.sqlite3")
    os.environ["ODOO20_DATA_DIR"] = str(data)
    os.environ["ODOO20_EXTRA_ADDONS"] = str(FIXTURES)
    config.get_config.cache_clear()
    context.config.cache_clear()
    context.index.cache_clear()
    if not context.config().has_odoo_root:
        pytest.exit("no Odoo 20 tree: set ODOO20_ROOT=/path/to/odoo (the folder containing odoo-bin)", returncode=2)
    im = context.index()
    im.build()
    return im


@pytest.fixture(scope="session")
def con(index):
    return index.db()


@pytest.fixture(scope="session")
def odoo_root(index):
    from odoo20_mcp import context
    return context.config().odoo_root
