# upgrade_code: Odoo's source rewriter (Odoo 20)

`odoo-bin upgrade_code` runs the best-effort rewrite scripts in `odoo/upgrade_code/` over addon
source files. This file documents the CLI, how scripts are selected, what each 19.x / 20.0
script and `owl3-migration` actually rewrites (with before/after taken from the scripts), the
traps (core is always in the path, non-idempotent scripts, stale OWL steps) and the safe
toolkit workflow. Everything the scripts do not cover is in [migration-matrix.md](migration-matrix.md).

## Contents

- CLI
- odoo-bin mode vs standalone mode
- How scripts are selected
- Script catalogue
- 19.1 t-call
- 19.3 base64-in-xml, account-groups, account-report-foldable
- 19.4 ir-access
- 19.4 ormcache-on-transaction
- 19.5 tuple-rec_names_search, material-symbols-icons
- 20.0 search-date-filters
- owl3-migration
- Caveats
- Safe workflow (toolkit)

## CLI

```text
odoo-bin [--addons-path=PATH,...] upgrade_code (--script NAME | --from VERSION)
         [--to VERSION] [--glob GLOB] [--dry-run] [--addons-path PATH,...]
```

| Option | Meaning |
|---|---|
| `--from VERSION` | run every versioned script with `VERSION <= script version <= --to` (inclusive) |
| `--to VERSION` | upper bound, default `20.0` (`release.version`) |
| `--script NAME` | run one script: a path, or a fragment matched as `odoo/upgrade_code/*NAME*.py` that must match exactly one file (`--script material` matches two files and fails; use `material-symbols`) |
| `--glob GLOB` | files to load, relative to each addons directory (default `**/*`), e.g. `my_module/**/*` |
| `--dry-run` | run the scripts in memory and print `updated: <path>` / `deleted: <path>` only (no diff) |
| `--addons-path` | addons directories (each one contains addon folders) |

`--script` and `--from` are mutually exclusive and one is required. Only files with extensions
`.py .js .css .scss .xml .csv .po .pot` are loaded (`__pycache__` and `.git` skipped). The exit
code is `1` when at least one file changed (also in dry run), `0` otherwise.

Source: odoo/cli/upgrade_code.py:41, 105-128, 204-249, 252-306; `odoo-bin upgrade_code --help`

## odoo-bin mode vs standalone mode

| Mode | Command | Files scanned |
|---|---|---|
| odoo-bin | `odoo-bin upgrade_code --addons-path=/my/addons --from 19.0 --dry-run` | `initialize_sys_path()` then `odoo.addons.__path__`: your paths **plus** `odoo/addons`, the community `addons/` and the data-dir addons. Scripts run over the Odoo tree too. |
| standalone | `PYTHONPATH=/path/to/odoo python /path/to/odoo/odoo/cli/upgrade_code.py --addons-path /my/addons --from 19.0` | exactly the given paths (`--addons-path` is required). |

In standalone mode the CLI itself only needs `release.py`/`parse_version`, but most scripts import
`odoo.upgrade_code.*` or `odoo.tools`, so run it with an Odoo 20 interpreter and the Odoo root on
`PYTHONPATH` (from reading the imports; not executed here). The toolkit calls `migrate()` directly
on a sandbox copy, which is the standalone behaviour without the CLI.

Source: odoo/cli/upgrade_code.py:46-66, 292-302; odoo/modules/module.py:142-155

## How scripts are selected

- Script files are named `<version>-<nn>-<name>.py` and expose `upgrade(file_manager)`.
- `--from/--to` compare `parse_version(<text before the first "-">)`; scripts run in filename
  order. Unversioned files (`owl3-migration.py`, `material_symbols_icons_mapping.py`,
  `tools_etree.py`, `tools_js_expressions.py`) parse below any number, so `--from` never
  selects them: run `--script owl3-migration` separately.
- `--from 19.0` selects 19.1 ... 20.0 (there is no 19.0 script). Porting from 18 or older:
  `--from 17.5` (the 17.5 example script does not write anything).

Source: odoo/cli/upgrade_code.py:191-201, odoo/upgrade_code/

## Script catalogue

