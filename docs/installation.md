# Installation

## Requirements

What you need depends on which parts you use:

| Part | Needs |
|---|---|
| Skills | Claude Code with plugin support |
| Static MCP tools (lookups, validator) and the edit hook | Python 3.12+ with `venv`, an Odoo 20.0 source checkout, `git` (fast `odoo_grep`) |
| Runtime tools (`odoo_test`, `odoo_db`, `odoo_server`, `odoo_shell`, `resolve="db"`, `odoo_upgrade_code`) | A Python environment that runs Odoo 20 (`odoo-bin`), PostgreSQL 16+ with a role that can create databases |
| JavaScript tests and tours | Google Chrome or Chromium on the `PATH` |
| `odoo_live_call` | A running Odoo 20 server and an API key with scope RPC |

Supported systems: Linux and macOS. On Windows, run Claude Code inside WSL2 (the scripts need bash, and
Odoo development on native Windows is not covered).

Odoo 20 itself needs Python 3.12-3.14 and PostgreSQL 16 or newer. A system Python with older packages
usually cannot run Odoo 20 (for example, Werkzeug older than 3.0 fails at import). Use a dedicated
virtualenv.

## 1. Get the Odoo 20 source

Skip this if you already have an Odoo 20.0 checkout.

```bash
git clone --depth 1 --branch 20.0 https://github.com/odoo/odoo.git ~/src/odoo20   # about 1.4 GB
```

Enterprise (if you have access) and your own addons stay in their own folders. You add them later with the
`extra_addons_paths` option.

## 2. Install the plugin

From a terminal. Replace `/path/to/your/odoo20` with the folder of **your** Odoo 20 checkout (the one that
contains `odoo-bin`):

```bash
claude plugin marketplace add mediafish-agency/odoo20-claude-toolkit
claude plugin install odoo20@mediafish-odoo --config odoo_root="/path/to/your/odoo20"
```

Or in one command (adds the marketplace if needed):

```bash
claude plugin install odoo20 --marketplace mediafish-agency/odoo20-claude-toolkit \
  --config odoo_root="/path/to/your/odoo20"
```

The `--config` part is optional when you start Claude Code inside the Odoo folder or next to it (see the
auto-detection rule below). If the configured folder has no `odoo-bin`, the server falls back to
auto-detection and `odoo_status` shows a warning. To change the value later:
`claude plugin configure odoo20@mediafish-odoo`.

Or inside Claude Code: `/plugin` -> *Marketplaces* -> add `mediafish-agency/odoo20-claude-toolkit`, then
install `odoo20` from it.

### Choosing the scope

By default the plugin is installed for your user (all projects). If you also work on Odoo 17-19 projects,
install it only where you work on Odoo 20, so its skills don't steer older projects towards Odoo 20 APIs:

```bash
cd ~/work/my-odoo20-project
claude plugin install odoo20@mediafish-odoo --scope project   # shared with the team via .claude/settings.json
# or --scope local                                             # this project, only for you
```

`odoo_root` can stay empty when you start Claude Code inside the Odoo tree or next to it. The server then
auto-detects an Odoo 20 tree in the project folder, its two parent folders, and their `odoo*` subfolders.

## 3. First run: `/odoo20:setup`

Start Claude Code in your project (`cd /path/to/your/project && claude`) and type this at the **Claude
prompt**. It is a Claude Code slash command: typed in bash it fails with `No such file or directory`.

```
/odoo20:setup
```

The setup skill walks through these steps and asks before anything that downloads or changes settings:

1. find (or clone) the Odoo 20 source tree;
2. install the MCP runtime (`mcp`, `lxml`, `ruff` in a private virtualenv) and index the source (1-2 minutes
   the first time, seconds afterwards);
3. reuse your existing Odoo 20 virtualenv, or create `~/.venvs/odoo20`;
4. check PostgreSQL access and the right to create databases;
5. save the plugin options;
6. after you reload the plugin, create the template database `odoo20_tmpl` used by the test runner.

