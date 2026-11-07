# ir.access: access rights and record rules in one model (Odoo 20)

Odoo 20 deleted `ir.model.access` and `ir.rule`. Every grant and every record filter is now an
`ir.access` row, usually declared in `security/ir.access.csv`. Read this before writing any
security data, converting a v19 module, or debugging an `AccessError`. Python-side checks
(`check_access`, `_access_domain` overrides) live in [access-api.md](../../orm/references/access-api.md);
house rules in [security guidelines](../../odoo-guidelines/guidelines/security.md) and the
[odoo-security audit skill](../../odoo-security/SKILL.md#access-control).

## Contents
- [The model](#the-model)
- [How a decision is made](#how-a-decision-is-made)
- [CSV format](#csv-format)
- [Recipes](#recipes)
- [XML records and disabling another module's row](#xml-records-and-disabling-another-modules-row)
- [The access domain operator](#the-access-domain-operator)
- [Manifest order](#manifest-order)
- [Testing access](#testing-access)
- [Pitfalls](#pitfalls)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## The model

| Field | Type | Notes |
|---|---|---|
| `name` | Char, required | Human label (shown in "Blame the following accesses" debug errors) |
| `active` | Boolean, default True | Inactive rows are ignored; this is how you disable a row from another module |
| `model_id` | Many2one `ir.model`, required, `ondelete='cascade'` | |
| `group_id` | Many2one `res.groups`, optional | Set = *permission*, empty = *restriction* |
| `operation` | Selection, required | One of the 15 ordered subsets of `crud` (below) |
| `domain` | Char | Python-literal domain, evaluated per user; empty = all records |
| `kind` | computed (`compute_sql`) | `'permission'` / `'restriction'`, searchable |
| `for_read`, `for_write`, `for_create`, `for_unlink` | computed Booleans (`compute_sql`, inverse) | Searchable flags derived from `operation` |
| `is_standard` | computed | True when the row has a module xmlid (not `__export__`/`__custom__`/`studio_customization`) |
| `note` | Html | |

`operation` values (exact keys of `CRUD_SELECTION`, letters always in c-r-u-d order):
`crud`, `cru`, `crd`, `cud`, `rud`, `cr`, `cu`, `cd`, `ru`, `rd`, `ud`, `c`, `r`, `u`, `d`.
There is no `w`: the write right is `u`. `rc`, `rw`, `dr` are invalid values and fail the import.

Methods `check_access(operation)` etc. take the ORM operation names `'read'`, `'write'`,
`'create'`, `'unlink'`; `IN_SELECTION` maps each to the `operation` keys containing its letter.

Other facts: `_allow_sudo_commands = False` on `ir.access`; `res.groups.access_ids` and
`ir.model.access_ids` are the One2many back to the rows; a row with a domain cannot target
`ir.access` itself (`_check_model_name`); `customize()` deactivates a standard row and edits a copy.

Source: odoo/addons/base/models/ir_access.py:16-126, odoo/addons/base/models/res_groups.py:30, odoo/addons/base/models/ir_model.py:249

## How a decision is made

`Model._access_domain(operation)` builds one domain per (user, allowed companies, operation):

```text
access_domain = OR(domains of PERMISSION rows whose group the user has, for this operation)
            AND AND(domains of RESTRICTION rows for this operation)
```

| Rule | Consequence |
|---|---|
| `Domain.OR([])` is FALSE | **Default deny**: a model with no permission row reachable by the user is inaccessible |
| Permissions are OR-ed | A broad row (manager, no domain) wins over a narrow one (salesman, own records); you never need to "exclude" the narrow row |
| A permission's domain limits only that row | `r` on all + `u` on own = read everything, update own only |
| Restrictions are AND-ed onto **every** user | They never grant; two non-overlapping restrictions lock everybody out |
| Group membership is transitive | `_get_group_ids()` includes implied groups, so a row for `base.group_user` also applies to every group implying it |
| `sudo()` / superuser | `has_access()` returns True when `env.su`; rows are not evaluated at all |
| `_inherits` children | The parent model's access domain is added as a restriction (`parent_field any parent_domain`) unless the model sets `_check_inherits_access = False` (e.g. `mail.mail`) |

Domain evaluation context (`ir.access._eval_context`): `user` (current user, empty context),
`time`, `company_ids` (ids of the companies active in the company switcher), `company_id`
(current company id). Domains with no variables are pre-parsed with `ast.literal_eval`, optimized
and cached once; others are `safe_eval`-ed per user. The result of `_access_domain` is cached per
transaction keyed on `(uid, allowed_company_ids)` (`env._access_context`); if your domain depends on
another context key, extend `ir.access._get_access_context()`.

Every row is validated at create/write (`_check_domain`): unknown fields in the domain make module
install fail with `Invalid domain ...`.

Source: odoo/orm/models.py:3601-3646 (`_access_domain`), odoo/orm/models.py:3464-3504 (`has_access`), odoo/addons/base/models/ir_access.py:186-210,282-324, odoo/orm/domains.py:598-640, odoo/orm/environments.py:208-220, addons/mail/models/mail_mail.py:31-41

## CSV format

File `security/ir.access.csv` (model `ir.access` comes from the file name; see
[data-files.md](data-files.md#csv-data-files)). Header used by all 236 core files:

```csv
id,name,model_id,group_id/id,operation,domain
```

| Column | Value |
|---|---|
| `id` | xmlid of the row, unique in the module (`access_<model>_<group>` for plain grants, `<model>_rule_<group>` for domain rows, see [xml guidelines](../../odoo-guidelines/guidelines/xml.md)) |
| `name` | required label |
| `model_id` | **technical model name** (`sale.order`); resolved by an exact `name_search` on `ir.model`, whose `_rec_names_search` is `('name', 'model')` |
| `group_id/id` | group xmlid, write it fully qualified (`sales_team.group_sale_salesman`); **empty = restriction** |
| `operation` | one of the 15 keys above |
| `domain` | optional, double-quoted Python literal; may use `user`, `company_ids`, `company_id`, `time` |

Source: addons/sale/security/ir.access.csv:1, odoo/tools/convert.py:739-771, odoo/addons/base/models/ir_fields.py:553-558, odoo/addons/base/models/ir_model.py:230

## Recipes

All rows below are real core lines unless marked "adapted".

1. Plain CRUD for a group, read for users (the old ACL pair):

```csv
access_maintenance_stage_user,maintenance.stage.user,maintenance.stage,base.group_user,r,
access_maintenance_stage_admin_user,equipment.request.stage system user,maintenance.stage,maintenance.group_equipment_manager,crud,
```

2. Read for every internal user vs. for everyone (portal and public included). `base.group_everyone`
is implied by `base.group_user`, `base.group_portal` and `base.group_public`. Never grant `c`/`u`/`d`
to it without a tight domain.

```csv
res_partner_rule_user,user read access,res.partner,base.group_user,r,
access_res_country_public,res_country group_user_all,res.country,base.group_everyone,r,
```

3. Own records for users, all records for managers (tiers are OR-ed, no exclusion needed):

```csv
sale_order_personal_rule,Personal Orders,sale.order,sales_team.group_sale_salesman,cru,"['|',('user_id','=',user.id),('user_id','=',False)]"
sale_order_see_all,All Orders,sale.order,sales_team.group_sale_salesman_all_leads,cru,
sale_order_see_all_1,All Orders,sale.order,sales_team.group_sale_manager,crud,
```

4. Multi-company restriction (no group, AND-ed for everybody). Append `+ [False]` when `company_id`
is optional:

```csv
sale_order_comp_rule,Sales Order multi-company,sale.order,,crud,"[('company_id', 'in', company_ids)]"
maintenance_equipment_comp_rule,Maintenance Equipment Multi-company rule,maintenance.equipment,,crud,"[('company_id', 'in', company_ids + [False])]"
```

5. Portal: documents of the user's commercial partner, lines through the parent's access:

```csv
sale_order_rule_portal,Portal Personal Quotations/Sales Orders,sale.order,base.group_portal,r,"[('partner_id','child_of',[user.commercial_partner_id.id])]"
sale_order_line_rule_portal,Portal Sales Orders Line,sale.order.line,base.group_portal,r,"[('order_id', 'access', 'read')]"
```

6. Wizard (TransientModel) usable only by its creator. Transient models use the same mechanism, so
they need a permission row too:

```csv
access_sale_mass_cancel_orders,access.sale.mass.cancel.orders,sale.mass.cancel.orders,sales_team.group_sale_salesman,cru,
sale_mass_cancel_orders_rule,Sales Mass Cancel Orders: access only your own wizard,sale.mass.cancel.orders,,crud,"[('create_uid', '=', user.id)]"
```

7. Split rights on one model: users read all but update only themselves (base partner rows):

```csv
res_partner_rule_user,user read access,res.partner,base.group_user,r,
res_partner_rule_write_self,self user write access,res.partner,base.group_user,u,"[('id', '=', user.partner_id.id)]"
```

8. New model in a custom module (adapted):

```csv
id,name,model_id,group_id/id,operation,domain
access_library_book_user,library.book.user,library.book,base.group_user,r,
access_library_book_manager,library.book.manager,library.book,library.group_library_manager,crud,
library_book_comp_rule,library.book multi-company,library.book,,crud,"[('company_id', 'in', company_ids + [False])]"
```

Source: addons/maintenance/security/ir.access.csv:4,11-12, addons/sale/security/ir.access.csv:29-36,48-49, odoo/addons/base/security/ir.access.csv:39,54,58, odoo/addons/base/security/base_groups.xml:92-96

## XML records and disabling another module's row

Use XML when the domain is long or you need `ref()`. Fields are the same; `model_id` takes the
`ir.model` xmlid `<module>.model_<model_with_underscores>`:

```xml
<record id="project_task_rule_portal_project_sharing" model="ir.access">
    <field name="name">Project/Task: portal users: portal user can edit with project sharing feature</field>
    <field name="model_id" ref="project.model_project_task"/>
    <field name="group_id" ref="base.group_portal"/>
    <field name="operation">cu</field>
    <field name="domain">[('project_id.privacy_visibility', 'in', ['invited_users', 'portal'])]</field>
</record>
```

To switch off a row owned by a dependency, write `active` on its xmlid (never delete it, and do not
override its `domain`, so uninstall can simply re-enable it):

```xml
<odoo noupdate="1">
    <record id="product.product_pricelist_comp_rule" model="ir.access">
        <field name="active" eval="False"/>
    </record>
</odoo>
```

```python
def uninstall_hook(env):
    if access := env.ref('product.product_pricelist_comp_rule', raise_if_not_found=False):
        access.active = True
```

Source: addons/project/security/project_security.xml:45-60 (domain shortened), addons/website_sale/security/ir_access.xml:1-17, addons/website_sale/__init__.py:44-51, addons/sale_timesheet/security/sale_timesheet_security.xml:10-16

## The access domain operator

`('field', 'access', op)` keeps records whose many2one target (or the record itself for `'id'`)
passes `op` in `('read', 'write', 'create', 'unlink')` for the current user. It replaces v19 rules
that copied the parent's rule domain onto child models.

- Works only on `many2one` fields and `id`; not on properties paths or x2many.
- For a model-level check (`Model.browse().has_access('read')`) it is resolved first: if the user
  has no access to the comodel at all, the condition becomes FALSE.
- `ir.access._check_domain` skips `access` conditions while validating, so rows referencing
  models of later-loaded modules still install.

Full operator list: [domain.md](../../orm/references/domain.md).

Source: odoo/orm/domains.py:1926-1963, odoo/orm/models.py:3482-3492, odoo/addons/base/models/ir_access.py:186-210, addons/sale/security/ir.access.csv:12,36

## Manifest order

List `security/ir.access.csv` **last** in `data` (222 of the 236 core modules that ship one do,
e.g. `maintenance`, `sale`, `project`, `account`, `mail`), after the XML that defines the groups it
references. Groups and privileges go in `security/<module>_security.xml`, listed **first**. See
[module structure](../../odoo-guidelines/guidelines/module_structure.md) and
[manifest guidelines](../../odoo-guidelines/guidelines/manifest.md).

```python
'data': [
    'security/maintenance.xml',          # groups, privileges, XML ir.access
    'data/maintenance_data.xml',
    'views/maintenance_views.xml',
    'security/ir.access.csv',            # last
],
```

`odoo_validate` flags `ir.model.access.csv` in a manifest (MAN002) or a CSV with `perm_read`
columns (SEC002).

Source: addons/maintenance/__manifest__.py:11-21, odoo/upgrade_code/19.4-00-ir-access.py:402-404

## Testing access

```python
from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged, TransactionCase

@tagged('post_install', '-at_install')
class TestLibraryAccess(TransactionCase):
    def test_user_cannot_delete(self):
        user = new_test_user(self.env, login='lib_user', groups='base.group_user')
        book = self.env['library.book'].create({'name': 'B'})
        self.assertTrue(book.with_user(user).has_access('read'))
        with self.assertRaises(AccessError):
            book.with_user(user).unlink()
        # model-level check: empty recordset
        self.assertFalse(self.env['library.book'].with_user(user).browse().has_access('unlink'))
```

Patterns from core: `addons/sale/tests/test_access_rights.py` (portal, employee, salesman cases).
Run with `odoo_test`; list the effective rows for a model with `odoo_access`; in a shell,
`env['sale.order'].with_user(u)._access_domain('read')` shows the combined domain.

Source: odoo/tests/common.py:268, addons/sale/tests/test_access_rights.py:124-162, odoo/orm/models.py:3443-3530

## Pitfalls

- A group-less row is a **restriction**, not "access for everyone" (v19 global ACL). For everyone
  use `base.group_everyone`; for internal users `base.group_user`.
- Forgetting the permission row for a new model or wizard: default deny, and the v20 loader no
  longer logs "The models ... have no access rules" (that warning existed in v19 `loading.py`).
- A restriction that does not cover a group's legitimate records (e.g. a company restriction on a
  model without `company_id` values) hides them from everyone, admins included (only `sudo()` passes).
- `operation` letters in the wrong order (`rc`) or `w` instead of `u` fail the import.
- Domain field typos fail at install (`_check_domain`); check with `odoo_model` first.
- Granting `c`/`u`/`d` to `base.group_portal`/`base.group_public`/`base.group_everyone` is an audit
  finding unless the domain pins records to the user (see the odoo-security skill).

Source: odoo/addons/base/models/ir_access.py:16-38,180-210, odoo/orm/models.py:3638-3646

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `security/ir.model.access.csv`, header `id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink` | `security/ir.access.csv`, header `id,name,model_id,group_id/id,operation,domain` (SEC002, MAN002) | addons/sale/security/ir.access.csv:1 |
| `model_id:id` = `model_sale_order` | `model_id` = `sale.order` | odoo/addons/base/models/ir_fields.py:553-558 |
| `perm_read=1,perm_write=1,perm_create=1,perm_unlink=0` | `operation` = `cru` | odoo/addons/base/models/ir_access.py:16-32 |
| ACL row with empty group = everyone may | `base.group_everyone` row; empty group now means restriction | odoo/addons/base/security/base_groups.xml:92 |
| `ir.rule` with `groups` (many2many) + `domain_force` + `perm_*` | one `ir.access` row per group, `domain`, `operation` (SEC001) | odoo/addons/base/models/ir_access.py:64-126 |
| global `ir.rule` (no groups) | group-less `ir.access` row (restriction) | odoo/orm/models.py:3636-3646 |
| ACL "r" + rule "own records" on the same group | one row `r` with the own-records domain, or two rows (`r` unrestricted + `u` with domain) | odoo/addons/base/security/ir.access.csv:54,58 |
| `domain_force` `[(1, '=', 1)]` | empty `domain` | odoo/upgrade_code/19.4-00-ir-access.py:27,729-731 |
| child rule copying the parent rule domain | `[('parent_id', 'access', 'read')]` | addons/sale/security/ir.access.csv:36 |
| `<record model="ir.rule">` with `<field name="active" eval="False"/>` to disable | same on the `ir.access` xmlid | addons/website_sale/security/ir_access.xml:11-16 |
| `res.groups.model_access` / `rule_groups` | `res.groups.access_ids` (SEC006) | odoo/addons/base/models/res_groups.py:30 |
| `check_access_rights` / `check_access_rule` / `_filter_access_rules` | `check_access` / `has_access` / `_filtered_access` (SEC003, SEC004) | odoo/orm/models.py:3443-3530 |
| override `_check_access` | override `_access_domain(operation)` (SEC005) | odoo/orm/models.py:3575, addons/mail/models/mail_mail.py:38 |

Automatic conversion: `odoo-bin upgrade_code --script 19.4-00-ir-access --addons-path=<your addons>`
(or the `odoo_upgrade_code` tool for a sandboxed diff). It reads every manifest's `ir.model.access.csv`
and `ir.rule` XML, folds rules into the ACL groups using group implications, writes
`security/ir.access.csv` (or `ir.access.csv` if the module had no `security/` files), appends it to the
manifest `data` and removes the emptied old files. It is not idempotent (run it once) and logs
`WARNING` lines for ACL/rule combinations it could only approximate: review each one.

Source: odoo/upgrade_code/19.4-00-ir-access.py:1,78-237,279-405, odoo/cli/upgrade_code.py:205-262
