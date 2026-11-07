# Calendar, graph, pivot, activity, hierarchy and QWeb views (Odoo 20)

Attributes and children of the non-list/form view types as read by Odoo 20 (RNG + JS parsers), the new
calendar `schedule` and `<popover>` (with `card_id`), and which view types are validated by RNG versus
Python. List/form: [list-form.md](list-form.md); kanban/card: [kanban-card.md](kanban-card.md);
search: [search.md](search.md).

## Contents
- View types and how they are validated
- Calendar
- Calendar popover
- Graph
- Pivot
- Activity (mail)
- Hierarchy (web_hierarchy)
- QWeb views
- v19 habit -> Odoo 20

## View types and how they are validated

| `ir.ui.view.type` | Module | RNG (`odoo/addons/base/rng/`) | Python checks | Usable in `view_mode` |
|---|---|---|---|---|
| `list` | base | `list_view.rng` | `_validate_tag_list` | yes |
| `form` | base | none | `_validate_tag_*` (page, label, button, field...) | yes |
| `search` | base | `search_view.rng` | `_validate_tag_search`, `_validate_tag_filter`, `_validate_tag_searchpanel` | no (`search_view_id`) |
| `kanban` | base | none | directives whitelist, `card_id` inlining | yes |
| `card` | base | none | directives whitelist | no (`card_id` only) |
| `calendar` | base | `calendar_view.rng` | `_validate_tag_calendar` | yes |
| `graph` | base | `graph_view.rng` | `_validate_tag_graph` (only `<field>` children) | yes |
| `pivot` | base | `pivot_view.rng` | - | yes |
| `qweb` | base | none (`import_xml.rng` for `<template>`) | key required | no |
| `activity` | mail | `activity_view.rng` | directives whitelist | yes (mail adds it) |
| `hierarchy` | web_hierarchy | none | `_validate_tag_hierarchy` | yes (web_hierarchy adds it) |

The view-mode icons and multi-record flags come from `_get_view_info()` (`addons/web/models/ir_ui_view.py`).
After writing a view, run `odoo_validate(<module>)` (RNG + legacy rules) and check the combined arch with
`odoo_views(xmlid, resolve="db")`.

Source: odoo/addons/base/models/ir_ui_view.py:157-165,1926-1981, odoo/tools/view_validation.py:314, addons/mail/models/ir_ui_view.py, addons/mail/models/ir_action_act_window.py, addons/web_hierarchy/models/ir_ui_view.py, addons/web_hierarchy/models/ir_actions.py

## Calendar

