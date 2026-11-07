---
name: data-security
description: >-
  Default for any Odoo work in this Odoo 20.0 tree even when no version is named; takes priority over generic odoo-* skills (17-19 advice such as ir.model.access.csv, ir.rule records is wrong in 20). Who can see/edit records, access rights, record rules, groups, cron, sequences, email templates, translations - Odoo 20 data and security files: the new ir.access model (security/ir.access.csv with
  id,name,model_id,group_id/id,operation,domain; permission vs restriction rows; 'access' domain operator)
  that replaces ir.model.access and ir.rule, groups and privileges, XML/CSV data files (type="bytes", noupdate,
  function), ir.cron, sequences, server actions, mail templates and activity types, i18n .po/.pot,
  migrations/upgrades scripts, neutralize.sql, and populate blueprints.
when_to_use: >-
  Editing security/, data/, demo/, i18n/, migrations/, upgrades/ or populate/ in an Odoo 20 addon, granting or
  restricting access, or converting ir.model.access.csv / ir.rule records. Data-migration scripts
  (migrations/<ver>/pre|post-*.py) for existing databases live here; porting code is odoo20:migrate.
---

# Odoo 20 data and security

## Workflow

1. See current access for a model: `odoo_access(model)`; group xmlids: `odoo_search(kind="xmlid",
   query="group_")`; check a data record: `odoo_xmlid`.
2. Write rows following [ir-access.md](references/ir-access.md); audit with
   [odoo-security](../odoo-security/SKILL.md) (never grant c/u/d to portal/public/everyone without reason).
3. List `security/ir.access.csv` **last** in the manifest `data`. `odoo_validate` checks operations, models,
   groups, domains and models left without any permission row.

## Odoo 20 rules

- One model, `ir.access`. CSV header: `id,name,model_id,group_id/id,operation,domain`.
  - `model_id` = technical model name (`library.book`), not `model_library_book`.
  - `operation` = ordered subset of `crud`: crud, cru, crd, cud, rud, cr, cu, cd, ru, rd, ud, c, r, u, d.
  - With `group_id` -> **permission** (OR-ed across the user's groups); empty `group_id` -> **restriction**
    (AND-ed for everybody). No permission row -> nobody has access.
  - Multi-company: a restriction row with `[('company_id', 'in', company_ids)]`.
  - Portal on children: `[('order_id', 'access', 'read')]`.
  - "All users": `base.group_everyone`.
- Disable another module's row: `<record id="module.row_xmlid" model="ir.access"><field name="active" eval="False"/></record>`.
- Binary data from files: `<field name="image" type="bytes" file="module/static/img/x.png"/>` (not base64).
- XML eval `pytz` is a shim without `.localize()`; prefer dynamic date strings in domains.
- `mail.activity.type.suggested_next_type_id` replaces the chaining fields; icons are Material names.

## References

- [ir-access.md](references/ir-access.md) - ir.access semantics, recipes, conversion from ir.model.access/ir.rule
- [groups-privileges.md](references/groups-privileges.md) - res.groups, privileges, base groups, field/menu groups
- [data-files.md](references/data-files.md) - XML/CSV data syntax, noupdate, eval context, load order
- [cron-sequences-actions.md](references/cron-sequences-actions.md) - ir.cron, ir.sequence, server actions
- [mail-data.md](references/mail-data.md) - mail templates, activity types, layouts, subtypes
- [i18n.md](references/i18n.md) - translations in code and data, export/import
- [migration-scripts.md](references/migration-scripts.md) - migrations/ and upgrades/ scripts
- [populate.md](references/populate.md) - populate blueprints and odoo-bin duplicate
