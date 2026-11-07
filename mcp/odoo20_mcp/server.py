"""odoo20 MCP server: tool registration (stdio)."""
from __future__ import annotations

import logging
import sys
from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from . import context as ctx
from .tools import static
from .util import ToolError

INSTRUCTIONS = """\
Odoo 20 developer tools over the Odoo source tree (static index), a local Odoo 20 runtime (odoo-bin) and, \
optionally, a running server (JSON-2).

Use them as evidence before writing Odoo code: never assume a model, field, method, xmlid, view, template, \
JS export, registry key or asset bundle exists - look it up. Entry point: odoo_search (symbols) or odoo_grep \
(free text); then odoo_model / odoo_method / odoo_views / odoo_xmlid / odoo_access / odoo_js / odoo_assets / \
odoo_module.

Static vs database: the index answers "who defines, inherits, overrides, references" across all modules; \
scope_module narrows to what is installed with that module (its install closure). Answers that depend on the \
actual installed set (combined view arch, real asset files, final fields) come from resolve="db" on an \
allowlisted database.

After editing an addon: odoo_validate(<module path>) - Odoo 19->20 breaking patterns with fixes, Odoo's RNG \
schemas, cross-module checks (fields in views, missing depends, ir.access rows, JS imports) and ruff; then \
odoo_test(<module>) to install it and run its tests on a throwaway database. Porting older code: \
odoo_upgrade_code (sandboxed copy, returns a diff; apply=true writes).

Safety: runtime tools only touch databases matching the configured allowlist (default odoo20_*); database \
writes, shell commits and live write calls need the allow_writes option; tools never write inside the Odoo \
source tree. Long jobs return a job id - poll odoo_job. Rule ids such as ORM001 or JS002 are explained in the \
odoo20:develop skill (references/version-traps.md).
"""

RO = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
Fmt = Annotated[Literal["markdown", "json"], Field(description="Output format")]
Limit = Annotated[int, Field(ge=1, le=500, description="Maximum rows")]
Offset = Annotated[int, Field(ge=0, description="Rows to skip (pagination)")]
ScopeModule = Annotated[str | None, Field(
    description="Restrict to what is installed together with this module (its dependencies plus auto_install "
                "modules). Omit to consider all indexed modules.")]

Resolve = Annotated[Literal["static", "db"], Field(
    description='"static" = source index; "db" = ask Odoo itself in an allowlisted database (slower, exact)')]
DbName = Annotated[str | None, Field(description="Allowlisted database for resolve=\"db\" (default: live_db option, "
                                                 "else odoo20_tmpl)")]

server = MCPServer(name="odoo20", instructions=INSTRUCTIONS, version="0.1.0")


@server.tool(annotations=RO, structured_output=False)
def odoo_status(refresh: Annotated[bool, Field(description="Start a background re-index of changed modules")] = False,
                format: Fmt = "markdown") -> str:
    """Odoo version, source/addons paths, index state, runtime interpreter, database allowlist, live config.

    Call first in a session or when other tools say the index is building."""
    return static.status(refresh, format)


@server.tool(annotations=RO, structured_output=False)
def odoo_search(query: Annotated[str, Field(description="Name or fragment, e.g. 'sale.order', 'partner_id', "
                                                     "'view_order_form', 'many2one_avatar', 'useProps'")],
                kind: Annotated[Literal["module", "model", "field", "method", "xmlid", "owl_template", "js_registry",
                                        "js_module", "js_class", "asset_bundle"] | None,
                                Field(description="Restrict to one symbol kind")] = None,
                module: Annotated[str | None, Field(description="Restrict to one module")] = None,
                limit: Limit = 30, offset: Offset = 0, format: Fmt = "markdown") -> str:
    """Find Odoo symbols by (fuzzy, substring) name across all indexed modules: modules, models, fields
    (model.field), methods (model.method()), XML ids, OWL templates, JS registry entries (category:key),
    JS modules (@addon/path), JS classes and asset bundles. Returns name, kind, module and file:line."""
    return static.search(query, kind, module, limit, offset, format)


