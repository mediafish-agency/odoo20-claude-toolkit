# odoo20 MCP tools

The `odoo20` MCP server indexes the Odoo 20 source (framework + every addon + your extra addons paths),
validates addons, and drives `odoo-bin` on allowlisted databases. Static tools are read-only and fast;
runtime tools need the Odoo runtime interpreter (`scripts/setup_odoo_runtime.sh`).

## Lookup (static, read-only)

| Question | Tool call |
|---|---|
| Is the index ready? Which roots/runtime/DB policy? | `odoo_status()` (`refresh=true` re-indexes changed modules) |
| Where is X defined? (model, field, method, xmlid, template, registry key, JS module/class, bundle) | `odoo_search(query, kind=?)` |
| Free text: usages, strings, xmlids in JS, anything else | `odoo_grep(pattern, regex=?, module=?, glob='*.py')` |
| What does module M contain / depend on / who depends on it? | `odoo_module(name)` |
| All fields of a model across modules, with who defines/overrides them | `odoo_model(model)`; one field: `odoo_model(model, field='x')`; as installed with M: `scope_module='M'` |
| Final fields in a real database | `odoo_model(model, resolve='db', db=?)` |
| Who overrides method m, in which order, do they call super()? | `odoo_method(model, method, include_code=true)` |
| Where is an xmlid defined and referenced? | `odoo_xmlid('module.name')` |
| View inheritance tree / primary views of a model | `odoo_views(xmlid=...)`, `odoo_views(model=..., view_type='form')` |
| Exact combined arch Odoo computes | `odoo_views(xmlid=..., resolve='db')` |
| Who can read/write model M? | `odoo_access(model)` |
| JS: registry entries, patches of a class, module exports/importers, OWL template, class | `odoo_js(registry='fields')`, `odoo_js(patches_of='FormController')`, `odoo_js(module_path='@web/core/utils/hooks')`, `odoo_js(template='web.Dialog')`, `odoo_js(js_class='Interaction')` |
| What is in an asset bundle? | `odoo_assets(bundle)`; final file list: `resolve='db'` |

`scope_module` = what is installed together with that module: its dependencies plus the auto_install
modules they trigger (e.g. `base` always brings `web`).

## Quality

| Need | Tool |
|---|---|
| Check an addon (or one file) | `odoo_validate(path)` - legacy rules (ids in version-traps.md), Odoo RNG schemas, cross-module checks (fields in views exist, missing `depends`, ir.access rows, xmlids, JS imports/exports, unloaded files), ruff with Odoo's ruff.toml |
| Port <=19 code automatically | `odoo_upgrade_code(path)` -> diff of Odoo's own upgrade scripts on a sandbox copy; `apply=true` writes |

## Authoring and runtime (allowlisted databases only, default `odoo20_*`)

| Need | Tool |
|---|---|
| New addon skeleton that installs and passes tests | `odoo_scaffold(name, dest, model, label, features)` |
| Install + run tests on a throwaway DB (template `odoo20_tmpl`) | `odoo_test(modules, test_tags=?)` -> results or job id |
| Long job status / log / cancel | `odoo_job(job_id, action='log', grep='ERROR|FAIL')` |
| Databases: list, create_template, create, install, upgrade, neutralize, drop | `odoo_db(action, name, modules)` |
| Dev server for browsing / tours / JSON-2 | `odoo_server('start', db=..., port=8070)` |
| Inspect real data or behaviour in Python | `odoo_shell(db, code)` (rolled back unless `commit=true` + allow_writes) |
| Call a running server (JSON-2) | `odoo_live_call(model, method, kwargs=...)` (writes need allow_writes) |

## Habits

- Start broad (`odoo_search`) then go precise (`odoo_model` / `odoo_views` / `odoo_method`).
- Before overriding a method, read its chain (`odoo_method`) and keep the signature + `super()` call.
- Before an xpath, read the target view tree (`odoo_views`) and anchor on `name`s present in it.
- Before importing JS, confirm the export (`odoo_js(module_path=...)`).
- Results cite `file:line`; open them with the Read tool when you need the full code.
