# Search views (Odoo 20)

`<search>` archs: fields, filters, group-bys, date filters (new `end_date`, relative `default_period`
values, child options), parent filters (new), the search panel, `search_default_*` keys and the
dynamic date strings usable in any domain. Read this before writing or extending a search view.

## Contents
- Validation and structure
- `<field>` in search
- `<filter>`: domain, group-by, separators
- Date filters
- Parent filters (new)
- `search_default_*` and `searchpanel_default_*`
- Search panel
- Dynamic dates in domains
- v19 habit -> Odoo 20

## Validation and structure

- Root `<search string="...">`; children: `field`, `filter`, `separator`, `group`, `newline`,
  `searchpanel` (one at most). RNG `search_view.rng` + `common.rng`; the `<searchpanel>` is removed
  before the RNG pass and validated in Python only.
- `<group>` in a search view takes **no `string`/`expand`** (not in the RNG `group` definition): core uses
  a bare `<group>` around group-by filters.
- Consecutive filters form one OR-ed block; a `<separator/>` (or a `<group>`) starts a new block, and
  blocks are AND-ed.
- Filter `domain`s are validated (field names must exist); `date`/`end_date` must name searchable
  date/datetime fields.
- Check: `odoo_validate(<module>)` (XML007 flags removed date attributes, XML013 suggests dynamic dates).

Source: odoo/addons/base/rng/search_view.rng, odoo/addons/base/rng/common.rng:285-300, odoo/addons/base/models/ir_ui_view.py:1968-1981,2036-2079, addons/sale/views/sale_order_views.xml:1102-1139

## `<field>` in search

| Attribute | Effect |
|---|---|
| `name` | model field (must exist) |
| `string` | label in the autocomplete |
| `filter_domain` | domain applied instead of `[(name, op, value)]`; `self` = typed text, `raw_value` = selected value |
| `operator` | operator used in `[(name, operator, value)]` when there is no `filter_domain` (ignored if `filter_domain` is set) |
| `domain` | restricts the many2one/many2many autocomplete sub-items |
| `context` | merged into the context when the facet is active |
| `invisible`, `groups` | visibility |

```xml
<field name="name" string="Order"
       filter_domain="['|', '|', ('name', 'ilike', self), ('client_order_ref', 'ilike', self),
                      ('partner_id', 'child_of', self)]"/>
<field name="parent_id" string="Manager" domain="[('company_id', 'in', allowed_company_ids)]"/>
```

Source: addons/web/static/src/search/search_arch_parser.js:116-212, addons/web/static/src/search/search_model.js:2182-2190, addons/web/static/src/search/search_bar/search_bar.js:312-330, addons/hr/views/hr_employee_views.xml:9-15

## `<filter>`: domain, group-by, separators

| Kind | Markup |
|---|---|
| domain filter | `<filter name="my_orders" string="My Orders" domain="[('user_id', '=', uid)]"/>` |
| group-by | `<filter name="customer" string="Customer" context="{'group_by': 'partner_id'}"/>` |
| date group-by | `context="{'group_by': 'date_order:month'}"` (intervals `year`, `quarter`, `month`, `week`, `day`; default `month`) |
| hidden (for `search_default_*` / actions) | `invisible="1"` (python expr on the context) |
| context filter | `context="{...}"` without `group_by` |

Other attributes: `help` (tooltip, also used as label fallback), `groups`. A `group_by` value must be a
string naming an existing field (validated).

```xml
<filter name="my_sale_orders_filter" string="My Orders" domain="[('user_id', '=', uid)]"/>
<filter invisible="1" string="Late Activities" name="activities_overdue"
        domain="[('my_activity_date_deadline', '&lt;', 'today')]"/>
<group>
    <filter name="salesperson" string="Salesperson" context="{'group_by': 'user_id'}"/>
    <filter name="order_month" string="Order Date" context="{'group_by': 'date_order'}"/>
</group>
```

Source: addons/web/static/src/search/search_arch_parser.js:214-330, addons/web/static/src/search/utils/dates.js:55-73, odoo/addons/base/models/ir_ui_view.py:2255-2273, addons/sale/views/sale_order_views.xml:1119-1137

