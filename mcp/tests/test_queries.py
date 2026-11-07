"""Query layer against the real Odoo 20 tree."""
import re

from odoo20_mcp.query import core as q


def test_load_order_mirrors_module_graph(con):
    g = q.graph(con)
    assert g.order["base"] == 0
    assert g.order["web"] < g.order["sale"] < g.order["sale_stock"]


def test_merged_sale_order(con):
    info = q.model_info(con, "sale.order", q.scope_modules(con, None))
    assert "mail.thread" in info["parents"] or "mail.activity.mixin" in info["parents"]
    fields = info["fields"]
    assert fields["partner_id"]["comodel"] == "res.partner"
    assert fields["message_ids"]["origin"] == "mail.thread"
    assert "picking_ids" in fields  # added by sale_stock


def test_scope_module_limits_fields(con):
    scope = q.scope_modules(con, "sale")
    fields = q.merged_fields(con, "sale.order", scope)
    assert "picking_ids" not in fields


def test_install_closure_includes_auto_install(con):
    g = q.graph(con)
    assert "base_setup" in g.install_closure("web")


def test_method_chain_order(con):
    chain = q.method_chain(con, "sale.order", "action_confirm", q.scope_modules(con, None))
    modules = [c["module"] for c in chain]
    assert modules[-1] == "sale" or "sale" in modules
    g = q.graph(con)
    own = [c for c in chain if c["via"] == "sale.order"]
    orders = [g.order[c["module"]] for c in own]
    assert orders == sorted(orders, reverse=True)


def test_view_tree(con):
    tree = q.view_tree(con, "sale.view_order_form")
    assert tree["root"]["view"]["xmlid"] == "sale.view_order_form"
    assert len(tree["root"]["children"]) > 10


def test_access_rows_match_csv(con, odoo_root):
    rows = q.access_rows(con, "sale.order")
    sale_rows = [r for r in rows if r["module"] == "sale" and r["source"] == "csv"]
    csv_lines = [line for line in (odoo_root / "addons/sale/security/ir.access.csv").read_text().splitlines()[1:]
                 if ",sale.order," in line]
    assert len(sale_rows) == len(csv_lines)


def test_backend_bundle_has_owl_compat(con):
    entries = q.asset_entries(con, "web._assets_core", None)
    assert any("owl3_compatibility_layer.js" in (e["path"] or "") for e in entries)


def test_fields_registry_matches_independent_parse(con, odoo_root):
    """Independent parse of registry.category("fields").add("key" (multi-line chains and variables) in web."""
    keys = set()
    base = odoo_root / "addons/web/static/src/views/fields"
    for path in base.rglob("*.js"):
        text = path.read_text(encoding="utf-8")
        keys |= set(re.findall(r'category\(\s*"fields"\s*\)\s*\.add\(\s*"([\w.]+)"', text, re.S))
        for var in re.findall(r'(\w+)\s*=\s*registry\s*\.\s*category\(\s*"fields"\s*\)', text):
            keys |= set(re.findall(var + r'\s*\.\s*add\(\s*"([\w.]+)"', text, re.S))
    indexed = {r["key"] for r in con.execute(
        "SELECT key FROM js_registry WHERE category='fields' AND module='web' AND file LIKE 'static/src/views/fields/%'")}
    assert len(keys) > 50
    assert keys - indexed == set()
