"""Calibration against the real Odoo 20 core: Odoo's own code must not raise false errors.

Run with:  pytest -m slow   (about a minute)
"""
import pytest
from odoo20_mcp.validate.engine import check_tree
from odoo20_mcp.validate.semantic import check_module

# Genuine upstream problems in Odoo 20.0 (c8a62e5f) that the checks rightly report.
KNOWN_UPSTREAM = {
    ("PARSE", "odoo/addons/test_assetsbundle/static/accessible.xml"),          # intentionally invalid fixtures
    ("PARSE", "odoo/addons/test_assetsbundle/static/invalid_src/xml/invalid_xml.xml"),
    ("PARSE", "odoo/addons/test_assetsbundle/static/invalid_src/xml/second_invalid_xml.xml"),
    # named imports that the target module does not export (resolve to undefined at runtime)
    ("JSI003", "addons/html_editor/static/tests/utils/selection.test.js"),
    ("JSI003", "addons/mail/static/src/core/common/thread.js"),
    ("JSI003", "addons/mail/static/tests/chatter/web/chatter.test.js"),
    ("JSI003", "addons/mail/static/tests/chatter/web/chatter_topbar.test.js"),
    ("JSI003", "addons/point_of_sale/static/tests/unit/tools/lazy_getter.test.js"),
    ("JSI003", "addons/web/static/src/views/kanban/kanban_record.js"),
    ("JSI003", "addons/web/static/tests/core/utils/indexed_db.test.js"),
    ("JSI003", "addons/web/static/tests/views/fields/parsers.test.js"),
}

pytestmark = pytest.mark.slow


def test_core_has_no_legacy_errors(odoo_root):
    errors = []
    for base in (odoo_root / "addons", odoo_root / "odoo" / "addons"):
        for mod in sorted(base.iterdir()):
            if (mod / "__manifest__.py").exists():
                errors += [f for f in check_tree(mod, odoo_root) if f.severity == "error"]
    assert [(f.rule, f.file, f.line) for f in errors] == []


def test_core_has_no_semantic_errors(con, odoo_root):
    unexpected = []
    for (module,) in con.execute("SELECT name FROM modules WHERE path LIKE ?", (f"{odoo_root}/%",)).fetchall():
        for f in check_module(con, odoo_root, module):
            if f.severity == "error" and (f.rule, f.file) not in KNOWN_UPSTREAM:
                unexpected.append((f.rule, f.file, f.line, f.message))
    assert unexpected == []