## Date filters

`<filter date="field">` turns a filter into a period picker (month, quarter, year options plus
relative options). Attributes:

| Attribute | Value |
|---|---|
| `date` | date/datetime field, searchable (validated) |
| `end_date` | **new**: second date field; matches records whose `[date, end_date]` range overlaps the period (a missing end = starts and ends on `date`); requires `date` |
| `default_period` | comma list of options selected when the filter is activated without an explicit option |
| `domain` | AND-ed with the period domain |

`default_period` values accepted by the validator:
- `month`, `month-1`, `month-2`, `year`, `year-1`, `year-2` (pattern `(year|month)([+-]N)?`; the UI
  generates offsets -2..0 only)
- `first_quarter`, `second_quarter`, `third_quarter`, `fourth_quarter`
- relative: `today`, `this_week`, `this_month`, `this_quarter`, `this_year`
- `custom_<child name>` for a child option (below)

Default when absent: `month`. Child options: inner `<filter name string domain>` (all three
required) become extra options with id `custom_<name>`.

```xml
<filter string="Creation Date" name="filter_creation_date" date="create_date" default_period="month"/>
<filter name="filter_session_date" date="create_date" string="Session Date">
    <filter name="rated_on_last_24_hours" string="Last 24 Hours"
            domain="[('create_date', '&gt;=', 'now -24H'), ('create_date', '&lt;=', 'now')]"/>
    <filter name="rated_on_last_7_days" string="Last 7 Days"
            domain="[('create_date', '&gt;=', 'today -7d'), ('create_date', '&lt;', 'today')]"/>
</filter>
<filter string="Period" name="period" date="date_from" end_date="date_to" default_period="this_month"/>
```

Source: odoo/addons/base/rng/common.rng:376-378, odoo/addons/base/models/ir_ui_view.py:40-41,2036-2079, addons/web/static/src/search/search_arch_parser.js:237-330, addons/web/static/src/search/utils/dates.js:17-62,268-300,395-401, addons/im_livechat/views/discuss_channel_views.xml:24-28, addons/crm/views/crm_lead_views.xml:635, addons/web/static/tests/search/search_bar_menu/filter_menu.test.js:648-690

## Parent filters (new)

A `<filter string="...">` with children and no `date` becomes an accordion entry ("parent filter"):

- children `<filter name string domain>`: fixed options (all three attributes required);
- or one child `<field name="..."/>` (many2one, many2many or selection): options loaded lazily from the
  field values; an inner `domain` filters the loaded comodel records.
- `name` is optional on the parent (RNG second form: `string` + children only).

```xml
<filter string="Status">
    <filter domain="[('state', '=', 'confirm')]" string="First Approval" name="approve"/>
    <filter domain="[('state', '=', 'validate')]" string="Approved" name="validated"/>
</filter>
<filter string="Stage" name="stage_options">
    <field name="stage_id"/>
</filter>
```

Source: odoo/addons/base/rng/common.rng:379-407, addons/web/static/src/search/search_arch_parser.js:265-330, addons/web/static/src/search/search_model.js:933-990, addons/hr_holidays/views/hr_leave_views.xml:55-62, addons/web/static/tests/search/search_bar_menu/filter_menu.test.js:1360-1415

## `search_default_*` and `searchpanel_default_*`

Put them in the action `context` (or a button `context`):

| Key | Value |
|---|---|
| `search_default_<filter name>` | truthy: activate the filter |
| `search_default_<group-by filter name>` | number = rank among default group-bys |
| `search_default_<date filter name>` | `1`/`True` (use `default_period`), or option ids `'year-1,month-1'`, or a relative id `'today'` |
| `search_default_<child filter name>` | activate that child option of its date/parent filter |
| `search_default_<field name>` | value of a `<field>`: id for many2one, list of ids for x2many, key for selection, text otherwise |
| `searchpanel_default_<field name>` | active value (id) of a search panel category |

```xml
<field name="context">{'search_default_sales': 1, 'search_default_salesperson': 1}</field>
```

