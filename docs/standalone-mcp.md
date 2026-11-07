# Using the MCP server without the plugin

The `odoo20` MCP server is a plain stdio server. Any MCP client can run it: Claude Desktop, Cursor,
VS Code, Claude Code without the plugin, or your own agent built on the Claude Agent SDK. You get the
20 tools. The skills and the post-edit hook are Claude Code plugin features and are not available this way.

## 1. Get the code and install the runtime

```bash
git clone https://github.com/mediafish-agency/odoo20-claude-toolkit.git ~/src/odoo20-claude-toolkit
export ODOO20_DATA_DIR=~/.local/share/odoo20-mcp       # where the venv, index and logs go
ODOO20_ROOT=~/src/odoo20 bash ~/src/odoo20-claude-toolkit/scripts/bootstrap.sh
```

Optional, for the runtime tools: a Python that runs Odoo 20
(`bash ~/src/odoo20-claude-toolkit/scripts/setup_odoo_runtime.sh ~/src/odoo20`) and a PostgreSQL role
with `CREATEDB`. See [installation.md](installation.md).

## 2. Register the server

The command is always `bash /absolute/path/to/odoo20-claude-toolkit/mcp/run.sh`, configured with the
environment variables from [configuration.md](configuration.md). Use absolute paths: most clients do not
expand `~`.

**Claude Code** (without the plugin):

```bash
claude mcp add odoo20 --scope user \
  -e ODOO20_ROOT=/home/me/src/odoo20 \
  -e ODOO20_DATA_DIR=/home/me/.local/share/odoo20-mcp \
  -e ODOO20_PYTHON=/home/me/.venvs/odoo20/bin/python \
  -- bash /home/me/src/odoo20-claude-toolkit/mcp/run.sh
```

**Claude Desktop** (`claude_desktop_config.json`), **Cursor** (`~/.cursor/mcp.json`) and other clients that
use the `mcpServers` format:

```json
{
  "mcpServers": {
    "odoo20": {
      "command": "bash",
      "args": ["/home/me/src/odoo20-claude-toolkit/mcp/run.sh"],
      "env": {
        "ODOO20_ROOT": "/home/me/src/odoo20",
        "ODOO20_EXTRA_ADDONS": "/home/me/src/enterprise,/home/me/work/addons",
        "ODOO20_PYTHON": "/home/me/.venvs/odoo20/bin/python",
        "ODOO20_DATA_DIR": "/home/me/.local/share/odoo20-mcp",
        "ODOO20_DB_ALLOW": "odoo20_*"
      }
    }
  }
}
```

**VS Code** (`.vscode/mcp.json`):

```json
{
  "servers": {
    "odoo20": {
      "type": "stdio",
      "command": "bash",
      "args": ["/home/me/src/odoo20-claude-toolkit/mcp/run.sh"],
      "env": {
        "ODOO20_ROOT": "/home/me/src/odoo20",
        "ODOO20_DATA_DIR": "/home/me/.local/share/odoo20-mcp"
      }
    }
  }
}
```

Keep `ODOO20_LIVE_API_KEY` out of files you share or commit. Most clients can read it from your environment
or a secret store instead.

## 3. Check it

Ask the assistant to call `odoo_status`. To see startup errors directly:

```bash
ODOO20_ROOT=~/src/odoo20 ODOO20_DATA_DIR=~/.local/share/odoo20-mcp \
  bash ~/src/odoo20-claude-toolkit/mcp/run.sh < /dev/null
```

It prints nothing and exits when everything is fine (stdin closed). Otherwise it prints what is missing.

## The edit check from the command line

The pattern check the plugin's hook runs after each edit also works on its own, for example in a git
pre-commit hook or in CI:

```bash
PYTHONPATH=~/src/odoo20-claude-toolkit/mcp \
  ~/.local/share/odoo20-mcp/venv/bin/python -m odoo20_mcp.check path/to/file.xml path/to/file.py
```

It exits with status 1 when a file has errors.
