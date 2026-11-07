# Fields (Odoo 20)

Every field class in `odoo/orm/fields_*.py` with the parameters it really accepts in 20.0, the common
parameters (compute / related / index / groups ...), binary values (`BinaryValue`), properties, JSON and
the `Command` API for x2many writes. Read when declaring or extending fields.

## Contents

- [Imports](#imports)
- [Field classes](#field-classes)
- [Common parameters](#common-parameters)
- [Computed fields](#computed-fields)
- [Related and company-dependent fields](#related-and-company-dependent-fields)
- [Selection](#selection)
- [Numbers, money, dates, text](#numbers-money-dates-text)
- [Relational fields](#relational-fields)
- [Binary and Image: BinaryValue](#binary-and-image-binaryvalue)
- [Json, Properties, PropertiesDefinition](#json-properties-propertiesdefinition)
- [Command API (x2many writes)](#command-api-x2many-writes)
- [Field access: groups and NO_ACCESS](#field-access-groups-and-no_access)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

House rules (suffixes, when to index, reserved fields, related-through-x2many trap) are in
[fields guidelines](../../odoo-guidelines/guidelines/fields.md); not repeated here. Check the final merged
definition of a field (all modules) with `odoo_model`.

## Imports

```python
from odoo import api, fields, models, Command      # Command also: from odoo.fields import Command
from odoo.fields import Domain                      # domain objects, see domain.md
from odoo.tools import BinaryBytes, BinaryValue     # binary values
from odoo.tools.translate import mark_as_copy      # copy=mark_as_copy('title')
```

`odoo.fields` exports: `Field, Id, Json, Boolean, Integer, Float, Monetary, Char, Text, Html, Selection,
Date, Datetime, Many2one, Many2many, One2many, Many2oneReference, Reference, Properties,
PropertiesDefinition, Binary, Image, Command, Domain, NO_ACCESS, parse_field_expr`.

Source: odoo/fields/__init__.py, odoo/init.py:43-50, odoo/tools/__init__.py:7

## Field classes

| Class | Positional args | Specific params | Column / notes |
|---|---|---|---|
| `Boolean` | `string` | - | `bool` |
| `Integer` | `string` | - | `int4`, `aggregator='sum'` by default |
| `Float` | `string, digits, min_display_digits` | `digits=(16, 2)` or a `decimal.precision` name (`'Product Unit'`); `min_display_digits` int or precision name | `numeric` if `digits` given, else `float8`; `aggregator='sum'` |
| `Monetary` | `string, currency_field` | `currency_field` (default `'currency_id'`, then `'x_currency_id'`; assert if missing) | `numeric`; `aggregator='sum'`; also accepts `aggregator='sum_currency'` |
| `Char` | `string` | `size`, `trim=True`, `translate` | `varchar[(size)]` |
| `Text` | `string` | `translate` | `text` |
| `Html` | `string` | `sanitize=True` (or `'email_outgoing'` shortcut), `sanitize_overridable`, `sanitize_tags`, `sanitize_attributes`, `sanitize_style`, `sanitize_form`, `sanitize_conditional_comments`, `sanitize_output_method`, `strip_style`, `strip_classes`, `translate` | `text`; `translate=True` + sanitize becomes `html_translate` |
| `Date` | `string` | - | python `date` |
| `Datetime` | `string` | - | python naive `datetime` in UTC |
| `Selection` | `selection, string` | `selection`, `selection_add`, `ondelete`, `validate=True`, `group_expand=True` | `varchar` |
| `Reference` | `selection, string` | `selection` = list of `(model, label)` or method | `varchar` `"model,id"`, no FK |
| `Many2one` | `comodel_name, string` | `domain, context, ondelete, bypass_search_access, delegate, check_company` | `int4` FK |
| `One2many` | `comodel_name, inverse_name, string` | `domain, context, bypass_search_access` | virtual; `copy=False` by default |
| `Many2many` | `comodel_name, relation, column1, column2, string` | `domain, context, check_company, ondelete='cascade'` | relation table |
| `Many2oneReference` | `string` | `model_field` (name of the Char holding the model) | `int4`, no FK, `aggregator=None` |
| `Binary` | `string` | `attachment=True` | `ir.attachment` (or `bytea` if `attachment=False`) |
| `Image` | `string` | `max_width=0`, `max_height=0`, `verify_resolution=True` | Binary that resizes on write |
| `Json` | `string` | - | `jsonb`; no search, no index, values copied on read |
| `Properties` | `string` | `definition='<m2o field>.<PropertiesDefinition field>'` | `jsonb`, stored, precomputed |
| `PropertiesDefinition` | `string` | - | `jsonb`, `copy=True` |
| `Id` | - | - | the `id` field (do not declare) |

Source: odoo/orm/fields_misc.py, odoo/orm/fields_numeric.py, odoo/orm/fields_textual.py:495-660,
odoo/orm/fields_selection.py, odoo/orm/fields_temporal.py, odoo/orm/fields_relational.py:32-1300,
odoo/orm/fields_reference.py, odoo/orm/fields_binary.py, odoo/orm/fields_properties.py:34,977

## Common parameters

All are keyword arguments of `Field` (first positional is `string` unless the table above says otherwise).

| Param | Meaning |
|---|---|
| `string`, `help` | label (default: field name without `_id`/`_ids`, title-cased), tooltip |
| `readonly` | UI only; code can still write |
| `required` | `NOT NULL` in DB (a `Many2one` with `required=True` cannot use `ondelete='set null'`) |
| `default` | static value or callable `(model) -> value`; `default=None` discards inherited defaults |
| `copy` | bool or callable `(record) -> value`; default `True`, `False` for o2m, computed, related, company-dependent and fields named `state` |
| `store` | `True` by default, `False` for computed and related |
| `index` | `True`/`'btree'`, `'btree_not_null'`, `'trigram'` (GIN, needs `pg_trgm`), `False`/`None`. Translated fields only get `'trigram'`. Multi-column: `models.Index` |
| `groups` | comma-separated group xmlids, or `fields.NO_ACCESS` |
| `compute`, `inverse`, `search` | method names (or callables) |
| `compute_sudo` | default `True` for stored computes and related, `False` otherwise |
| `compute_sql` | **new in 20**: method `(self, table) -> SQL` giving the SQL value; makes a non-stored field searchable, sortable, groupable. Requires an explicit `compute_sudo` |
| `precompute` | compute stored field before INSERT (only on stored compute/related; a `default` disables it) |
| `recursive` | declare dependencies like `parent_id.X` on `X` |
| `depends`, `depends_context` | field-level alternative to the decorators (used for lambda computes) |
| `init_storage` | **new in 20**: method/callable run when the column is added to a non-empty table; fills NULLs (no ORM inside); return truthy to also recompute. `init_storage=lambda model: None` skips initialization |
| `related`, `related_sudo` | see below |
| `company_dependent` | see below |
| `aggregator` | `sum, avg, min, max, count, count_distinct, bool_and, bool_or` (+ `array_agg`, `array_agg_distinct`, `recordset` in `_read_group`); `None`/`False` disables |
| `group_expand` | method `(self, records_or_values, domain)` returning groups to always show; `True` on Selection |
| `translate` | Char/Text/Html: `True` or a callable (`html_translate`, `xml_translate`) |
| `tracking` | only on models inheriting `mail.thread`: `True` or an int sequence (see [mail-mixins.md](mail-mixins.md)) |
| `prefetch` | `True`, `False`, or a prefetch group name |
| `change_default`, `falsy_value_label`, `exportable`, `default_export_compatible`, `export_string_translation` | UI/import-export flags |

Unknown kwargs are kept but log "unknown parameter" unless the model's `_valid_field_parameter` accepts them
(`tracking` via `mail.track.mixin`, `related_sudo` in base, `company_default_for` on `res.company`,
`user_writeable` on `res.users`). `group_operator=` is no longer mapped (rule ORM010).

Source: odoo/orm/fields.py:92-317,441-524, odoo/orm/registry.py:937-1000 (indexes),
odoo/orm/models.py:327-340 (`READ_GROUP_AGGREGATE`), odoo/orm/models.py:2107 (`sum_currency`),
addons/mail/models/mail_track_mixin.py:39

## Computed fields

```python
total = fields.Monetary(compute='_compute_total', store=True)   # readonly unless inverse given

@api.depends('line_ids.price_subtotal')
def _compute_total(self):
    for rec in self:
        rec.total = sum(rec.line_ids.mapped('price_subtotal'))
```

- Defaults applied by the ORM: computed fields are `store=False`, `readonly=not inverse`, `copy=False`
  (unless stored and `readonly=False`), `compute_sudo=store`.
- `store=True, readonly=False` = editable computed field (user value kept until a dependency changes).
- Assign the field on **every** record of `self`. `@api.depends` must list every field read; stored fields must
  not depend on context except `lang` (translated) / `company` (company-dependent): see
  [orm guidelines](../../odoo-guidelines/guidelines/orm.md#computes-onchange-and-constraints).
- `search=`: return a `Domain` replacing the condition, or `NotImplemented` for unsupported operators.
  Operators arrive normalized (`'='` -> `'in'`, booleans -> `'in' [True]`).

```python
def _search_is_assigned(self, operator, value):
    if operator not in ('=', '!=') or value not in (True, False):
        return NotImplemented
    ...
```

- `compute_sql=` (non-stored, SQL-representable):

```python
code = fields.Char(compute='_compute_code', inverse='_inverse_code',
                   compute_sql='_compute_sql_code', compute_sudo=True)

def _compute_sql_code(self, table):
    table = table._with_model(self.with_company(self.env.company.root_id).sudo())
    return table.code_store
```

- `init_storage=` replaces the deprecated `_init_column` overrides:

```python
attendance_kiosk_key = fields.Char(default=lambda s: uuid.uuid4().hex, copy=False,
                                   init_storage='_init_column_attendance_kiosk_key')
```

Source: odoo/orm/fields.py:466-500,1299-1345,1357-1371, addons/account/models/account_account.py:46,321,
addons/hr_attendance/models/res_company.py:27,95, addons/maintenance/models/maintenance.py:231

## Related and company-dependent fields

- `related='partner_id.country_id'`: defaults `store=False`, `readonly=True`, `copy=False`,
  `compute_sudo=related_sudo` (default `True`). `related` + `compute` warns and drops `compute`.
- A non-stored related is searchable when the target is searchable, and gets an automatic `compute_sql`
  when every hop is SQL-representable (so it sorts/groups).
- `store=True` on a related makes it a stored computed field; add `index` / `precompute` as needed.
- `company_dependent=True`: value stored as a `jsonb` dict keyed by company id; fallback from `ir.default`.
  Only for `char, float, boolean, integer, text, many2one, date, datetime, selection, html`; cannot be
  `required` or `translate`; defaults `copy=False`, `index='btree_not_null'`, depends on context `company`.

```python
standard_price = fields.Float('Cost', company_dependent=True, ...)   # addons/product/models/product_product.py:95
```

Source: odoo/orm/fields.py:41-44,477-515,642-704

## Selection

```python
state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], default='draft', group_expand=True)
# in an extension
business_domain = fields.Selection(
    selection_add=[("sale_order", "Sale Order")], ondelete={"sale_order": "cascade"})
```

- `selection` may be a list, a method name, or a callable; with a method, `selection_add` is not allowed.
- `selection_add` items are `(value, label)` or `(value,)` to reposition an existing value.
- `ondelete` per added value: `'set null'` (default), `'cascade'`, `'set default'` (field needs a default),
  `'set <value>'`, or a callable receiving the records. A **required** field must not use `'set null'`
  (ValueError at load).

Source: odoo/orm/fields_selection.py:19-160, addons/sale/models/account_analytic_applicability.py

## Numbers, money, dates, text

- Float precision helpers: `fields.Float.round(v, precision_digits=d)`, `fields.Float.is_zero(...)`,
  `fields.Float.compare(a, b, precision_digits=d)`; `d = self.env['decimal.precision'].precision_get('Product Unit')`.
- `Monetary` is written after its currency (`write_sequence = 10`); keep a `currency_id` Many2one next to it
  (see the recipe in [recipes.md](recipes.md)).
- Date helpers: `fields.Date.today()`, `fields.Date.context_today(record, timestamp=None)`,
  `fields.Datetime.now()`, `fields.Datetime.today()`, `fields.Datetime.context_timestamp(record, ts)`,
  `to_date`, `to_datetime`, `to_string`, `start_of`, `end_of`, `add`, `subtract`. User timezone is
  `self.env.tz` (a `tzinfo`; `pytz` is not available, rule ORM015).
- Date/datetime field expressions in domains and groupby: `date:month`, and properties such as
  `date.year_number`, `quarter_number`, `month_number`, `iso_week_number`, `day_of_month`, `day_of_week`
  (see [domain.md](domain.md)).
- `Char` named `name`/`x_name` copies as "<value> (copy)" by default (`mark_as_copy`), see
  [models-inheritance.md](models-inheritance.md#copy--copy_data).

Source: odoo/orm/fields_numeric.py:60-240, odoo/orm/fields_temporal.py:29-309,
odoo/orm/environments.py:315, odoo/orm/fields_textual.py:529-534

## Relational fields

| Topic | Rule |
|---|---|
| `Many2one.ondelete` default | `'restrict'` if required else `'set null'`; transient -> regular model: `'cascade'` if required else `'set null'`; `'restrict'` forbidden towards `ir.model*` |
| `domain` | a list / `Domain` / callable `(model) -> domain` also filters x2many values read by the ORM and x2many `any` conditions; a **string** domain is client-side only; no field domain is validated on write |
| `check_company=True` | validated by `_check_company()` (automatic with `_check_company_auto = True`) |
| `bypass_search_access=True` | skip comodel access when searching through the field (set automatically for delegate fields) |
| `One2many` | needs `inverse_name` = a Many2one (or Many2oneReference) on the comodel |
| `Many2many` | implicit relation table only if model and comodel differ; give `relation, column1, column2` explicitly when two m2m fields target the same comodel |
| `Reference` | value is a record; write a record or `"model,id"` |
| `Many2oneReference` | `res_id = fields.Many2oneReference(model_field='res_model')` with a Char `res_model` |

Source: odoo/orm/fields_relational.py:91-104,208-300,844-860,895-935,1238-1300, odoo/orm/fields_reference.py,
addons/mail/models/mail_activity.py:66, addons/mail/models/mail_thread.py:156

## Binary and Image: BinaryValue

In 20.0 a binary field value is a `BinaryValue` (`odoo/tools/binary.py`), never base64 bytes.

| Operation | Code |
|---|---|
| read raw bytes | `rec.file.content` or `bytes(rec.file)` |
| base64 string | `rec.file.to_base64()` |
| metadata | `rec.file.size`, `.mimetype`, `.filename`, `.checksum` (sha256), `.open()` (IO stream), `.decode()` |
| empty test | `if rec.file:` (empty value is `EMPTY_BINARY`, falsy) |
| write bytes | `rec.file = BinaryBytes(data, filename='report.pdf')` |
| write from RPC / base64 | a `str` is base64-decoded; a dict `{'content': ..., 'filename': ...}` also works; `{'filename': 'x'}` renames |
| search | only existence: `('file', '=', False)` / `('file', '!=', False)` |

- Writing raw `bytes` raises `TypeError: use BinaryValue instead of bytes` (only `ir.attachment.raw` accepts
  bytes). `ir.attachment.datas` no longer exists: use `raw` (rule ORM014).
- `read()` / RPC returns `{'content': <base64>, 'size': n, 'filename': ...}` (filename omitted when empty).
- The `bin_size` context is gone; use `.size` (field expressions `<field>.size` and `<field>.filename` are
  supported by `Binary`).
- `Image(max_width=, max_height=)` resizes on write; use `image.mixin` for `image_1920` + resized related
  `image_1024/512/256/128`.
- XML data: `<field name="image_1920" type="bytes" file="module/static/img/x.png"/>` (`type="base64"` is
  flagged by XML006); see [data-files.md](../../data-security/references/data-files.md).

Source: odoo/tools/binary.py, odoo/orm/fields_binary.py:27-300,
odoo/addons/base/models/ir_attachment.py:618, odoo/addons/base/models/image_mixin.py,
addons/auth_totp/wizard/auth_totp_wizard.py:55

## Json, Properties, PropertiesDefinition

- `Json`: free JSON in `jsonb`; reading returns a deep copy (mutating it does nothing); not searchable,
  not indexable. Example: `addons/account/models/account_bank_statement_line.py:150`.
- `Properties` + `PropertiesDefinition`: per-container user-defined sub-fields.

```python
# container (project.project)
task_properties_definition = fields.PropertiesDefinition('Task Properties')
# child (project.task)
task_properties = fields.Properties('Properties', definition='project_id.task_properties_definition', copy=True)
```

- `definition` has exactly one dot: `<many2one on self>.<PropertiesDefinition on comodel>`.
- Property types: `boolean integer float text char html date datetime monetary signature many2one many2many
  selection tags separator`. Definition keys: `name, string, type, comodel, default, suffix, selection, tags,
  domain, view_in_cards, fold_by_default, currency_field, hidden`.
- Write a dict `{property_name: value}` on the child (a list of full definitions also updates the container);
  `read()` returns a list of definition dicts with `value`.
- Domain on one property: `('task_properties.<property_name>', '=', value)`.

Source: odoo/orm/fields_misc.py:54-86, odoo/orm/fields_properties.py:34-260,799,977-1000,
addons/project/models/project_project.py:174, addons/project/models/project_task.py:196

## Command API (x2many writes)

| Command | Tuple | Effect |
|---|---|---|
| `Command.create(vals)` | `(0, 0, vals)` | create and link |
| `Command.update(id, vals)` | `(1, id, vals)` | write on linked record |
| `Command.delete(id)` | `(2, id, 0)` | delete record (and link) |
| `Command.unlink(id)` | `(3, id, 0)` | unlink (o2m: deletes if inverse is `ondelete='cascade'`) |
| `Command.link(id)` | `(4, id, 0)` | add link |
| `Command.clear()` | `(5, 0, 0)` | unlink all |
| `Command.set(ids)` | `(6, 0, ids)` | replace links |

```python
order.write({'order_line': [Command.create({'product_id': p.id}), Command.unlink(old_line.id)]})
partner.category_id = [Command.set(tags.ids)]
```

Use the functions in Python; RPC clients (JSON-2) must send the literal tuples/lists. On comodels with
`_allow_sudo_commands = False` (e.g. `ir.access`, `ir.actions.*`) x2many commands issued from a `sudo()` /
`with_user()` environment run without sudo, as the transaction's original user.

Source: odoo/orm/commands.py, odoo/orm/models.py:499, odoo/orm/fields_relational.py:834-839

## Field access: groups and NO_ACCESS

```python
oauth_access_token = fields.Char(readonly=True, copy=False, prefetch=False, groups=fields.NO_ACCESS)
cost = fields.Float(groups='base.group_user,base.group_portal')
```

- `groups`: users outside all listed groups get no read/write (AccessError), and the field is removed from
  `fields_get` and views. `fields.NO_ACCESS` (`'.'`) denies everyone except superuser / `sudo()`.
- Programmatic checks: `has_field_access(field, 'read'|'write')`, `check_field_access(field, op)`; override
  `_has_field_access` for custom rules. Details in [access-api.md](access-api.md); declaring groups in
  [groups-privileges.md](../../data-security/references/groups-privileges.md).

Source: odoo/orm/models.py:115,2722-2790, addons/auth_oauth/models/res_users.py:24,
addons/auth_totp/models/res_users.py:33

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `fields.Float(group_operator='avg')` | `aggregator='avg'` (no mapping anymore, ORM010) | odoo/orm/fields.py:315 |
| `base64.b64decode(rec.datas)` / `rec.file` is base64 bytes | `rec.file.content`; `rec.file.to_base64()` | odoo/tools/binary.py |
| `rec.file = base64.b64encode(data)` / raw `bytes` | `rec.file = BinaryBytes(data, filename=...)` (bytes raise TypeError) | odoo/orm/fields_binary.py:108 |
| `attachment.datas` | `attachment.raw` (ORM014) | odoo/addons/base/models/ir_attachment.py:618 |
| `with_context(bin_size=True)` | `.size` on the value | odoo/orm/fields_binary.py |
| `_init_column()` / `_table_has_rows()` overrides | `init_storage=` field param | odoo/orm/models.py:2490 |
| non-stored compute needs `search=` + no sort/group | add `compute_sql=` (with explicit `compute_sudo`) | odoo/orm/fields.py:1031-1072 |
| `copy_data` override to append " (copy)" | automatic on `name`; `copy=mark_as_copy('f')` | odoo/tools/translate.py:954 |
| `_check_field_access(field, op)` | `check_field_access(field, op)` | odoo/orm/models.py:2794 |
| `pytz.timezone(self.env.user.tz)` | `self.env.tz` (zoneinfo) (ORM015) | odoo/orm/environments.py:315 |
| `<field type="base64" file=...>` | `type="bytes"` (XML006) | odoo/upgrade_code/19.3-00-base64-in-xml.py |

Run `odoo_validate` on changed files to catch these patterns.
