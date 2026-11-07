# Troubleshooting

Start with `odoo_status`. It shows the Odoo tree in use, the addons paths, the index state, the runtime
interpreter, the database allowlist and the data folder.

## The `odoo20` MCP server does not connect

`/mcp` shows `plugin:odoo20:odoo20` as failed.

- **First session after installing**: the `SessionStart` hook is still installing the runtime in the
  background. Wait a minute, then reconnect from `/mcp`. Or run `/odoo20:setup`.
- **See the actual error** by starting the server by hand. It exits quietly when everything is fine:

  ```bash
  bash ~/.claude/plugins/cache/mediafish-odoo/odoo20/*/mcp/run.sh < /dev/null
  ```

- `runtime not installed yet`: run the bootstrap script it names. It needs Python >= 3.12 with `venv`
  (Debian/Ubuntu: `sudo apt install python3-venv`; macOS: `brew install python@3.12`). Use
  `PYTHON=/path/to/python3.12 bash .../scripts/bootstrap.sh` for an interpreter that is not on the `PATH`.
- Behind a proxy: the bootstrap uses pip, so set `HTTPS_PROXY`/`PIP_INDEX_URL` as you would for pip.

## "No Odoo 20 source tree configured"

Set the `odoo_root` option to the folder that contains `odoo-bin`, then `/reload-plugins`. Auto-detection only
accepts trees whose `odoo/release.py` says version 20. A tree in some unrelated folder will not be found.

## "The Odoo source index is being built"

The first index build takes 15-20 seconds for Community, longer with Enterprise. Retry after a moment, or
watch `odoo_status`. After that, only changed modules are re-indexed when the server starts or when you call
`odoo_status(refresh=true)`. A damaged index is rebuilt after you delete `index.sqlite3` in the data folder.

## A module is not found

Its folder must be in `odoo_root` or in `extra_addons_paths`, and it must contain a `__manifest__.py`.
Point `extra_addons_paths` at the folder *containing* the modules, not at a module itself. A module name that
exists in two paths uses the first one; `odoo_status` lists such shadowed modules.

## Runtime tools fail

| Message or symptom | Fix |
|---|---|
| `Odoo runtime interpreter ... not found` | Set `odoo_python` to a Python that runs Odoo 20, or run `/odoo20:setup` to create `~/.venvs/odoo20` |
| `TypeError ... unbound_message` or other import errors in `odoo-bin` | That interpreter has packages too old for Odoo 20 (for example a system Werkzeug 2.x). Use a virtualenv built from Odoo's `requirements.txt` |
| `role "<you>" does not exist` | `sudo -u postgres createuser --createdb "$USER"` |
| `permission denied to create database` | `sudo -u postgres psql -c 'ALTER ROLE "<you>" CREATEDB'` |
| `password authentication failed` / remote server | Set `odoo_config` to an `odoo.conf` with `db_host`, `db_user`, `db_password`, ... (see [configuration.md](configuration.md)) |
| `database '...' is not in the allowlist` | Use a name matching `db_allow` (default `odoo20_*`). This refusal is deliberate |
| `odoo_test` says the template is missing | Run `odoo_db(action="create_template")` once |
| Browser tests reported as **SKIPPED** | Install `websocket-client` in the Odoo virtualenv (`setup_odoo_runtime.sh` does it) and make Chrome or Chromium available on the `PATH` |
| A long run returned a job id | Poll it with `odoo_job(job_id)`. Logs: `odoo_job(job_id, action="log", grep="ERROR|FAIL")` |

## The edit hook reports findings you disagree with

Each finding names a rule id (for example `XML003`). The catalogue with reasons and fixes is in
[version-traps.md](../skills/develop/references/version-traps.md). For a deliberate exception, put a comment
containing `odoo20-ignore: XML003` on that line. If the rule is wrong for Odoo 20.0, please open an issue
with the snippet.

## Claude still writes Odoo 17-19 code

- Check that the plugin is enabled in this project (`/plugin`) and that the skills are listed under
  `/odoo20:`.
- Other installed Odoo skills may compete; see [skills.md](skills.md#living-with-other-odoo-skills).
- Ask explicitly: *"use /odoo20:develop"* or the specific skill. Then ask Claude to run
  `/odoo20:validate` on the result.

## Reporting a problem

Open an issue at <https://github.com/mediafish-agency/odoo20-claude-toolkit/issues> with your OS, the Claude
Code version (`claude --version`), the `odoo_status` output, and the error. Remove any paths or names you
don't want public.
