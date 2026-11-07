# Groups and privileges (Odoo 20)

How to declare `res.groups` and `res.groups.privilege` records, which base groups exist in v20,
how the light/regular user tier works, and how groups gate fields, views, menus and code.
Access rows themselves are in [ir-access.md](ir-access.md); the `groups=` field parameter is
detailed in [fields.md](../../orm/references/fields.md).

## Contents
- [res.groups fields](#resgroups-fields)
- [res.groups.privilege (the "Scope")](#resgroupsprivilege-the-scope)
- [Declaring groups in XML](#declaring-groups-in-xml)
- [Base groups to know](#base-groups-to-know)
- [Light vs regular users](#light-vs-regular-users)
- [Using groups](#using-groups)
- [Pitfalls](#pitfalls)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## res.groups fields

| Field | Meaning |
|---|---|
| `name` (translate, required) | Label; `full_name` (computed, `_rec_name`) is `"<privilege> / <name>"` when a privilege is set |
| `privilege_id` | Many2one `res.groups.privilege`, label **"Scope"**; groups of one privilege render as one selection on the user form |
| `sequence` | Order inside the privilege (lowest = fewest rights) |
| `implied_ids` | Groups every member automatically gets (table `res_groups_implied_rel`) |
| `implied_by_ids` | Reverse of `implied_ids` (same table); lets a group attach itself under existing groups |
| `all_implied_ids` / `all_implied_by_ids` | Transitive closures (computed, searchable) |
| `disjoint_ids` | Computed: `base.group_user`, `base.group_portal`, `base.group_public` are mutually exclusive |
| `user_ids` / `all_user_ids` | Explicit members / members including implication |
| `access_ids` | One2many to `ir.access` (replaces v19 `model_access` + `rule_groups`) |
| `menu_access`, `view_access` | Many2many to `ir.ui.menu` / `ir.ui.view` (inverse of their `group_ids`) |
| `comment` | Description shown in the user form |
| `share` | Group used for external sharing (portal-like) |
| `api_key_duration` | Max API key lifetime in days for members (`CHECK >= 0`) |

Model facts: `_order = 'privilege_id, sequence, name, id'`, `_allow_sudo_commands = False`,
`_clear_cache_name = 'groups'` with `_clear_cache_on_fields = {'implied_ids', 'implied_by_ids'}`.
A constraint rejects a group that would imply two disjoint groups.

Source: odoo/addons/base/models/res_groups.py:14-90,92-121,412-418

## res.groups.privilege (the "Scope")

| Field | Meaning |
|---|---|
| `name` (translate, required) | Shown as the selection label in the user form |
| `description` (translate) | Help text |
| `placeholder` (translate, default "No") | Label of the empty choice ("user has none of these groups") |
| `sequence` (default 100) | Order inside the category |
| `category_id` | Many2one `ir.module.category` (the app section of the user form; `ir.module.category.privilege_ids` is the inverse) |
| `group_ids` | One2many to `res.groups.privilege_id` |

Put each app's tiered groups (User / All documents / Administrator) under one privilege, each
implying the previous one. Feature-toggle groups (`group_use_lead`, `group_multi_company`) have no
privilege.

Source: odoo/addons/base/models/res_groups_privilege.py:1-15, odoo/addons/base/models/ir_module.py:90, odoo/addons/base/models/res_groups.py:541-577

## Declaring groups in XML

File `security/<module>_security.xml`, listed first in the manifest `data` (before views that use the
groups and before `security/ir.access.csv`, which goes last).

```xml
<odoo>
    <record model="res.groups.privilege" id="res_groups_privilege_sales">
        <field name="name">Sales</field>
        <field name="sequence">1</field>
        <field name="category_id" ref="base.module_category_sales"/>
    </record>

    <record id="group_sale_salesman" model="res.groups">
        <field name="name">User: Own Documents Only</field>
        <field name="sequence">10</field>
        <field name="privilege_id" ref="res_groups_privilege_sales"/>
        <field name="implied_ids" eval="[Command.link(ref('base.group_user'))]"/>
        <field name="comment">the user will have access to his own data in the sales application.</field>
    </record>

    <record id="group_sale_manager" model="res.groups">
        <field name="name">Administrator</field>
        <field name="sequence">30</field>
        <field name="privilege_id" ref="res_groups_privilege_sales"/>
        <field name="implied_ids" eval="[Command.link(ref('group_sale_salesman_all_leads'))]"/>
        <field name="user_ids" eval="[Command.link(ref('base.user_root')), Command.link(ref('base.user_admin'))]"/>
    </record>
</odoo>
```

- Core still writes `(4, ref(...))` in many files; `Command.link(...)` is the same command and is
  available in the XML eval context.
- Give the manager group to `base.user_root` and `base.user_admin` so the admin sees the app.
- Use `implied_by_ids` to hang a new group under an existing one without editing it, as base does
  for `group_no_one` and `group_everyone`.
- Categories come from `odoo/addons/base/data/ir_module_category_data.xml`
  (`base.module_category_sales`, `base.module_category_services`, `base.module_category_supply_chain`,
  `base.module_category_human_resources`, ...). Check an xmlid with `odoo_xmlid`.

Source: addons/sales_team/security/sales_team_security.xml:2-31 (adapted to `Command.link`), addons/maintenance/security/maintenance.xml:1-17, odoo/tools/convert.py:49-60, odoo/addons/base/data/ir_module_category_data.xml:38,43,53,100

## Base groups to know

All in `odoo/addons/base/security/base_groups.xml`:

| xmlid | Name | Notes |
|---|---|---|
| `base.group_user` | Role / User | Internal user; disjoint with portal and public |
| `base.group_user_regular` | Is regular user | v20: auto-implied by every non-light group (see below); `api_key_duration` 90 |
| `base.group_portal` | Role / Portal | |
| `base.group_public` | Role / Public | Website visitor (`base.public_user`) |
| `base.group_everyone` | Role / Everyone | v20: implied by user, portal and public; use it in `ir.access` for "everybody" |
| `base.group_erp_manager` | Access Rights | Implies `group_user`; may manage users and groups |
| `base.group_system` | Role / Administrator | Implies `group_erp_manager` and `group_sanitize_override` |
| `base.group_sanitize_override` | Bypass HTML Field Sanitize | |
| `base.group_no_one` | Technical Features | Implied by `group_user` and `group_system`; effective only in debug mode |
| `base.group_multi_company` | Multi Companies | Feature group |
| `base.group_multi_currency` | Multi Currencies | Feature group |
| `base.group_allow_export` | Allowed (privilege Export) | Implied by `group_system` |
| `base.group_partner_manager` | Creation (privilege Contact) | Implies `group_user`; implied by `group_erp_manager` |
| `base.default_user_group` | Default access for new users | noupdate container of groups given to new users |

Source: odoo/addons/base/security/base_groups.xml:11-121

## Light vs regular users

v20 classifies internal users: `res.users.role` is `light_user`, `regular_user` or `group_system`.
A user is *light* when all of their groups are listed by `res.groups._get_light_group_xmlids()`;
`base.group_user_regular` is recomputed (`_apply_group_regular`) on every group create/write/unlink
and again at the end of module loading, so that each non-light group implies it. Light users never
get `base.group_no_one` menus, even in debug.

A feature-toggle group (a `res.config.settings` Boolean with `implied_group=`) must be declared
light, otherwise enabling the setting turns every internal user into a regular user:

```python
from odoo import models

class ResGroups(models.Model):
    _inherit = 'res.groups'

    def _get_light_group_xmlids(self):
        return (
            *super()._get_light_group_xmlids(),
            'crm.group_use_lead',
            'crm.group_use_recurring_revenues',
        )
```

Source: odoo/addons/base/models/res_groups.py:439-498, odoo/addons/base/models/res_users.py:263,430-478,1276, odoo/modules/loading.py:515-522, odoo/addons/base/models/ir_ui_menu.py:70-76, addons/crm/models/res_groups.py:1-14, addons/crm/models/res_config_settings.py:14-15

## Using groups

| Where | Syntax | Effect |
|---|---|---|
| Python field | `fields.Integer(groups="sales_team.group_sale_salesman")` | Field hidden from views/`fields_get` and raises `AccessError` on read/write for non-members; comma = OR, `!xmlid` = NOT |
| Python field, nobody | `groups=fields.NO_ACCESS` (`'.'`) | Only `sudo()` can read/write (secrets, tokens) |
| View node | `<field name="company_id" groups="base.group_multi_company"/>` | Node removed server-side for non-members; `!` supported |
| View record | `<field name="group_ids" eval="[Command.link(ref('x'))]"/>` | Whole view only for members; **not allowed on extension views** (`_check_groups`), put `groups` on nodes instead |
| Menu | `<menuitem ... groups="group_equipment_manager,base.group_user"/>` | Visible if user in any group; `-module.group` in `groups` *removes* a group when updating another module's menu; no groups = visible if the action's model is readable |
| Template | `<template ... groups="base.group_user">` | Sets `group_ids` on the `ir.ui.view` |
| Actions | `group_ids` on `ir.actions.act_window`, `ir.actions.server`, `ir.actions.report` | Restricts the action |
| Python check | `self.env.user.has_group('base.group_system')` | One fully qualified xmlid |
| Python check | `self.env.user.has_groups('base.group_user,!base.group_portal')` | Spec string, same syntax as `groups=` |
| Role helpers | `user._is_internal()`, `_is_portal()`, `_is_public()`, `_is_system()`, `_is_admin()`, `_is_regular()` | Wrap `has_group` with `sudo()` |

Notes:
- `has_group` on another user raises `AccessError` unless the caller is internal or `sudo()`; it returns
  True for `base.group_no_one` only in a debug request.
- Field `groups` are reflected into `ir.model.fields` after data loading
  (`_reflect_field_groups`); the view validator warns when a node uses a field whose groups do not
  cover the node's groups. Check with `odoo_views` / `odoo_validate`.
- Hiding a field with `groups` is UI and API security; hiding with `invisible=` is not.

Source: odoo/orm/models.py:115,2721-2735, odoo/addons/base/models/res_users.py:1163-1227,1272-1300, odoo/addons/base/models/ir_ui_view.py:552-558,1348-1372,1511-1513, odoo/tools/convert.py:335-345,550-553, odoo/addons/base/models/ir_ui_menu.py:29-32,69-123, odoo/addons/base/models/ir_actions.py:313,640, odoo/addons/base/models/ir_actions_report.py:59, odoo/addons/base/models/ir_model.py:1438, addons/sale/models/res_partner.py:13-17, addons/maintenance/views/maintenance_views.xml:946-976, addons/account/views/account_move_views.xml:603

## Pitfalls

- A group with no `ir.access` permission rows grants nothing on data; menus and fields only.
- Loading `security/ir.access.csv` before the XML that defines its groups fails the import
  (unresolved `group_id/id`): groups XML first, CSV last.
- Do not add users to `base.group_user` and `base.group_portal` at once (disjoint constraint).
- `base.group_everyone` is a technical union group: do not assign it to users, imply nothing from it.
- Feature groups toggled from settings: add them to `_get_light_group_xmlids` (see above).
- `has_group('group_x')` without the module prefix: must be fully qualified.

Source: odoo/addons/base/models/res_groups.py:92-121,412-418, odoo/addons/base/models/res_users.py:1215-1227

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `res.groups.model_access` (One2many `ir.model.access`) | `access_ids` (One2many `ir.access`) (SEC006) | odoo/addons/base/models/res_groups.py:30 |
| `res.groups.rule_groups` (Many2many `ir.rule`) | `access_ids` rows with a `domain` | odoo/addons/base/models/res_groups.py:30 |
| `privilege_id` labelled "Privilege" | same field, labelled "Scope" | odoo/addons/base/models/res_groups.py:44 |
| empty-group ACL for "all users" | `base.group_everyone` permission row | odoo/addons/base/security/base_groups.xml:92-96 |
| `res.users.role` = `group_user` / `group_system` | `light_user` / `regular_user` / `group_system`; `base.group_user_regular` auto-maintained | odoo/addons/base/models/res_users.py:263 |
| settings feature groups needed nothing | override `_get_light_group_xmlids` for them | addons/crm/models/res_groups.py:9-14 |
| `groups_id` on users/views/menus (pre-19) | `group_ids` | odoo/addons/base/models/res_users.py:250, odoo/addons/base/models/ir_ui_view.py:184 |
