---
name: ops
description: >-
  Start the server, create/copy a database, update a module (-u), read logs, profile - running Odoo 20 from source: odoo-bin subcommands (server, shell, db init/load/dump/duplicate/
  drop, module install/upgrade/list with --dry-run, neutralize, i18n, upgrade_code, populate, duplicate),
  odoo.conf options and v20 changes (http_interface default 127.0.0.1, unsafe_policy, db_system, --dev
  features), Python 3.12-3.14 / PostgreSQL >= 16 runtime setup, PDF engine binaries, logging, debugging and
  profiling.
when_to_use: >-
  Starting or configuring an Odoo 20 server, creating or copying databases, installing/updating modules from
  the CLI, reading logs, profiling slow code, or setting up the Odoo 20 Python environment.
---

# Running Odoo 20

## With the toolkit (preferred inside Claude)

- Databases: `odoo_db(action="list|create_template|create|install|upgrade|neutralize|drop", name=...)` -
  only names matching the allowlist (default `odoo20_*`) are touched; `odoo20_tmpl` (base + web) is the template
  copied for tests.
- Dev server: `odoo_server("start", db="odoo20_dev", port=8070)` (127.0.0.1, `--dev xml,qweb,access`), then
  `odoo_server("logs")` / `odoo_server("stop")`.
- Python inside a database: `odoo_shell(db, code)` (rolled back unless `commit=true` with allow_writes).
- The runtime interpreter is the plugin option `odoo_python` (default `~/.venvs/odoo20/bin/python`; `odoo_status`
  shows it). Create one with `/odoo20:setup` or
  `bash "${CLAUDE_SKILL_DIR}/../../scripts/setup_odoo_runtime.sh" <odoo_root>`; a system Python usually cannot run
  Odoo 20 (e.g. Werkzeug older than 3.0).

## Odoo 20 facts

- `odoo-bin module install|upgrade -n/--dry-run` only marks modules and rolls back: it does not validate them.
- `odoo-bin populate` (from the `populate` addon) generates data from blueprints; the old duplication tool is
  now `odoo-bin duplicate`.
- `--http-interface` defaults to `127.0.0.1`; set `0.0.0.0` (or use a proxy) to expose a server.
- `-O`/`PYTHONOPTIMIZE` is refused; `--dev reload` needs watchdog/inotify.

## References

- [cli.md](references/cli.md) - every subcommand with verified flags and common workflows
- [config.md](references/config.md) - important options and their v20 changes
- [runtime-setup.md](references/runtime-setup.md) - Python/PostgreSQL versions, dependencies, PDF engines, Chrome
- [debugging-profiling.md](references/debugging-profiling.md) - logs, dev modes, shell, profiler, common errors