@server.tool(annotations=RO, structured_output=False)
def odoo_grep(pattern: Annotated[str, Field(description="Text to find (literal unless regex=true)")],
              regex: Annotated[bool, Field(description="Treat pattern as a Perl/Python-style regex")] = False,
              ignore_case: bool = False,
              module: Annotated[str | None, Field(description="Search only this module")] = None,
              glob: Annotated[str | None, Field(description="File name glob, e.g. '*.py', '*.xml', '*.test.js'")] = None,
              context: Annotated[int, Field(ge=0, le=10, description="Context lines around matches")] = 0,
              limit: Limit = 100,
              include_vendor: Annotated[bool, Field(description="Also search i18n/ and static/lib/")] = False) -> str:
    """Full-text search over the Odoo source tree (framework + all addons) and extra addons paths, using git grep.
    Use for usages, string literals, xmlids in JS/Python, and anything the symbol index does not cover."""
    return static.grep(pattern, regex, ignore_case, module, glob, context, limit, include_vendor)


@server.tool(annotations=RO, structured_output=False)
def odoo_module(name: Annotated[str, Field(description="Technical module name, e.g. 'sale_stock'")],
                format: Fmt = "markdown") -> str:
    """Module overview: manifest, depends, dependency/install closure, dependents, load order, files by type,
    models defined/extended, views, data records, asset bundles, tests, migrations/upgrades/populate dirs."""
    return static.module_info(name, format)


@server.tool(annotations=RO, structured_output=False)
def odoo_model(model: Annotated[str, Field(description="Model name, e.g. 'sale.order'")],
               field: Annotated[str | None, Field(description="Show one field: merged attributes, every "
                                                              "definition/override and views using it")] = None,
               scope_module: ScopeModule = None,
               include: Annotated[str, Field(description="Comma list of sections: inheritance, fields, methods, "
                                                         "constraints, or all")] = "all",
               include_tests: Annotated[bool, Field(description="Include test_* modules when no scope_module")] = False,
               resolve: Resolve = "static", db: DbName = None,
               limit: Limit = 200, offset: Offset = 0, format: Fmt = "markdown") -> str:
    """Merged view of an Odoo model across modules (static): every contributing class in load order, mixin
    parents, _inherits delegation, attributes (_order, _rec_name...), all fields with type/comodel/key attributes
    and which modules define or override them, methods and SQL constraints/indexes.
    resolve="db": the final fields (fields_get) of the model in an allowlisted database."""
    if resolve == "db":
        from .tools import runtime
        return runtime.model_db(model, db, format)
    return static.model_info(model, scope_module, include_tests, field, include, limit, offset, format)


@server.tool(annotations=RO, structured_output=False)
def odoo_method(model: Annotated[str, Field(description="Model name")],
                method: Annotated[str, Field(description="Method name, e.g. 'action_confirm', 'write', '_compute_amount'")],
                scope_module: ScopeModule = None,
                include_code: Annotated[bool, Field(description="Include the source of each override (first 8)")] = False,
                format: Fmt = "markdown") -> str:
    """Override chain of a model method in call order (last-loaded override first, down to mixins and
    BaseModel): module, file:line, decorators, signature, and whether each override calls super()."""
    return static.method_info(model, method, scope_module, include_code, format)


@server.tool(annotations=RO, structured_output=False)
def odoo_xmlid(xmlid: Annotated[str, Field(description="Fully qualified XML id, e.g. 'sale.view_order_form'")],
               limit: Limit = 100, format: Fmt = "markdown") -> str:
    """Where an XML id is defined (model, file:line, key values, noupdate) and every XML/CSV/Python reference to it
    (ref=, eval ref(), %(xmlid)d, inherit_id, groups, menu parent/action, env.ref, has_group)."""
    return static.xmlid_info(xmlid, limit, format)


