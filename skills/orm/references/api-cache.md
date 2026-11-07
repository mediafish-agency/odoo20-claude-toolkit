# odoo.api decorators, environment, context and ormcache (Odoo 20)

Everything exported by `odoo.api` (decorators, `Environment`, `ormcache`), how to switch user,
company, superuser mode and context, `self.env._()` translations, the per-transaction `ormcache`
with its named caches and invalidation, and `models.CachedModel`. Read before decorating a method,
caching a lookup, or touching `env`/context.

## Contents

- [What odoo.api exports](#what-odooapi-exports)
- [Method decorators](#method-decorators)
- [Environment](#environment)
- [Switching user, company, sudo, context](#switching-user-company-sudo-context)
- [Translations with self.env._](#translations-with-selfenv_)
- [ormcache](#ormcache)
- [Cache names and invalidation](#cache-names-and-invalidation)
- [CachedModel](#cachedmodel)
- [Tooling](#tooling)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

House rules on computes/onchange/constraints and RPC-exposed methods:
[ORM guidelines](../../odoo-guidelines/guidelines/orm.md#computes-onchange-and-constraints),
[Methods and extension points](../../odoo-guidelines/guidelines/orm.md#methods-and-extension-points).

## What odoo.api exports

```python
from odoo import api
# decorators: api.autovacuum, constrains, depends, depends_context, model, model_create_multi,
#             onchange, ondelete, private, readonly, ormcache
# objects:    api.Environment, api.NewId, api.SUPERUSER_ID
# typing:     api.CommandValue, ContextType, DomainType, IdType, ValuesType
```

There is no `api.Self`, `api.deprecated`, `api.returns`, `api.multi`, `api.one`. Use `typing.Self`
and `odoo.tools.func.deprecated` (validator rule ORM007).

Source: odoo/api/__init__.py, odoo/orm/types.py:13-17, odoo/tools/func.py:260-300

## Method decorators

| Decorator | Use | Rules / gotchas |
|---|---|---|
| `@api.depends('a', 'b.c')` | compute dependencies | dotted paths allowed; depending on `id` raises `NotImplementedError`; may take one callable `lambda self: (...)` |
| `@api.depends_context('company', 'lang')` | non-stored compute varies with context | special keys: `company` (env.company.id), `uid` (uid + su), `lang`, `active_test`; other values must be hashable (lists become tuples) |
| `@api.constrains('a', 'b')` | Python constraint, raise `ValidationError` | simple names only (dotted ignored); runs only when a listed field is in the `create`/`write` vals; may take a callable |
| `@api.onchange('a')` | form-view helper on a pseudo-record | UI only; dotted names ignored; may return `{'warning': {'title', 'message', 'type': 'notification'}}` |
| `@api.ondelete(at_uninstall=False)` | block `unlink` on business conditions | name it `_unlink_if_*` / `_unlink_except_*`; `at_uninstall=True` only if it must also block module uninstall |
| `@api.model` | method where only the model matters | on a method named `create` it is turned into `model_create_multi` |
| `@api.model_create_multi` | `create(self, vals_list)` | accepts a dict or a list of dicts from callers, you always get a list |
| `@api.private` | public name not callable over RPC | use for public helpers that must not be RPC entry points |
| `@api.readonly` | RPC call may run on a read-only cursor | `/web/dataset/call_kw` reads the flag; never write inside such a method |
| `@api.autovacuum` | run by the daily `ir.autovacuum` cron | method name must start with `_` (asserted); may return `(done, remaining)` |
| `@api.ormcache(...)` | memoize a model method | see [ormcache](#ormcache) |

```python
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

class LibraryBook(models.Model):
    _name = 'library.book'
    _description = "Book"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault('code', self.env['ir.sequence'].next_by_code('library.book'))
        return super().create(vals_list)

    @api.depends('line_ids.price')
    def _compute_total(self):
        for book in self:
            book.total = sum(book.line_ids.mapped('price'))

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        if any(b.date_end and b.date_start > b.date_end for b in self):
            raise ValidationError(self.env._("End date must be after start date."))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_borrowed(self):
        if any(b.state == 'borrowed' for b in self):
            raise UserError(self.env._("You cannot delete a borrowed book."))
```

Real examples: `@api.depends_context` in `addons/sale/models/product_product.py:44`,
`@api.autovacuum` in `addons/bus/models/bus.py:80`, `@api.readonly` in
`addons/mail/models/mail_activity.py:768`. CRUD override details: [models-inheritance.md](models-inheritance.md).

Source: odoo/orm/decorators.py:44-333, odoo/orm/environments.py:501-527, addons/web/controllers/dataset.py:15-34, odoo/addons/base/models/ir_autovacuum.py:17-40

## Environment

`self.env` is an `api.Environment` (a mapping of model names to empty recordsets).

| Attribute / method | Value |
|---|---|
| `env.cr`, `env.uid`, `env.su`, `env.context` | cursor, user id, superuser flag, `frozendict` context |
| `env['res.partner']` | empty recordset; `'x.y' in env` tests the model exists |
| `env.user` | current user (sudoed record) |
| `env.company`, `env.companies` | from `allowed_company_ids` (checked against the user unless `su`), else user company/companies |
| `env.lang` | context `lang` (validated) or `None`; `env.tz` is a `ZoneInfo` (context `tz`, user tz, else UTC) |
| `env.website` | `website` record from context `website_id` (possibly empty) |
| `env.ref('mod.xmlid', raise_if_not_found=True)` | record or `None` when not raising |
| `env.is_superuser()`, `env.is_admin()`, `env.is_system()` | su / "Access Rights" group / "Settings" group (all true in su) |
| `env.registry`, `env.transaction` | registry and per-transaction state (`transaction.invalidate_ormcache`) |
| `env.execute_query(SQL)`, `env.execute_query_dict(SQL)` | see [sql-query.md](sql-query.md) |
| `env.flush_all()`, `env.invalidate_all(flush=True)` | record-cache maintenance, see [sql-query.md](sql-query.md#flush-and-invalidate) |
| `env(cr=None, user=None, context=None, su=None)` | new/reused environment with changed parameters |

`env.clear()` is deprecated in 20 (use `env.transaction.clear()` / `reset()`). `self._cr`,
`self._uid`, `self._context` are deprecated since 19: use `self.env.cr`, `.uid`, `.context`.

Source: odoo/orm/environments.py:44-420, odoo/orm/models.py:5398-5410

## Switching user, company, sudo, context

| Call | Effect |
|---|---|
| `records.sudo()` / `sudo(False)` | superuser mode on/off, same user; switching on **drops all `default_*` context keys** |
| `records.with_user(user)` | another user, always `su=False` (unless it is the superuser) |
| `records.with_company(company)` | puts `company` first in `allowed_company_ids` (so `env.company == company`) |
| `records.with_context(key=val)` | merge into the current context |
| `records.with_context({...}, key=val)` | replace the context (keeps `allowed_company_ids` if present) |
| `records.with_env(env)` | attach to another environment, same prefetch |

All are `@api.private` and return a new recordset sharing the prefetch set. `with_context(company=...)`
warns: the `company` key has a special meaning for `@api.depends_context`. Prefix your own
context keys and never leave a stray `default_<field>` in context
([Recordsets, domains and context](../../odoo-guidelines/guidelines/orm.md#recordsets-domains-and-context)).
Security review of `sudo()`/`with_user()`: [Don't over-sudo](../../odoo-security/SKILL.md#dont-over-sudo).

Source: odoo/orm/models.py:5431-5545, odoo/orm/environments.py:126-149, odoo/tools/misc.py:927-931

## Translations with self.env._

```python
raise UserError(self.env._("Book %(name)s is already borrowed.", name=book.name))
```

- Language is `env.lang` (en_US when unset); the module is detected from the caller.
- Pass either positional or keyword format arguments, not both; a `LazyGettext` (from
  `LazyTranslate(__name__)` module constants) is accepted without arguments.
- Translate static literals only: [Translate only static literals](../../odoo-guidelines/guidelines/python.md#translate-only-static-literals).
  Full i18n workflow: [i18n.md](../../data-security/references/i18n.md).

Source: odoo/orm/environments.py:344-378, odoo/tools/translate.py:1146-1240

## ormcache

Memoize a pure function of its arguments on a model method. Import from `odoo.api`
(`odoo.tools.ormcache` still resolves but emits a `DeprecationWarning`, rule ORM003).

```python
# odoo/addons/base/models/decimal_precision.py:12-27
class DecimalPrecision(models.Model):
    _name = 'decimal.precision'
    _clear_cache_name = 'stable'          # any create/write/unlink clears cache 'stable'

    @api.model
    @api.ormcache('application', cache='stable')
    def precision_get(self, application):
        self.flush_model(['name', 'digits'])
        self.env.cr.execute('select digits from decimal_precision where name=%s', (application,))
        res = self.env.cr.fetchone()
        return res[0] if res else 2
```

- Arguments of `ormcache(*args, cache='default')` are **expressions** over the method parameters,
  evaluated to build the key: `'model_name'`, `'self.env.uid'`, `'self.env.company.id'`,
  `'frozenset(modules)'`. The key always includes `self._name` and the method; it does **not**
  include `self.ids`, the user, the company or the context unless you list them
  (example `odoo/addons/base/models/ir_default.py:171`).
- Any other keyword (`skiparg=`, `keys=`) is silently ignored in 20.
- Never return recordsets (cursor-bound) or mutable objects you later mutate: return ids,
  tuples, `frozendict`.
- Unhashable key values log "cache lookup error" and call the method uncached.
- Storage is **per transaction**: a layer over the registry-wide (per process) LRU. Values
  computed in a transaction are pushed to the shared LRU on commit; an invalidation is visible
  to other transactions/processes only after commit (database signaling); a savepoint rollback
  restores the previous layer.

Source: odoo/orm/cache.py:59-181, odoo/tools/__init__.py:22-28, odoo/orm/environments.py:579-620, odoo/orm/environments.py:935-1060

## Cache names and invalidation

| Cache | Size | `invalidate_ormcache(name)` also clears | Typical content |
|---|---|---|---|
| `default` | 8192 | `templates.cached_values` | most business lookups |
| `stable` | 1024 | `default`, `templates.cached_values` | rarely-changing config (`ir.config_parameter`, `ir.model`, `CachedModel`) |
| `assets` | 512 | `templates.cached_values` | asset bundles |
| `templates` | 1024 | `templates.cached_values` | compiled QWeb |
| `routing` | 1024 | `routing.rewrites`, `templates.cached_values` | HTTP routing |
| `groups` | 64 | `default`, `templates`, `templates.cached_values` | `res.groups` processing |

Invalidate, from the most declarative to the most manual:

1. `_clear_cache_name = 'default'` on the model: `create`, `write` and `unlink` call
   `env.transaction.invalidate_ormcache(name)`.
2. `_clear_cache_on_fields = {'active', ...}`: restrict the `write` trigger to these fields
   (`None` = any field). Example `addons/product/models/product_product.py:22-26`.
3. Explicit: `self.env.transaction.invalidate_ormcache('stable')` (no argument = `'default'`;
   names with a dot are refused). Example `addons/analytic/models/analytic_plan.py:274`.

`env.registry.clear_cache(...)`, `clear_all_caches()`, `signal_changes()`, `reset_changes()` no longer
exist (rule ORM004, `odoo-bin upgrade_code` script `19.4-00-ormcache-on-transaction`).
Access-rule cache: `env.transaction.invalidate_access_cache(model_name)` (renamed from
`clear_access_cache`).

Source: odoo/orm/registry.py:53-73, odoo/orm/environments.py:833-860, odoo/orm/models.py:486-490, odoo/orm/models.py:3797, odoo/orm/models.py:3980-3984, odoo/orm/models.py:4225

## CachedModel

`models.CachedModel` is a `Model` base class (not itself in the registry) that keeps selected
field values of a record subset in the `stable` ormcache, so reads of those fields cost no query.

```python
# odoo/addons/base/models/res_currency.py:51-59
class ResCurrency(models.CachedModel):
    _name = 'res.currency'
    _cached_data_domain = [('active', '=', True)]
    _cached_data_fields = ('name', 'symbol', 'position', 'decimal_places', 'active')
```

| Member | Meaning |
|---|---|
| `_cached_data_domain` | which records are cached (default `[]`: all, archived included) |
| `_cached_data_fields` | tuple of fields to cache: no dependency on other models or context, not translated |
| `_clear_cache_name = 'stable'`, `_clear_cache_on_fields` | preset: writing a cached field clears the cache |
| `Model.get_all()` | `@api.model @api.private`: browse all cached records (no query once cached), e.g. `env['res.lang'].get_all()` |
| `_cached_data()` | `frozendict` `{'id': ids, field: values}` (ormcache `stable`) |

- Reads of cached fields still check field access and `check_access('read')`.
- Core cached models: `res.company`, `res.country`, `res.currency`, `res.lang`, `website`. Extend
  them with a normal `models.Model` + `_inherit` (e.g. `addons/account/models/res_currency.py:12`).
- To use another cache, override `_clear_cache_name` and `_cached_data` (see
  `odoo/addons/base/models/website.py:5-36`).

Source: odoo/orm/models_cached.py, odoo/models/__init__.py, odoo/addons/base/models/res_lang.py:83-92

## Tooling

- `odoo_method` shows every override of a method (e.g. who extends `_get_model_defaults`).
- `odoo_grep "invalidate_ormcache('stable')"` to see which models share a cache before adding
  a new consumer.
- `odoo_validate` flags ORM002 (`ormcache_context`), ORM003 (import), ORM004 (registry cache API),
  ORM007 (`api.deprecated`/`api.Self`).
- `odoo_shell` to inspect `env.transaction.ormcaches__` or time a cached method on a real DB.

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `from odoo.tools import ormcache` / `@tools.ormcache(...)` | `@api.ormcache(...)` (ORM003) | odoo/api/__init__.py |
| `@tools.ormcache_context('x', keys=('lang',))` | `@api.ormcache('x', 'self.env.lang')` (ORM002) | odoo/orm/cache.py:74 |
| `@ormcache(skiparg=1)` | removed; keyword silently ignored, list key expressions instead | odoo/orm/cache.py:74-76 |
| `self.env.registry.clear_cache('x')` | `self.env.transaction.invalidate_ormcache('x')` or `_clear_cache_name` (ORM004) | odoo/orm/environments.py:833 |
| `registry.clear_all_caches()` | invalidate the named caches you depend on | odoo/orm/registry.py:66-73 |
| `env.transaction.clear_access_cache()` | `invalidate_access_cache()` | odoo/orm/environments.py:852-856 |
| `env.clear()` | `env.transaction.clear()` / `reset()` | odoo/orm/environments.py:380 |
| `api.Self`, `@api.deprecated` | `typing.Self`, `odoo.tools.func.deprecated` (ORM007) | odoo/api/__init__.py |
| `self._cr`, `self._uid`, `self._context` | `self.env.cr`, `self.env.uid`, `self.env.context` | odoo/orm/models.py:5398-5410 |