On the very first session the `SessionStart` hook already starts installing the MCP runtime in the
background. Until it finishes, `/mcp` shows the `odoo20` server as failed. Wait about a minute, then
reconnect it from `/mcp` (or restart Claude Code).

### Manual setup (without the skill)

The plugin is installed under `~/.claude/plugins/cache/mediafish-odoo/odoo20/<version>/`; below, `PLUGIN`
means that folder.

```bash
# MCP runtime + source index
ODOO20_ROOT=~/src/odoo20 bash PLUGIN/scripts/bootstrap.sh

# A Python that runs Odoo 20: reuse yours, or create ~/.venvs/odoo20
bash PLUGIN/scripts/setup_odoo_runtime.sh ~/src/odoo20
#   building some packages needs system headers:
#   Debian/Ubuntu: sudo apt install python3-dev python3-venv libpq-dev libldap2-dev libsasl2-dev \
#                  libxml2-dev libxslt1-dev libjpeg-dev zlib1g-dev
#   macOS:         brew install python@3.12 postgresql@16 openldap

# PostgreSQL role for your OS user, allowed to create databases (once)
sudo -u postgres createuser --createdb "$USER"

# Plugin options (see configuration.md); omitted keys keep their values
claude plugin configure odoo20@mediafish-odoo                     # show current values
printf '%s' '{"odoo_root": "/home/me/src/odoo20", "odoo_python": "/home/me/.venvs/odoo20/bin/python"}' \
  | claude plugin configure odoo20@mediafish-odoo --values-stdin
```

Then, in Claude Code, run `/reload-plugins` (or restart) and ask Claude to run
`odoo_db(action="create_template")`.

## 4. Check that everything works

- `/mcp` lists `plugin:odoo20:odoo20` as **connected**.
- Ask *"run odoo_status"*: Odoo 20.0, index ready, runtime interpreter found, your addons paths listed.
- Typing `/odoo20:` shows the plugin's skills.
- Have Claude put `t-esc` in a server QWeb template of one of your addons: right after the edit, the hook
  reports rule `XML003` and Claude replaces it with `t-out`.

## Team setup

Commit this to your project's `.claude/settings.json` (or run the install with `--scope project`, which
writes it for you). Teammates who trust the folder are then offered the plugin automatically:

```json
{
  "extraKnownMarketplaces": {
    "mediafish-odoo": {
      "source": { "source": "github", "repo": "mediafish-agency/odoo20-claude-toolkit" }
    }
  },
  "enabledPlugins": {
    "odoo20@mediafish-odoo": true
  }
}
```

Each developer still runs `/odoo20:setup` once, because paths, virtualenvs and PostgreSQL roles are personal.
Put shared options such as `extra_addons_paths` in the project documentation. Paths differ per machine, so
the options are not committed.

## Updating

```bash
claude plugin marketplace update mediafish-odoo
claude plugin update odoo20@mediafish-odoo
```

Restart Claude Code afterwards. When a release changes the MCP server's Python dependencies, the
`SessionStart` hook reinstalls them automatically. The source index refreshes changed modules whenever the
server starts. After pulling a new Odoo 20 revision, nothing else needs to be done.

## Uninstalling

```bash
claude plugin uninstall odoo20@mediafish-odoo        # also deletes its data folder unless --keep-data
claude plugin marketplace remove mediafish-odoo
```

Things the plugin created outside its data folder, which you may want to remove by hand:

- databases matching `odoo20_*` (for example `odoo20_tmpl`): `dropdb odoo20_tmpl`;
- their filestores under `~/.local/share/Odoo/filestore/` (Linux; on macOS
  `~/Library/Application Support/Odoo/filestore/`);
- the Odoo virtualenv `~/.venvs/odoo20`, if `setup_odoo_runtime.sh` created it;
- any leftover `~/.claude/plugins/data/odoo20-*` folder (for example `odoo20-standalone`).
