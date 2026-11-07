# Migration scripts (Odoo 20)

How to ship data/schema migration scripts with a module: folder layout (`migrations/`, `upgrades/`,
`--upgrade-path`), version folder naming incl. `0.0.0`, the `pre-`/`post-`/`end-` stages, the
`migrate(cr, version)` contract, common patterns and how to test an upgrade. Read it whenever you bump
a module version and stored data must change. Source code rewrites (v19 -> v20 APIs) are a different
tool: `odoo-bin upgrade_code` / the `odoo_upgrade_code` MCP tool.

## Contents
- [When scripts run](#when-scripts-run)
- [Where scripts live](#where-scripts-live)
- [Version folder names](#version-folder-names)
- [Stages: pre, post, end](#stages-pre-post-end)
- [The script contract](#the-script-contract)
- [Patterns](#patterns)
- [Testing an upgrade](#testing-an-upgrade)
- [Pitfalls](#pitfalls)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## When scripts run

A script runs only when **all** of these hold:

| Condition | Detail |
|---|---|
| The module is being upgraded | its state is `to upgrade`: `odoo-bin -u my_module`, `odoo-bin module upgrade my_module`, or the Apps "Upgrade" button. Never on install (`-i`), never on `--reinit`. |
| The manifest version was bumped | for a folder version `V`: `installed_version < V <= manifest version`. Upgrading without bumping `version` runs nothing. |
| The file name starts with the stage prefix | `pre-*.py`, `post-*.py`, `end-*.py`; other files (README, helpers, `foo.py` at the root) are ignored. |

- `installed_version` is the `latest_version` stored in `ir_module_module` (full form, e.g. `20.0.1.2`).
- The manifest `version` is normalised by `adapt_version()`: `1.3` becomes `20.0.1.3`. Accepted
  manifest forms are `x.y`, `x.y.z`, `20.0.x.y`, `20.0.x.y.z` (`check_version`).
- A fresh install never runs migration scripts: put install-time logic in `pre_init_hook` /
  `post_init_hook` (called with `env`), and anything that must also run on existing databases in a
  migration script.

Source: odoo/modules/migration.py:150-230, odoo/modules/loading.py:154-170, odoo/modules/loading.py:236-250, odoo/modules/module.py:579-607

## Where scripts live

`MigrationManager._get_files()` merges three sources per module; scripts of the same version and
stage from all sources are sorted together by file basename.

| Source | Layout | Notes |
|---|---|---|
| `<module>/migrations/` | `migrations/<version>/<stage>-<name>.py` | classic location (e.g. `addons/account/migrations/1.6/pre-migrate.py`) |
| `<module>/upgrades/` | `upgrades/<version>/<stage>-<name>.py` | same semantics (e.g. `addons/hr_holidays/upgrades/1.6/pre-migrate.py`) |
| `--upgrade-path DIR,...` | `DIR/<module>/<version>/<stage>-<name>.py` | out-of-tree scripts; the dir is appended to `odoo.upgrade.__path__`. A dir is accepted only if it contains `*/*/{pre,post,end}-*.py`. |

```text
my_module/
|-- __manifest__.py              # 'version': '1.3'
`-- migrations/
    |-- 1.2/
    |   `-- post-fill_ref.py
    |-- 1.3/
    |   |-- pre-rename_column.py
    |   |-- post-recompute_total.py
    |   `-- end-check_invariants.py
    `-- 0.0.0/
        `-- end-invariants.py    # every version change
```

- A folder named `tests` is skipped; a folder whose name does not match `VERSION_RE` is skipped with
  a warning ("Invalid version for upgrade script").
- `--pre-upgrade-scripts PATH,...` runs individual files before **any** module is loaded, only when
  `-u` is given (they run with stage `pre` against `base`).

Source: odoo/modules/migration.py:100-148, odoo/tools/config.py:274-277, odoo/tools/config.py:908-939, odoo/modules/module.py:157-161, odoo/modules/loading.py:365-367

## Version folder names

`VERSION_RE` accepts an optional Odoo-series prefix followed by 2 or 3 numeric parts.

| Folder | Compared as | Use |
|---|---|---|
| `1.3` / `1.3.1` (major-less) | `20.0.1.3`, but only the module part is compared: `installed[2:] < 1.3 <= current[2:]` | default choice: survives a later series bump without re-running |
| `20.0.1.3` (full) | full version compare `installed < 20.0.1.3 <= current` | tie the script to this Odoo series |
| `0.0.0` | runs whenever `installed_version < current_version` | invariants / repairs on every version change |

- `0.0.0` runs **first** in the `pre` stage and **last** in `post` and `end`.
- Major-less folders are not re-run across a series migration: a module at `19.0.1.3` going to
  `20.0.1.3` does not re-execute `1.3/`.

Source: odoo/modules/migration.py:32-56, odoo/modules/migration.py:156-209

## Stages: pre, post, end

| Stage | Runs | Registry/ORM state | Typical use |
|---|---|---|---|
| `pre-` | before the module's Python code is imported and before its tables are updated | models of modules loaded earlier; **not** this module's new fields/models | raw SQL: rename columns/tables, fix data that would break new constraints, drop obsolete indexes |
| `post-` | after the module's models are set up, schema updated and its `data` (and `demo` if installed) loaded | full ORM for this module and its dependencies | ORM fixes, recomputes, update records by xmlid |
| `end-` | after **all** modules of the update are loaded and the registry is complete | full ORM, all modules | cross-module data, reloading charts, final invariants |

Order inside one module update: `pre` scripts -> load Python -> `init_models` (schema) -> load data ->
`post` scripts -> group reflection -> translations. `end` scripts run in STEP 3.5 for every module of
the graph, before `registry.finalize_constraints()`.

Source: odoo/modules/loading.py:154-232, odoo/modules/loading.py:482-497

## The script contract

```python
# my_module/migrations/1.3/post-recompute_total.py
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    ...
```

- The module must define `migrate`; its parameters must be exactly `(cr, version)` (the names
  `_cr` / `_version` are also accepted), positional. Anything else raises `TypeError` at load.
- `version` is the **installed** version before the upgrade (string, may be `''`), not the folder name.
- `cr` is the update cursor: never `cr.commit()` / `cr.rollback()` (see
  [Transactions](../../odoo-guidelines/guidelines/orm.md#transactions-and-exceptions)).
- The file is executed standalone (`load_script` with module name
  `odoo.upgrade.<module>.<version>.<name>`): use absolute imports, no relative ones.
- `from odoo import api, SUPERUSER_ID` works because `odoo.init` exposes `odoo.SUPERUSER_ID`.
  `api.Environment(cr, uid, context, su=False)`; uid `SUPERUSER_ID` implies `su=True`.
- The log shows `module my_module: Running upgrade [>1.3] pre-rename_column` (pre), `[1.3>]` (post),
  `[$1.3]` (end), then `my_module.pre from 20.0.1.2 to 1.3 in 0.012 seconds`.

Source: odoo/modules/migration.py:233-268, odoo/modules/module.py:646-652, odoo/init.py:39-50, odoo/orm/environments.py:64-67

## Patterns

### 1. Rename a stored field without losing data (pre)

Renaming a field in Python alone loses the data: the new name gets an empty column, and at the end of
the update the old `ir.model.fields` row is unlinked, which drops the old column (`_drop_column`).
Rename the column in `pre-`, and the metadata row so ids referencing the field survive:

```python
# migrations/1.3/pre-rename_column.py
from odoo.tools import sql


def migrate(cr, version):
    if sql.column_exists(cr, 'x_library_book', 'isbn_code'):
        sql.rename_column(cr, 'x_library_book', 'isbn_code', 'isbn')
        cr.execute("""
            UPDATE ir_model_fields SET name = 'isbn'
             WHERE model = 'x.library.book' AND name = 'isbn_code'
        """)
        cr.execute("""
            UPDATE ir_model_data SET name = 'field_x_library_book__isbn'
             WHERE model = 'ir.model.fields' AND name = 'field_x_library_book__isbn_code'
        """)
```

- Field xmlids follow `<module>.field_<model_with_underscores>__<field>`.
- `odoo.tools` itself only re-exports `SQL` and `drop_view_if_exists`; import helpers from
  `odoo.tools.sql` (`column_exists`, `rename_column`, `create_column`, `table_exists`,
  `drop_constraint`, `add_foreign_key`, `index_exists`, `drop_index`...).

Source: odoo/addons/base/models/ir_model.py:77, odoo/addons/base/models/ir_model.py:992-1012, odoo/addons/base/models/ir_model.py:1116-1141, odoo/addons/base/models/ir_model.py:2724-2800, odoo/tools/sql.py:327-375, odoo/tools/__init__.py:15

### 2. Fix data / schema with SQL (pre)

```python
# addons/account/migrations/1.6/pre-migrate.py (core)
def migrate(cr, version):
    cr.execute("DROP INDEX IF EXISTS account_move_sanitize_payment_ref_idx;")
    cr.execute("""
        CREATE INDEX account_move_sanitize_payment_ref_idx
                  ON account_move (regexp_replace(COALESCE(payment_reference, ref, ''), '[^a-zA-Z0-9]', '', 'g'));
    """)
```

`addons/analytic/migrations/1.2/pre-migrate.py` shows `sql.drop_constraint` / `sql.add_foreign_key`.
Always pass values as query parameters (`cr.execute(query, params)` or `SQL(...)`), see
[sql-query.md](../../orm/references/sql-query.md).

Source: addons/account/migrations/1.6/pre-migrate.py, addons/analytic/migrations/1.2/pre-migrate.py

### 3. Update records by xmlid with the ORM (post)

```python
# addons/project/migrations/1.4/post-migrate.py (core)
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env.ref('project.rating_project_request_email_template').active = True
```

Use `env.ref(xmlid, raise_if_not_found=False)` when the record may have been deleted by the user
(`addons/hr_expense/migrations/2.1/pre-migrate.py`). Records in `noupdate="1"` blocks are not
rewritten by the data files on `-u`: a post script is the way to change them.

Source: addons/project/migrations/1.4/post-migrate.py, addons/hr_expense/migrations/2.1/pre-migrate.py

### 4. Recompute a stored compute whose logic changed (post)

A **new** stored computed field is computed for existing rows when its column is created
(`_init_column_data`, unless a `default` fills it). When only the compute **logic** changed, mark
existing records explicitly:

```python
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    orders = env['x.order'].search([('state', '!=', 'cancel')])
    env.add_to_compute(orders._fields['amount_total'], orders)
    orders.flush_recordset(['amount_total'])   # runs the pending recompute now
```

`env.add_to_compute` asserts the field is stored and computed; `flush_recordset` /
`flush_model` call `_recompute_recordset` / `_recompute_model` before writing. Batch very large
tables (search in chunks) to bound memory.

Source: odoo/orm/fields.py:1298-1345, odoo/orm/environments.py:483-488, odoo/orm/models.py:5834-5860, addons/account/models/account_account.py:931

### 5. Cross-module work and invariants (end, 0.0.0)

```python
# addons/l10n_es/migrations/5.4/end-migrate.py (core)
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for company in env['res.company'].search([('chart_template', 'like', r'es\_%')], order="parent_path"):
        env['account.chart.template'].try_loading(company.chart_template, company, force_create=False)
```

`addons/l10n_ch/migrations/0.0.0/pre-migrate-qr-template.py` is a `0.0.0` repair that runs on every
version change (fixes a view's `inherit_id` before the data files are reloaded).

Source: addons/l10n_es/migrations/5.4/end-migrate.py, addons/l10n_ch/migrations/0.0.0/pre-migrate-qr-template.py

## Testing an upgrade

1. Make a throwaway copy of a database that has the **old** module version installed:
   `odoo-bin db -c odoo.conf duplicate prod_copy upg_test` (`-f` drops an existing target,
   `-n` neutralizes the copy), or install the old code on a fresh DB.
2. Bump `version` in `__manifest__.py`, add the scripts.
3. Run the upgrade and stop:
   ```bash
   ./odoo-bin -c odoo.conf -d upg_test -u my_module --stop-after-init
   # or
   ./odoo-bin module upgrade -c odoo.conf -d upg_test my_module
   ```
   `module upgrade --outdated` only upgrades modules whose on-disk version is newer;
   `module upgrade -n` only marks modules and rolls back: it does **not** execute scripts.
4. Check the log for `Running upgrade [>1.3] ...` lines; inspect the data with `odoo_db` /
   `odoo_shell`; then run the module tests on that DB (`--test-enable` / `--test-tags`, or the
   `odoo_test` MCP tool on a scratch DB).
5. Re-running step 3 on a DB already at the new version runs no script (version unchanged). Still
   write scripts defensively (`column_exists` guards): a multi-version jump runs several folders in
   one update, and a failed update is retried from the old version.

Source: odoo/cli/db.py:159-170, odoo/cli/module.py:100-107, odoo/cli/module.py:189-208, odoo/tools/config.py:255-260, odoo/tools/config.py:472

## Pitfalls

- **Forgot to bump the version**: `-u` reloads data and schema but runs no script.
- **ORM in `pre-` for this module's new fields**: they do not exist yet; use SQL.
- **Copying old core scripts**: some still update `ir_rule` (`addons/hr_holidays/upgrades/1.6/`,
  `addons/hr_timesheet_attendance/upgrades/1.1/`); `ir.rule` and `ir.model.access` no longer exist as
  models in v20, target `ir.access` (see [ir-access.md](ir-access.md)).
- **v20 API in scripts**: `ir.config_parameter` has `get_str/get_int/get_float/get_bool` and
  `set_*` only (ORM001), `ir.attachment.datas` is gone (`raw`, ORM014), no `pytz` (ORM015). Run
  `odoo_validate` on migration scripts too.
- **Long scripts**: the timing line is logged at `RUNBOT` level above 20 s; batch large updates in SQL.
- **Uninstall vs upgrade**: removing a module is not a migration; use `uninstall_hook`.

Source: odoo/modules/migration.py:220-230, addons/hr_holidays/upgrades/1.6/pre-migrate.py, odoo/addons/base/models/ir_config_parameter.py

## v19 habit -> Odoo 20

The migration mechanism itself is unchanged from 19.0 (only a per-stage timing log was added). What
changes is what the scripts may touch.

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `odoo-bin -u mod` only | also `odoo-bin module upgrade [-n] [--outdated] mod` | odoo/cli/module.py |
| SQL on `ir_model_access` / `ir_rule` | rows live in `ir_access` (model `ir.access`) | odoo/addons/base/models/ir_access.py |
| `env['ir.config_parameter'].get_param('k')` | `.sudo().get_str('k')` (typed getters) | odoo/addons/base/models/ir_config_parameter.py |
| `odoo-bin populate` to fake volume before testing | `odoo-bin duplicate` (or blueprints, see [populate.md](populate.md)) | odoo/cli/duplicate.py |
| editing source by hand for API renames | `odoo-bin upgrade_code` (`odoo_upgrade_code`) for code, migrations for data | odoo/upgrade_code/ |
