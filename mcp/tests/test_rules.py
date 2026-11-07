"""Rule catalogue integrity and detection on the fixture addons."""
from collections import Counter

from conftest import CLEAN, LEGACY
from odoo20_mcp.validate.engine import check_file, check_tree
from odoo20_mcp.validate.rules import NEEDLES, RULES, RULES_BY_ID

EXPECTED_LEGACY = {
    "SEC001", "SEC002", "SEC003", "ORM001", "ORM002", "ORM004", "ORM005", "ORM009", "ORM010", "ORM011",
    "ORM012", "ORM013", "ORM025", "XML016", "HTTP006", "HTTP007", "HTTP008", "OWL007", "JS018", "ORM014", "ORM015", "ORM016", "ORM017", "HTTP001", "HTTP004", "TEST001", "REP002",
    "REP003", "XML001", "XML002", "XML003", "XML004", "XML005", "XML006", "XML007", "XML008", "XML009",
    "XML010", "XML012", "XML013", "OWL001", "OWL003", "OWL005", "OWL006", "JS001", "JS002", "JS004", "JS005",
    "JS007", "JS008", "JS009", "JS011", "JS017", "SCSS001", "SCSS002", "MAN001", "MAN002",
}


def test_rule_ids_unique_and_documented(odoo_root):
    ids = [r.id for r in RULES]
    assert len(ids) == len(set(ids))
    for rule in RULES:
        assert rule.severity in {"error", "warning", "info"}, rule.id
        assert rule.title and rule.fix, rule.id
        assert rule.pattern or rule.check, rule.id
        assert (odoo_root / rule.source).exists(), f"{rule.id}: evidence path missing: {rule.source}"
        if rule.fixed_by:
            scripts = {p.stem.split("-", 2)[-1] if p.stem[0].isdigit() else p.stem
                       for p in (odoo_root / "odoo" / "upgrade_code").glob("*.py")}
            full = {p.stem for p in (odoo_root / "odoo" / "upgrade_code").glob("*.py")}
            assert rule.fixed_by in full or rule.fixed_by in scripts, f"{rule.id}: unknown script {rule.fixed_by}"


def test_every_regex_rule_has_needles():
    missing = [r.id for r in RULES if r.pattern and r.id not in NEEDLES]
    assert not missing
    assert set(NEEDLES) <= set(RULES_BY_ID)


def test_legacy_fixture_triggers_each_rule():
    found = {f.rule for f in check_tree(LEGACY)}
    assert EXPECTED_LEGACY - found == set()


def test_clean_fixture_has_no_legacy_findings():
    findings = [f for f in check_tree(CLEAN) if f.severity in {"error", "warning"}]
    assert findings == []


def test_line_numbers_and_comment_suppression(tmp_path):
    mod = tmp_path / "m"
    (mod / "models").mkdir(parents=True)
    (mod / "__manifest__.py").write_text("{'name': 'm'}")
    src = mod / "models" / "a.py"
    src.write_text("x = 1\n# self.toggle_active()\nself.toggle_active()\nself.toggle_active()  # odoo20-ignore: ORM005\n")
    hits = [f for f in check_file(src) if f.rule == "ORM005"]
    assert [f.line for f in hits] == [3]


def test_hook_output(tmp_path, monkeypatch):
    import io
    import json

    from odoo20_mcp import check
    src = LEGACY / "views" / "legacy_views.xml"
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"tool_input": {"file_path": str(src)}})))
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    assert check.hook() == 0
    payload = json.loads(out.getvalue())
    text = payload["hookSpecificOutput"]["additionalContext"]
    assert "XML001" in text and "legacy_views.xml" in text


def test_severity_mix_is_sane():
    counts = Counter(f.severity for f in check_tree(LEGACY))
    assert counts["error"] > 30
