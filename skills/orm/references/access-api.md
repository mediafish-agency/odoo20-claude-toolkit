# Access API in Python (Odoo 20)

How Python code checks and customizes access in Odoo 20: `check_access` / `has_access` /
`_filtered_access`, the `_access_domain` extension point, field-level access, `sudo()`/`with_user()`,
group checks and the typed `ir.config_parameter` API. The data side (`security/ir.access.csv`, rows,
restrictions, v19 conversion) is in [ir-access.md](../../data-security/references/ir-access.md); groups
are in [groups-privileges.md](../../data-security/references/groups-privileges.md).

## Contents

- [Record and model checks](#record-and-model-checks)
- [Where the ORM checks for you](#where-the-orm-checks-for-you)
- [Customizing access: `_access_domain`](#customizing-access-_access_domain)
- [The `access` domain operator](#the-access-domain-operator)
- [Field-level access](#field-level-access)
- [sudo, with_user, with_company](#sudo-with_user-with_company)
- [Group and role checks](#group-and-role-checks)
- [Typed ir.config_parameter API](#typed-irconfig_parameter-api)
- [Testing access](#testing-access)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## Record and model checks

`operation` is always one of `'read'`, `'write'`, `'create'`, `'unlink'` (asserted against
`IN_SELECTION` in `ir_access.py`).

| Method | Decorators | Result | Use it for |
|---|---|---|---|
| `records.check_access(operation)` | `@api.private`, `@typing.final` | `None`, raises `AccessError` | guard before doing something in `sudo()` on behalf of the user |
| `records.has_access(operation)` | `@typing.final` | `bool` | branch without exceptions (same logic as `check_access`) |
| `records._filtered_access(operation)` | `@typing.final` | subset of `records` | keep only the records the user may access (`filtered(has_access)` but batched) |
| `Model._access_domain(operation)` | `@api.model`, `@api.ormcache('operation', 'self.env._access_context')` | `Domain` | the only override point (see below) |

```python
# model-level: empty recordset = "does the user have this permission at all?"
if not self.env['account.move'].has_access('read'):
    return {}

# record-level, raises AccessError with the standard message
accounts.check_access('write')

# silently drop what the user cannot see
accessible = self.env['account.payment'].browse(ids)._filtered_access('read')
```

- In superuser mode (`env.su`) all three return "allowed" immediately.
- Record checks are evaluated with `sudo().with_context(active_test=False).filtered_domain(domain)`:
  archived records are checked like active ones.
- `has_access('read')` / `_filtered_access('read')` fill a per-transaction read cache
  (`env._access_cache`), so repeated checks are cheap.
- `_filtered_access` keeps new (`NewId`) records.
- These three methods are `typing.final`: do **not** override them, override `_access_domain`.
- `check_access` is `@api.private` (not callable over RPC); `has_access` stays RPC-callable.

Source: odoo/orm/models.py:3443, odoo/orm/models.py:3464, odoo/orm/models.py:3506,
odoo/addons/base/models/ir_access.py:34, addons/account/models/account_account.py:1252,
addons/account/controllers/portal.py:123, addons/account/models/account_move.py:2553

## Where the ORM checks for you

You rarely need explicit checks around plain CRUD; the ORM already does them:

| ORM call | Checks performed |
|---|---|
| `create(vals_list)` | `check_access('create')` on the model, field `write` access per given field, then `check_access('create')` on the created records (domain rows apply after insert) |
| `write(vals)` | `check_access('write')` on `self`, `check_field_access(field, 'write')` per key |
| `unlink()` | `check_access('unlink')` |
| `read()` / `fetch()` / field access | `check_access('read')`, field `groups` |
| `search()` / `_search()` | ANDs `_access_domain('read')` into the query unless `env.su` or `_search(..., bypass_access=True)` |
| `Many2one` with `bypass_search_access=True` on create/write | `check_access('read')` on the target record |

Explicit checks are needed when you **switch to sudo** (portal controllers, cross-model side effects),
when you read records by raw SQL, or before returning data computed in sudo. See
[Don't over-sudo](../../odoo-security/SKILL.md#dont-over-sudo).

Source: odoo/orm/models.py:3849, odoo/orm/models.py:4117, odoo/orm/models.py:4169,
odoo/orm/models.py:4449, odoo/orm/models.py:4861

## Customizing access: `_access_domain`

`_access_domain(operation)` returns the security `Domain` built from `ir.access` rows:
`Domain.OR(permissions) & Domain.AND(restrictions)`, plus, when `_check_inherits_access` is true
(default), an `any` restriction on each `_inherits` parent. Override it to add Python-level logic,
always combining with `super()`:

```python
from odoo.fields import Domain

class MailMail(models.Model):
    _name = 'mail.mail'
    _inherits = {'mail.message': 'mail_message_id'}
    _check_inherits_access = False   # replace the default parent check by our own

    def _access_domain(self, operation):
        if not self.env['mail.message'].has_access(operation):
            return Domain.FALSE
        return super()._access_domain(operation)
```

Rules:

- Return a `Domain` (`Domain.TRUE`, `Domain.FALSE`, or `super()` result `&`/`|` yours).
- The **base** implementation is ormcached per `(model, operation, env._access_context)`, where
  `_access_context` is `(uid, allowed_company_ids, ...)`. Your override body is not cached, so it may read
  the context (`hr.employee` grants read when a private context marker is set), but anything that the
  base domain depends on must be part of `ir.access._get_access_context()` (the `website` module adds
  `website_id` this way).
- Domain strings in `ir.access` rows are evaluated with `user`, `time`, `company_ids`, `company_id`
  (`ir.access._eval_context()`; `website` adds `website`).
- `_access_domain_heavy = True` (model attribute, used by `mail.message`, `ir.attachment`,
  `mail.activity`) tells the ORM not to build SQL for related fields / sorting through that model.
- Overriding `_check_access` still works but is deprecated since 20.0 (flagged by `odoo_validate` rule
  SEC005); `check_access_rights`, `check_access_rule`, `_filter_access_rules(_python)` are gone
  (SEC003, SEC004).

Inspect the effective rows and domain for a model with `odoo_access`, and the merged method with
`odoo_method model=<model> method=_access_domain`.

Source: odoo/orm/models.py:3601, odoo/orm/models.py:463, odoo/orm/environments.py:208,
odoo/addons/base/models/ir_access.py:308, odoo/addons/base/models/ir_access.py:312,
addons/mail/models/mail_mail.py:38, addons/hr/models/hr_employee.py:1642,
addons/website/models/ir_access.py, addons/sale_pdf_quote_builder/models/quotation_document.py:55

## The `access` domain operator

`(field, 'access', operation)` is true when the user has `operation` access on the record that a
`many2one` (or `id`) points to. It is the v20 way to say "follow the parent's rules":

```csv
id,name,model_id,group_id/id,operation,domain
base_user_account_move_line_rule,Normal User Account Move Line,account.move.line,hr_expense.group_hr_expense_team_approver,r,"[('move_id', 'access', 'read')]"
```

- Only `many2one` and `id` fields; value must be `'read'|'write'|'create'|'unlink'`.
- Resolved through the comodel's `_access_domain`, so overrides apply transitively.
- Also usable in Python domains (`search`, `filtered_domain`). Full operator list: [domain.md](domain.md).

Source: odoo/orm/domains.py:1926, addons/hr_expense/security/ir.access.csv:22,
addons/mail/security/ir.access.csv:65

## Field-level access

| API | Kind | Notes |
|---|---|---|
| `fields.X(..., groups='mod.group_a,mod.group_b')` | declaration | comma-separated xmlids, `!` negates; field hidden from `fields_get` and views, raises on read/write |
| `groups=fields.NO_ACCESS` | declaration | `'.'`: nobody (not even admins) except `sudo()`; e.g. tokens, TOTP secrets |
| `Model.has_field_access(field, operation)` | `@api.model` | `bool`; `operation` in `'read'`, `'write'` |
| `Model.check_field_access(field, operation)` | `@api.model` | raises `AccessError` |
| `Model._has_field_access(field, operation)` | `@api.model` | override hook, call `super()` first |

Both take a **`Field` object**, not a name: `record._fields['name']`.

```python
# controller: verify field rights before a sudo operation on a user-chosen field
document.check_access('write')
if field := document._fields.get(field_name):
    document.check_field_access(field, 'read')
    document.check_field_access(field, 'write')
```

```python
# extend field access (portal users only see a whitelist)
def _has_field_access(self, field, operation):
    if not super()._has_field_access(field, operation):
        return False
    if not self.env.su and self.env.user._is_portal():
        readable, writeable = self._portal_accessible_fields()
        return field.name in (readable if operation == 'read' else writeable)
    return True
```

`_check_field_access` is a deprecated alias of `check_field_access` since 20.0;
`check_field_access_rights(operation, field_names)` no longer exists (SEC003). Security reasoning for
sensitive fields: [Field-level access](../../odoo-security/SKILL.md#field-level-access).

Source: odoo/orm/models.py:2703, odoo/orm/models.py:2722, odoo/orm/models.py:2737,
odoo/orm/models.py:2794, odoo/orm/models.py:115, odoo/fields/__init__.py:21,
addons/html_editor/controllers/main.py:732, addons/project/models/project_task.py:1106,
odoo/addons/base/models/res_users.py:651, addons/auth_totp/models/res_users.py:33

## sudo, with_user, with_company

| Call | Effect |
|---|---|
| `records.sudo()` / `sudo(False)` | superuser mode on/off; user stays the same; no access checks, no record rules |
| `records.with_user(user)` | `@api.private`; switch user, **leaves** superuser mode (unless `user` is the superuser) |
| `records.with_company(company)` | `@api.private`; puts `company` first in `allowed_company_ids` (`env.company`), keeps the others |
| `env.su`, `env.is_superuser()`, `env.is_admin()`, `env.is_system()` | introspection |

Pattern for code that must read more than the user can, then return only what the user may see:

```python
records_sudo = self.sudo().search(domain)      # computation in sudo
...
return records_sudo.with_env(self.env)._filtered_access('read')
```

The full sudo checklist (what must never be attacker-controlled, `_allow_sudo_commands`, controllers)
is in [Don't over-sudo](../../odoo-security/SKILL.md#dont-over-sudo); do not duplicate it here.

Source: odoo/orm/models.py:5440, odoo/orm/models.py:5467, odoo/orm/models.py:5477,
odoo/orm/environments.py:178, odoo/orm/models.py:499

## Group and role checks

```python
self.env.user.has_group('base.group_system')                 # one xmlid
self.env.user.has_groups('base.group_user,!base.group_portal')  # spec, '!' negates
self.env.user._is_internal()    # also _is_portal(), _is_public(), _is_system(), _is_admin()
```

- `has_group` raises `AccessError` when a non-internal user asks about another user.
- `base.group_no_one` is only true in debug mode.
- Field/menu/view `groups=` attributes and the v20 group catalogue:
  [groups-privileges.md](../../data-security/references/groups-privileges.md).

Source: odoo/addons/base/models/res_users.py:1164, odoo/addons/base/models/res_users.py:1196,
odoo/addons/base/models/res_users.py:1272

## Typed ir.config_parameter API

`get_param` / `set_param` were removed (flagged by `odoo_validate` rule ORM001). Values are typed:

| Method | Default when missing or invalid | Stored as |
|---|---|---|
| `get_bool(key, default=False)` | `default` | `str2bool` of the text |
| `get_int(key, default=0)` | `default` | `int(text)` |
| `get_float(key, default=0.0)` | `default` | `float(text)` |
| `get_str(key, default='')` | `default` | raw text |
| `set_bool/set_int/set_float/set_str(key, value)` | - | `str(value)`; `None` clears the value (`set_int`/`set_float`/`set_str` also treat `False` as `None`) |

```python
ICP = self.env['ir.config_parameter'].sudo()
if ICP.get_bool('account.disable_dashboard_kpis'):
    return
batch_size = ICP.get_int('account.pdf_generation_batch') or 80
threshold = ICP.get_float('account.product_name_similarity_threshold', 0.9)
ICP.set_str('my_module.api_url', url)          # returns the previous value
```

- Getters call `check_access('read')`; only `base.group_system` has a row, so use `sudo()` in
  business code.
- An unparsable value logs a warning and returns `default`; values are cached in the `stable` ormcache.
- `res.config.settings` fields with `config_parameter='key'` pick the getter/setter from the field type
  (char/selection/datetime -> str, integer/many2one -> int, float, boolean).
- In XML data: a plain `<record model="ir.config_parameter">` with `key`/`value`, or
  `<function model="ir.config_parameter" name="set_int" eval="('analytic.project_plan', ref('...'))"/>`.

Source: odoo/addons/base/models/ir_config_parameter.py:65-160, odoo/addons/base/security/ir.access.csv:105,
odoo/addons/base/models/res_config.py:263-345, addons/account/models/account_move_send.py:755,
addons/account/models/product.py:537, addons/account/data/ir_config_parameter_data.xml,
addons/analytic/data/analytic_data.xml:17

## Testing access

```python
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger

@tagged('post_install', '-at_install')
class TestMyAccess(TransactionCase):
    @mute_logger('odoo.addons.base.models.ir_access')
    def test_salesman_own_orders(self):
        user = new_test_user(self.env, login='sm', groups='sales_team.group_sale_salesman')
        other_order = self.env['sale.order'].create({
            'partner_id': self.env.user.partner_id.id,
            'user_id': self.env.ref('base.user_admin').id,   # not the salesman's order
        })
        order = other_order.with_user(user)
        self.assertFalse(order.has_access('read'))
        with self.assertRaises(AccessError):
            order.read(['name'])
```

- Always test through `with_user(user)`: `sudo()` and the default `env` (superuser in tests) skip
  checks.
- Mute `odoo.addons.base.models.ir_access` to keep expected denials out of the log.
- Run it on a throwaway database with `odoo_test`; inspect rows with `odoo_access`.

Source: addons/sale/tests/test_access_rights.py:72, addons/sale/security/ir.access.csv:32, odoo/tests/common.py:268,
addons/account/tests/test_account_journal.py:9

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `records.check_access_rights('write')` + `check_access_rule('write')` | `records.check_access('write')` (SEC003) | odoo/orm/models.py:3443 |
| `check_access_rights(op, raise_exception=False)` | `Model.has_access(op)` on an empty recordset | odoo/orm/models.py:3464 |
| `records._filter_access_rules(op)` / `_filter_access_rules_python` | `records._filtered_access(op)` (SEC004) | odoo/orm/models.py:3506 |
| override `_check_access(operation)` | override `_access_domain(operation)` (SEC005) | odoo/orm/models.py:3575 |
| `ir.rule` record for Python-ish logic | `ir.access` row or `_access_domain` override | odoo/addons/base/models/ir_access.py |
| `check_field_access_rights(op, fnames)` | `check_field_access(field, op)` per `Field` | odoo/orm/models.py:2737 |
| `_check_field_access(field, op)` | `check_field_access(field, op)` (old name deprecated) | odoo/orm/models.py:2794 |
| `ICP.get_param('k', default)` / `set_param` | `get_str/get_int/get_float/get_bool`, `set_*` (ORM001) | odoo/addons/base/models/ir_config_parameter.py |
| `env.transaction.clear_access_cache()` | `env.transaction.invalidate_access_cache()` | odoo/orm/environments.py:851 |
