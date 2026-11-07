from conftest import CLEAN, LEGACY
from odoo20_mcp.validate.rng import check_data_file


def test_clean_module_data_files_pass(odoo_root):
    for rel in ("views/library_book_views.xml", "views/library_menus.xml"):
        assert check_data_file(CLEAN / rel, rel, odoo_root) == []


def test_legacy_views_rejected_by_odoo_rng(odoo_root):
    findings = check_data_file(LEGACY / "views/legacy_views.xml", "legacy_views.xml", odoo_root)
    rules = {f.rule for f in findings}
    assert "RNG002" in rules  # search filter start_month / calendar date_delay
    assert any("search" in f.message for f in findings)
    assert any("calendar" in f.message for f in findings)
