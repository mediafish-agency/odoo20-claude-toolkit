# Odoo 20 source architecture

Map of the Odoo 20 tree for developers: what lives where in `odoo/` (ORM, HTTP, modules, services,
tools, tests, CLI, upgrade scripts), the key web addons, how a request flows to a controller, how the
registry and environments live, and in which order modules load. Use it to know which file to read (or
which MCP tool to call) before writing code.

## Contents
- [Top level](#top-level)
- [odoo/orm (the ORM)](#odooorm-the-orm)
- [Facades: odoo.api, odoo.fields, odoo.models](#facades-odooapi-odoofields-odoomodels)
- [odoo/http](#odoohttp)
- [odoo/modules, odoo/service, odoo/tools](#odoomodules-odooservice-odootools)
- [odoo/tests, odoo/cli, odoo/upgrade_code](#odootests-odoocli-odooupgrade_code)
- [odoo/addons/base](#odooaddonsbase)
- [Key addons](#key-addons)
- [Request lifecycle](#request-lifecycle)
- [Registry and environment lifecycle](#registry-and-environment-lifecycle)
- [Module loading order](#module-loading-order)
- [Where to look for what](#where-to-look-for-what)

## Top level

| Path | Content |
|---|---|
| `odoo-bin`, `odoo/__main__.py` | entry points (`odoo.cli.main()`; `python -m odoo` works) |
| `odoo/init.py` | first import: refuses `-O`, checks Python >= 3.12, gc thresholds, monkeypatches, sets `odoo._`, `odoo.Command`, `odoo.SUPERUSER_ID` |
| `odoo/release.py` | `version_info = (20, 0, 0, FINAL, 0, '')`, `MIN_PY_VERSION`, `MAX_PY_VERSION`, `MIN_PG_VERSION` |
| `odoo/` itself | a **namespace package** (no `odoo/__init__.py`); `odoo.addons` and `odoo.upgrade` too |
| `odoo/sql_db.py` | psycopg2 connection pools, `Cursor`, `db_connect()`, SQL logging (`odoo.sql_db`) |
| `odoo/netsvc.py` | logging setup, `--log-*` handling |
| `odoo/exceptions.py` | `UserError` (422), `AccessError`/`AccessDenied` (403), `MissingError` (404), `LockError` (409), `ValidationError`, `RedirectWarning`, `ConcurrencyError` |
| `odoo/import_xml.rng` | schema of data files (`<odoo>`, `<record>`, `<template>`, `<menuitem>`...) |
| `odoo/_monkeypatches/` | patches of stdlib/third-party libs applied at init |
| `odoo/addons/` | `base` + `test_*` modules |
| `addons/` | the 648 community addons |
| `skills/` | Odoo's own agent skills (guidelines, security, review) |

Source: odoo-bin, odoo/__main__.py, odoo/init.py, odoo/release.py, odoo/exceptions.py

## odoo/orm (the ORM)

| File | Defines |
|---|---|
| `models.py` | `MetaModel`, `BaseModel`, `Model`, CRUD, `search`/`_search`, `read_group`/`_read_group`, `check_access`/`has_access`/`_filtered_access`, `get_public_method` |
| `models_transient.py`, `models_cached.py` | `TransientModel`, `CachedModel` (small, cached tables) |
| `model_classes.py` | class building per registry: `add_to_registry`, `_inherit`/`_inherits` resolution, field setup |
| `fields.py` + `fields_misc.py`, `fields_numeric.py`, `fields_textual.py`, `fields_selection.py`, `fields_temporal.py`, `fields_relational.py`, `fields_reference.py`, `fields_binary.py`, `fields_properties.py` | `Field` base and every field type (`Binary` values are `BinaryValue`) |
| `domains.py` | `Domain` (and/or/not nodes, operators incl. `access`, optimizations) |
| `query.py` | `Query`, `TableSQL`, `FieldSQL` (SQL building) |
| `table_objects.py` | `Constraint`, `Index`, `UniqueIndex` (replace `_sql_constraints`) |
| `environments.py` | `Environment` (`env.user`, `company(ies)`, `lang`, `tz`, `website`, `_()`, `flush_all`, `execute_query`), `Transaction`, record `Cache` |
| `registry.py` | `Registry` (one per database, model classes, field triggers, cursors) |
| `cache.py` | `ormcache` (per transaction in 20), `log_ormcache_stats` |
| `decorators.py` | `api.depends`, `constrains`, `onchange`, `ondelete`, `model`, `model_create_multi`, `private`, `readonly`, `autovacuum`, `depends_context` |
| `commands.py`, `identifiers.py`, `types.py`, `utils.py` | `Command`, `NewId`, typing aliases, `SUPERUSER_ID` and helpers |

Read the `odoo20:orm` skill before writing model code.

Source: odoo/orm/*.py

## Facades: odoo.api, odoo.fields, odoo.models

Import from these packages, not from `odoo.orm` internals:

| Import | Exposes |
|---|---|
| `from odoo import api` | decorators above, `ormcache`, `Environment`, `NewId`, `SUPERUSER_ID`, `ValuesType`/`DomainType`... |
| `from odoo import fields` | all field classes, `Command`, `Domain`, `NO_ACCESS`, `parse_field_expr` |
| `from odoo import models` | `Model`, `AbstractModel`, `TransientModel`, `CachedModel`, `BaseModel`, `Constraint`, `Index`, `UniqueIndex`, `Query`, `TableSQL`, `check_company_domain_parent_of`... |
| `from odoo.tools import SQL, config, ...` | utilities (`odoo.tools` exports were trimmed in 20, rule ORM017) |

Source: odoo/api/__init__.py, odoo/fields/__init__.py, odoo/models/__init__.py, odoo/tools/__init__.py

## odoo/http

Package replacing the single `http.py`: `__init__` (`request`, `Response`, `Controller`, `route`),
`requestlib` (`Request`), `routing_map` (`route()`, routing merge), `dispatcher` (http / jsonrpc /
json2 dispatchers, CSRF, errors), `router` (WSGI `Application` `root`, `serve_db`, `db_list`), `session`
(session store + functions), `stream` (`Stream`), `response`, `retrying`, `geoip`, `server` +
`server_log` (Odoo's own h11 HTTP server and access log), `_facade` (safe request/response proxies).
Details: the `odoo20:http` skill (`references/routing.md`).

Source: odoo/http/

## odoo/modules, odoo/service, odoo/tools

| Path | Content |
|---|---|
| `odoo/modules/module.py` | `Manifest` (`Manifest.for_addon(name)`), `_DEFAULT_MANIFEST`, `get_module_path`, `initialize_sys_path`, `adapt_version` |
| `odoo/modules/module_graph.py` | `ModuleGraph` / `ModuleNode`: dependency graph and **load order** |
| `odoo/modules/loading.py` | `load_modules()`, `load_module_graph()`, data/demo loading, hooks, `force_demo` |
| `odoo/modules/migration.py` | `MigrationManager`: `migrations/` and `upgrades/` scripts |
| `odoo/modules/db.py` | database create/duplicate/drop/dump/restore/rename/list (replaces `odoo.service.db`) |
| `odoo/modules/neutralize.py` | collects `data/neutralize.sql` of installed modules |
| `odoo/modules/registry/` | re-exports `odoo.orm.registry.Registry` |
| `odoo/service/server.py` | `ThreadedServer`, `GeventServer`, `PreforkServer`, cron threads, autoreload |
| `odoo/service/model.py`, `common.py` | XML-RPC/JSON-RPC `object` (`execute_kw`) and `common` services |
| `odoo/tools/` | `config.py`, `convert.py` (XML/CSV data loader), `translate.py`, `sql.py` (`SQL`, DDL helpers), `date_utils.py`, `float_utils.py`, `image.py`, `mail.py`, `misc.py` (`file_open`, `file_path`, `mute_logger`, `dumpstacks`...), `safe_eval/`, `template_inheritance.py` (xpath engine), `view_validation.py`, `js_transpiler.py`, `profiler.py`, `binary.py` (`BinaryValue`), `json.py`, `cloc.py`, `pdf/` |

Source: odoo/modules/*.py, odoo/service/*.py, odoo/tools/

## odoo/tests, odoo/cli, odoo/upgrade_code

| Path | Content |
|---|---|
| `odoo/tests/common.py`, `form.py` | `BaseCase`, `TransactionCase`, `HttpCase` (browser, tours), `tagged`, `users`, `warmup`, `new_test_user`, `MockHTTPClient`, `QueryLike`, `registry_test_mode()`; `Form` (form.py); all re-exported by `odoo.tests` |
| `odoo/tests/loader.py`, `tag_selector.py`, `result.py`, `suite.py` | discovery of `tests/test_*.py`, `--test-tags` parsing, reporting |
| `odoo/tests/shell.py`, `reports.py` | `run_tests()` from the shell; `try_report` helpers |
| `odoo/cli/` | one `Command` subclass per file (`server`, `db`, `module`, `shell`...), `templates/` for `scaffold` (stale) |
| `odoo/upgrade_code/` | source rewriting scripts `<version>-NN-<name>.py` + `owl3-migration.py`, run by `odoo-bin upgrade_code` |

Source: odoo/tests/, odoo/cli/, odoo/upgrade_code/

## odoo/addons/base

`models/`: `ir_access.py` (the single access model of 20), `ir_http.py` (auth methods, routing map,
dispatch hooks), `ir_ui_view.py` (views, inheritance, validation), `ir_qweb.py` (server QWeb),
`ir_actions.py` / `ir_actions_report.py` (actions, reports, PDF engine API), `ir_asset.py` +
`assetsbundle.py` (asset bundles), `ir_attachment.py`, `ir_binary.py` (file streaming),
`ir_config_parameter.py` (typed `get_*`/`set_*`), `ir_cron.py`, `ir_model.py` (model/field reflection,
`ir.model.data`), `ir_module.py`, `ir_profile.py`, `res_users.py` (+ API keys), `res_groups.py`,
`res_partner.py`, `res_company.py`, and `website.py` (the `website` model now lives in base, behind
`env.website`). Also `rng/` (view schemas), `data/`, `security/`, `views/`, `wizard/`, `report/`.

Source: odoo/addons/base/models/, odoo/addons/base/rng/

## Key addons

| Addon | Role (depends) |
|---|---|
| `web` | web client: OWL 3 + compat layer, views, fields, assets `web.assets_backend`, `/web`/`/odoo` routes, `/web/content`, `/web/image` (`base`, auto) |
| `rpc` | `/xmlrpc`, `/jsonrpc` (deprecated) and `/json/2` JSON-2 API (`base`, auto, server-wide) |
| `api_doc` | `/doc` API browser and `/doc-bearer/*.json` (`web`, auto) |
| `bus` | websocket `/websocket`, notifications (`base`, `web`, auto) |
| `http_routing` | slugs, frontend languages, `website=True` routes, error pages (`web`) |
| `mail` | `mail.thread`, activities, Discuss, chatter, mail templates |
| `portal` | `/my` customer portal, `portal.mixin`, `portal.entry`, `CustomerPortal` |
| `html_editor` | the HTML editor and its plugin system (`base`, `bus`, `web`, auto) |
| `html_builder` | generic builder (snippet options) used by `website` (`html_editor`) |
| `website` | website builder, pages, menus, sitemap, `website.layout` |
| `point_of_sale` | POS app (OWL plugins, receipts) |
| `web_tour` | tours (`@web_tour/...`) |
| `populate` | blueprint-based synthetic data + `odoo-bin populate` |
| `base_report_wkhtmltox`, `base_report_paper_muncher` | PDF engines |

Inspect any addon with `odoo_module <name>` (manifest, files, models, dependants).

Source: addons/*/__manifest__.py

## Request lifecycle

1. `odoo.http.router.Application.__call__` builds `Request`, loads the session from the `session_id`
   cookie and picks the database (`session.db`, `X-Odoo-Database` header, or the single visible db).
2. `/<module>/static/...` -> `serve_static`; no db -> `serve_nodb` (only `auth='none'` routes).
3. `serve_db`: `Registry(db)`, read-only cursor, `request.env = Environment(cr, session.uid,
   session.context)`, then `ir.http._match(path)` finds the endpoint in the routing map (cached
   ormcache `routing`, built from installed modules + server-wide modules).
4. Read/write decision from `routing['readonly']`; `retrying()` wraps the rest (retry on serialization
   failure, commit at the end).
5. `ir.http._authenticate(endpoint)` -> `_auth_method_<auth>(routing)`; `ir.http._pre_dispatch`
   (upload limit, lang, `model(...)` converter access checks, frontend context for `website=True`).
6. Dispatcher (`http`/`jsonrpc`/`json2`) parses parameters, checks CSRF (http), calls
   `ir.http._dispatch(endpoint)` -> your controller method (captcha check first if set).
7. `ir.http._post_dispatch` -> `save_session`, future headers/cookies, CSP; errors go through
   `ir.http._handle_error` -> dispatcher `handle_error`.
8. No route matched: `ir.http._serve_fallback()` (website pages, redirects, attachments by URL) or 404.

Source: odoo/http/router.py:245-595, odoo/addons/base/models/ir_http.py:253-535, odoo/http/dispatcher.py

## Registry and environment lifecycle

- `Registry(db_name)` returns the cached registry (LRU of 42) or builds one with `Registry.new()`,
  which loads modules (`load_modules`) and sets up model classes.
- `registry.cursor(readonly=False)` gives a cursor (a replica cursor for `readonly=True` when
  configured); `with registry.cursor() as cr:` commits on success and closes.
- `Environment(cr, uid, context, su=False)`; `uid == SUPERUSER_ID` implies `su=True`. All envs on one
  cursor share a `Transaction` holding the record cache and the ormcache layers
  (`env.transaction.invalidate_ormcache(...)` in 20).
- Cross-worker signaling: registry/cache sequences are compared per transaction
  (`Transaction._check_signaling`); after a module install other workers reload their registry.
- `request.env` is per request; inside models always use `self.env`.

Source: odoo/orm/registry.py:86-135,1163-1185, odoo/orm/environments.py:45-110,579-835

## Module loading order

`ModuleGraph` (`odoo/modules/module_graph.py`):

- Phase 0 is always `base`. Then in normal loading every other module is in one phase, ordered by
  **(depth, name)** where depth = longest dependency path to `base`.
- During install/upgrade, odd phases load modules that need no init, even phases the ones to install,
  so a module is processed after all its dependencies.
- A `test_*` module is ordered right after its last loaded dependency.

Per module (`load_module_graph`), when installing/upgrading: `migrations` **pre** scripts -> import the
Python package (`post_load` hook) -> `pre_init_hook(env)` (install) -> register model classes ->
`init_models` (tables/columns/constraints) -> `data` files in manifest order, then `demo` -> **post**
scripts -> translations -> `post_init_hook(env)` (install) -> state `installed`, commit -> `at_install`
tests. After all modules: **end** scripts, uninstalls (`uninstall_hook(env)`), `_register_hook()` on
every model, then `post_install` tests.

Source: odoo/modules/module_graph.py:33-130,202, odoo/modules/loading.py:115-305,320-600

## Where to look for what

| Question | Look at | MCP |
|---|---|---|
| Does model X have field Y after all inherits? | `odoo/orm/*`, addon `models/` | `odoo_model X` (`resolve="db"` for final) |
| Which modules override method M and in which order? | addons `models/` | `odoo_method X.M` |
| Final arch of a view / who inherits it | `ir_ui_view.py` | `odoo_views <xmlid>` (`resolve="db"`) |
| Who can read/write model X? | `security/ir.access.csv` of each addon | `odoo_access X` |
| Which files are in a bundle? | manifests `assets`, `ir_asset.py` | `odoo_assets web.assets_backend` |
| Where is a JS registry entry / patch? | `static/src` | `odoo_js` |
| What did 20 change for X? | `odoo/upgrade_code/`, version-traps | `odoo_validate`, `odoo_upgrade_code` |
| HTTP behaviour of a route option | `odoo/http/*.py`, `ir_http.py` | `odoo_grep` |

Source: odoo/addons/base/models/ir_ui_view.py:1059, odoo/addons/base/models/ir_asset.py:119, odoo/addons/base/models/ir_access.py,
odoo/upgrade_code/
