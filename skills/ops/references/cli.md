# odoo-bin command line (Odoo 20)

Every `odoo-bin` subcommand of Odoo 20 with its verified flags (from `--help` of this tree), what it really
does, and the everyday workflows: create a dev database, install/update a module, run tests, shell
one-liners, translations, code upgrades. Server/config options are detailed in [config.md](config.md).

## Contents
- [Invocation rules](#invocation-rules)
- [Command list](#command-list)
- [server (default)](#server-default)
- [db](#db)
- [module](#module)
- [shell](#shell)
- [neutralize, scaffold, i18n](#neutralize-scaffold-i18n)
- [upgrade_code](#upgrade_code)
- [Other commands](#other-commands)
- [Workflows](#workflows)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## Invocation rules

```text
odoo-bin [--addons-path=PATH,...] <command> [options]      # python -m odoo ... is equivalent
```

- No command (or a first argument starting with `-`) = `server`. `odoo-bin help` lists commands,
  `odoo-bin <command> --help` shows its options.
- A leading `--addons-path=...` (with `=`, before the command) is parsed first and kept for the command;
  it is also how commands shipped by addons (`<addon>/cli/<command>.py`, a `Command` subclass whose
  name equals the file name) are found.
- `-O`/`PYTHONOPTIMIZE` is refused at import ("Running odoo with Python optimization enabled ... is not
  supported").
- The `server`, `shell`, `neutralize`, `obfuscate`, `duplicate`, `populate` commands accept every server
  option (`-c`, `-d`, `--addons-path`, `--log-level`, ...); `db`, `module`, `i18n`, `scaffold`,
  `upgrade_code`, `cloc`, `deploy`, `start` have their own argparse options only.

Source: odoo/cli/command.py:20-145, odoo/__main__.py, odoo/init.py:11-14

## Command list

| Command | Purpose |
|---|---|
| `server` | run the HTTP/cron server; also install/update/test with `-i/-u/--test-tags` |
| `db` | `init`, `load`, `dump`, `duplicate`, `rename`, `drop` (filestore aware) |
| `module` | `install`, `upgrade`, `uninstall`, `force-demo`, `list` |
| `shell` | Python REPL with `env` on a database |
| `neutralize` | neutralize a production copy (no mails, crons, payment...) |
| `scaffold` | generate a module skeleton (stale template, see below) |
| `i18n` | `import`, `export`, `loadlang` |
| `upgrade_code` | rewrite source with `odoo/upgrade_code/*.py` scripts |
| `cloc` | count customization lines (path or database) |
| `deploy` | upload a module folder to a running server (`base_import_module`) |
| `obfuscate` | encrypt/decrypt columns of a database |
| `start` | quick start: addons path = current project, db = folder name |
| `duplicate` | grow a database by duplicating existing records (`--models`, `--factors`) |
| `populate` | synthetic data from `populate.blueprint` (provided by the `populate` addon) |
| `genproxytoken` | IoT: write `proxy_access_token` in the config (provided by `iot_drivers`) |
| `help` | list commands |

Source: odoo/cli/*.py, addons/populate/cli/populate.py, addons/iot_drivers/cli/genproxytoken.py

## server (default)

```bash
./odoo-bin -c ~/odoo20.conf -d mydb -i my_module --stop-after-init   # install then exit
./odoo-bin -c ~/odoo20.conf -d mydb -u my_module --dev=xml,qweb       # update, then serve
```

| Flag | Notes |
|---|---|
| `-d DB` | if the database does not exist it is created empty and `base` is installed (needs CREATEDB) |
| `-i MOD,...` / `-u MOD,...` / `--reinit MOD,...` | install / update / reinitialize (`all` accepted for `-i`/`-u`); need a single `-d` |
| `--stop`, `--stop-after-init` | exit after loading (implied by `--test-enable`/`--test-tags`) |
| `--test-tags SPEC` / `--test-enable` / `--test-file PATH` | run tests, see [Workflows](#workflows) |
| `--with-demo` / `--without-demo=BOOL` | demo data for **new** databases (default: no demo) |
| `--skip-auto-install` | do not auto-install `auto_install` modules |
| `--dev FEATURE,...` | `access`, `qweb`, `reload`, `replica`, `xml`, `all` (see [config.md](config.md#developer-mode---dev)) |
| `--save` | write the effective options to the config file (`-s` short form is gone) |

The server refuses to run with db user `postgres` ("Using the database user 'postgres' is a security
risk, aborting.") and warns for `root` and Python above 3.14.

Source: odoo/cli/server.py:30-127, odoo/tools/config.py:249-280,455-470

## db

```text
odoo-bin db [-c CONFIG] [-D DATA_DIR] [--addons-path P] [-r USER] [-w PWD] [--db_host H] [--db_port P] <sub> ...
```

Global options go **before** the subcommand: `odoo-bin db -c odoo.conf init mydb`.

| Subcommand | Arguments |
|---|---|
| `init DB` | `--with-demo`, `--force` (drop first), `--language en_US`, `--username admin`, `--password admin`, `--country CC`. Installs `base` + auto-install modules |
| `load [DB] DUMP` | DUMP = zip file or URL (raw pg dumps are refused: use `pg_restore`); `-f/--force`, `-n/--neutralize`, `--move` (keep the UUID) |
| `dump DB [PATH]` | `--format zip|dump` (default zip with filestore), `--no-filestore`; no PATH or `-` = stdout |
| `duplicate SRC DST` | `-f/--force`, `-n/--neutralize` (copies the filestore) |
| `rename SRC DST` | `-f/--force` |
| `drop DB` | drops db and filestore |

Database names must match `^[a-zA-Z0-9][a-zA-Z0-9_.-]+$`.

Source: odoo/cli/db.py:35-275, odoo/modules/db.py:45,399-560

## module

```text
odoo-bin module <install|upgrade|uninstall|force-demo|list> [-c CONFIG] [-d DB] [-D DATA_DIR] [-n] MODULE...
```

| Subcommand | Behaviour |
|---|---|
| `install MOD...` | `update_list()`, then `button_immediate_install()`; a `.zip` path imports a data module (needs `base_import_module`) |
| `upgrade MOD...` | `button_immediate_upgrade()`; `all`/`base` upgrades everything; `--outdated` keeps only modules whose disk version is newer |
| `uninstall MOD...` | `button_immediate_uninstall()` |
| `force-demo` | load demo data for every installed module |
| `list` | installed modules and pending state changes (`name, version in db, version on disk, state, description`) |

- `-n/--dry-run` (install/upgrade/uninstall) only **marks** the modules (`button_install()` etc.), prints
  everything that would change state, then rolls back. It loads no code and validates nothing: use it to
  see the dependency closure, not to test an install.
- The command needs exactly one database (from `-d` or the config file) and always runs with `--no-http`.
- Demo data: a module installed later gets demo only if all its dependencies have demo.

Source: odoo/cli/module.py:20-233, odoo/modules/loading.py:88-112, odoo/modules/module_graph.py:202

## shell

```bash
./odoo-bin shell -c odoo.conf -d mydb [--shell-interface ipython|ptpython|bpython|python] [--shell-file startup.py]
```

- Locals: `env` (superuser env, uid 1, context of `context_get()`), `self` (= `env.user`), `odoo`.
  Superuser bypasses `ir.access`: test rights with `env['x'].with_user(env.ref('base.user_admin'))`.
- Changes are **rolled back** when the shell exits: call `env.cr.commit()` to keep them.
- Piped stdin is executed as a script (same locals) instead of opening a REPL:

```bash
echo "print(env['res.partner'].search_count([]))" | ./odoo-bin shell -c odoo.conf -d mydb --log-level=warn
./odoo-bin shell -c odoo.conf -d mydb < scripts/fix_data.py     # end the script with env.cr.commit()
```

- Run tests from the shell (threaded mode only): `from odoo.tests.shell import run_tests;
  run_tests(env, '/my_module')`.

Source: odoo/cli/shell.py:55-162, odoo/orm/environments.py:64-71, odoo/tests/shell.py:19-55

## neutralize, scaffold, i18n

| Command | Usage |
|---|---|
| `neutralize -d DB [--stdout]` | runs every installed module's `data/neutralize.sql` (`--stdout` prints the SQL between `BEGIN;`/`COMMIT;`) |
| `scaffold NAME [DEST] [-t default|theme|PATH]` | renders `odoo/cli/templates/<t>` |
| `i18n export MODULE... [-l LANG...] [-o FILE] [-c] [-d]` | default `-l pot`: writes `i18n/<module>.pot` (or `<lang>.po`) in each module; `-o` one file (`.po/.pot/.tgz/.csv`, `-` = stdout) |
| `i18n import -l LANG FILE... [-w]` | import `.po`/`.csv`; `-w` overwrites existing terms |
| `i18n loadlang -l LANG...` | install languages (`fr`, `es_AR`, `sr@latin`) |

Scaffold warning: the bundled `default` template still emits `security/ir.model.access.csv` with the old
`perm_*` header and a commented manifest entry; Odoo 20 does not load that format. Generate modules
with the `odoo_scaffold` MCP tool (v20 templates) or follow
[module-anatomy](../../develop/references/module-anatomy.md).

Source: odoo/cli/neutralize.py, odoo/cli/scaffold.py, odoo/cli/templates/default/security/ir.model.access.csv.template,
odoo/cli/i18n.py

## upgrade_code

```bash
./odoo-bin upgrade_code --addons-path=/src/custom --from 19.0 --glob 'my_module/**/*' --dry-run
./odoo-bin upgrade_code --addons-path=/src/custom --script owl3-migration --glob 'my_module/**/*'
```

| Option | Meaning |
|---|---|
| `--from VERSION` / `--script NAME` | required, mutually exclusive: all scripts with version >= VERSION, or one script (name or fragment) |
| `--to VERSION` | default `20.0` |
| `--glob GLOB` | default `**/*`, relative to **each** addons path entry |
| `--dry-run` | print `updated:`/`deleted:` file names only, no diff, no write |
| `--addons-path` | extra paths; Odoo's own addons are always added |

- Exit status is 1 when files were (or would be) changed, 0 otherwise.
- `--from 19.0` runs the 19.1-20.0 scripts (t-call, base64-in-xml, ir-access, ormcache, material icons,
  rec_names tuple, search-date-filters, account scripts); `owl3-migration.py` is unversioned and only
  runs with `--script owl3-migration`.
- Without `--glob` it also rewrites Odoo's core tree: always restrict it, work on a git checkout, and
  prefer the sandboxed `odoo_upgrade_code` MCP tool, which shows a diff.

Source: odoo/cli/upgrade_code.py:108-306, odoo/modules/module.py:143-155, odoo/upgrade_code/

## Other commands

| Command | Key options |
|---|---|
| `cloc` | `-p/--path PATH` or `-d/--database DB` (with `--addons-path=`, counts only custom code), `-v` |
| `deploy PATH [URL]` | `--db`, `--login admin`, `--password admin`, `--verify-ssl`, `--force` (re-init, updates `noupdate` records); posts a zip to `/base_import_module/login_upload` |
| `obfuscate` | `--pwd`, `--fields table.col,...`, `--exclude`, `--file`, `--unobfuscate`, `--allfields`, `--vacuum`, `--pertablecommit`, `-y` |
| `start` | `--path DIR` (default cwd or `$VIRTUAL_ENV`), `-d DB` (default folder name); creates the db and sets `--db-filter=^DB$` |
| `duplicate` | `-d DB --models m1,m2 --factors 2,3 [--sep C]` |
| `populate` | `-d DB -b BLUEPRINT [--seed N] [--scale F] [-j N|auto] [--resume [ID]] [--profile]`; the `populate` module must be installed (upgrade it after installing modules that ship `populate/*.xml`) |
| `genproxytoken` | `-c CONFIG [--token-length N]` |

Source: odoo/cli/cloc.py, odoo/cli/deploy.py:17-85, odoo/cli/obfuscate.py, odoo/cli/start.py, odoo/cli/duplicate.py,
addons/populate/cli/populate.py:20-108, addons/populate/README.md

## Workflows

```bash
# 1. dev database with demo data
./odoo-bin db -c ~/odoo20.conf init dev20 --with-demo
# 2. install / update a custom module (addons_path in the config or as leading --addons-path=)
./odoo-bin module install -c ~/odoo20.conf -d dev20 my_module
./odoo-bin -c ~/odoo20.conf -d dev20 -u my_module --stop-after-init
# 3. what would an install pull in?
./odoo-bin module install -c ~/odoo20.conf -d dev20 -n my_module
# 4. tests of one module (at_install + post_install), exits with the result in the log
./odoo-bin -c ~/odoo20.conf -d test20 -i my_module --test-tags /my_module --stop-after-init
./odoo-bin -c ~/odoo20.conf -d test20 -u my_module --test-tags /my_module:TestBook.test_publish
# 5. throwaway copy of a database, neutralized
./odoo-bin db -c ~/odoo20.conf duplicate prod_copy test20 --force --neutralize
# 6. export the module's translation template
./odoo-bin i18n export -c ~/odoo20.conf -d dev20 my_module
# 7. dev server with auto-reload and views read from files
./odoo-bin -c ~/odoo20.conf -d dev20 --dev=reload,xml,qweb
```

- `--test-tags` spec: `[-][tag][/module][:class][.method][[params]]`; tag defaults to `standard` in
  include mode; `-` excludes. `--test-tags` alone enables tests and implies `--stop-after-init`.
- JS/tour tests (`HttpCase`) need Chrome, see [runtime-setup.md](runtime-setup.md#chrome-for-js-tests-and-tours).
- MCP equivalents: `odoo_db` (create/drop/neutralize allowlisted dbs), `odoo_test` (throwaway db +
  tests), `odoo_server`, `odoo_shell`, `odoo_job`.

Source: odoo/tools/config.py:315-345,820-840, odoo/cli/module.py, odoo/cli/db.py

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `odoo-bin -s` (save) | `--save` only | odoo/tools/config.py:253 |
| `odoo-bin populate --models ... --factors ...` (record duplication) | same options under `odoo-bin duplicate`; `populate` now runs blueprints (`-b`) from the `populate` addon | odoo/cli/duplicate.py, addons/populate/cli/populate.py |
| creating dbs through the `db` RPC service / `odoo.service.db` | `odoo-bin db init` / `odoo.modules.db.create` | odoo/modules/db.py:449 |
| trusting `scaffold` output | regenerate `security/ir.access.csv` (v20 header) | odoo/cli/templates/default/security/ir.model.access.csv.template |
| `module install -n` as a validation step | it only marks + rolls back; validate with `odoo_validate`, test with `odoo_test` | odoo/cli/module.py:162-166 |