@server.tool(annotations=RO, structured_output=False)
def odoo_views(xmlid: Annotated[str | None, Field(description="View or QWeb template xmlid: show its inheritance "
                                                              "tree, specs and t-call callers")] = None,
               model: Annotated[str | None, Field(description="List the primary views of this model")] = None,
               view_type: Annotated[str | None, Field(description="With model: list, form, kanban, search, "
                                                                  "calendar, graph, pivot, activity, card, hierarchy")] = None,
               resolve: Resolve = "static", db: DbName = None,
               format: Fmt = "markdown") -> str:
    """Backend views and server QWeb templates: inheritance tree (priority, mode, groups, xpath specs, file:line)
    for an xmlid, or the primary views of a model. resolve="db" (with xmlid) returns the exact combined arch
    computed by Odoo in an allowlisted database where the modules are installed."""
    if resolve == "db":
        if not xmlid:
            raise ToolError('resolve="db" needs `xmlid`')
        from .tools import runtime
        return runtime.views_db(xmlid, db, format)
    return static.views_info(xmlid, model, view_type, format)


@server.tool(annotations=RO, structured_output=False)
def odoo_access(model: Annotated[str, Field(description="Model name")], format: Fmt = "markdown") -> str:
    """Odoo 20 access control for a model: every ir.access row (CSV and XML) split into permissions (with a group,
    OR-ed) and restrictions (no group, AND-ed), with operation, domain, module and location; plus field-level groups."""
    return static.access_info(model, format)


@server.tool(annotations=RO, structured_output=False)
def odoo_js(registry: Annotated[str | None, Field(description="Registry category (e.g. 'fields', 'views', "
                                                              "'actions', 'services', 'public.interactions', "
                                                              "'web_tour.tours'); '' lists all categories")] = None,
            key: Annotated[str | None, Field(description="With registry: one key")] = None,
            patches_of: Annotated[str | None, Field(description="Class whose patch() calls to list, e.g. 'FormController'")] = None,
            module_path: Annotated[str | None, Field(description="ES module path, e.g. '@web/core/utils/hooks': "
                                                                 "file, exports, importers")] = None,
            template: Annotated[str | None, Field(description="OWL template name: definition, t-inherit "
                                                              "extensions, components using it")] = None,
            js_class: Annotated[str | None, Field(description="JS class: definition, subclasses, patches")] = None,
            limit: Limit = 200, offset: Offset = 0, format: Fmt = "markdown") -> str:
    """Odoo web client (OWL 3) lookups from static/src: registry entries, patch() targets, ES module exports and
    importers, OWL templates and their t-inherit extensions, component classes."""
    return static.js_info(registry, key, patches_of, module_path, template, js_class, limit, offset, format)


@server.tool(annotations=RO, structured_output=False)
def odoo_assets(bundle: Annotated[str, Field(description="Bundle name, e.g. 'web.assets_backend'")],
                scope_module: ScopeModule = None, resolve: Resolve = "static", db: DbName = None,
                limit: Limit = 300, offset: Offset = 0, format: Fmt = "markdown") -> str:
    """Asset bundle composition from all manifests in module load order: append/prepend/before/after/replace/
    remove/include directives and globs. resolve="db": the final ordered file list Odoo builds in an allowlisted
    database (installed modules only)."""
    if resolve == "db":
        from .tools import runtime
        return runtime.assets_db(bundle, db, format)
    return static.assets_info(bundle, scope_module, limit, offset, format)


@server.tool(annotations=RO, structured_output=False)
def odoo_validate(path: Annotated[str, Field(description="Module directory, folder of modules, or one file")],
                  checks: Annotated[str, Field(description="Comma list: legacy, rng, semantic, lint (default all)")] = "all",
                  min_severity: Annotated[Literal["error", "warning", "info"], Field(
                      description="Lowest severity to report")] = "info",
                  limit: Limit = 200, format: Fmt = "markdown") -> str:
    """Static validation for Odoo 20: legacy (<=19) patterns that break in 20 with the fix and the upgrade_code
    script that automates it; Odoo's RNG schemas for data files and views; cross-module checks (view fields and
    buttons exist on the model, missing depends, ir.access rows, xmlids, JS imports, unloaded files); ruff."""
    from .tools import quality
    return quality.validate(path, checks, min_severity, limit, format)


def main() -> None:
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    try:
        from .tools import register_runtime
        register_runtime.register(server)
    except ImportError:
        pass
    ctx.index().ensure_started()  # refresh changed modules in the background; never blocks startup
    server.run("stdio")


__all__ = ["server", "main", "ToolError"]