| Script | Files | Rewrites | Idempotent |
|---|---|---|---|
| 17.5-00-example | `models/*.py` | nothing (write line commented out) | yes |
| 17.5-01-tree-to-list | xml, py, js | `<tree>` -> `<list>`, view modes | yes |
| 18.1-00-sql-constraint | py | `_sql_constraints` -> `models.Constraint` attributes | yes |
| 18.1-02-route-jsonrpc | `controllers/*.py` | `type="json",` / `type='json',` -> `jsonrpc` | yes |
| 18.2-00-l10n-translate, 18.3-00-l10n-fiscal-position-taxes, 18.5-00-no-tax-tag-invert | l10n data | localization data formats | - |
| 18.5-00-deprecated-properties | py | `._cr/._uid/._context` -> `.env.cr/.env.uid/.env.context` | yes |
| 18.5-00-domain-dynamic-dates | xml in `data/`, `report/`, `views/` | `context_today()` domains -> dynamic date strings | - |
| **19.1-00-t-call** | server xml (not `/static/`) | `t-set` children of `t-call` -> call attributes | not guaranteed |
| **19.3-00-base64-in-xml** | xml | `type="base64" ... file=` -> `type="bytes"` | yes |
| **19.3-00-account-groups** | `l10n_*/data/template/*.csv` | `account.group` -> inactive `account.account` parents | no |
| **19.3-00-account-report-foldable** | xml | `account.report.line` `foldable` -> `foldability` | yes |
| **19.4-00-ir-access** | manifests, security csv/xml | `ir.model.access` + `ir.rule` -> `ir.access.csv` | **no** (header: "non-idempotent, requires all initial data to run") |
| **19.4-00-ormcache-on-transaction** | py | `registry.clear_cache` -> `transaction.invalidate_ormcache` | yes |
| **19.5-00-tuple-rec_names_search** | `models/**.py` | list -> tuple | yes |
| **19.5-00-material-symbols-icons** | xml, js, py, scss, css | Font Awesome / `oi-*` -> Material Symbols | mostly |
| **20.0-00-search-date-filters** | xml | drop `start_/end_month/year` on `<filter>` | yes |
| **owl3-migration** (`--script`) | `/static/` js and xml | OWL 2 -> OWL 3 (22 steps) | no (see below) |

## 19.1 t-call

Server QWeb `t-set` inside a `t-call` body no longer reaches the callee. For each `t-call` /
`t-snippet-call` whose attributes are all `t-*` (outside `<kanban>`):

```xml
<!-- before -->
<t t-call="web.external_layout">
    <t t-set="title" t-value="'Invoice'"/>
    <t t-set="company" t-value="doc.company_id"/>
    <t t-set="label">Total due</t>
    <div class="page">...</div>
</t>
<!-- after -->
<t t-call="web.external_layout" title.f="Invoice" company="doc.company_id" label.translate="Total due">
    <div class="page">...</div>
</t>
```

- quoted literal `t-value` or `t-valuef` -> `name.f="..."`; expression -> `name="expr"`; text body
  -> `name.translate="..."`.
- A `t-set` with children, `groups`, `t-groups`, `t-if`, or reused by another `t-set` is **moved
  before** the `t-call` and passed as `name="name"`; a `t-set` used by the body itself is left alone.
- Inherited `t-call`s with `position="inside"` become `position="attributes"` (+ `position="before"`
  for moved `t-set`s); root-level `t-call`s get wrapped in `<t>`/`<data>`.
- Empty `<t ...></t>` pairs in touched files become `<t .../>`. Failures are logged as warnings.

Source: odoo/upgrade_code/19.1-00-t-call.py:46-300

## 19.3 base64-in-xml, account-groups, account-report-foldable

```xml
<field name="image_1920" type="base64" file="my_module/static/img/logo.png"/>   <!-- before -->
<field name="image_1920" type="bytes" file="my_module/static/img/logo.png"/>    <!-- after -->
```

Regex `type="base64"(.*file=|\n.*file=)`: only double quotes, `file=` after `type=` on the same or
next line. `type="base64"` is still accepted with a DeprecationWarning.

`account-groups` only touches the chart-of-accounts CSVs of a fixed list of Odoo localizations
(`COA_TO_MIGRATE`: ar, bd, bh, co, do, ec, il, iq, jo, kh, kw, lb, mx, mz, om, pk, qa, sk, ua, us,
zm variants): `account.group` rows become inactive `account.account` rows and accounts get a
`parent_id` column. `account-report-foldable` removes `foldable` when it matches the computed
value, turns `True` into `<field name="foldability">foldable</field>`, and reports other
inconsistencies in the summary. Irrelevant for most custom addons.

Source: odoo/upgrade_code/19.3-00-base64-in-xml.py, odoo/tools/convert.py:139-145,
odoo/upgrade_code/19.3-00-account-groups.py:15, 119-203, odoo/upgrade_code/19.3-00-account-report-foldable.py:132-177

## 19.4 ir-access

```csv
# before: security/ir.model.access.csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_library_book_user,library.book user,model_library_book,base.group_user,1,0,0,0
access_library_book_manager,library.book manager,model_library_book,group_library_manager,1,1,1,1
```

```csv
# after: security/ir.access.csv (appended at the end of the manifest 'data')
id,name,model_id,group_id/id,operation,domain
access_library_book_user,library.book user,library.book,base.group_user,r,
access_library_book_manager,library.book manager,library.book,my_module.group_library_manager,crud,
```

