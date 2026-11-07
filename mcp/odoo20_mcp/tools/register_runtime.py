"""Registration of the authoring, runtime and live tools."""
from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.types import ToolAnnotations
from pydantic import Field

from . import runtime as rt
from . import scaffold as sc

READ_DB = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
WRITE_FILES = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False)
LIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True)

Db = Annotated[str | None, Field(description="Allowlisted database (default: live_db option, else the odoo20_tmpl template)")]
Wait = Annotated[int, Field(ge=0, le=900, description="Seconds to wait for completion before returning a job id")]


def register(server) -> None:
    @server.tool(annotations=DESTRUCTIVE, structured_output=False)
    def odoo_upgrade_code(
        path: Annotated[str, Field(description="Your addon directory (or a folder of addons). Never the Odoo tree.")],
        from_version: Annotated[str, Field(description="Version the code was written for")] = "19.0",
        include_owl3: Annotated[bool, Field(description="Also run the owl3-migration script when the addon has static/")] = True,
        script: Annotated[str | None, Field(description="Run only this script (name fragment, e.g. 'ir-access', "
                                                       "'owl3-migration', 'material-symbols')")] = None,
        apply: Annotated[bool, Field(description="Write the changes back (default: dry run returning a diff)")] = False,
        max_diff_lines: Annotated[int, Field(ge=20, le=2000, description="Diff lines per file")] = 300,
    ) -> str:
        """Run Odoo's own upgrade_code scripts (odoo/upgrade_code) on a sandbox copy of your addon and return a
        unified diff: 19.x -> 20.0 rewrites (t-call params, base64->bytes, ir.model.access+ir.rule -> ir.access,
        ormcache, Material Symbols icons, search date filters) plus OWL 2 -> 3. apply=true writes the result.
        Then run odoo_validate for what the scripts do not cover."""
        return rt.upgrade_code(path, from_version, include_owl3, script, apply, max_diff_lines)

    @server.tool(annotations=WRITE_FILES, structured_output=False)
    def odoo_scaffold(
        name: Annotated[str, Field(description="Technical module name (snake_case)")],
        dest: Annotated[str, Field(description="Existing addons folder to create the module in")],
        model: Annotated[str | None, Field(description="Main model, e.g. 'library.book'")] = None,
        label: Annotated[str | None, Field(description="Human name, e.g. 'Library Books'")] = None,
        features: Annotated[str, Field(description="Comma list of: views, mail, owl, report, controller, wizard, "
                                                   "interaction, tests (default views,tests)")] = "views,tests",
    ) -> str:
        """Create an Odoo 20 module skeleton that installs and passes its tests as generated: model with
        models.Constraint, security/ir.access.csv (permission + multi-company restriction), list/form/search
        views with <chatter/>, action with path, menus, optional OWL 3 field widget + Hoot test, PDF report,
        JSON controller, wizard, website Interaction, Python tests."""
        return sc.scaffold(name, dest, model, label, features)

    @server.tool(annotations=DESTRUCTIVE, structured_output=False)
    def odoo_db(
        action: Annotated[Literal["list", "create_template", "create", "install", "upgrade", "neutralize", "drop"],
                          Field(description="list databases; create_template (odoo20_tmpl: base+web); create a DB "
                                            "(copy of the template); install/upgrade modules; neutralize; drop")],
        name: Annotated[str | None, Field(description="Database (must match the allowlist, default odoo20_*)")] = None,
        modules: Annotated[str, Field(description="Comma list of modules for create/install/upgrade")] = "",
        with_demo: Annotated[bool, Field(description="Load demo data (create_template/create from scratch)")] = False,
        wait: Wait = 120,
    ) -> str:
        """Manage allowlisted Odoo 20 databases with odoo-bin (db init/duplicate/drop, module install/upgrade,
        neutralize). Databases outside the allowlist are never touched. Long operations return a job id."""
        return rt.db_tool(action, name, modules, with_demo, wait)

    @server.tool(annotations=DESTRUCTIVE, structured_output=False)
    def odoo_test(
        modules: Annotated[str, Field(description="Comma list of modules to install and test")],
        test_tags: Annotated[str | None, Field(description="--test-tags spec (default '/module' for each module), "
                                                           "e.g. '/sale:TestSaleOrder.test_x', 'post_install', '-at_install'")] = None,
        db: Annotated[str | None, Field(description="Existing allowlisted DB to update+test (default: throwaway copy "
                                                    "of odoo20_tmpl, dropped afterwards)")] = None,
        keep_db: Annotated[bool, Field(description="Keep the throwaway database for inspection")] = False,
        install: Annotated[bool, Field(description="With db: install (-i) instead of update (-u)")] = False,
        timeout: Annotated[int, Field(ge=60, le=7200, description="Kill the run after N seconds")] = 1800,
        wait: Wait = 300,
        js_tests: Annotated[bool, Field(description="Also run the modules' Hoot JS unit tests (web WebSuite in "
                                                    "headless Chrome; slower)")] = False,
    ) -> str:
        """Install/update modules and run their tests with odoo-bin (--test-tags, --stop-after-init) on a throwaway
        copy of the template database. Returns pass/fail counts and failure tracebacks (or a job id to poll)."""
        return rt.test_tool(modules, test_tags, db, keep_db, install, timeout, wait, js_tests)

    @server.tool(annotations=READ_DB, structured_output=False)
    def odoo_job(
        job_id: Annotated[str | None, Field(description="Job id (omit to list this session's jobs)")] = None,
        action: Annotated[Literal["status", "log", "cancel"], Field(description="status, log tail, or cancel")] = "status",
        lines: Annotated[int, Field(ge=10, le=2000, description="Log lines for action=log")] = 120,
        grep: Annotated[str | None, Field(description="Regex filter for action=log, e.g. 'ERROR|FAIL'")] = None,
    ) -> str:
        """Status, log tail or cancellation of a background job started by odoo_test / odoo_db / odoo_server."""
        return rt.job_tool(job_id, action, lines, grep)

    @server.tool(annotations=DESTRUCTIVE, structured_output=False)
    def odoo_server(
        action: Annotated[Literal["start", "stop", "status", "logs"], Field(description="Server action")] = "status",
        db: Annotated[str | None, Field(description="Allowlisted database to serve")] = None,
        port: Annotated[int, Field(ge=1024, le=65535)] = 8070,
        dev: Annotated[str, Field(description="--dev features: access, qweb, xml (reload needs watchdog)")] = "xml,qweb,access",
        update: Annotated[str, Field(description="Modules to update (-u) at start")] = "",
    ) -> str:
        """Run an Odoo 20 development server on 127.0.0.1 for an allowlisted database (for browsing, the JSON-2
        live tool, tours, or browser debugging with the chrome-devtools MCP)."""
        return rt.server_tool(action, db, port, dev, update)

    @server.tool(annotations=DESTRUCTIVE, structured_output=False)
    def odoo_shell(
        db: Annotated[str, Field(description="Allowlisted database")],
        code: Annotated[str, Field(description="Python run with `env` (superuser); print() output and the variable "
                                               "`result` are returned")],
        commit: Annotated[bool, Field(description="Commit the transaction (needs allow_writes); default rolls back")] = False,
        timeout: Annotated[int, Field(ge=10, le=1800)] = 180,
    ) -> str:
        """Execute Python in an Odoo 20 environment (like odoo-bin shell) to inspect real data or behaviour.
        Rolled back unless commit=true and the allow_writes option is on; cr.commit() inside the code is blocked."""
        return rt.shell_tool(db, code, commit, timeout)

    @server.tool(annotations=LIVE, structured_output=False)
    def odoo_live_call(
        model: Annotated[str, Field(description="Model, e.g. 'res.partner'")],
        method: Annotated[str, Field(description="Public method, e.g. 'search_read', 'fields_get', 'action_confirm'")],
        ids: Annotated[list[int] | None, Field(description="Record ids (for record methods)")] = None,
        kwargs: Annotated[dict[str, Any] | None, Field(description="Keyword arguments, e.g. {'domain': [...], "
                                                                   "'fields': [...], 'limit': 20}")] = None,
        context: Annotated[dict[str, Any] | None, Field(description="Context, e.g. {'lang': 'en_US'}")] = None,
        timeout: Annotated[int, Field(ge=5, le=300)] = 60,
    ) -> str:
        """Call a running Odoo 20 server through the JSON-2 API (POST /json/2/<model>/<method>, Bearer API key).
        Read methods (search_read, read, fields_get, read_group, ... or @api.readonly) run freely; anything else
        needs the allow_writes option."""
        return rt.live_call(model, method, ids, kwargs, context, timeout)
