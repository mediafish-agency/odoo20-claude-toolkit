# Skills

Skills are instructions plus reference files that Claude loads when a task matches their description. The
plugin's skills are namespaced: their full names are `odoo20:<name>`, and you can call any of them directly
as `/odoo20:<name>`.

## Topic skills (loaded automatically)

| Skill | Use it for | References |
|---|---|---|
| `develop` | Entry point: Odoo 20 architecture, addon anatomy and manifest, which file type and API to use, what changed since 19, how to use the MCP tools | architecture, module-anatomy, version-traps (generated from the validator), mcp-tools |
| `orm` | `models/*.py`, `wizard/*.py`: models and inheritance, all field types and parameters, `fields.Domain` and the `access` operator, decorators, `ormcache`/`CachedModel`, `models.Constraint`/`Index`, `_read_group`, `SQL`, access API, typed config parameters, mail mixins | 8 |
| `http` | `controllers/*.py` and API clients: the `odoo.http` package, `route()` types `http`/`jsonrpc`/`json2`, `bearer` auth, CSRF, streams, sessions, portal and website routes, JSON-2 clients in Python/JS/curl | 4 |
| `views` | `views/*.xml`: list (`<column>`), form (`<chatter/>`), kanban card templates and the new `card` view, search filters (`end_date`, `default_period`), calendar/graph/pivot/activity/hierarchy, xpath inheritance, widgets, Material Symbols icons, actions, menus, settings pages | 10 |
| `data-security` | `security/ir.access.csv` (permissions and restrictions), groups and privileges, data/demo files, cron, sequences, mail templates and activity types, `i18n/`, `migrations/`, `data/neutralize.sql`, populate blueprints | 8 |
| `qweb-reports` | Server QWeb (`t-out` only, `t-call` attribute parameters), `Markup` safety, `ir.actions.report`, layouts, paper formats, the pluggable PDF engines, `_get_report_values`, email QWeb | 3 |
| `owl` | `static/src/**`: OWL 3 with Odoo's compatibility layer (`useProps` + `t.*`, `proxy()`, signals, `this.` in templates, `t-call-slot`), services as Plugins, registries, field widgets, custom views, `patch`, assets, SCSS and dark mode, icons, TypeScript/ESLint tooling | 11 |
| `website-pos` | Website/portal JavaScript with Interactions (no `publicWidget`/jQuery), snippets and builder options, `html_editor` plugins, Point of Sale plugins, patches, payment providers and receipts | 4 |
| `testing` | Python tests (`TransactionCase`, `HttpCase`, `tagged`, `Form`, query counts, `MockHTTPClient`), Hoot JS tests (`@odoo/hoot`, `makeTestApp`, `onRpc`), tours, running tests through the MCP tools | 4 |
| `migrate` | Porting Odoo 19 (or older) addons: Odoo's `upgrade_code` scripts on a sandbox copy, then the manual matrix for what they don't cover | 3 |
| `ops` | Running Odoo 20 from source: `odoo-bin` subcommands and options, `odoo.conf`, databases, Python/PostgreSQL runtime, PDF engine binaries, logging, debugging, profiling | 4 |

Each `SKILL.md` keeps the essentials (workflow, top rules, a "v19 habit -> v20" table) and links to
`references/*.md` files that Claude opens only when needed. Every API statement in a reference cites the
Odoo 20 source file (and usually the line) it was checked against. `scripts/check_skill_refs.py` verifies
in CI that every cited path, Python import and JS import still exists in Odoo 20.0.

## Workflow commands (you type them)

| Command | What it does |
|---|---|
| `/odoo20:setup [odoo path]` | First-run setup and health check: source tree, MCP runtime and index, Odoo virtualenv, PostgreSQL, plugin options, template database |
| `/odoo20:new-module <name> [features]` | Scaffolds an addon that installs (features: `views,mail,owl,report,controller,wizard,interaction,tests`), adapts it to your requirement, validates and tests it |
| `/odoo20:validate [path]` | Runs the validator on an addon, file or folder of addons and explains or fixes the findings. Claude also uses it on its own before declaring work done |
| `/odoo20:run-tests <modules> [test-tags]` | Installs the modules on a throwaway database and runs their Python (and optionally Hoot) tests, then reports failures with tracebacks |
| `/odoo20:migrate <path>` | The `migrate` skill as a command |

`setup`, `new-module` and `run-tests` can only be started by you (`disable-model-invocation`), because they
install software or create databases.

## Odoo's official skills

Odoo ships five skills in its own repository (`skills/` in Odoo 20.0). They are included unchanged, because
they link to each other and must sit side by side:

| Skill | Purpose |
|---|---|
| `odoo-guidelines` | House rules for addon code outside `static/` |
| `odoo-web-guidelines` | House rules for `static/` (JavaScript, OWL templates, SCSS) |
| `odoo-review` | Reviewing a diff, commit, PR or module against those rules |
| `odoo-security` | Security audit: access control, injection, `sudo`, routes, deserialization, ... |
| `odoo-git` | Odoo's commit message and branch conventions |

The odoo20 skills cover what changed in Odoo 20 and how to build things. For house rules, reviews and
security audits they point to these official skills.

## Living with other Odoo skills

If you also have generic Odoo skills installed (for Odoo 17-19, or ones that claim to cover "19/20"), their
advice often contradicts Odoo 20 (`ir.model.access.csv`, `useState`, `t-esc`, `attrs`, `<tree>`, ...). The
odoo20 skill descriptions say they take priority for Odoo 20 work. To be certain:

- install this plugin with `--scope project` in your Odoo 20 projects only, and keep older-version skills out
  of those projects;
- or start a task with `/odoo20:develop` (or the specific skill) to load it explicitly.

## Without the MCP server

The skills still work when the `odoo20` MCP server is not connected: they fall back to reading the Odoo
source with Claude Code's own file tools. You lose the merged model, method and view lookups, the validator,
and the runtime checks, which are what keep the code verified rather than remembered.