(Output derived from the script's writer, not executed.)

- ACL rows -> permissions (`operation` letters in `c r u d` order, empty domain). ACL without group
  -> group `base.group_everyone` (INFO log).
- `ir.rule` with groups -> rows for those groups, limited to operations the ACLs grant; global
  rules -> rows without group (restrictions) keeping `domain_force` as `domain`.
- Emptied `ir.model.access.csv` / XML files are deleted and removed from the manifest; files
  keeping other records are rewritten.
- Records of other modules (`other.access_x`) and records with `active` False are skipped with
  WARNING/ERROR logs: port them by hand (`ir.access` records with `active` False).
- The file goes to `security/ir.access.csv` if the module already listed `security/` files, else
  `ir.access.csv` at the module root.
- It resolves model xmlids from `.py` files and group implications from `res.groups` XML of every
  module in the file manager, and walks each module's `depends`. It indexes `base.group_user`
  directly, so it needs `base` and every dependency on the addons path; on a path holding only
  your addon expect a `KeyError`/"You may not access file" failure (from code reading).
- Not idempotent: never run it on a module that already has `ir.access.csv`. Read every WARNING
  ("acl group without rules, giving access to ALL records", "ir.rule ... without effective
  operations") and check the result with `odoo_access`.

Source: odoo/upgrade_code/19.4-00-ir-access.py:1, 78-238, 296-406, 477-628, 637-668

## 19.4 ormcache-on-transaction

```python
self.env.registry.clear_cache()            # before
self.env.transaction.invalidate_ormcache() # after
```

Plain text substitution of `\bregistry\.clear_cache`: `registry = self.env.registry;
registry.clear_cache('x')` becomes `transaction.invalidate_ormcache('x')` (an undefined name), and
`self.pool.clear_cache()` / `clear_all_caches()` are not touched. Review every hit (ORM004).

Source: odoo/upgrade_code/19.4-00-ormcache-on-transaction.py, odoo/orm/environments.py:833

## 19.5 tuple-rec_names_search, material-symbols-icons

```python
    _rec_names_search = ['name', 'ref']    # before
    _rec_names_search = ('name', 'ref')    # after; ['name'] -> ('name',)
```

Only files under a `models` directory, lines indented by exactly 4 spaces, string literals only.

Material Symbols (examples are the script's own self-tests):

| Before | After |
|---|---|
| `<i class="fa fa-user fa-fw text-muted"/>` | `<i class="oi oi-fw oi-filled text-muted" data-icon="person"/>` |
| `<i class="oi oi-archive"/>` | `<i class="oi" data-icon="archive"/>` |
| `<button icon="fa-star" string="a"/>` | `<button icon="star" icon_class="oi-filled" string="a"/>` |
| `options="{'icon': 'fa fa-star'}"` | `options="{'icon': 'star', 'icon_class': 'oi-filled'}"` |
| `<Foo icon="'fa-star'"/>` (OWL component) | `<Foo icon="'star'" iconClass="'oi-filled'"/>` |
| Python `{'icon': 'fa fa-star'}` | `{'icon': 'star', 'iconClass': 'oi-filled'}` |
| JS `{ icon: "fa fa-star" }`, `return "fa fa-phone";` | `{ icon: "star" }`, `return "phone";` |
| JS `querySelector('.fa-star')` | `querySelector('[data-icon="star"].oi-filled')` |
| test `toHaveClass("fa-user")` | `toHaveAttribute("data-icon", "person")` |
| SCSS `.fa.fa-star-o, .fa-spin` | `.oi[data-icon='star']:not(.oi-filled), .oi-spin` |

Not converted: `classList.add("fa-phone")`, mixed strings like `"fa fa-phone text-danger"`, class
names built dynamically, icons stored in data. Skips the `web` addon and `lib/`, `node_modules/`,
`o_spreadsheet/` directories. Mapping: `odoo/upgrade_code/material_symbols_icons_mapping.py`.

Source: odoo/upgrade_code/19.5-00-tuple-rec_names_search.py, odoo/upgrade_code/19.5-00-material-symbols-icons.py:473-563

## 20.0 search-date-filters

```xml
<filter name="date" date="date" start_month="-2" end_month="0" start_year="-1" end_year="0"/>  <!-- before -->
<filter name="date" date="date"/>                                                             <!-- after -->
```

Only removes the attributes; adding `end_date=` / `default_period=` is manual (views skill).

Source: odoo/upgrade_code/20.0-00-search-date-filters.py, odoo/addons/base/rng/common.rng:377-378

## owl3-migration

Run with `--script owl3-migration`. It touches `/static/` files only (`.js` incl. tests, `.xml`),
skipping some core paths. Steps, in order:

| # | Step | Result |
|---|---|---|
| 1 | `useEffect` | renamed `useLayoutEffect`, imported from `@web/owl2/utils` (ok) |
| 2-8 | `onWillRender`, `onRendered`, `useComponent`, `useEnv`, `useSubEnv`, `useChildSubEnv`, `useRef` | import moved from `@odoo/owl` to `@web/owl2/utils` |
| 9-12 | `useState`, `reactive` (also from compat imports) | replaced by `proxy` from `@odoo/owl` |
| 13 | `useExternalListener` | import moved to `@web/owl2/utils` |
| 14 | `t-portal` | `t-custom-portal` |
| 15 | `t-esc` (templates, JS `xml` literals, test strings, `<attribute name="t-esc">`) | `t-out` |
| 16-17 | `t-ref`, `t-model` | `t-custom-ref`, `t-custom-model` |
| 18-19 | `this.` in XML templates of components (`static template = "..."`) and in `xml\`...\`` test fragments | bare component names prefixed with `this.` |
| 20 | `t-slot` | `t-call-slot` |
| 21 | parametric `t-call` in static templates | `t-set` children -> call attributes |
| 22 | `useService("x")` for mapped services | `usePlugin(XPlugin)` + import |

Known stale steps in this tree (verify after running):
- `@web/owl2/utils` only exports `render`, `onWillRender`, `useLayoutEffect`, `useEnv`,
  `useSubEnv`: imports of `onRendered`, `useComponent`, `useChildSubEnv`, `useRef`,
  `useExternalListener` from it are broken. Use OWL 3 equivalents (`signal.ref()`,
  `useListener`, ...).
- Only `click` and `portal` custom directives exist, so `t-custom-ref` / `t-custom-model` fail at
  template compile (`Custom directive "ref" is not defined`). Rewrite them by hand (`t-ref="this.x"`
  with `signal.ref()`, `t-model` on a proxy/signal).
- Service map: `action` -> `ActionManagerPlugin` (real class `ActionPlugin` in
  `@web/webclient/actions/action_plugin`), `sortable` -> `@web/core/util/sortable_plugin` (real path
  `@web/core/utils/sortable_plugin`); several entries target Enterprise modules.
- Steps 14-17 and 20 re-read the file from disk (`file.path.read_text()`), discarding earlier
  in-memory rewrites of the same file in that run: apply, then run the script again until a dry
  run reports no change, reviewing each diff.

Source: odoo/upgrade_code/owl3-migration.py:5-20, 535-564, 605-1341; addons/web/static/src/owl2/utils.js:9-16;
addons/web/static/src/env.js:47-54; addons/web/static/src/owl2/owl3_compatibility_layer.js:266;
addons/web/static/lib/owl/owl.js:5434-5441

## Caveats

1. With odoo-bin, core addons are always appended to the path: scripts run on the Odoo tree, and a
   non-dry run rewrites it. `--glob 'my_module/**/*'` narrows the loaded files, but scripts that
   walk manifests (ir-access) still see every module. Prefer the toolkit or standalone mode.
2. `--dry-run` lists file names only; there is no diff. Diff a copy instead.
3. All scripts are best effort ("they are not silver bullets"): read every change, then validate.
4. ir-access and account-groups are not idempotent; owl3-migration needs several passes; t-call
   and owl3 `this.` steps can be partial (warnings printed, `EXCLUDED_TEMPLATES`).
5. Server-side `t-esc`/`t-raw`, `get_param`, `read_group`, access API, HTTP imports, bank fields,
   `static props`, publicWidget, QUnit are **not** rewritten by any script.

Source: odoo/cli/upgrade_code.py:1-31, 240-249; odoo/modules/module.py:142-155

## Safe workflow (toolkit)

1. Commit or back up the addon (git).
2. `odoo_upgrade_code(path="/my/addons/my_module", from_version="19.0")` copies the addon(s) to a
   temp sandbox, runs each script from `from_version` to 20.0 separately (plus `owl3-migration`
   when the addon has `static/`, unless `include_owl3=false`), never touches the Odoo tree, and
   returns a unified diff per file plus per-script status (and a warning when `ir.access.csv`
   already exists). Use `script="ir-access"` / `"owl3-migration"` / `"material-symbols"` to run one.
3. Review the diff; re-run with `apply=true` to write the changes back. For owl3-migration,
   repeat until the dry run shows no change.
4. `odoo_validate(path)`: fix remaining rule hits using [migration-matrix.md](migration-matrix.md).
5. `odoo_test(modules="my_module")` on a throwaway database, then Hoot suites and tours
   (testing skill, `running-tests.md`).

If ir-access fails in the sandbox because base/dependencies are missing, write
`security/ir.access.csv` by hand (data-security skill) and run the other scripts with `script=`.

Source: odoo20-toolkit/mcp/odoo20_mcp/tools/runtime.py:74-140,
odoo20-toolkit/mcp/odoo20_mcp/runtime/helpers/upgrade_runner.py
