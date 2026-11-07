# Configuration

The plugin options are set in `/plugin` -> `odoo20` -> *Configure*, with
`claude plugin configure odoo20@mediafish-odoo` (shows the values; `--values-stdin` saves a JSON object), or at
install time with `--config key=value`. After changing an option, run `/reload-plugins` (or restart Claude Code)
so the MCP server restarts with the new values.

## Options

| Option | Default | Environment variable (standalone) | Meaning |
|---|---|---|---|
| `odoo_root` | *(auto-detect)* | `ODOO20_ROOT` | The Odoo 20.0 source tree (the folder containing `odoo-bin`) |
| `extra_addons_paths` | — | `ODOO20_EXTRA_ADDONS` | Comma-separated addons folders: Enterprise, OCA, your own |
| `odoo_python` | `~/.venvs/odoo20/bin/python` | `ODOO20_PYTHON` | Interpreter that runs `odoo-bin` for the runtime tools |
| `odoo_config` | — | `ODOO20_ODOO_CONFIG` | An existing `odoo.conf` whose database connection settings are reused |
| `db_allow` | `odoo20_*` | `ODOO20_DB_ALLOW` | Comma-separated glob patterns of databases the tools may use |
| `allow_writes` | `false` | `ODOO20_ALLOW_WRITES` | Allow `odoo_shell` commits and write calls through `odoo_live_call` |
| `live_url` | — | `ODOO20_LIVE_URL` | A running Odoo 20 server for `odoo_live_call`, e.g. `http://127.0.0.1:8070` |
| `live_db` | — | `ODOO20_LIVE_DB` | Database sent as `X-Odoo-Database` to that server |
| `live_api_key` | — | `ODOO20_LIVE_API_KEY` | API key for that server (sensitive: kept in the OS credential store) |
| — | see below | `ODOO20_DATA_DIR` | Folder for the MCP runtime, index, generated `odoo.conf` and job logs |

Empty values mean "use the default".

### `odoo_root`

Resolution order:

1. the option (or `ODOO20_ROOT`);
2. auto-detection: the project folder, its two parents, and the `odoo*` subfolders of those, keeping the first
   folder that has `odoo-bin` and whose `odoo/release.py` says version 20. A layout like
   `project/{odoo,enterprise,custom}` is found from any of its subfolders;
3. otherwise the tools answer with a message asking you to set the option.

`odoo_status` shows which tree is used and whether it was configured or detected. Set the option to pin a
tree when several Odoo 20 checkouts are nearby.

### `extra_addons_paths`

Every folder listed here is indexed, validated and added to the generated `addons_path`, so its modules can be
looked up, cross-checked (fields used in views, `depends`, xmlids, JS imports), installed and tested.

```text
/home/me/src/enterprise,/home/me/work/acme/addons,/home/me/oca/web
```

Order matters as in Odoo: the core folders come first, then these folders in the order given. A module name
found twice uses the first one, and `odoo_status` lists such shadowed modules. Commas, new lines or `:` can
separate paths.

### `odoo_python`

Any interpreter that can run Odoo 20 works, typically the virtualenv you already use for Odoo 20
(`/path/to/venv/bin/python`). `scripts/setup_odoo_runtime.sh ODOO_ROOT [VENV_DIR] [--isolated]` creates one
(default `~/.venvs/odoo20`). It installs only the requirements your system does not already satisfy, plus
`websocket-client` (without it, browser tests are skipped).

### `odoo_config` and PostgreSQL

The runtime tools always run `odoo-bin` with a config file of their own,
`<data dir>/odoo20.conf` (mode 600). It contains the `addons_path` built from `odoo_root` and
`extra_addons_paths`, `http_interface = 127.0.0.1` and `list_db = True`. Your `~/.odoorc` is never used.

By default Odoo connects to the local PostgreSQL socket as your OS user. If you need another host, port,
role or password, set `odoo_config` to an `odoo.conf` that has them. These keys of its `[options]` section are
copied into the generated file: `db_host`, `db_port`, `db_user`, `db_password`, `db_sslmode`, `pg_path`. The
`PGHOST`, `PGPORT`, `PGUSER` and `PGPASSWORD` environment variables also work, because Odoo and `psql` both read
them.

The role needs the `CREATEDB` right: the test runner duplicates `odoo20_tmpl` into a throwaway database for
each run and drops it afterwards.

### `db_allow`

Every runtime tool checks the database name against these patterns before doing anything. With the default
`odoo20_*`, the template is `odoo20_tmpl` and throwaway test databases are named
`odoo20_test_<module>_<time>`. Keep the
default pattern, or a list that still includes it (for example `odoo20_*,acme_dev_*`), because the template
name is fixed. Never add a pattern that matches a production database.

### `allow_writes`

Off by default. When on:

- `odoo_shell(..., commit=true)` commits; without `commit=true` it still rolls back;
- `odoo_live_call` may call methods other than reads (`create`, `write`, `action_confirm`, ...).

Tools that build or drop allowlisted databases (`odoo_db`, `odoo_test`) do not depend on this option; they are
gated by `db_allow` and by Claude Code's permission prompt.

### Live server (`live_url`, `live_db`, `live_api_key`)

`odoo_live_call` talks to a running Odoo 20 server through the JSON-2 API (`POST /json/2/<model>/<method>`
with `Authorization: Bearer <key>`). To get a key, sign in as the user the calls should run as, open
*My Preferences* -> *Security* tab -> *API Keys* -> *Create API Key* and keep the scope *RPC*. Enter it in the
`/plugin` configuration screen (not in the chat), so it is stored in the OS credential store and never appears
in a transcript.

A dev server started with `odoo_server(action="start", db="odoo20_dev")` listens on `http://127.0.0.1:8070`.

## Data folder

The MCP runtime (virtualenv), the source index (about 120 MB for Community), the generated `odoo20.conf` and
job logs live in one folder, chosen in this order:

1. `ODOO20_DATA_DIR`, if set;
2. the plugin's own data folder (`~/.claude/plugins/data/odoo20-<marketplace>/`), if it already holds a runtime;
3. any other `~/.claude/plugins/data/odoo20-*` folder that holds a runtime (so a reinstall from another
   marketplace, or a manual bootstrap, does not build a second index);
4. the plugin's own data folder;
5. `~/.claude/plugins/data/odoo20-standalone`.

Deleting `index.sqlite3` there forces a full re-index on the next start (about 15-20 seconds).

## Project-level instructions

The skills follow Odoo's house rules (the official `odoo-guidelines` skills). Team-specific conventions such as
module prefixes, the author string or the license belong in your project's `CLAUDE.md`. The skills read it
like any other instruction.
