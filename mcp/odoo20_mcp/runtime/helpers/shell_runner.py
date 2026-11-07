"""Run Python code in an Odoo 20 environment (odoo_shell tool).

The transaction is rolled back unless payload['commit'] is true; while the code runs, cr.commit()
raises unless commits are allowed, so user code cannot persist changes behind the tool's back.
"""
import contextlib
import io
import json
import sys
import traceback

payload = json.loads(sys.argv[1])
sys.path.insert(0, payload["odoo_root"])


def out(obj):
    print("@@ODOO20@@" + json.dumps(obj, default=str))


def main():
    import odoo.cli  # noqa: F401
    from odoo import api
    from odoo.api import SUPERUSER_ID
    from odoo.modules.registry import Registry
    from odoo.tools import config

    config.parse_config(["-c", payload["conf"], "-d", payload["db"]], setup_logging=False)
    registry = Registry(payload["db"])
    stdout = io.StringIO()
    with registry.cursor() as cr:
        uid = payload.get("uid") or SUPERUSER_ID
        ctx = api.Environment(cr, uid, {})["res.users"].context_get()
        env = api.Environment(cr, uid, ctx)
        real_commit = cr.commit
        allow_commit = bool(payload.get("commit"))

        def guarded_commit():
            if not allow_commit:
                raise PermissionError("cr.commit() is disabled in odoo_shell unless commit=true and allow_writes=true")
            return real_commit()
        cr.commit = guarded_commit
        namespace = {"env": env, "self": env.user, "odoo": sys.modules["odoo"], "api": api, "result": None}
        error = None
        with contextlib.redirect_stdout(stdout):
            try:
                exec(compile(payload["code"], "<odoo_shell>", "exec"), namespace)  # noqa: S102 - the tool's purpose
                if allow_commit:
                    env.flush_all()
                    real_commit()
            except Exception:  # noqa: BLE001
                error = traceback.format_exc()[-4000:]
        if not allow_commit or error:
            cr.rollback()
        result = namespace.get("result")
        return {"stdout": stdout.getvalue()[-20000:], "result": repr(result)[:5000] if result is not None else None,
                "error": None, "exception": error, "committed": allow_commit and not error}


try:
    out(main())
except Exception as exc:  # noqa: BLE001
    out({"error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()[-3000:]})
