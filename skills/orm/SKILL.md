---
name: orm
description: >-
  Default for any Odoo work in this Odoo 20.0 tree even when no version is named; takes priority over generic odoo-* skills (17-19 advice such as _sql_constraints, name_get, read_group(lazy=) is wrong in 20). Add or compute a field, onchange, constraint, override create/write/unlink, inherit a model - Odoo 20 Python ORM: models and inheritance (_name/_inherit/_inherits, mixins, CachedModel), every field type
  and parameter (compute/related/store, compute_sql, init_storage, BinaryValue, Properties, Json, Monetary),
  fields.Domain and its operators (including the new 'access' operator and dynamic dates), api decorators,
  api.ormcache, models.Constraint/Index, _read_group/read_group/formatted_read_group, SQL/TableSQL, access API
  (check_access, has_access, _access_domain), typed ir.config_parameter, mail.thread mixins.
when_to_use: >-
  Writing or reviewing models/*.py or wizard/*.py in an Odoo 20 addon, overriding create/write/unlink or another
  module's method, adding computed/related fields, constraints, domains, caching or raw SQL.
---

# Odoo 20 ORM

## Workflow

1. Read what you extend: `odoo_model(model, scope_module=<your module>)` (fields merged across the modules
   installed with yours), `odoo_method(model, method, include_code=true)` before any override.
2. Write the code following the rules below and Odoo's [ORM guidelines](../odoo-guidelines/guidelines/orm.md),
   [fields guidelines](../odoo-guidelines/guidelines/fields.md) and
   [performance guidelines](../odoo-guidelines/guidelines/performance.md).
3. Every new model needs rows in `security/ir.access.csv` (see `odoo20:data-security`).
4. `odoo_validate(<module>)`, then `odoo_test(<module>)`.

## Odoo 20 rules that differ from older versions

- `from odoo import api, fields, models` stays; `from odoo.api import ormcache` (not `odoo.tools`);
  `ormcache_context` is gone; invalidate with `self.env.transaction.invalidate_ormcache(name)` or declare
  `_clear_cache_name` / `_clear_cache_on_fields`.
- SQL constraints/indexes are class attributes: `_code_uniq = models.Constraint('UNIQUE(code)', "msg")`,
  `models.Index(...)`, `models.UniqueIndex(...)`. `_sql_constraints` does not exist.
- `read_group(domain, groupby, aggregates, ...)` returns tuples like `_read_group` (records turned into ids); UI-style dicts come from
  `formatted_read_group` (web). No `lazy=`, no `fields=` list.
- Access: `records.check_access('write')`, `records.has_access('read')`, `records._filtered_access('read')`;
  customise record-level access by overriding `_access_domain(operation)`. `check_access_rights/_rule` are gone.
- Config: `ICP.get_str/get_int/get_float/get_bool(key, default)` and `set_*`; `get_param/set_param` are gone.
- Binary fields hold `BinaryValue`; never write raw `bytes` (use base64 `str`, `BinaryBytes`, or
  `ir.attachment.raw`); `ir.attachment.datas` is gone.
- `display_name` via `_compute_display_name`; `toggle_active` -> `action_archive/action_unarchive`;
  `_check_recursion` -> `_has_cycle()`; `_rec_names_search` is a tuple; `group_operator=` -> `aggregator=`.
- Domains: build with `fields.Domain` (`Domain('a', '=', 1) & Domain(...)`), never concatenate user lists into a
  security domain; dynamic dates like `'today -30d'` are valid domain values.
- Translations: `self.env._("Text %(name)s", name=x)`; `LazyTranslate(__name__)` for module-level constants.
- Timezones: `zoneinfo` / `self.env.tz`; `pytz` is not a dependency anymore.

## References

- [models-inheritance.md](references/models-inheritance.md) - model types, inheritance kinds, overriding CRUD, load order
- [fields.md](references/fields.md) - every field class and parameter in v20, Binary semantics, Command
- [domain.md](references/domain.md) - Domain API, operators, `access`, dynamic dates
- [api-cache.md](references/api-cache.md) - decorators, environment/context, ormcache, CachedModel
- [sql-query.md](references/sql-query.md) - SQL wrapper, Query/TableSQL, read_group family, SQL views
- [access-api.md](references/access-api.md) - check_access/_access_domain, sudo, typed config parameters
- [mail-mixins.md](references/mail-mixins.md) - mail.thread, activities, tracking, portal/utm mixins
- [recipes.md](references/recipes.md) - short end-to-end recipes with core examples