| Attribute | Value / effect |
|---|---|
| `date_start` | **required** date/datetime field |
| `date_stop` | end field (defaults to `date_start`) |
| `all_day` | boolean field marking all-day events |
| `color` | field used for colours (and the default filter colour) |
| `mode` | initial scale: `day`, `week`, `month`, `year` |
| `scales` | allowed scales, e.g. `month,year` |
| `schedule` | **new**: `1` shows a "to schedule" list of records with empty dates that can be dragged onto the calendar (needs `edit` allowed, not on small screens) |
| `event_limit` | max events per day cell (int, default 5) |
| `quick_create` / `quick_create_view_id` | quick create on/off, form view id (`%(xmlid)d`) used for it |
| `form_view_id` | form used to open/create events |
| `event_open_popup` | `1`: open records in a dialog instead of the full form |
| `multi_create_view` | xmlid of the multi-create form |
| `create_name_field` | char field filled by quick create |
| `aggregate` | `field` or `field:agg` (default: the field's aggregator, else `sum`): total shown next to each side-panel filter value |
| `create` `edit` `delete` | `0` disables |
| `hide_date` / `hide_time` | hide the date/time in event pills |
| `show_unusual_days`, `show_date_picker` (default on), `month_overflow` (default on) | display options |
| `js_class`, `string` | generic |

Field children: every `<field>` is loaded and shown in the default popover. Filter side panel attributes on
a field: `filters="1"` (filter on its values), `avatar_field`, `color` (colour field of the comodel),
`write_model` + `write_field` (persist filters, e.g. `calendar.filters`), `filter_field`.

```xml
<calendar date_start="date_deadline" string="Tasks" mode="month" color="color" event_limit="5"
          hide_time="true" event_open_popup="true" quick_create="0" show_unusual_days="True"
          js_class="project_task_calendar" schedule="1" scales="day,week,month,year">
    <field name="user_ids" widget="many2many_avatar_user" invisible="not user_ids"/>
    <field name="stage_id" filters="1" widget="task_stage_with_state_selection"/>
</calendar>
```

Source: odoo/addons/base/rng/calendar_view.rng, addons/web/static/src/views/calendar/calendar_arch_parser.js, addons/web/static/src/views/calendar/calendar_controller.js:116-121, addons/web/static/src/views/calendar/calendar_model.js:41-43,489-496,643-696, addons/project/views/project_task_views.xml:900-925, addons/calendar/views/calendar_views.xml:443-476

## Calendar popover

`<popover>` (at most one, inside `<calendar>`) customises the event popover; RNG children: `<field>` and
one `<templates>`. Template names:

| `t-name` | Role |
|---|---|
| `popover-header` | header (default: the record `display_name`) |
| `popover-body` | body (rendered as a card) |
| `popover-footer` | buttons; replaces the default Edit/Delete footer unless it has `replace="0"` |

`card_id="%(module.card_view)d"` on `<popover>` loads a [card view](kanban-card.md) and uses its
`card` template as the body when no `popover-body` is given. Without any template the body lists the
calendar `<field>`s; a field `options="{'icon': 'location_on'}"` shows that icon instead of the label.

```xml
<popover>
    <field name="source_stale"/>
    <templates>
        <t t-name="popover-body" class="gap-3">
            <div class="alert alert-warning" role="status" invisible="not source_stale">...</div>
            <div class="d-flex gap-2" invisible="not worked_hours">
                <i class="oi oi-fw text-400" data-icon="schedule" aria-hidden="true" title="Worked Hours"/>
                <field name="worked_hours" widget="float_time"/>
            </div>
        </t>
    </templates>
</popover>
<!-- custom footer: replaces the default one (add replace="0" on the t to keep both) -->
<popover>
    <templates>
        <t t-name="popover-footer">
            <button class="btn btn-secondary" type="object" name="action_open_document" string="View"/>
        </t>
    </templates>
</popover>
```

Source: odoo/addons/base/rng/calendar_view.rng:45-64, addons/web/static/src/views/card/card_popover/card_popover.js:11-200, addons/web/static/src/views/calendar/calendar_common/calendar_common_popover.js:155-180, addons/hr_attendance/views/hr_attendance_view.xml:319-343, addons/mail/views/mail_activity_views.xml:440-455

## Graph

| Root attribute | Value |
|---|---|
| `type` | `bar` (default), `line`, `pie` |
| `stacked` | stack bars/lines |
| `order` | `asc` / `desc` |
| `cumulated`, `cumulated_start` | cumulative line chart |
| `disable_linking` | no click-through to the records |
| `sample`, `string`, `class`, `js_class` | generic |

Field children only: `type="measure"` (the **last** measure is the active one; default count),
otherwise a group-by (groupable types) with optional `interval="month"`; `invisible="1"` removes the
field from the Measures menu (numeric fields with an `aggregator` are offered automatically);
`string`, `widget`, `options` customise labels/formatting.

```xml
<graph string="Sales Analysis" type="line" sample="1">
    <field name="date" interval="month"/>
    <field name="product_uom_qty" type="measure"/>
</graph>
```

Source: odoo/addons/base/rng/graph_view.rng, addons/web/static/src/views/graph/graph_arch_parser.js, addons/web/static/src/views/graph/graph_view.js:36, addons/web/static/src/views/utils.js:81-106, odoo/addons/base/models/ir_ui_view.py:1952-1958, addons/sale/report/sale_report_views.xml:20-49

## Pivot

| Root attribute | Value |
|---|---|
| `disable_linking` | no click-through |
| `display_quantity` | show the Count measure |
| `default_order` | e.g. `amount desc` |
| `stacked`, `sample`, `string`, `class`, `js_class` | generic |

Field children: `type="row"` / `type="col"` (group-bys, `interval` for dates), `type="measure"` (or an
`operator` attribute), `invisible="1"` (hide from the Measures menu), `string`, `widget`, `options`.

```xml
<pivot string="Sales Analysis" sample="1">
    <field name="team_id" type="col"/>
    <field name="date" interval="month" type="row"/>
    <field name="product_uom_qty" type="measure"/>
</pivot>
```

Source: odoo/addons/base/rng/pivot_view.rng, addons/web/static/src/views/pivot/pivot_arch_parser.js:17-80, addons/sale/report/sale_report_views.xml:8-12

## Activity (mail)

Requires `mail` and a model inheriting `mail.activity.mixin` (the view filters on `activity_ids`).
RNG: `string` is **required**; optional
`create`, `js_class`; children `<field>` and one `<templates>` holding an `activity-box` template.

```xml
<activity string="Leads or Opportunities" js_class="crm_activity">
    <field name="user_id"/>
    <templates>
        <div t-name="activity-box">
            <field name="user_id" widget="many2one_avatar_user"/>
            <field name="name" display="full" class="o_text_block o_text_bold"/>
        </div>
    </templates>
</activity>
```

Source: odoo/addons/base/rng/activity_view.rng, addons/mail/static/src/views/web/activity/activity_arch_parser.js, addons/crm/views/crm_lead_views.xml:473-490

## Hierarchy (web_hierarchy)

Depend on `web_hierarchy`. Allowed root attributes (anything else raises): `class`, `js_class`, `string`,
`create`, `edit`, `delete`, `parent_field` (many2one to the same model, default `parent_id`),
`child_field` (one2many to the same model), `draggable`, `default_order`, `avatar_field`, `label`.
Children: `<field>` and at most one `<templates>` with a mandatory `hierarchy-box` template.

```xml
<hierarchy child_field="child_ids" js_class="hr_employee_hierarchy" avatar_field="image_128"
           label="people" draggable="1">
    <field name="name"/>
    <field name="job_title"/>
    <templates>
        <t t-name="hierarchy-box">
            <div class="d-flex flex-column text-center">
                <field class="fw-bold" name="name"/>
                <field name="job_title"/>
            </div>
        </t>
    </templates>
</hierarchy>
```

Source: addons/web_hierarchy/models/ir_ui_view.py:7-56, addons/web_hierarchy/static/src/hierarchy_arch_parser.js, addons/hr/views/hr_employee_views.xml:696-720

## QWeb views

`type="qweb"` views are server templates (reports, website, portal, mail bodies); they are not shown by the
web client view switcher. Declare them with `<template>` (shortcut for an `ir.ui.view` record):

| `<template>` attribute | Effect |
|---|---|
| `id` | xmlid; also the `t-name`/`key` (`module.id`) |
| `name` | view name |
| `inherit_id` | parent template (extension) |
| `primary="True"` | with `inherit_id`: a new template built from the parent (mode `primary`) |
| `priority` | application order among extensions |
| `active` | `True`/`False`; applied when the view is created, never changed by `-u` |
| `customize_show` | `True`/`False` (website "Customize" menu) |
| `groups` | `group_ids` of the view |
| `technical_usage` | selection extended by modules (`mail_post_source` in mail) |
| `key`, `track`, `website_id` | advanced |

A `qweb` view must have a `key` (`CHECK (type != 'qweb' OR key IS NOT NULL)`; `<template>` sets it).
Directives and rendering: [qweb-directives.md](../../qweb-reports/references/qweb-directives.md);
inheritance: [inheritance.md](inheritance.md).

Source: odoo/import_xml.rng:160-200, odoo/tools/convert.py:490-568, odoo/addons/base/models/ir_ui_view.py:570-573

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| calendar `date_delay="duration"` | `date_stop` field (XML008) | odoo/addons/base/rng/calendar_view.rng |
| no way to plan undated records from the calendar | `schedule="1"` | addons/web/static/src/views/calendar/calendar_arch_parser.js:41 |
| popover = flat list of calendar fields | `<popover>` with `popover-header/body/footer` templates or `card_id` | odoo/addons/base/rng/calendar_view.rng:49-62 |
| `fa fa-*` in popovers/templates | `<i class="oi" data-icon="..."/>` (XML004) | odoo/upgrade_code/19.5-00-material-symbols-icons.py |
| `t-esc` in activity/hierarchy/calendar templates | `t-out` | odoo/addons/base/models/ir_ui_view.py:2438-2456 |
