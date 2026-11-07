# Domains (Odoo 20)

How to build, combine, inspect and validate search domains with `odoo.fields.Domain`, the complete
v20 operator list (including `any!` and the new `access` operator), relative-date values such as
`'today -30d'`, and how to compose domains safely from user input. Read before writing any
`search()`, `filtered_domain()`, view/filter `domain=` or `ir.access` domain.

## Contents

- [The Domain object](#the-domain-object)
- [Combining domains](#combining-domains)
- [Inspecting and rewriting](#inspecting-and-rewriting)
- [Optimization levels and validation](#optimization-levels-and-validation)
- [Operator reference](#operator-reference)
- [Value normalization rules](#value-normalization-rules)
- [The `access` operator](#the-access-operator)
- [Dynamic (relative) dates](#dynamic-relative-dates)
- [What a `search=` method receives](#what-a-search-method-receives)
- [Safe composition from untrusted input](#safe-composition-from-untrusted-input)
- [Custom SQL conditions](#custom-sql-conditions)
- [Tooling](#tooling)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

House rules (use `Domain`, never hand-build `'&'`/`'|'` lists) live in
[ORM guidelines](../../odoo-guidelines/guidelines/orm.md#recordsets-domains-and-context); this file is the API.

## The Domain object

```python
from odoo.fields import Domain          # canonical import (odoo/fields/__init__.py)

Domain('state', '=', 'sale')            # one condition: (field_expr, operator, value)
Domain([('state', '=', 'sale'), ('amount_total', '>', 0)])   # list form: implicit AND
Domain(['|', ('a', '=', 1), ('b', '=', 2)])                  # legacy prefix lists still parse
Domain(True) is Domain.TRUE             # also Domain([]) -> TRUE
Domain(False) is Domain.FALSE
Domain(existing_domain)                 # a Domain passes through unchanged
```

| API | Meaning |
|---|---|
| `Domain.TRUE` / `Domain.FALSE` | constants (match all / nothing) |
| `Domain.AND(iterable)` / `Domain.OR(iterable)` | combine many; items may be lists or Domains; `AND([])` is TRUE, `OR([])` is FALSE |
| `d1 & d2`, `d1 \| d2`, `~d` | and / or / not (returns a new Domain; nested ANDs/ORs are flattened) |
| `d.is_true()`, `d.is_false()` | test the constants (use these, not `bool(d)`) |
| `list(d)` | legacy prefix-notation list (for JSON, XML, `ir.actions` domains) |
| `repr(d)` | the same list as a string |
| `Domain.NEGATIVE_OPERATORS` | read-only map `'not in' -> 'in'`, `'!=' -> '='`, ... |
| `Domain.custom(to_sql=, predicate=, optimize=)` | condition that renders its own SQL (advanced, see below) |

- Domain objects are **immutable** and **not hashable** (`__hash__` raises); compare with `==`.
- `Domain(a, op, v)` checks the operator immediately (`ValueError: Invalid operator`); the field
  name is checked only when the domain is optimized against a model.
- A recordset as value logs a warning and is replaced by `.ids`; a `NewId` value logs a warning and
  becomes an empty `in`/`not in`. Pass `records.ids`.
- `bool(domain)` is `not domain.is_true()` (kept for compatibility, marked TODO-deprecate). `if domain:`
  therefore means "is not TRUE", not "is non-empty".

Source: odoo/orm/domains.py:193-500, odoo/orm/domains.py:598-660, odoo/fields/__init__.py

## Combining domains

```python
domain = Domain('company_id', 'in', self.env.companies.ids)
if partner:
    domain &= Domain('partner_id', 'child_of', partner.commercial_partner_id.id)
if not include_cancel:
    domain &= Domain('state', '!=', 'cancel')
orders = self.env['sale.order'].search(domain)

# many sub-domains you already hold
domain = Domain.OR(Domain('name', 'ilike', term) for term in terms)
```

- Never `domain + [...]`: `Domain.__add__` returns a plain **list** (or `&` if both are Domains),
  `list + Domain` also returns a list. Use `&`.
- `~Domain('a', 'in', ids)` becomes `('a', 'not in', ids)` directly; negating `<`, `>` etc. is
  resolved at optimization time and adds `OR field IS NULL` when the field has no falsy value.
- Dotted paths are allowed: `Domain('partner_id.country_id.code', '=', 'BE')`; the ORM rewrites each
  hop to `('partner_id', 'any', ...)`.

Source: odoo/orm/domains.py:317-361, odoo/orm/domains.py:890-910, odoo/orm/domains.py:974-985

## Inspecting and rewriting

| Method | Use |
|---|---|
| `d.iter_conditions()` | yield every `DomainCondition` (has `.field_expr`, `.operator`, `.value`) |
| `d.map_conditions(fn)` | rebuild the domain, `fn(condition) -> Domain` for each condition |
| `d.is_condition(field_expr='', operator=(), value=())` | is `d` a single condition, optionally matching field / operator(s) / value type |

```python
# addons/analytic/models/analytic_mixin.py:176 - redirect a pseudo-field to a real one
domain = Domain(domain).map_conditions(
    lambda cond: Domain('distribution_analytic_account_ids', cond.operator, cond.value)
    if cond.field_expr == 'analytic_distribution' else cond)

# addons/account/models/account_account.py:1006 - does the caller filter on active?
any(c.field_expr == self._active_name for c in Domain(domain).iter_conditions())
```

Source: odoo/orm/domains.py:399-416, odoo/orm/domains.py:930-950, addons/analytic/models/analytic_mixin.py:176

## Optimization levels and validation

| Call | Level | What it does |
|---|---|---|
| `d.optimize(model)` | BASIC | validates fields/operators, normalizes (`=` -> `in`, paths -> `any`), merges; transaction independent, safe to send to the client |
| `d.optimize_dynamic(model)` | DYNAMIC_VALUES | BASIC + expands relative dates and the `access` operator |
| `d.optimize_full(model)` | FULL | + runs field `search=` methods, resolves inherited fields, `child_of`/`parent_of`; only standard operators remain |
| `d.validate(model)` | FULL, no searches | raises `ValueError`/`UserError` if the domain is invalid for `model` |
| `records.filtered_domain(d)` | in Python | evaluate on records already in memory |

`search()`/`_search()` call `optimize_full` themselves; call the methods above only to inspect or
pre-validate. Real use: `addons/account/models/account_move_line.py:2062` iterates
`Domain(domain).optimize_dynamic(self).iter_conditions()` to read resolved date values.

Source: odoo/orm/domains.py:173-186, odoo/orm/domains.py:418-497, odoo/orm/models.py:4861-4950

## Operator reference

The full v20 set is `STANDARD_CONDITION_OPERATORS` plus the operators registered with
`@operator_optimization` (rewritten into standard ones before SQL).

| Operator | Value | Notes |
|---|---|---|
| `=`, `!=` | scalar (or `False` for "not set") | rewritten to `in` / `not in` with a one-element set; a list value logs a warning |
| `in`, `not in` | collection | `False` in the set means "not set"; on relational fields `int` ids, `str` values search `display_name` |
| `<`, `>`, `<=`, `>=` | scalar | on date/datetime fields comparing to `False` yields FALSE and datetimes are truncated to the second |
| `like`, `not like`, `ilike`, `not ilike` | `str` | add `%` around the value; `ilike` is case-insensitive and uses `unaccent` when installed |
| `=like`, `not =like`, `=ilike`, `not =ilike` | `str` pattern | you write the `%`/`_` wildcards yourself; empty value means "equals empty / not set" |
| `=?` | any | "if value is falsy then TRUE else `=`"; handy for optional filters |
| `child_of`, `parent_of` | id(s) or name(s) | hierarchy on `_parent_name`; uses `parent_path` when `_parent_store = True` |
| `any`, `not any` | Domain/list, `Query`, `SQL` | sub-domain on the comodel of a relational field (or `id`); **comodel record rules apply** |
| `any!`, `not any!` | same | like `any` but **bypasses access rules** on the comodel; allowed in `Domain(...)` calls, **rejected in list form** |
| `access` | `'read'`, `'write'`, `'create'`, `'unlink'` | new in 20: "the user has this access on the target record", see below |

Removed in 20: `'<>'` and `'=='` (were deprecated aliases in 19) now raise "Invalid operator".

```python
Domain('order_line', 'any', [('product_id.type', '=', 'service')])   # x2many sub-domain
Domain('parent_id', 'child_of', self.id)
Domain('partner_id', 'in', ['Azure Interior'])    # string on m2o -> display_name search
Domain('email', '=ilike', 'john%@example.com')
Domain('ref', '=?', self.env.context.get('default_ref'))
```

Source: odoo/orm/domains.py:80-124, odoo/orm/domains.py:1340-1500, odoo/orm/domains.py:1517-1556, odoo/orm/domains.py:1799-1925

## Value normalization rules

- Booleans: compare only with `True`/`False`. `('flag', '=', False)` is rewritten to
  `('flag', 'not in', [True])`; `1`, `0`, `'1'` still work but emit
  `DeprecationWarning: Since 20.0, compare booleans only with booleans`.
- Many2one/x2many compared to a **string** become `('field', 'any', [('display_name', op, value)])`;
  `<`/`>` with a string on a relational field raise `TypeError`.
- `like` operators need a `str`; an `SQL` value raises "Use Domain.custom instead of SQL".
- Datetime values must be naive (UTC); aware datetimes are converted with a warning.
- Selection `not in` may be rewritten to `in` of the remaining keys (index friendly).
- A non-stored field without `search=` (or `compute_sql=`) raises
  "Field has no SQL representation because it is not stored" at search time.
- `('id', 'in', query)` / `('field', 'any', query)` accept a `Query` from `_search()` (sub-select, no
  extra rules added). See [sql-query.md](sql-query.md).

Source: odoo/orm/domains.py:859-888, odoo/orm/domains.py:1021-1022, odoo/orm/domains.py:1497-1590, odoo/orm/domains.py:1641-1800

## The `access` operator

`(field, 'access', operation)` keeps records whose `field` (a Many2one, or `id`) points to a record
the **current user** may `read`/`write`/`create`/`unlink`. It is resolved with the comodel's
`_access_domain(operation)`:

- comodel fully forbidden -> `Domain.FALSE`; fully allowed (or superuser) -> `field != False`;
- otherwise -> `(field, 'any!', <comodel access domain>)` in SQL, and `has_access()` in Python
  (`filtered_domain`);
- raises on properties, on non-many2one fields, or on an unknown operation.

Typical use is in `ir.access` rows ("you can read a message line if you can read its channel"):

```csv
access_mail_call_artifact_user,call.artifact.user,mail.call.artifact,base.group_user,r,"[('discuss_call_history_id', 'access', 'read')]"
```

Data-file syntax and permission/restriction semantics: [ir-access.md](../../data-security/references/ir-access.md);
Python side (`_access_domain`, `check_access`): [access-api.md](access-api.md).

Source: odoo/orm/domains.py:1926-1966, addons/mail/security/ir.access.csv:176, addons/hr_expense/security/ir.access.csv:22

## Dynamic (relative) dates

Date and datetime conditions (and date/datetime properties) accept relative-date strings, resolved
at the DYNAMIC level in the user's timezone (`env.tz`) and language (`week_start`). Works in Python
`search()` and in XML domains (filters, actions, `ir.access`).

```text
relative_date := ('today' | 'now')? offset*          (default start: 'now')
offset        := [+-=]<int>[dwmy]  |  [+-=]<int>[HMS]  |  [+-=](monday|...|sunday|week_start)
units         := d days, w weeks, m months, y years, H hours, M minutes, S seconds
```

| Term | Effect |
|---|---|
| `today` | start from the user's current date (result is a `date`) |
| `now` | start from the current datetime (result converted to naive UTC) |
| `+3d`, `-1m`, `-24H` | add / subtract |
| `=1d`, `=6m`, `=3H` | set that part (`=1d` first of month); on datetimes resets lower parts to 0 (`=Nw` is not supported) |
| `=tuesday` | that weekday of the current week; `+monday` next Monday (same day if already Monday), `-friday` previous |
| `=week_start` | first day of the week for the user's language |
| `2025-01-31` | strings starting with digits and `-` are ISO dates |

Real core uses:

```xml
<!-- addons/event/views/event_registration_views.xml:239 -->
<filter string="Last 30 days" name="filter_last_month_creation"
        domain="[('create_date', '&gt;=', 'today -30d'), ('create_date', '&lt;', 'today')]"/>
<!-- addons/im_livechat/views/discuss_channel_views.xml:25 -->
domain="[('create_date', '&gt;=', 'now -24H'), ('create_date', '&lt;=', 'now')]"
<!-- addons/mail/views/mail_activity_views.xml:278 -->
('date_deadline', '&gt;=', '=week_start'), ('date_deadline', '&lt;', '=week_start +1w')
```

```python
self.env['event.registration'].search([('create_date', '>=', 'today -30d')])
```

- For datetime fields use ranges (`>=` / `<`), as core does; `today` on a datetime field means
  local midnight converted to UTC.
- Without `today` the start is `now` (a datetime); for Date fields, starting with `today` keeps the
  computation in dates.
- Replaces `context_today()` + `relativedelta(...)` + `strftime` in XML domains (validator rule
  XML013; `odoo-bin upgrade_code` script `18.5-00-domain-dynamic-dates` rewrites them).

Source: odoo/tools/date_utils.py:129-225, odoo/orm/domains.py:1590-1750, odoo/upgrade_code/18.5-00-domain-dynamic-dates.py:269-273

## What a `search=` method receives

By the time a field's search method runs (FULL level), BASIC normalization has already happened:
`=` arrives as `in` with a set, booleans as `in`/`not in` `[True]`. Return a domain (list or
`Domain`) or `NotImplemented` for operators you do not support; the ORM then retries with the
inverse operator and negates the result, and finally tries `=` per value.

```python
# addons/sale/models/sale_order_line.py:1634
def _search_deferred_revenue(self, operator, value):
    if operator != "in":
        return NotImplemented
    return [("id", "in", self._get_accrual_line_ids("deferred").ids)]
```

Full recipe: [recipes.md](recipes.md). Field declaration (`search=`, `compute_sql=`):
[fields.md](fields.md).

Source: odoo/orm/domains.py:1008-1116, addons/sale/models/sale_order_line.py:481-488

## Safe composition from untrusted input

1. Parse strings with `ast.literal_eval`, never `eval`; build with `Domain(...)`.
2. Validate against the model: `domain.validate(model)` (no search executed).
3. AND the user part onto your mandatory part: `Domain(user_part) & base`. The parsed tree keeps an
   injected `'|'` inside the user sub-tree, unlike list concatenation.
4. Optionally allow-list fields with `iter_conditions()`.
5. Search **as the user**, not under `sudo()`: record rules and field `groups` are enforced
   (`_to_sql` calls `check_field_access(field, 'read')`; `any` applies comodel rules).
6. List-form domains cannot contain `any!`/`not any!` (rule-bypassing operators): `ValueError`.

```python
# adapted from addons/mail/wizard/mail_compose_message.py:1683-1695
try:
    domain = Domain(ast.literal_eval(raw) if isinstance(raw, str) else raw)
    domain.validate(self.env[model_name])
except ValueError as e:
    raise ValidationError(self.env._("Invalid domain %(domain)s", domain=raw)) from e
allowed = {'name', 'state', 'partner_id'}
if any(c.field_expr.split('.')[0] not in allowed for c in domain.iter_conditions()):
    raise AccessError(self.env._("Filtering on this field is not allowed."))
records = self.env[model_name].search(Domain('company_id', 'in', self.env.companies.ids) & domain)
```

See also [Domain injection](../../odoo-security/SKILL.md#domain-injection) and
[Don't over-sudo](../../odoo-security/SKILL.md#dont-over-sudo).

Source: odoo/orm/domains.py:240-268, odoo/orm/domains.py:418-422, odoo/orm/domains.py:1171-1185, addons/mail/wizard/mail_compose_message.py:1680-1695

## Custom SQL conditions

`Domain.custom(to_sql=lambda table: SQL(...))` injects a condition that renders its own SQL from a
`TableSQL`; without `predicate=` a `filtered_domain()` on it runs an SQL query. Core example in
`odoo/orm/fields.py:1384` (`ir.default` fallback). Prefer a `compute_sql=` field or a normal
condition; see [sql-query.md](sql-query.md) for `TableSQL`.

Source: odoo/orm/domains.py:284-299, odoo/orm/domains.py:765-812, odoo/orm/fields.py:1376-1386, odoo/orm/models.py:5732-5741

## Tooling

- `odoo_method` / `odoo_grep` to find a field's `_search_*` method or an existing domain helper.
- `odoo_shell` to try `Domain(...).optimize_full(env['x'])` and print `list(...)` on a real DB.
- `odoo_validate` flags `odoo.osv` imports (ORM016) and `context_today()` domains (XML013).

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `from odoo.osv import expression; expression.AND([...])` | `Domain.AND([...])` / `d1 & d2` (ORM016) | odoo/orm/domains.py:301-309 |
| `expression.TRUE_DOMAIN`, `FALSE_DOMAIN` | `Domain.TRUE`, `Domain.FALSE` | odoo/orm/domains.py:274-280 |
| `['|', a, b] + other` list surgery | `(Domain(a) \| Domain(b)) & Domain(other)` | odoo/orm/domains.py:317-360 |
| `if not domain:` to test "empty" | `domain.is_true()` | odoo/orm/domains.py:362-370 |
| operators `'<>'`, `'=='` | `'!='`, `'='` (aliases removed, raise) | odoo/orm/domains.py:1340-1370 |
| `('active', '=', 1)` on booleans | `('active', '=', True)` | odoo/orm/domains.py:1558-1577 |
| `(context_today() - relativedelta(days=30)).strftime('%Y-%m-%d')` in XML | `'today -30d'` (XML013) | odoo/tools/date_utils.py:129 |
| record rule on parent via `('parent_id.user_ids', 'in', [user.id])` | `('parent_id', 'access', 'read')` | odoo/orm/domains.py:1926 |
| `search` method handling only `=` | handle `in` (or return `NotImplemented`) | odoo/orm/domains.py:1041-1116 |