Source: addons/web/static/src/search/search_model.js:1805-1825, addons/web/static/src/search/search_arch_parser.js:138-205,283-305, addons/web/static/tests/search/search_bar_menu/filter_menu.test.js:427-440

## Search panel

```xml
<searchpanel view_types="kanban,list,graph,pivot,hierarchy">
    <field name="company_id" groups="base.group_multi_company" icon="business" enable_counters="1"/>
    <field name="department_id" icon="group" icon_class="oi-filled" enable_counters="1"/>
    <field name="state" select="multi" expand="1" icon="check_box" enable_counters="1"/>
</searchpanel>
```
| Attribute | Applies to | Notes |
|---|---|---|
| `view_types` | `<searchpanel>` | default `kanban,list` |
| `class` | `<searchpanel>` | |
| `select` | field | `one` (category, default) or `multi` (checkbox filter) |
| `icon` / `icon_class` | field | Material Symbols name; defaults `folder` (category) / `filter_alt` (filter), class `oi-filled` |
| `string`, `color` | field | |
| `enable_counters` | field | show record counts (disabled for categories if any multi filter has a `domain`) |
| `expand` | field | also show values without records |
| `limit` | field | max values loaded (default 200; core uses `limit="false"` to load all) |
| `hierarchize`, `depth` | category | tree of parent/child values (default hierarchize) |
| `domain`, `groupby` | `select="multi"` only | `domain` on a category raises "Searchpanel item with select multi cannot have a domain" |

Source: odoo/addons/base/models/ir_ui_view.py:2160-2166, addons/web/static/src/search/search_arch_parser.js:375-450, addons/hr/views/hr_employee_views.xml:11-14, addons/hr_expense/views/hr_expense_views.xml:602-606

## Dynamic dates in domains

Domain values on date/datetime fields may be **strings** parsed server-side by the ORM (and client-side
by `parseSmartDateInput`), so a filter needs no `context_today()` arithmetic:

```python
# grammar (odoo/tools/date_utils.py:parse_date)
# relative_date := ('today' | 'now')? offset*
# offset        := [=+-]N[dwmy] | [=+-]N[HMS] | [=+-](monday..sunday | week_start)
```
- `today` gives a date at midnight in the user's timezone; `now` (default) a datetime.
- `+`/`-` shift; `=` sets a part and resets the smaller ones: `'=1d'` first day of the month,
  `'=week_start'` first day of the week (locale), `'=6m'` June.

```xml
<filter name="last_30" string="Last 30 days" domain="[('date', '&gt;=', 'today -30d')]"/>
<filter name="this_week" string="This week"
        domain="[('date', '&gt;=', 'today =week_start'), ('date', '&lt;', 'today =week_start +1w')]"/>
```
Works in Python too: `self.search([('create_date', '>=', 'now -24H')])`.

Source: odoo/tools/date_utils.py:129-190, odoo/orm/domains.py:1590-1610,1650-1670, addons/web/static/src/core/l10n/dates.js:322, odoo/upgrade_code/18.5-00-domain-dynamic-dates.py

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `start_month`/`end_month`/`start_year`/`end_year` on date filters | removed; UI offsets fixed to -2..0 (XML007, `20.0-00-search-date-filters`) | odoo/upgrade_code/20.0-00-search-date-filters.py |
| two filters for "starts in"/"ends in" a period | one filter with `end_date=` | odoo/addons/base/rng/common.rng:377 |
| `default_period` only months/years/quarters/custom | also `today`, `this_week`, `this_month`, `this_quarter`, `this_year` | odoo/addons/base/models/ir_ui_view.py:41 |
| every `<filter>` needs `name` | parent filters: `string` + children | odoo/addons/base/rng/common.rng:399-406 |
| `context_today().strftime(...)` / `relativedelta` in domains | `'today -30d'`, `'=week_start'` (XML013) | odoo/upgrade_code/18.5-00-domain-dynamic-dates.py |
| `<group expand="0" string="Group By">` | bare `<group>` | odoo/addons/base/rng/common.rng:285-300 |
| fa icons in searchpanel `icon=` | Material names + `icon_class` | addons/web/static/src/search/search_arch_parser.js:420-440 |
