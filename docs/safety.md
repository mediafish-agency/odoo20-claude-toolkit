# Safety model

The toolkit runs real commands (`odoo-bin`, `psql`, `git grep`, pip) on your machine. These are the limits
it enforces, and the ones you control.

## What can be touched

| Resource | Rule |
|---|---|
| Odoo source tree (`odoo_root`) | Never written. `odoo_scaffold` and `odoo_upgrade_code` refuse targets inside it. `odoo_upgrade_code` runs Odoo's scripts on a sandbox copy of your addon, with the core exposed read-only, and writes back to your addon only with `apply=true` |
| Your addons | Written only by `odoo_scaffold` (a new module folder that must not exist yet) and `odoo_upgrade_code(apply=true)`. All other edits go through Claude Code's own Edit/Write tools, under your usual permission settings |
| Databases | Only names matching `db_allow` (default `odoo20_*`). Every runtime tool checks the name before running anything. `odoo_db(action="list")` shows the allowlisted names and only a *count* of the others |
| Database contents | `odoo_shell` runs in a transaction that is rolled back, unless `commit=true` **and** `allow_writes=true`. A `cr.commit()` inside the code raises an error |
| Live server | `odoo_live_call` runs read methods (`search_read`, `read`, `fields_get`, `read_group`, `search_count`, ... and methods marked `@api.readonly`) freely. Any other method needs `allow_writes=true` |
| Network | Dev servers started by `odoo_server` and the generated `odoo.conf` bind to `127.0.0.1`. The MCP server itself uses stdio and opens no port |
| Secrets | `live_api_key` is a sensitive option, kept in the OS credential store. It is passed to the server through its environment and never printed. `odoo_status` only says "set" or "unset". The generated `odoo20.conf`, which may contain a database password copied from `odoo_config`, is created with mode 600 |

## Permission prompts

Every tool that can change something is marked `destructiveHint`: `odoo_upgrade_code`, `odoo_db`, `odoo_test`,
`odoo_server`, `odoo_shell` and `odoo_live_call`. Claude Code asks before running them unless you allow them.
The read-only tools are marked `readOnlyHint`.

To skip prompts for the read-only tools, add them to your settings (`.claude/settings.json` or
`~/.claude/settings.json`):

```json
{
  "permissions": {
    "allow": [
      "mcp__plugin_odoo20_odoo20__odoo_status",
      "mcp__plugin_odoo20_odoo20__odoo_search",
      "mcp__plugin_odoo20_odoo20__odoo_grep",
      "mcp__plugin_odoo20_odoo20__odoo_module",
      "mcp__plugin_odoo20_odoo20__odoo_model",
      "mcp__plugin_odoo20_odoo20__odoo_method",
      "mcp__plugin_odoo20_odoo20__odoo_xmlid",
      "mcp__plugin_odoo20_odoo20__odoo_views",
      "mcp__plugin_odoo20_odoo20__odoo_access",
      "mcp__plugin_odoo20_odoo20__odoo_js",
      "mcp__plugin_odoo20_odoo20__odoo_assets",
      "mcp__plugin_odoo20_odoo20__odoo_validate",
      "mcp__plugin_odoo20_odoo20__odoo_job"
    ]
  }
}
```

`odoo_model`, `odoo_views` and `odoo_assets` with `resolve="db"` run an `odoo-bin` helper that only reads,
then rolls back, on an allowlisted database.

## What the hooks run

| Hook | Runs | Network |
|---|---|---|
| `SessionStart` (startup) | `scripts/bootstrap.sh --if-missing --quiet` in the background. When the MCP runtime is missing or its dependency list changed, it creates a virtualenv in the plugin data folder and installs `mcp`, `lxml`, `ruff` and `pytest` from PyPI, then builds the index | PyPI, only when installing |
| `PostToolUse` (Write, Edit, MultiEdit) | `scripts/post_edit_check.sh`: when the edited file is inside an Odoo addon, a local pattern check of that one file. Findings are returned to Claude as context | none |

## Recommendations

- Keep production databases on another PostgreSQL server or role than the one the tools use. The allowlist
  is a guard rail, not an access control system.
- Leave `allow_writes` off unless you are working on a disposable database.
- Use an API key from a test user on a test database for `odoo_live_call`, and set an expiry date on it.
- Review the diff of `odoo_upgrade_code` before running it with `apply=true`, and commit your addon first.

Report vulnerabilities as described in [SECURITY.md](../SECURITY.md).
