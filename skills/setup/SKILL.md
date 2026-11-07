---
name: setup
description: >-
  First-run setup and health check of the odoo20 toolkit: locate (or clone) the Odoo 20 source tree, install
  the MCP runtime and build the source index, reuse or create a Python venv that runs Odoo 20, check
  PostgreSQL access, save the plugin options, and create the odoo20_tmpl test template database.
argument-hint: "[path to the Odoo 20 source tree]"
disable-model-invocation: true
---

# odoo20 setup

`PLUGIN` below means the plugin folder: `${CLAUDE_SKILL_DIR}/../..` (resolve it once with
`cd "${CLAUDE_SKILL_DIR}/../.." && pwd`). Optional argument: `$ARGUMENTS` = the Odoo 20 source tree.

Work through the steps in order, run the checks yourself, and report each result in one line. Ask before
anything that downloads a lot, writes outside the plugin data folder, or changes the user's settings. Never run
`sudo` yourself: print the command for the user instead.

## 1. Odoo 20 source tree

- Use the argument if given. Otherwise read the "Odoo root" line of `odoo_status` (when the `odoo20` MCP server
  is connected), else look for a folder with `odoo-bin` in the project folder, its parents, or their `odoo*`
  subfolders.
- Confirm it is Odoo 20: `grep -m1 '^version_info' <root>/odoo/release.py` must show `(20, ...`.
- None found: offer to clone Community (about 1.4 GB, ask first):
  `git clone --depth 1 --branch 20.0 https://github.com/odoo/odoo.git <dir>`.
  Enterprise or other addons go in the `extra_addons_paths` option (step 5), not in `odoo_root`.

## 2. MCP runtime and source index

```bash
ODOO20_ROOT="<root>" bash "PLUGIN/scripts/bootstrap.sh"
```

Needs Python >= 3.12 with `venv` (Debian/Ubuntu: `sudo apt install python3-venv`). The first run installs
`mcp`, `lxml`, `ruff` into the plugin data folder and indexes the whole tree (about 1-2 minutes); later runs
only re-index changed modules.

## 3. Python that runs Odoo 20 (`odoo_python`)

- Ask whether the user already has an Odoo 20 virtualenv. If yes, check it:
  `<venv>/bin/python <root>/odoo-bin --version` must print `Odoo Server 20.0...`.
- If not, create one (asks pip to build packages; ask first):
  `bash "PLUGIN/scripts/setup_odoo_runtime.sh" "<root>"` (creates `~/.venvs/odoo20`). If pip fails on
  missing headers, show the `apt`/`brew` line printed at the top of that script and stop until the user has
  installed them.
- Optional for browser tests (tours, Hoot): Google Chrome or Chromium on the PATH.

## 4. PostgreSQL

- `psql -d postgres -Atc "select current_user, version()"` must work (PostgreSQL >= 16) for the OS user,
  and the role needs `CREATEDB` (`psql -d postgres -Atc "select rolcreatedb from pg_roles where rolname = current_user"`).
- If the role is missing, print for the user: `sudo -u postgres createuser --createdb "$USER"`.
- Remote server, other role or password: use the user's existing `odoo.conf` through the `odoo_config` option
  (its `db_host`, `db_port`, `db_user`, `db_password`, `db_sslmode`, `pg_path` are reused).

## 5. Plugin options

Show the current values with `claude plugin list` (find the id `odoo20@<marketplace>`) and
`claude plugin configure <id>`. Propose the values found above, and after the user agrees save them:

```bash
printf '%s' '{"odoo_root": "<root>", "odoo_python": "<venv>/bin/python"}' \
  | claude plugin configure <id> --values-stdin
```

Optional keys: `extra_addons_paths` (comma-separated), `odoo_config`, `db_allow` (default `odoo20_*`),
`allow_writes`, `live_url`, `live_db`. The `live_api_key` secret should be entered by the user in `/plugin` ->
odoo20 -> configure, so it never appears in the transcript.

Then tell the user to run `/reload-plugins` (or restart Claude Code) and reconnect the server in `/mcp`, so
the MCP server restarts with the new options.

## 6. Template database and final check

After the server reconnects:

1. `odoo_status`: Odoo 20.0, index ready, runtime interpreter found.
2. `odoo_db(action="create_template")`: creates `odoo20_tmpl` (base + web), used by `odoo_test` for throwaway
   databases (a few minutes; poll with `odoo_job`).
3. Optional smoke test: `odoo_validate` on one of the user's addons.

Finish with a short table: step, status, what the user still has to do.
