# Models and inheritance (Odoo 20)

How to declare models in Odoo 20: base classes, the three inheritance mechanisms, model attributes that
exist in 20.0, how extensions chain (load order / MRO), and the correct way to override `create`,
`write`, `unlink`, `copy`, `default_get` and `display_name`. Read before adding or extending a model.

## Contents

- [Base classes](#base-classes)
- [Inheritance mechanisms](#inheritance-mechanisms)
- [Rules enforced when the registry loads](#rules-enforced-when-the-registry-loads)
- [Model attributes](#model-attributes)
- [Load order, MRO and super()](#load-order-mro-and-super)
- [Redefining a field in an extension](#redefining-a-field-in-an-extension)
- [Overriding CRUD methods](#overriding-crud-methods)
- [display_name and name search](#display_name-and-name-search)
- [Archiving and hierarchies](#archiving-and-hierarchies)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

House rules (naming, `_order` tiebreaker, batch `create`, `_inherits` caveats) live in
[ORM guidelines](../../odoo-guidelines/guidelines/orm.md#recordsets-domains-and-context); this file does not
repeat them. Inspect a merged model (fields, parents, defining modules) with `odoo_model`, and the
override chain of a method with `odoo_method`.

## Base classes

Import with `from odoo import api, fields, models` (`odoo.models` re-exports `odoo.orm`).

| Class | Table | Use |
|---|---|---|
| `models.Model` | yes (`_auto = True`) | regular persisted business model |
| `models.AbstractModel` | no | mixins / pure-Python services; in v20 it is literally `BaseModel` |
| `models.TransientModel` | yes, vacuumed | wizards; rows removed by the `_transient_vacuum` autovacuum after `_transient_max_hours` / `_transient_max_count` (config `transient_age_limit`, `osv_memory_count_limit`) |
| `models.CachedModel` | yes | `Model` with a stable per-registry cache of `_cached_data_fields` for `_cached_data_domain` records; used by `res.company`, `res.currency`, `res.country`, `res.lang`. Details in [api-cache.md](api-cache.md) |

Also exported from `odoo.models`: `Constraint`, `Index`, `UniqueIndex` (SQL table objects, see
[recipes.md](recipes.md)), `Query`, `TableSQL` (see [sql-query.md](sql-query.md)).

- `TransientModel` must keep `_log_access` on (TypeError otherwise).
- A `Many2one` from a `Model` to a `TransientModel` raises `ValueError` at schema update; from a transient to
  a regular model the default `ondelete` is `'set null'` (or `'cascade'` if required).

Source: odoo/models/__init__.py, odoo/orm/models.py:6574, odoo/orm/models_transient.py,
odoo/orm/models_cached.py, odoo/orm/model_classes.py:231, odoo/orm/fields_relational.py:270-280

## Inheritance mechanisms

| Goal | Declaration | Result |
|---|---|---|
| Classic extension (add/alter fields, override methods) | `_inherit = 'sale.order'` (no `_name`) | same model, same table |
| Extension that also adds a mixin | `_name = 'res.partner'` + `_inherit = ['res.partner', 'website.published.multi.mixin']` | same model, mixin fields/methods added |
| New model built from mixins | `_name = 'maintenance.equipment'` + `_inherit = ['mail.thread', 'mail.activity.mixin', 'maintenance.mixin']` | new table, mixin fields copied in |
| Prototype (copy another model) | `_name = 'x.new'` + `_inherit = 'x.old'` | new table with copies of the parent's fields and methods |
| Delegation | `_inherits = {'res.partner': 'partner_id'}` + required `Many2one` | new table, parent fields readable/writable via the link, stored on the parent |
| Extend every model | `_inherit = 'base'` | adds to all models (`addons/mail/models/models.py`) |

```python
# classic extension
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    x_reference = fields.Char()

# extension + mixin: _name is REQUIRED when _inherit is a list
class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'website.published.multi.mixin']
```

A list `_inherit` never infers `_name`: without `_name` the metaclass derives one from the class name and
logs "Class X has no _name, please make it explicit" (you silently create a new model). Only a string
`_inherit` sets `_name` for you.

Delegation (`_inherits`) requirements, checked at setup: the link field must be a `Many2one`, `required=True`,
with `ondelete='cascade'` or `'restrict'`; it becomes `delegate=True` automatically. Declaring
`delegate=True` on a field that is not in `_inherits` raises `TypeError`. Inherited fields are related
fields with `related_sudo=False`. In v20 the parent's access domain is added as a *restriction* on the
child (you need access to the `res.partner` to read the `res.users`); set `_check_inherits_access = False`
to skip it (done by `hr.employee`, `mail.mail`, `mail.alias.mixin`). Methods are not delegated.

```python
class ProductProduct(models.Model):
    _name = 'product.product'
    _inherits = {'product.template': 'product_tmpl_id'}

    product_tmpl_id = fields.Many2one(
        'product.template', 'Product Template',
        bypass_search_access=True, index=True, ondelete="cascade", required=True)
```

Source: odoo/orm/models.py:246-275 (MetaModel), odoo/orm/model_classes.py:497-541,
odoo/orm/models.py:3622 (`_check_inherits_access`), addons/product/models/product_product.py:19,
addons/website/models/res_partner.py:8, addons/maintenance/models/maintenance.py:113

## Rules enforced when the registry loads

| You wrote | Error |
|---|---|
| extension that sets `_table` | `TypeError ... cannot redefine _table while extending` |
| `models.Model` extending an `AbstractModel` by its own name | `TypeError ... transforms the abstract model ... into a non-abstract model` |
| `Model` extending a `TransientModel` (or the reverse) | `TypeError ... transforms the (transient) model` |
| `AbstractModel` with a `Model` in `_inherit` | `TypeError ... abstract model ... cannot inherit from non-abstract model` |
| `_inherit` of a model not loaded yet (missing manifest `depends`) | `TypeError: Model 'x' does not exist in registry.` (extension) or `... inherits from non-existing model 'y'` (new model) |
| `_sql_constraints = [...]` / `_constraints` | ignored with a warning: the constraint is never created (rule ORM012) |
| class without `_description` on a new model | warning `The model x has no _description` |

Source: odoo/orm/model_classes.py:165-279

## Model attributes

| Attribute | Default | Notes |
|---|---|---|
| `_name` | - | dotted model name |
| `_description` | `_name` | label; warned if missing on a new model |
| `_explanation` | `None` | new in 20: verbose purpose text, reflected into `ir.model.explanation`; extension classes with the same `_name` are concatenated (e.g. `addons/sale/models/sale_order.py:36`) |
| `_inherit` / `_inherits` | `()` / `{}` | see above |
| `_order` | `'id'` | default `ORDER BY`; end with a unique field (house rule) |
| `_rec_name` | `'name'` / `'x_name'` if present | field used by the default `_compute_display_name` |
| `_rec_names_search` | `()` | **tuple** of field paths used by `_search_display_name`; may be a `@property` (sale.order does this). Lists are flagged by rule ORM011 |
| `_parent_name` / `_parent_store` | `'parent_id'` / `False` | `_parent_store = True` needs `parent_path = fields.Char(index=True)`; enables fast `child_of`/`parent_of` |
| `_active_name` | auto | `'active'` or `'x_active'` |
| `_fold_name` | `'fold'` | kanban group folding |
| `_check_company_auto` | `False` | calls `_check_company()` on create/write for fields with `check_company=True` |
| `_check_inherits_access` | `True` | see delegation |
| `_allow_sudo_commands` | `True` | `False`: x2many commands targeting this model from a `sudo()`/`with_user()` env run without sudo, as the transaction's original user (`ir.access`, `ir.actions.*`) |
| `_clear_cache_name` / `_clear_cache_on_fields` | `''` / `None` | ormcache to invalidate on create/write/unlink (optionally only for these fields). See [api-cache.md](api-cache.md) |
| `_auto` / `_table` / `_log_access` | per class | `_auto = False` + SQL view; see [sql-query.md](sql-query.md) |
| `_table_sql` | property | SQL for the table or view (replaces `_table_query`, rule ORM008); see [sql-query.md](sql-query.md) |
| `_depends` | `{}` | `{model: [fields]}` to flush before reading a SQL-view model |
| `_transient_max_hours` / `_transient_max_count` | config | `TransientModel` only |

Table objects are class attributes whose name starts with `_`:

```python
class MaintenanceEquipment(models.Model):
    _name = 'maintenance.equipment'
    _serial_no = models.Constraint(
        'unique(serial_no)',
        'Another asset already exists with this serial number!',
    )
```

`_valid_field_parameter(field, name)` decides which unknown field kwargs are accepted (base accepts
`related_sudo`; `mail.track.mixin` adds `tracking`). Unknown ones log "Field x: unknown parameter".

Source: odoo/orm/models.py:406-528, odoo/orm/model_classes.py:464-486,
odoo/addons/base/models/ir_model.py:481, addons/maintenance/models/maintenance.py:203,
odoo/addons/base/models/ir_access.py:69, odoo/orm/fields_relational.py:834-839

## Load order, MRO and super()

- Modules load in dependency order (manifest `depends`); inside a module, classes register in the order
  Python creates them, i.e. the import order of `models/__init__.py`.
- Each `Registry.load(module)` calls `add_to_registry` for every class of that module. For an extension,
  the new class becomes the **first** base of the registry class, followed by the previous bases; every
  model (except `base`) implicitly ends with `base` in its parents.
- So `super()` in your override calls the definition loaded just before yours: the module you depend on,
  or another module loaded earlier. Two modules that both extend `sale.order` without depending on each
  other have no guaranteed relative order: add the `depends` you rely on.
- Always call `super()` and return its result; never skip it to "replace" core behaviour.
- `_register_hook()` runs after the registry is built (patch-time logic); `_unregister_hook()` undoes it.

Check the real chain with `odoo_method` (lists every module defining the method, in MRO order) and the
merged field definition with `odoo_model`.

Source: odoo/orm/registry.py:435-463, odoo/orm/model_classes.py:180-226, odoo/orm/models.py:5304

## Redefining a field in an extension

Redeclaring a field merges parameters: later definitions update earlier ones, unless the field class is not
compatible (then previous params are dropped).

```python
class AccountAnalyticApplicability(models.Model):
    _inherit = "account.analytic.applicability"

    business_domain = fields.Selection(
        selection_add=[("sale_order", "Sale Order")], ondelete={"sale_order": "cascade"}
    )
```

- Only pass what changes: `name = fields.Char(required=True)` keeps the original string, translate, etc.
- On a `Selection`, use `selection_add` (+ `ondelete` per new value, mandatory policy other than
  `'set null'` if the field is required); redefining `selection=` logs "overrides existing selection".
- Details of every parameter: [fields.md](fields.md).

Source: odoo/orm/fields.py:441-524 (`_get_attrs`), odoo/orm/fields_selection.py:96-150,
addons/sale/models/account_analytic_applicability.py

## Overriding CRUD methods

### create: always batch

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

- `@api.model_create_multi` wraps a dict into `[dict]`; your body always gets a list. `@api.model` on a
  method named `create` is converted to `model_create_multi` automatically, but write it explicitly.
- Post-processing goes after `super()` on the returned recordset (`maintenance.equipment.create`
  subscribes owners).

### write

```python
def write(self, vals):
    if "pricelist_id" in vals and any(so.state == "sale" for so in self):
        raise UserError(self.env._("You cannot change the pricelist of a confirmed order !"))
    return super().write(vals)
```

`write(vals)` is called on a multi-record set and must return `super()`'s `True`. Do not write inside a
compute; use `@api.depends` (see [fields.md](fields.md#computed-fields)).

### unlink: use @api.ondelete

```python
@api.ondelete(at_uninstall=False)
def _unlink_except_draft_or_cancel(self):
    for order in self:
        if order.state not in ("draft", "cancel"):
            raise UserError(order.env._("You can not delete a sent quotation ..."))
```

`unlink()` first runs `check_access('unlink')`, then every `@api.ondelete` method; with
`at_uninstall=False` the check is skipped while the defining module is being uninstalled. Overriding
`unlink` to raise blocks uninstall: only override it for side effects, and call `super()`.

### copy / copy_data

- `copy(default=None)` = `create(self.with_context(active_test=False).copy_data(default))`; works on
  multi-record sets. Override `copy_data` (returns one vals dict per record) to adapt values.
- Fields with `copy=False` are skipped; `copy` may be a callable `(record) -> value`.
- New in 20: a `Char` named `name` / `x_name` (with `translate` bool and no explicit `copy`) defaults to
  `copy=mark_as_copy('name')`, which appends " (copy)". Do not re-implement this in `copy_data`. For other
  fields: `from odoo.tools.translate import mark_as_copy` then `fields.Char(copy=mark_as_copy('title'))`.

```python
def copy_data(self, default=None):
    default = dict(default or {})
    default.setdefault("order_line", [])
    vals_list = super().copy_data(default=default)
    for order, vals in zip(self, vals_list):
        vals["order_line"] = [Command.create(v) for v in order._get_copiable_order_lines().copy_data()]
    return vals_list
```

### default_get

```python
@api.model
def default_get(self, fields):
    result = super().default_get(fields)
    if 'project_id' in fields and not result.get('project_id'):
        result['project_id'] = self.env.context.get('active_id')
    return result
```

Only fill keys present in `fields`. Prefer field `default=` (static value or `lambda self: ...`) or a
`default_<field>` context key; override `default_get` only for cross-field defaults.

Source: addons/sale/models/sale_order.py:1452-1500, addons/maintenance/models/maintenance.py:62,208,
addons/project/models/project_update.py:27, odoo/orm/decorators.py:91-133,274-333,
odoo/orm/models.py:1317,3658-3678,4963-5044, odoo/orm/fields_textual.py:529-534,
odoo/tools/translate.py:954

## display_name and name search

`name_get` does not exist (rule ORM009). `display_name` is a computed field; override its compute and declare
what it reads:

```python
@api.depends("name", "partner_id", "client_order_ref")
@api.depends_context("sale_show_partner_name", "formatted_display_name")
def _compute_display_name(self):
    super()._compute_display_name()
    for order in self:
        ...
```

- Default compute: `display_name = record[_rec_name]` converted for display, else `"model,id"`.
- Searching `display_name` (and `name_search`) goes through `_search_display_name(operator, value)`, which
  ORs the conditions on `_rec_names_search` (or `_rec_name`); relational paths search their
  `display_name`. Override `_search_display_name` and return a `Domain` for custom matching.
- `name_create(name)` needs a `_rec_name`.

Source: odoo/orm/models.py:1503-1590, addons/sale/models/sale_order.py:56-60,500,
addons/maintenance/models/maintenance.py:125

## Archiving and hierarchies

- A field named `active` (or `x_active`) enables archiving: default searches add `active = True`
  (disable with context `active_test=False`). Use `records.action_archive()` / `action_unarchive()`;
  `toggle_active` was removed (rule ORM005).
- Cycle checks: `if self._has_cycle(): raise ValidationError(...)` in an `@api.constrains('parent_id')`
  (`_check_recursion` was removed, rule ORM006). `_has_cycle(field_name)` also handles many2many.

Source: odoo/orm/models.py:5125,5282-5302, addons/project/models/project_task.py:604

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `_sql_constraints = [(name, def, msg)]` | `_name_uniq = models.Constraint('UNIQUE(name)', msg)` / `models.Index` / `models.UniqueIndex` (ORM012) | odoo/orm/model_classes.py:176 |
| `_table_query = "SELECT ..."` | `_table_sql` property returning `SQL` (ORM008) | odoo/orm/models.py:531 |
| `_rec_names_search = ['name', 'ref']` | `('name', 'ref')` tuple (ORM011, upgrade script `19.5-00-tuple-rec_names_search`) | odoo/upgrade_code/19.5-00-tuple-rec_names_search.py |
| `toggle_active()` | `action_archive()` / `action_unarchive()` (ORM005) | odoo/orm/models.py:5282 |
| `_check_recursion()` / `_check_m2m_recursion(f)` | `_has_cycle()` / `_has_cycle(f)` (ORM006) | odoo/orm/models.py:5125 |
| `copy_data` override adding `_("%s (copy)")` to `name` | automatic for `name`; `copy=mark_as_copy('field')` elsewhere | odoo/tools/translate.py:954 |
| `_init_column(name)` / `_table_has_rows()` in `_auto_init` | field param `init_storage=` (both old methods deprecated) | odoo/orm/models.py:2490-2497 |
| `_check_field_access(field, op)` | `check_field_access(field, op)` / `has_field_access` (see [access-api.md](access-api.md)) | odoo/orm/models.py:2794 |
| `get_formview_action()` | `get_record_default_action(access_uid=None)` (ORM020) | odoo/addons/base/models/ir_ui_view.py:3307 |

Run `odoo_validate` on the file to catch these mechanically.
