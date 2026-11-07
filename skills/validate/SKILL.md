---
name: validate
description: >-
  Validate an Odoo 20 addon or file with the odoo20 MCP validator (Odoo 19->20 breaking patterns with fixes,
  Odoo's RNG schemas, cross-module checks for fields, buttons, depends, ir.access, xmlids and JS imports, ruff)
  and explain or fix the findings.
when_to_use: >-
  The user asks to check, lint or validate Odoo code, or before declaring Odoo work done. Invoke as
  /odoo20:validate [path].
argument-hint: "[module path | file | folder of modules] (default: the addon being edited)"
allowed-tools: mcp__plugin_odoo20_odoo20__odoo_validate mcp__plugin_odoo20_odoo20__odoo_status
---

# Validate Odoo 20 code

Target: `$ARGUMENTS` (default: the addon you are working on; ask if unclear).

1. `odoo_validate(path=<target>)`. For a large folder start with `min_severity="error"`.
2. For each error: read the cited line, apply the `fix:` given (rule ids are documented in
   `../develop/references/version-traps.md`; cross-module rules at the end of that file). If the finding names
   an `upgrade_code` script and there are many hits, propose `odoo_upgrade_code` instead of hand edits.
3. A finding that is a deliberate exception may be suppressed with a comment containing
   `odoo20-ignore: RULE_ID` on that line - only with a reason.
4. Re-run until no errors remain; mention remaining warnings. Static checks do not replace
   `odoo_test` - suggest running it.
