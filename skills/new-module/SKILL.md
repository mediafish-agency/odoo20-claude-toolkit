---
name: new-module
description: >-
  Create a new Odoo 20 addon end to end: scaffold a skeleton that installs (models.Constraint,
  security/ir.access.csv, list/form/search views with <chatter/>, action path, menus, optional OWL 3 widget,
  report, controller, wizard, website Interaction, tests), adapt it to the requirement, validate and test it.
argument-hint: "<module_name> [features: views,mail,owl,report,controller,wizard,interaction,tests]"
disable-model-invocation: true
---

# New Odoo 20 module

Arguments: `$ARGUMENTS` (module name, optional comma-separated features). Ask for the business requirement,
the main model name and the target addons folder when they are not given.

1. `odoo_status` - index ready, runtime found. Check the name is free: `odoo_search(query=<name>, kind="module")`.
2. Look for existing modules covering part of the need (`odoo_search`, `odoo_module`) and depend on them
   instead of re-implementing.
3. `odoo_scaffold(name, dest=<addons folder>, model=..., label=..., features=...)`. If the folder is not an
   indexed addons path, tell the user to add it to the plugin option `extra_addons_paths` (needed for
   validation and installation).
4. Adapt models/views/security to the requirement using `odoo20:orm`, `odoo20:views`, `odoo20:data-security`
   (and `odoo20:owl` / `odoo20:qweb-reports` / `odoo20:http` for those features). Keep one model per file,
   `ir.access.csv` last in `data`.
5. `odoo_validate(<module path>)` until no errors; `odoo_test(<name>)` until green.
6. Summarise: files, models, access rules, how to install (`odoo_db(action="install", ...)`) and test results.
