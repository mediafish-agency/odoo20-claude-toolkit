---
name: migrate
description: >-
  Port Odoo 19 (or older) custom addons to Odoo 20: run Odoo's own upgrade_code scripts safely on a sandbox
  copy (t-call params, base64->bytes, ir.model.access+ir.rule -> ir.access, ormcache, Material Symbols, search
  date filters, OWL 2 -> 3), then fix what the scripts do not cover (get_param, Binary, read_group, access API,
  http imports, removed modules, kanban->card widgets, publicWidget->Interaction, QUnit->Hoot, services->plugins).
when_to_use: >-
  Port an addon written for Odoo <= 19 to Odoo 20 (it fails to install, uses old APIs, or the user asks to
  migrate/port it). Not for `-u` module updates (odoo20:ops) or database migration scripts
  (odoo20:data-security). Invoke as /odoo20:migrate <addon path>.
argument-hint: "<addon path or folder of addons>"
---

# Port an addon to Odoo 20

Target: `$ARGUMENTS` (default: the addon under discussion; ask if unclear).

## Procedure

1. **Inventory.** `odoo_module` (if indexed) or read the manifest; note `version`, `depends` (check each still
   exists in 20: [removed-modules.md](references/removed-modules.md)), static code, security files.
2. **Baseline.** `odoo_validate(<path>)` - keep the report; every rule id is explained in
   `../develop/references/version-traps.md`.
3. **Automated rewrite (dry run).** `odoo_upgrade_code(<path>)` returns the diff of Odoo's scripts (versions
   19.0 -> 20.0, plus `owl3-migration` when the addon has static code). Review it; known caveats:
   `19.4-00-ir-access` is not idempotent and fails on manifests listing missing files; `owl3-migration` may
   import names `@web/owl2/utils` does not export (e.g. `useRef`) - JSI003 catches it.
4. **Apply** with `odoo_upgrade_code(<path>, apply=true)` once the user agrees (or edit by hand).
5. **Manual fixes** from [migration-matrix.md](references/migration-matrix.md), driven by
   `odoo_validate` findings (errors first). Set the manifest version to `20.0.x.y.z` or `x.y` (a `19.0.*`
   version makes Odoo 20 mark the module uninstallable).
6. **Prove it.** `odoo_validate` clean of errors -> `odoo_test(<module>)` -> fix failures -> repeat. For data
   migrations of existing databases add `migrations/<version>/` scripts (`odoo20:data-security`).
7. Report: what the scripts changed, what was fixed manually, remaining warnings, test results.

## References

- [migration-matrix.md](references/migration-matrix.md) - every 19 -> 20 change by layer, automated or manual, rule id
- [removed-modules.md](references/removed-modules.md) - removed/added modules and their replacements
- [upgrade-code.md](references/upgrade-code.md) - how Odoo's upgrade_code works, each script, caveats
