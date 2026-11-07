# ORM recipes (Odoo 20)

Short end-to-end patterns, each adapted from a real Odoo 20 module (cited under the recipe). Check the
merged model with `odoo_model`, run the result with `odoo_test`; `odoo_validate` flags the v19
leftovers listed in the last table.

## Contents

1. [Stored computed field](#1-stored-computed-field)
2. [Editable compute instead of onchange](#2-editable-compute-instead-of-onchange)
3. [Monetary amount with currency](#3-monetary-amount-with-currency)
4. [SQL constraints and indexes](#4-sql-constraints-and-indexes)
5. [Python constraint (and hierarchy cycles)](#5-python-constraint-and-hierarchy-cycles)
6. [Sequence number on create](#6-sequence-number-on-create)
7. [Wizard returning an action](#7-wizard-returning-an-action)
8. [Archive and unarchive](#8-archive-and-unarchive)
9. [Multi-company consistency](#9-multi-company-consistency)
10. [Pre-fill a form with `default_get`](#10-pre-fill-a-form-with-default_get)
11. [Cron method with progress](#11-cron-method-with-progress)
12. [Search on a non-stored computed field](#12-search-on-a-non-stored-computed-field)
13. [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## 1. Stored computed field

```python
class MaintenanceMixin(models.AbstractModel):
    _name = 'maintenance.mixin'

    maintenance_ids = fields.One2many('maintenance.request')
    maintenance_count = fields.Integer(compute='_compute_maintenance_count', store=True)
    maintenance_open_count = fields.Integer(compute='_compute_maintenance_count', store=True)

    @api.depends('maintenance_ids.state')
    def _compute_maintenance_count(self):
        for record in self:
            record.maintenance_count = len(record.maintenance_ids)
            record.maintenance_open_count = len(record.maintenance_ids.filtered(
                lambda mr: mr.state not in ['done', 'cancelled']))
```

- List **every** field read, dotted paths included; assign the field on **every** record of `self`.
- One method may compute several fields. No side effects in a stored compute.
- Aggregates over many records: prefer one `_read_group` in the compute (see
  `maintenance.equipment.category._compute_maintenance_count`) to a per-record `search_count`.
- House rules: [Computes, onchange and constraints](../../odoo-guidelines/guidelines/orm.md#computes-onchange-and-constraints).
  All field parameters: [fields.md](fields.md).

Source: addons/maintenance/models/maintenance.py:69-111, addons/maintenance/models/maintenance.py:55

## 2. Editable compute instead of onchange

Prefer `compute=` + `store=True` + `readonly=False` over `@api.onchange`: it runs in the UI **and** on
`create`/`write` from code, imports and RPC.

```python
validity_date = fields.Date(
    string="Expiration",
    compute="_compute_validity_date", store=True, readonly=False,
    copy=False, precompute=True,
)

@api.depends("company_id")
def _compute_validity_date(self):
    today = fields.Date.context_today(self)
    for order in self:
        days = order.company_id.quotation_validity_days
        order.validity_date = today + timedelta(days) if days > 0 else False
```

| Need | Use |
|---|---|
| value derived from other fields, user may override | `compute` + `store=True` + `readonly=False` |
| value known before insert (needed by `create`, sequences, constraints) | add `precompute=True` (ignored when a default or explicit value is given) |
| warning popup or UI-only side effect | `@api.onchange('field')`, may return `{'warning': {'title': ..., 'message': ...}}` |
| integrity rule | recipe 4 or 5, never onchange |

Source: addons/sale/models/sale_order.py:169-177, addons/sale/models/sale_order.py:550,
addons/maintenance/models/maintenance.py:199, odoo/orm/fields.py:216, odoo/orm/models.py:6517

## 3. Monetary amount with currency

```python
company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
company_currency_id = fields.Many2one(related='company_id.currency_id', string="Company Currency")
currency_id = fields.Many2one('res.currency', required=True)
date = fields.Date(default=fields.Date.context_today)
amount = fields.Monetary(currency_field='currency_id')
amount_company = fields.Monetary(
    currency_field='company_currency_id',
    compute='_compute_amount_company', store=True)

@api.depends('amount', 'currency_id', 'company_currency_id', 'date', 'company_id')
def _compute_amount_company(self):
    for rec in self:
        rec.amount_company = rec.currency_id._convert(
            from_amount=rec.amount, to_currency=rec.company_currency_id,
            company=rec.company_id, date=rec.date)
```

- `currency_field` defaults to `currency_id` (then `x_currency_id`); setup asserts the field exists.
- Monetary aggregates with `sum` by default; compare amounts with `currency.compare_amounts(a, b)`,
  `currency.is_zero(x)`, round with `currency.round(x)`.

Source: odoo/orm/fields_numeric.py:188-240, addons/account/models/account_payment.py:138,
addons/account/models/account_payment.py:228, addons/account/models/account_payment.py:582,
odoo/addons/base/models/res_currency.py:286-356

## 4. SQL constraints and indexes

```python
from odoo import models

class MaintenanceEquipment(models.Model):
    _name = 'maintenance.equipment'

    _serial_no = models.Constraint(
        'unique(serial_no)',
        'Another asset already exists with this serial number!',
    )

class SaleOrder(models.Model):
    _name = 'sale.order'
    _date_order_id_idx = models.Index("(date_order desc, id desc)")

class CalendarUser(models.Model):
    _name = 'calendar.user'
    _unique_user_per_calendar = models.UniqueIndex('(user_id, calendar_id)')
    _single_primary_calendar_per_user = models.UniqueIndex('(user_id) WHERE is_primary')
```

- Attribute names start with `_`; the SQL object is named `<table>_<attr without leading _>`.
- `Constraint(definition, message='')`: `CHECK (...)`, `UNIQUE (...)`, `FOREIGN KEY ...`. The message
  may be a callable `(env, diagnostics) -> str`. Do not end the name with `_not_null` (warning:
  PostgreSQL 18 uses that suffix for NOT NULL).
- `Index(definition)` / `UniqueIndex(definition, message='')`: definition is what follows `ON <table>`.
- `_sql_constraints = [...]` is ignored with a warning (flagged by `odoo_validate` rule ORM012).

Source: odoo/orm/table_objects.py:88-240, odoo/models/__init__.py:27,
addons/maintenance/models/maintenance.py:203, addons/sale/models/sale_order.py:497,
addons/calendar/models/calendar_user.py:14, odoo/orm/model_classes.py:175

## 5. Python constraint (and hierarchy cycles)

```python
from odoo.exceptions import ValidationError

@api.constrains('schedule_date', 'schedule_end')
def _check_schedule_interval(self):
    for request in self:
        if request.schedule_date and request.schedule_end and request.schedule_date > request.schedule_end:
            raise ValidationError(self.env._("End date cannot be earlier than start date."))

@api.constrains('parent_id')
def _check_category_recursion(self):
    if self._has_cycle():
        raise ValidationError(self.env._("Error! You cannot create recursive categories."))
```

- Only plain field names: dotted names are ignored. Triggered only when one of the fields is in
  the `create`/`write` values.
- `_check_recursion()` / `_check_m2m_recursion()` are gone: use `_has_cycle(field_name=None)`
  (ORM006).
- To forbid deleting records in some state use `@api.ondelete(at_uninstall=False)` (e.g.
  `addons/mrp/models/mrp_unbuild.py:141`), see [models-inheritance.md](models-inheritance.md).

Source: odoo/orm/decorators.py:53, addons/maintenance/models/maintenance.py:339,
addons/point_of_sale/models/pos_category.py:18, odoo/orm/models.py:5125

## 6. Sequence number on create

```python
@api.model_create_multi
def create(self, vals_list):
    for vals in vals_list:
        if vals.get("name", self.env._("New")) == self.env._("New"):
            vals["name"] = self.env["ir.sequence"].with_company(
                vals.get("company_id")
            ).next_by_code("sale.order") or self.env._("New")
    return super().create(vals_list)
```

```xml
<odoo noupdate="1">
    <record id="seq_sale_order" model="ir.sequence">
        <field name="name">Sales Order</field>
        <field name="code">sale.order</field>
        <field name="prefix">S</field>
        <field name="padding">5</field>
        <field name="company_id" eval="False"/>
    </record>
</odoo>
```

- `next_by_code(sequence_code, sequence_date=None)` picks the sequence of `env.company` (or a
  company-less one) and returns `False` when none exists. It checks `read` access on `ir.sequence`
  (internal users only): use `sudo()` for portal/public flows.
- Sequence fields and options: [cron-sequences-actions.md](../../data-security/references/cron-sequences-actions.md).

Source: addons/sale/models/sale_order.py:1452, addons/sale/data/ir_sequence_data.xml,
odoo/addons/base/models/ir_sequence.py:295, odoo/addons/base/security/ir.access.csv:24,
addons/mrp/models/mrp_unbuild.py:134

## 7. Wizard returning an action

```python
class SaleMassCancelOrders(models.TransientModel):
    _name = "sale.mass.cancel.orders"
    _description = "Cancel multiple quotations"

    sale_order_ids = fields.Many2many(
        comodel_name="sale.order",
        default=lambda self: self.env.context.get("active_ids"),
        relation="sale_order_mass_cancel_wizard_rel",
    )

    def action_mass_cancel(self):
        self.sale_order_ids._action_cancel()
        # core returns nothing (closes the dialog); returning an action opens the records
        return self.sale_order_ids._get_records_action(name=self.env._("Cancelled orders"))
```

Open it with an `ir.actions.act_window` (`res_model` = the wizard, `view_mode` `form`, `target` `new`,
`binding_model_id` `model_sale_order`, `binding_view_types` `list,kanban` for the Actions menu), and
grant access:

```csv
id,name,model_id,group_id/id,operation,domain
access_sale_mass_cancel_orders,access.sale.mass.cancel.orders,sale.mass.cancel.orders,sales_team.group_sale_salesman,cru,
sale_mass_cancel_orders_rule,Sales Mass Cancel Orders: access only your own wizard,sale.mass.cancel.orders,,crud,"[('create_uid', '=', user.id)]"
```

- Transient models need `ir.access` rows like any model (default deny); the group-less row keeps
  each user on their own wizard records. See [ir-access.md](../../data-security/references/ir-access.md).
- Return values: `None`/`False` closes the dialog, `{'type': 'ir.actions.act_window_close'}`,
  `records._get_records_action(**overrides)` (list or form depending on count),
  `self.env['ir.actions.actions']._for_xml_id('module.action_xmlid')` (then patch `domain`/`res_id`).
- `get_formview_action` was renamed `get_record_default_action` (ORM020).

Source: addons/sale/wizard/mass_cancel_orders.py, addons/sale/wizard/mass_cancel_orders_views.xml:35,
addons/sale/security/ir.access.csv:48-49, odoo/addons/base/models/ir_ui_view.py:3307,
odoo/addons/base/models/ir_ui_view.py:3324, odoo/addons/base/models/ir_actions.py:206,
addons/sale/models/sale_order.py:1891

## 8. Archive and unarchive

```python
active = fields.Boolean(default=True)

def action_archive(self):
    # archive hidden subtasks together with their parent
    child_tasks = self.child_ids.filtered(lambda t: not t.display_in_project)
    if child_tasks:
        child_tasks.action_archive()
    return super().action_archive()

def write(self, vals):
    if 'active' in vals and not vals['active']:
        self.env['project.project'].search([('stage_id', 'in', self.ids)]).write({'active': False})
    return super().write(vals)
```

- A field named `active` (or `x_active`) sets `_active_name`; `search` then hides archived records
  unless the domain mentions `active` or the context has `active_test=False`.
- The web client shows Archive/Unarchive in the action menu and calls `action_archive` /
  `action_unarchive`. `toggle_active` no longer exists (ORM005): call those two methods.
- React to (un)archiving in `write` (as above) or by overriding the two actions.

Source: odoo/orm/models.py:5282-5302, odoo/orm/model_classes.py:475-485, odoo/orm/models.py:4897,
addons/project/models/project_task.py:2169, addons/project/models/project_project_stage.py:55,
addons/web/static/src/model/relational_model/record.js:1514

## 9. Multi-company consistency

```python
class MaintenanceRequest(models.Model):
    _name = 'maintenance.request'
    _check_company_auto = True      # run _check_company() on create/write

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    equipment_id = fields.Many2one('maintenance.equipment', check_company=True)
```

```csv
id,name,model_id,group_id/id,operation,domain
maintenance_request_comp_rule,Maintenance Request Multi-company rule,maintenance.request,,crud,"[('company_id', 'in', company_ids + [False])]"
```

- `check_company=True` adds a company domain to the field in views and lets `_check_company()` raise a
  `UserError` on cross-company links; `_check_company_auto` triggers it automatically.
- The comodel decides what "compatible" means via `_check_company_domain(companies)` (default:
  `company_id in companies + [False]`); use `models.check_company_domain_parent_of` for branch
  companies.
- Records visibility per company is an `ir.access` restriction row (above). Switch company in code with
  `with_company(company)`.

Source: addons/maintenance/models/maintenance.py:245-285, addons/maintenance/security/ir.access.csv:7,
odoo/orm/models.py:3339-3440, odoo/orm/fields_relational.py:125, odoo/orm/models.py:3989,
addons/product/models/product_template.py:26

## 10. Pre-fill a form with `default_get`

```python
from odoo import Command

@api.model
def default_get(self, fields):
    result = super().default_get(fields)
    record_ids = self.env.context.get('active_ids')
    if record_ids and 'opportunity_ids' in fields:
        opps = self.env['crm.lead'].browse(record_ids).filtered(lambda o: o.won_status != 'won')
        result['opportunity_ids'] = [Command.set(opps.ids)]
    return result
```

- Signature `default_get(self, fields)` (a list of names); only fill keys in `fields`.
- Prefer field `default=` (callable) or a compute for single fields; use `default_get` when defaults
  depend on each other or on the context (`active_ids`, `active_model`).
- Beware leaking `default_<field>` context keys into unrelated creates
  ([Recordsets, domains and context](../../odoo-guidelines/guidelines/orm.md#recordsets-domains-and-context)).

Source: addons/crm/wizard/crm_merge_opportunities.py:20, odoo/orm/models.py:1317,
odoo/orm/commands.py:118, addons/mail/models/mail_mail.py:45

## 11. Cron method with progress

```python
@api.model
def _cron_send_pending_emails(self):
    pending = self.search([("pending_email_template_id", "!=", False)])
    self.env["ir.cron"]._commit_progress(remaining=len(pending))
    for order in pending:
        order = order.with_prefetch()   # avoid prefetching after each commit
        order._send_order_notification_mail(order.pending_email_template_id, allow_deferred_sending=False)
        order.pending_email_template_id = None
        if not self.env["ir.cron"]._commit_progress(processed=1):
            break                         # time budget used: cron is rescheduled ASAP
```

```xml
<record id="send_pending_emails_cron" model="ir.cron">
    <field name="name">Sales: Send pending emails</field>
    <field name="model_id" ref="model_sale_order"/>
    <field name="state">code</field>
    <field name="code">model._cron_send_pending_emails()</field>
    <field name="user_id" ref="base.user_root"/>
    <field name="interval_number">1</field>
    <field name="interval_type">days</field>
</record>
```

- `_commit_progress(processed=0, *, remaining=None, deactivate=False)` commits and returns the seconds
  left (`0` means stop); outside a cron it just commits. Roll back a failed item with
  `_rollback_progress()`. Skip rows locked by others with `records.try_lock_for_update()`.
- Keep the method private (`_cron_...`); trigger it early with `cron._trigger(at=None, coalesce=0)`.
  XML fields and behaviour: [cron-sequences-actions.md](../../data-security/references/cron-sequences-actions.md).

Source: addons/sale/models/sale_order.py:1740, addons/sale/data/ir_cron.xml:15,
odoo/addons/base/models/ir_cron.py:750, odoo/addons/base/models/ir_cron.py:872-921,
odoo/addons/base/models/ir_cron.py:451-454,
addons/account/models/account_move.py:7224, odoo/orm/models.py:5093

## 12. Search on a non-stored computed field

```python
from odoo.fields import Domain

is_expired = fields.Boolean(compute="_compute_is_expired", search="_search_is_expired")

def _search_is_expired(self, operator, value):
    if operator != 'in':
        return NotImplemented   # ORM retries with the positive operator and negates
    return Domain('state', 'in', ('draft', 'sent')) & Domain('validity_date', '<', 'today')
```

- The method receives the **optimized** condition: booleans always arrive as `('in', [True])` or
  `('not in', [True])`; `=`/`!=` on other types usually arrive as `in`/`not in` with a collection.
- Return a domain (list or `Domain`), or `NotImplemented` for operators you do not support; for a
  negative operator the ORM then calls you with the positive one and negates
  (`Domain.NEGATIVE_OPERATORS` lists them).
- Field access is checked before calling the method; with `compute_sudo=True` it runs in sudo.
- Dynamic dates such as `'today'` are valid domain values ([domain.md](domain.md)). Comparing a
  boolean with a non-boolean (`('active', '=', 'True')`) emits a DeprecationWarning since 20.0.

Source: addons/sale/models/sale_order.py:465, addons/sale/models/sale_order.py:812,
addons/sale/models/sale_order.py:1119 (adapted from prefix notation), odoo/orm/domains.py:1041-1110,
odoo/orm/domains.py:1558-1576, odoo/orm/domains.py:282

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `_sql_constraints = [('name', 'unique(x)', 'msg')]` | `_name_uniq = models.Constraint('unique(x)', 'msg')` (ORM012) | odoo/orm/model_classes.py:175 |
| `self._check_recursion()` | `self._has_cycle()` (ORM006) | odoo/orm/models.py:5125 |
| `records.toggle_active()` | `action_archive()` / `action_unarchive()` (ORM005) | odoo/orm/models.py:5282 |
| `ICP.get_param('k')` in crons/settings | `get_str/get_int/get_bool/get_float` (ORM001) | odoo/addons/base/models/ir_config_parameter.py |
| `record.get_formview_action()` | `record.get_record_default_action()` (ORM020) | odoo/addons/base/models/ir_ui_view.py:3307 |
| `ir.model.access.csv` row for a wizard | `security/ir.access.csv` row + group-less `create_uid` restriction (SEC002) | addons/sale/security/ir.access.csv:48 |
| `read_group(..., lazy=False)` dict results in computes | `_read_group(domain, groupby, aggregates)` tuples (ORM013), see [sql-query.md](sql-query.md) | addons/maintenance/models/maintenance.py:56 |
