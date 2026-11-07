"""Index-backed checks on the fixture addons."""
from odoo20_mcp.validate.semantic import check_module


def test_clean_module_has_no_semantic_errors(con, odoo_root):
    findings = check_module(con, odoo_root, "odoo20_clean_demo")
    assert [f for f in findings if f.severity in {"error", "warning"}] == []


def test_legacy_module_semantic_findings(con, odoo_root):
    findings = check_module(con, odoo_root, "odoo19_legacy_demo")
    rules = {f.rule for f in findings}
    for expected in ("MAN102", "MAN104", "MAN105", "VIEW002", "VIEW004", "REF001", "JSI001", "JSI003", "SEC106", "PYI001"):
        assert expected in rules, (expected, sorted(rules))
    view_errors = {f.message for f in findings if f.rule == "VIEW002"}
    assert any("missing_field" in m for m in view_errors)
    ref = [f for f in findings if f.rule == "REF001"]
    assert any("mail.menu_root_discuss" in f.message for f in ref)


def test_missing_dependency_and_removed_template(con, odoo_root):
    """depends=['base'] still installs `web` (auto_install), so web.* refs are in scope: the removed
    web.external_layout_boxed layout is reported as not found, while mail.* is a missing dependency."""
    findings = check_module(con, odoo_root, "odoo19_legacy_demo")
    assert any(f.rule == "REF003" and "web.external_layout_boxed" in f.message for f in findings)
    assert not any(f.rule == "REF001" and "web." in f.message for f in findings)
    assert any(f.rule == "REF001" and "mail.menu_root_discuss" in f.message for f in findings)
