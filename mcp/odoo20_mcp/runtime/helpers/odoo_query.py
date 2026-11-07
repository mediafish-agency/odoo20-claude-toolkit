"""Read-only queries against an Odoo 20 database (run with the Odoo interpreter, never commits).

Usage: python odoo_query.py '<json payload>'; prints one line '@@ODOO20@@<json>'.
"""
import json
import sys
import traceback

payload = json.loads(sys.argv[1])
sys.path.insert(0, payload["odoo_root"])


def out(obj):
    print("@@ODOO20@@" + json.dumps(obj, default=str))


def main():
    import odoo.cli  # noqa: F401  (same bootstrap as odoo-bin)
    from odoo import api
    from odoo.api import SUPERUSER_ID
    from odoo.tools import config

    op = payload["op"]
    args = ["-c", payload["conf"]] + (["-d", payload["db"]] if payload.get("db") else [])
    config.parse_config(args, setup_logging=False)
    if op == "list_dbs":
        from odoo.modules import db as dbmod
        return {"databases": dbmod.list_dbs(force=True)}
    from odoo.modules.registry import Registry
    registry = Registry(payload["db"])
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        try:
            if op == "combined_arch":
                view = env.ref(payload["xmlid"], raise_if_not_found=False)
                if not view or view._name != "ir.ui.view":
                    return {"error": f"view {payload['xmlid']!r} not found in database {payload['db']!r} (module installed?)"}
                root = view
                while root.inherit_id and root.mode != "primary":
                    root = root.inherit_id
                return {"xmlid": payload["xmlid"], "root": root.get_external_id().get(root.id), "model": root.model,
                        "type": root.type, "arch": root.get_combined_arch()}
            if op == "asset_paths":
                paths = env["ir.asset"]._get_asset_paths(payload["bundle"], payload.get("assets_params") or {})
                return {"bundle": payload["bundle"], "paths": [[p[0], p[1]] if len(p) > 1 else [p[0], None] for p in paths]}
            if op == "fields_get":
                model = payload["model"]
                if model not in env:
                    return {"error": f"model {model!r} is not installed in database {payload['db']!r}"}
                attrs = payload.get("attributes") or ["type", "string", "relation", "required", "readonly", "store",
                                                      "compute", "related", "groups", "selection", "help"]
                return {"model": model, "fields": env[model].fields_get(attributes=attrs)}
            if op == "xmlid":
                rec = env["ir.model.data"].sudo().search_read(
                    [("module", "=", payload["xmlid"].split(".")[0]), ("name", "=", payload["xmlid"].split(".", 1)[1])],
                    ["model", "res_id", "noupdate"], limit=1)
                return {"xmlid": payload["xmlid"], "data": rec}
            if op == "modules":
                mods = env["ir.module.module"].search_read([("state", "in", payload.get("states") or ["installed"])],
                                                          ["name", "state", "latest_version"], order="name")
                return {"modules": mods}
            return {"error": f"unknown op {op!r}"}
        finally:
            cr.rollback()


try:
    out(main())
except Exception as exc:  # noqa: BLE001
    out({"error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()[-3000:]})
