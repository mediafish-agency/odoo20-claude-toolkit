# Changelog

## 0.1.1 - 2026-11-07

- A wrong `odoo_root` option (a folder without `odoo-bin`) no longer breaks the tools: an Odoo 20 tree found
  near the project is used instead, with a warning in `odoo_status`; otherwise errors name the bad path.
- Install docs: `odoo_root` is a placeholder for your own checkout; `/odoo20:setup` is typed at the Claude
  prompt, not in a shell.
- Generated references no longer depend on indexing order.

## 0.1.0 - 2026-11-07

First public release.

- 15 skills for Odoo 20.0: `develop`, `orm`, `http`, `views`, `data-security`, `qweb-reports`, `owl`,
  `website-pos`, `testing`, `migrate`, `ops`, and the workflow commands `setup`, `new-module`, `validate`,
  `run-tests`; 63 reference files verified against the Odoo 20.0 source.
- Odoo's five official skills (`odoo-guidelines`, `odoo-web-guidelines`, `odoo-review`, `odoo-security`,
  `odoo-git`) included unchanged from Odoo 20.0.
- MCP server `odoo20` with 20 tools: source index and lookups (models, methods, views, xmlids, ir.access, JS
  registries/patches/exports, assets); validator with 91 Odoo 19 -> 20 rules, Odoo's RNG schemas,
  cross-module checks and ruff; Odoo's `upgrade_code` run on a sandbox copy; scaffolding; databases,
  tests (Python and Hoot), dev server, guarded shell; JSON-2 client.
- Hooks: runtime bootstrap on session start; Odoo 20 check of every edited file.
- Odoo 20 source tree auto-detection, reuse of an existing `odoo.conf` for the PostgreSQL connection,
  Linux and macOS support.
