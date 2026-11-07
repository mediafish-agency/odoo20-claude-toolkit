# SQL, queries, grouping and SQL-backed models (Odoo 20)

When and how to leave plain `search()`/`read`: the `odoo.tools.SQL` wrapper, `env.execute_query`,
`_search()` + `Query`/`TableSQL`, `search_fetch`/`fetch`, the three grouping APIs
(`_read_group`, `read_group`, `formatted_read_group`), record-cache flush/invalidation, and report
models backed by `_table_sql` or an SQL view. Read before writing any SQL string.

## Contents

- [Pick the right tool](#pick-the-right-tool)
- [The SQL wrapper](#the-sql-wrapper)
- [Executing SQL](#executing-sql)
- [_search, Query and TableSQL](#_search-query-and-tablesql)
- [search_fetch and fetch](#search_fetch-and-fetch)
- [Grouping: _read_group, read_group, formatted_read_group](#grouping-_read_group-read_group-formatted_read_group)
- [Flush and invalidate](#flush-and-invalidate)
- [SQL-backed models (_table_sql, _auto = False)](#sql-backed-models-_table_sql-_auto--false)
- [odoo.tools.sql helpers](#odootoolssql-helpers)
- [Tooling](#tooling)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

Security rules for SQL (parameters, `SQL.identifier`, prefer the ORM):
[Use the ORM; parameterize SQL](../../odoo-security/SKILL.md#use-the-orm-parameterize-sql).
Batching rules: [Batch ORM calls](../../odoo-guidelines/guidelines/performance.md#batch-orm-calls).

## Pick the right tool

| Need | Use | Access rules / active / flush |
|---|---|---|
| records matching a domain | `search(domain, offset, limit, order)` | yes / yes / yes |
| records + some fields in one query | `search_fetch(domain, field_names, ...)` | yes / yes / yes |
| counts, sums, per-group values | `_read_group(domain, groupby, aggregates)` | yes / yes / yes |
| custom SELECT over ORM-filtered rows | `query = Model._search(domain)` then `env.execute_query(query.select(SQL(...)))` | yes / yes / yes |
| ids as a sub-query inside another domain | `('id', 'in', Model._search(domain))` | yes / yes / yes |
| bulk UPDATE, DDL, migration | `env.cr.execute(SQL(...))` + manual flush/invalidate | **no** / no / **no** |

Source: odoo/orm/models.py:1416-1500, odoo/orm/models.py:1996-2085, odoo/orm/models.py:4861-4950

## The SQL wrapper

```python
from odoo.tools import SQL

SQL("UPDATE %s SET %s = %s WHERE id = ANY(%s)",
    SQL.identifier(self._table), SQL.identifier('state'), 'done', self.ids)
SQL("SELECT id FROM %(table)s WHERE name ILIKE %(pat)s",
    table=SQL.identifier('res_partner'), pat=f"%{term}%")      # named args
SQL(", ").join(SQL.identifier(f) for f in fnames)              # join pieces / params
SQL("name LIKE 'a%%'")                                         # literal % must be doubled
```

- Code is a `%`-format string with `%s` positional **or** `%(name)s` named arguments, never both.
- Arguments are either Python values (become query parameters) or `SQL` objects (inlined with
  their own parameters). Never build the code string with f-strings, `+` or `%` on user data.
- `SQL.identifier(name)` / `SQL.identifier(alias, column)` quote identifiers (asserted against a
  regex). `to_flush=field` attaches flush metadata (see below).
- `SQL()` is empty and falsy; equality compares code + params.
- v20 `SQL` has no public `.code`/`.params`/`.to_flush` and is not iterable. Debug with
  `env.cr.mogrify(sql)`; pass `SQL` objects straight to `cr.execute`.

Source: odoo/tools/sql.py:38-195, odoo/sql_db.py:392-410

## Executing SQL

| Call | Flushes | Returns |
|---|---|---|
| `self.env.execute_query(sql)` | the fields recorded in the SQL metadata (`to_flush`) | `list[tuple]` (`[]` if no result set) |
| `self.env.execute_query_dict(sql)` | same | `list[dict]` keyed by column name |
| `self.env.cr.execute(sql)` | nothing | use `cr.fetchall()`, `cr.fetchone()`, `cr.dictfetchall()`, `cr.rowcount` |

SQL built from `query.table.<field>`, from `_search()`, or with `SQL.identifier(..., to_flush=field)`
carries `to_flush`; a hand-written `SQL("SELECT ... FROM sale_order")` does not. Then flush yourself
first: `self.env['sale.order'].flush_model(['state', 'amount_total'])`.

```python
# odoo/addons/base/models/ir_default.py:178-195 (condensed)
self.flush_model()
rows = self.env.execute_query(SQL(
    "SELECT f.name, d.json_value FROM ir_default d JOIN ir_model_fields f ON d.field_id = f.id"
    " WHERE f.model = %s AND %s",
    model_name,
    SQL("d.condition = %s", condition) if condition else SQL("d.condition IS NULL"),
))
```

Source: odoo/orm/environments.py:548-577, odoo/sql_db.py:361, odoo/sql_db.py:398-405

## _search, Query and TableSQL

`Model._search(domain, offset=0, limit=None, order=None, *, active_test=True, bypass_access=False)`
returns an unexecuted `Query` with the domain, access domain and `active` filter applied. No
default order unless you pass `order`.

| `Query` member | Meaning |
|---|---|
| `query.table` | `TableSQL` of the main table |
| `query.select(*sql)` / `query.subselect(*sql)` | full SELECT / parenthesized sub-select (default column: id) |
| `query.add_where(SQL(...))` | AND a condition (string + params is deprecated) |
| `query.add_join(kind, alias, table, condition)` | `kind` in `JOIN`, `LEFT JOIN`, `LEFT JOIN LATERAL` |
| `query.order`, `.groupby`, `.having`, `.limit`, `.offset` | set as `SQL` / int |
| `query.get_result_ids()`, `len(query)`, `bool(query)`, `iter(query)` | execute (memoized ids) |
| `query.is_empty()` | known to return nothing (no SQL run) |
| `Query(model)` / `records._as_query()` | build one by hand / from a recordset |

`TableSQL` renders fields through their own `to_sql` (related, `compute_sql`, company-dependent and
translated fields included) and checks field access:

| Expression | SQL |
|---|---|
| `table.name` or `table['name']` | `"sale_order"."name"` (+ flush metadata) |
| `table.partner_id.country_id` | joins `res_partner` (LEFT JOIN, or JOIN when the column is NOT NULL; comodel access rules unless sudo), then the column |
| `table._join('partner_id')`, `table._join('tag_ids', only_ids=True)` | explicit join through a relational field (`only_ids` for many2many: relation table only), returns the joined `TableSQL` |
| `table._sudo()`, `table._with_model(model)` | same alias, other environment/context |
| `table.id` | primary key |

```python
# addons/account/models/account_move_line.py:2475-2480
query_account = self.env['account.account']._search([
    ('company_ids', 'in', self.env.companies.ids),
    ('code', '!=', False),
])
query_account.add_where(SQL('EXISTS(%s)', query_line.select()))
account_codes = self.env.execute_query(
    query_account.select(SQL("DISTINCT %s", query_account.table.code)))
```

```python
# addons/account/models/sequence_mixin.py:303-311
query.add_where(SQL("%s = %s", query.table.sequence_prefix, with_prefix))
query.order = SQL("%s DESC", query.table.sequence_number)
query.limit = 1
result = self.env.execute_query(query.select(query.table[self._sequence_field]))
```

Pass a `Query` as a domain value to get a sub-select instead of materialized ids:
`self.search([('partner_id', 'in', self.env['res.partner']._search(dom))])`.

Source: odoo/orm/query.py:51-396, odoo/orm/models.py:4861-4961, odoo/orm/fields.py:1357-1409, odoo/orm/fields_relational.py:463-482, odoo/orm/fields_relational.py:550-575

## search_fetch and fetch

```python
# one query: search + load the listed fields into the cache
orders = self.env['sale.order'].search_fetch(
    [('state', '=', 'sale')], ['name', 'partner_id', 'amount_total'], limit=80)

# records you already hold: load fields in bulk before a loop
lines.fetch(['product_id', 'price_subtotal'])
```

- `search_fetch` is `@api.private` (not RPC); `field_names=None` means every accessible
  `prefetch=True` field. Non-stored fields in the list are computed.
- `fetch()` skips new records and fields already in cache; it checks read access.
- `search()` is `search_fetch(domain, [])`. Prefer these over `read()` in server code.

Source: odoo/orm/models.py:1431-1500, odoo/orm/models.py:3098-3140

## Grouping: _read_group, read_group, formatted_read_group

| Method | Where | Returns | Use |
|---|---|---|---|
| `_read_group(domain, groupby=(), aggregates=(), having=(), offset=0, limit=None, order=None)` | `odoo/orm/models.py` | `list[tuple]`, records for relational groupby / `recordset` aggregates | server code (default choice) |
| `read_group(...)` same signature, `@typing.final` | `odoo/orm/models.py` | same tuples with records turned into ids | RPC / external callers |
| `formatted_read_group(...)` same signature | `addons/web/models/models.py` | `list[dict]`: one key per groupby spec and aggregate, `__extra_domain`, `__fold` | web client; override this for UI tweaks |
| `web_read_group(...)` | `addons/web/models/models.py` | groups + unfolded records | list/kanban views only |

Spec syntax:

| Part | Values |
|---|---|
| groupby | `'field'`, `'m2o_field.sub_field'` (many2one paths), `'date_field:day|week|month|quarter|year'` (dates require a granularity), `'date_field:year_number|quarter_number|month_number|iso_week_number|day_of_year|day_of_month|day_of_week|hour_number|minute_number|second_number'`, properties |
| aggregates | `'__count'`, `'field:sum|avg|max|min|count|count_distinct|bool_and|bool_or|array_agg|array_agg_distinct|recordset'`, `'amount:sum_currency'` (monetary, converted at current rate) |
| having | domain on aggregate specs, operators `in not in < > <= >= = !=`: `[('__count', '>', 1)]` |
| order | groupby specs and/or aggregate specs: `'__count desc'`, `'amount_total:sum desc, partner_id'` |

```python
# addons/sale/models/crm_team.py:13-17
sale_order_data = self.env["sale.order"]._read_group(
    [("team_id", "in", self.ids), ("state", "!=", "cancel")], ["team_id"], ["__count"])
data_map = {team.id: count for team, count in sale_order_data}

# addons/sale/models/product_product.py:33-36
for product, product_uom_qty in self.env["sale.report"]._read_group(
        domain, ["product_id"], ["product_uom_qty:sum"]):
    r[product.id] = product_uom_qty
```

With no `groupby`, `_read_group` returns exactly one row (empty values when nothing matches).
Field-level default aggregation for the UI is the field's `aggregator=` ([fields.md](fields.md)).

Source: odoo/orm/models.py:329-342, odoo/orm/models.py:1930-2300, odoo/orm/utils.py:26-46, addons/web/models/models.py:567-580, addons/web/models/models.py:1020-1110

## Flush and invalidate

The ORM keeps pending writes and computed values in memory. Raw SQL does not see them, and the
cache does not see raw SQL writes.

| Before raw SQL that reads | After raw SQL that writes |
|---|---|
| `Model.flush_model(['f1', 'f2'])` | `records.invalidate_recordset(['f1'])` or `Model.invalidate_model(['f1'])` |
| `records.flush_recordset(['f1'])` | `records.modified(['f1'])` so stored computes depending on `f1` get recomputed |
| `self.env.flush_all()` | `self.env.invalidate_all()` (flushes first unless `flush=False`) |

```python
records.flush_recordset(['quantity'])
self.env.cr.execute(SQL(
    "UPDATE %s SET quantity = quantity + 1 WHERE id = ANY(%s)",
    SQL.identifier(records._table), records.ids))
records.invalidate_recordset(['quantity'])
records.modified(['quantity'])
```

`increment_fields_skiplock(records, *fields)` in `odoo.tools.sql` is a ready-made locked counter
increment. Never `cr.commit()` in business code
([Transactions and exceptions](../../odoo-guidelines/guidelines/orm.md#transactions-and-exceptions)).

Source: odoo/orm/models.py:5834-5860, odoo/orm/models.py:6227-6290, odoo/orm/environments.py:387-420, odoo/tools/sql.py:680-714

## SQL-backed models (_table_sql, _auto = False)

Two v20 patterns for read-only report models. Both need `_auto = False` (no table created),
`readonly=True` fields, and `ir.access` rows like any model
([ir-access.md](../../data-security/references/ir-access.md)).

**1. `_table_sql` property (preferred, no database view).** The returned SQL is used as a
sub-select in `FROM`; build it from `_search()` so access rules, `active` and flushing come for free.

```python
# addons/sale/report/sale_report.py:12-14, 123-128 (simplified)
class SaleReport(models.Model):
    _name = "sale.report"
    _auto = False

    @property
    def _table_sql(self) -> SQL:
        query = self.env['sale.order.line'].sudo()._search(self._order_line_domain())
        query.groupby = SQL(", ").join(self._groupby_list(query.table))
        return query.subselect(*self._select_dict_to_list(self._select_dict(query.table)))
```

Return a parenthesized SELECT (`query.subselect(...)` does it; hand-written SQL must add the
parentheses, see `addons/website/models/website_technical_page.py:62-75`). Name every column
after a field (`SQL("%s AS partner_id", table.order_id.partner_id)`) and include `id`.
When reading with `sudo()`, check access yourself first, as
`addons/account/report/account_invoice_report.py:85` does (`check_access('read')`).

**2. Database view in `init()`** (still used by several reports):

```python
# addons/crm/report/crm_activity_report.py:84-93 (condensed)
def init(self):
    tools.drop_view_if_exists(self.env.cr, self._table)
    self.env.cr.execute(SQL("""CREATE OR REPLACE VIEW %s AS (%s %s %s %s)""",
        SQL.identifier(self._table), self._select(), self._from(), self._join(), self._where()))
```

With a view, declare `_depends = {'stock.move': ['state', ...]}` so searches flush the source
fields first (`addons/stock/report/report_stock_quantity.py:12-19`); the base `_table_sql` turns
`_depends` into flush metadata.

Source: odoo/orm/models.py:506-550, odoo/orm/query.py:16-21, addons/sale/report/sale_report.py:123-128, addons/account/report/account_invoice_report.py:82-93, addons/crm/report/crm_activity_report.py:84-94

## odoo.tools.sql helpers

`odoo.tools` itself exports only `SQL` and `drop_view_if_exists`. Import the rest from
`odoo.tools.sql` (rule ORM017): `table_exists`, `column_exists`, `create_column`, `rename_column`,
`table_columns`, `create_index(cr, indexname, tablename, expressions, method='btree', where='', *, comment=None, unique=False)`,
`index_exists`, `drop_index`, `add_constraint`, `drop_constraint`, `make_identifier`,
`make_index_name`, `escape_like_value`, `increment_fields_skiplock`. Indexes and constraints on
model tables are declared with `models.Index` / `models.Constraint` instead
([models-inheritance.md](models-inheritance.md), [fields.md](fields.md)). Migration-time SQL:
[migration-scripts.md](../../data-security/references/migration-scripts.md).

Source: odoo/tools/__init__.py:15, odoo/tools/sql.py:197-800

## Tooling

- `odoo_method _table_sql` lists every SQL-backed model to copy from.
- `odoo_shell`: `print(env.cr.mogrify(query.select()))` shows the final SQL with parameters.
- `odoo_validate` flags ORM008 (`_table_query`), ORM013 (`read_group(lazy=)`), ORM017
  (`from odoo.tools import Query`/sql helpers), ORM018 (`flush_query`).
- `odoo_test` to run the module tests; `assertQueryCount` catches N+1 regressions.

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `from odoo.tools import Query` | `from odoo.models import Query, TableSQL` (ORM017) | odoo/models/__init__.py |
| `from odoo.tools import create_index, column_exists, ...` | `from odoo.tools.sql import ...` (ORM017) | odoo/tools/__init__.py |
| `Query(self.env, self._table, self._table_sql)` | `Query(self)` (or `records._as_query()`) | odoo/orm/query.py:57 |
| `_table_query = "SELECT ..."` / `def _table_query` | `@property def _table_sql(self) -> SQL` (ORM008) | odoo/orm/models.py:530 |
| `self.env.flush_query(sql)` then `cr.execute` | `self.env.execute_query(sql)` (ORM018) | odoo/orm/environments.py:548 |
| `self._field_to_sql(alias, 'f', query)` | `query.table.f` / `table['f']` | odoo/orm/query.py:324-332 |
| `query.join(...)`, `query.left_join(...)` | `table.m2o_field.col`, `table._join('f')`, `query.add_join(...)` (old ones warn) | odoo/orm/query.py:134-166 |
| `query.add_where("a = %s", [x])`, `query.order = "name"` | `add_where(SQL(...))`, `query.order = SQL(...)` (strings warn) | odoo/orm/query.py:127-176 |
| `sql.code`, `sql.params` | `env.cr.mogrify(sql)` for debugging | odoo/tools/sql.py:112-176 |
| `read_group(domain, fields, groupby, lazy=False)` dicts | `_read_group(domain, groupby, aggregates)` tuples, `formatted_read_group` for dicts (ORM013) | odoo/orm/models.py:1930-2085 |
| `'amount:sum'` dict keys `amount`, `__domain` | `formatted_read_group` keys are the specs (`'amount:sum'`), `__extra_domain` | addons/web/models/models.py:1350-1386 |
| `escape_psql(s)` | `escape_like_value(s)` | odoo/tools/sql.py:660-667 |
