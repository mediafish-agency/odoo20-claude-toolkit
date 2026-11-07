---
name: develop
description: >-
  Default for any Odoo work in this Odoo 20.0 tree even when no version is named; takes priority over generic odoo-* skills (17-19 advice such as ir.model.access.csv, useState, SavepointCase is wrong in 20). Entry point for any Odoo 20 (20.0) development task (new module, __manifest__.py, a feature across Python+XML+JS): building or changing an addon, understanding how the
  Odoo 20 framework is organised, deciding which file type and API to use, and knowing what changed since
  Odoo 19 (ir.access security, OWL 3, Material Symbols icons, JSON-2, PDF engines, card views). Use it before
  writing Odoo code in this workspace, when a request mentions Odoo/an addon/a module without a specific layer,
  or when another Odoo skill or doc disagrees with Odoo 20 behaviour.
when_to_use: >-
  Creating a module, adding a feature across Python+XML+JS, explaining Odoo 20 architecture, or choosing between
  the odoo20 skills (orm, http, views, data-security, qweb-reports, owl, website-pos, testing, migrate, ops).
  Not for Odoo <= 19 projects, except porting them (odoo20:migrate).
---

# Odoo 20 development (router)

This workspace targets **Odoo 20.0**. Odoo 20 broke many Odoo 17-19 habits; older notes, blog posts and
other skills (including generic `odoo-*` skills that claim "19/20") are often wrong here. When they disagree,
the Odoo 20 source and the `odoo20:*` skills win.

## Golden rules

1. **Evidence before code.** Never write a model, field, method, xmlid, view, template, JS import, registry key,
   CLI flag or XML attribute from memory. Look it up with the `odoo20` MCP tools (below) or read the source.
2. **Validate every change.** After editing an addon run `odoo_validate(<module path>)`; fix every error. The
   PostToolUse hook already flags Odoo 19 patterns in each edited file — act on its report.
3. **Prove it runs.** `odoo_test(<module>)` installs the module on a throwaway copy of the `odoo20_tmpl`
   database and runs its tests. Static checks are not a substitute.
4. **Follow Odoo's house rules** in `../odoo-guidelines/SKILL.md` (Python/XML) and
   `../odoo-web-guidelines/SKILL.md` (static/), and `../odoo-security/SKILL.md` for anything touching access,
   `sudo`, routes, SQL or HTML. For reviews use `../odoo-review/SKILL.md`; for commits `../odoo-git/SKILL.md`.
5. **Never touch the Odoo source tree** (`odoo_root`) for a feature: extend through your own addon
   (inheritance, `patch`, xpath). Never run tools against databases outside the allowlist.

## Which skill for which file

| You are touching | Read |
|---|---|
| `models/*.py`, `wizard/*.py` (models, fields, domains, computes, constraints, caching, SQL) | `odoo20:orm` |
| `controllers/*.py`, external API clients (JSON-2), portal/website routes | `odoo20:http` |
| `views/*.xml`: list/form/kanban/card/search/calendar/..., actions, menus, xpath inheritance, widgets, icons | `odoo20:views` |
| `security/ir.access.csv`, groups, `data/*.{xml,csv}`, cron, sequences, mail templates, `i18n/`, `migrations/`, `populate/` | `odoo20:data-security` |
| `__manifest__.py`, addon layout, load order | `references/module-anatomy.md` (this skill) |
| `report/*.py` (`_get_report_values`), report actions/templates | `odoo20:qweb-reports` |
| server QWeb templates, PDF reports, report layouts/engines, email QWeb | `odoo20:qweb-reports` |
| `static/src/**/*.{js,xml,scss}` for the backend web client (OWL 3, services/plugins, registries, field widgets, assets) | `odoo20:owl` |
| website/portal frontend JS (Interactions), website builder snippets/options, html_editor, Point of Sale | `odoo20:website-pos` |
| `tests/*.py`, Hoot `static/tests/*.test.js`, tours | `odoo20:testing` |
| porting a <=19 addon, `odoo_upgrade_code` | `odoo20:migrate` |
| running Odoo: CLI, config, databases, debugging, profiling, populate | `odoo20:ops` |

Workflow skills the user can type: `/odoo20:setup` (first run / health check), `/odoo20:new-module`, `/odoo20:validate`,
`/odoo20:run-tests`, `/odoo20:migrate`. `setup`, `new-module` and `run-tests` are user-only: when acting on your own, call `odoo_scaffold` / `odoo_test` directly.

## Standard workflow for a feature

1. `odoo_status` (index ready, runtime found). Locate what you extend: `odoo_search`, `odoo_model`,
   `odoo_views`, `odoo_method`, `odoo_js`, `odoo_xmlid`, `odoo_access`.
2. Pick the owning addon and check its `depends` with `odoo_module`; add a dependency instead of
   duplicating code. New addon: `odoo_scaffold` (or `/odoo20:new-module`) - never `odoo-bin scaffold`, whose
   template still emits the obsolete `ir.model.access.csv`.
3. Implement layer by layer using the matching skill; keep `security/ir.access.csv` complete (no access row =
   nobody can use the model).
4. `odoo_validate` -> fix -> `odoo_test` -> fix. For UI behaviour start `odoo_server` and check in a browser
   (the chrome-devtools MCP can drive it).
5. Report the files changed and the checks run (static vs install/tests) honestly.

## Odoo 20 in one screen (details: references/version-traps.md)

- **Security**: `ir.model.access` and `ir.rule` are gone -> one `ir.access` model, CSV
  `id,name,model_id,group_id/id,operation,domain`; rows with a group grant (OR), rows without restrict (AND).
- **ORM**: `from odoo.api import ormcache`; `read_group` has `_read_group`'s signature; `get_param` removed
  (`get_str/get_int/...`); Binary values are `BinaryValue`; `odoo.osv` removed; `name_get` gone.
- **HTTP**: `odoo.http` is a package (`Stream`/`content_disposition` from `odoo.http.stream`); route types
  `http|jsonrpc|json2`; JSON-2 `/json/2/<model>/<method>` with Bearer API keys; XML-RPC deprecated.
- **Views/QWeb**: `<list>`, python-expression modifiers, `<chatter/>`, kanban `t-name="card"` + new `card`
  view, list `<column>`, Material Symbols `<i class="oi" data-icon="..."/>`, server QWeb `t-out` only,
  `t-call` parameters as attributes.
- **Web client**: OWL 3 with a compat layer - `props = useProps({...})` (static props throw), `proxy()`,
  signals, `this.` in templates, services are Plugins, no jQuery/publicWidget/QUnit (Interactions, Hoot).
- **Runtime**: Python 3.12-3.14, PostgreSQL >= 16, `--http-interface` defaults to 127.0.0.1, PDF engines
  pluggable (`base_report_wkhtmltox`, `base_report_paper_muncher`).

## References

- [references/architecture.md](references/architecture.md) - where things live in the v20 source and how a request/module load flows
- [references/module-anatomy.md](references/module-anatomy.md) - addon layout, manifest keys, load order, a complete minimal module
- [references/version-traps.md](references/version-traps.md) - generated catalogue of every Odoo 19 -> 20 trap the validator checks
- [references/mcp-tools.md](references/mcp-tools.md) - what each `odoo20` MCP tool answers and when to use it
