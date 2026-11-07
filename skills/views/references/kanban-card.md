# Kanban and card views (Odoo 20)

Odoo 20 kanban cards are rendered by the shared **card** machinery (`CardArchParser`, `CardCompiler`):
a kanban defines `<templates><t t-name="card">`, and the same card can live in a reusable `card`
view (`ir.ui.view` type `card`) referenced by `<kanban card_id>` and by calendar `<popover card_id>`.
Read this before writing any kanban, card or calendar popover arch.

## Contents
- Validation model
- `<kanban>` root attributes
- `<kanban>` children
- The card template (`card`, `menu`, layout tags)
- Record values and the rendering context
- Action links inside cards
- Reusable `card` views (`card_id`)
- Widgets in cards
- v19 habit -> Odoo 20

## Validation model

- Kanban and card archs have **no RNG**: they are checked by Python (`_validate_tag_*`, attribute
  checks) and by the JS parsers at load time.
- Allowed QWeb directives in kanban/card/calendar archs: `t-name`, `t-out`, `t-set`, `t-value`, `t-if`,
  `t-elif`, `t-else`, `t-foreach`, `t-as`, `t-key`, `t-att*`, `t-call`, `t-debug`. Anything else
  (`t-esc`, `t-raw`, `t-on-*`, `t-ref`, `t-component`...) raises "Forbidden owl directive used in arch".
- Use `t-out` only; `__comp__` in an expression is forbidden.
- Check with `odoo_validate(<module>)` (XML009 flags `kanban-box`, JS009 flags `kanban.*` widget keys).

Source: odoo/addons/base/models/ir_ui_view.py:2233-2234,2312-2321,2432-2456, addons/web/static/src/views/card/card_arch_parser.js

## `<kanban>` root attributes

| Attribute | Effect |
|---|---|
| `card_id="%(module.view_card)d"` | inline the `card` view (server-side, `_postprocess_tag_kanban`) |
| `default_group_by` | e.g. `stage_id`, `date_start:week` |
| `default_order` | e.g. `priority desc, sequence, id desc` (else the `handle` field) |
| `highlight_color` | integer field used as the card colour stripe (`color`) |
| `quick_create` | `0` disables the column quick create (default on when `create` is allowed) |
| `on_create` | `quick_create`, or an action xmlid run by the "New" button |
| `quick_create_view` | xmlid of the small form used by quick create |
| `create` `edit` `delete` `duplicate` | `0` disables |
| `archivable` `group_create` `group_edit` `group_delete` | `0` disables the group/column actions |
| `records_draggable` / `groups_draggable` | `0` disables drag and drop |
| `can_open` | `0`: clicking a card does not open it |
| `action` + `type` | what a card click runs instead of opening the form |
| `limit` / `count_limit` | records per column / count cap |
| `examples` | key of the `kanban_examples` registry (column setup examples) |
| `class`, `js_class`, `sample`, `dialog_size` | generic view attributes |

Source: addons/web/static/src/views/kanban/kanban_arch_parser.js:7-121, odoo/addons/base/models/ir_ui_view.py:1790-1794, addons/web/static/src/views/view.js:359-376, addons/web/static/src/views/kanban/kanban_controller.js:448-467

## `<kanban>` children

| Child | Purpose |
|---|---|
| `<field name="..."/>` (outside templates) | load a field you only use in expressions (`record.x.raw_value`) |
| `<progressbar field colors sum_field help/>` | column progress bar; `colors` is JSON `{"value": "success"}` |
| `<header><button .../></header>` | control-panel buttons |
| `<control>` | x2many kanban only: `<create string context invisible class>`, `<button>`, `<delete>` |
| `<templates>` | `<t t-name="card">`, optional `<t t-name="menu">`, helper templates for `t-call` |

Fields referenced only inside `t-if`/`t-att` expressions are **not** auto-added: declare them as
`<field>` (root or inside the template). Fields used in `invisible`/`readonly`/`required` are added
automatically.

```xml
<kanban highlight_color="color" default_group_by="stage_id" class="o_kanban_small_column"
        on_create="quick_create" quick_create_view="crm.quick_create_opportunity_form"
        archivable="false" sample="1" js_class="crm_kanban">
    <field name="stage_id" options='{"group_by_tooltip": {"requirements": "Description"}}'/>
    <field name="active"/>
    <progressbar field="activity_state"
                 colors='{"planned": "success", "today": "warning", "overdue": "danger"}'
                 sum_field="expected_revenue"/>
    <templates>...</templates>
</kanban>
```

Source: addons/crm/views/crm_lead_views.xml:503-514, addons/web/static/src/views/kanban/kanban_arch_parser.js:51-133, odoo/addons/base/models/ir_ui_view.py:1663-1670

## The card template

```xml
<templates>
    <t t-name="menu">
        <t t-if="widget.editable"><a role="menuitem" type="open" class="dropdown-item">Edit</a></t>
        <t t-if="widget.deletable"><a role="menuitem" type="delete" class="dropdown-item">Delete</a></t>
        <field name="color" widget="kanban_color_picker"/>
    </t>
    <t t-name="card">
        <widget name="web_ribbon" title="Lost" bg_color="text-bg-danger" invisible="won_status != 'lost'"/>
        <field name="name" class="fw-bold fs-5"/>
        <field name="tag_ids" widget="many2many_tags" options="{'color_field': 'color'}"/>
        <footer class="pt-1">
            <div class="d-flex align-items-center">
                <field name="priority" widget="priority" class="me-2"/>
                <field name="activity_ids" widget="kanban_activity"/>
            </div>
            <field name="user_id" widget="many2one_avatar_user" class="ms-auto"/>
        </footer>
    </t>
</templates>
```
- `t-name="card"` is mandatory ("Missing 'card' template" otherwise); its `class` attribute is put on
  the card root (`class="flex-row"` for an image-left layout).
- `t-name="menu"` adds the card dropdown.
- Layout tags styled by `card.scss`: `<main>` (compiled to `div.o_record_main`), `<aside>` (image column,
  `class="o_card_aside_full"` to fill the height), `<footer>` (pushed to the bottom, flex row).
- `<field>` without `widget` renders as a plain `<span>` with the formatted value; with a widget it is
  a real field component (and is forced readonly while the record is open in a dialog).
- `invisible="..."` on fields/divs works in cards (python expression on the record).

Source: addons/crm/views/crm_lead_views.xml:515-550, addons/web/static/src/views/card/card_compiler.js:24-138, addons/web/static/src/views/card/card.scss:55-110, addons/web/static/src/views/card/card_renderer.js:134-137, addons/hr/views/hr_employee_public_views.xml:176-200

## Record values and the rendering context

| Name | Content |
|---|---|
| `record.<f>.value` | formatted string (formatter of the field type) |
| `record.<f>.raw_value` | many2one: id or `false`; x2many: list of ids; date/datetime: ISO string; else the raw value |
| `record.id.raw_value` | the record id |
| `widget.editable` / `widget.deletable` | view rights (`edit`/`delete`) and not readonly |
| `context`, `luxon`, `JSON`, `selection_mode` | helpers |

```xml
<span t-if="record.owner_user_id.raw_value">Requested by: <field name="owner_user_id"/></span>
<main t-att-class="['done', 'cancelled'].includes(record.state.raw_value) ? 'opacity-50' : ''">
<div t-attf-class="o_hierarchy_node_color_{{ record.department_color.raw_value }}"/>
```
`t-if`/`t-att*`/`t-out` expressions are OWL (JavaScript) expressions: `!x`, `.includes()`, ternaries,
and the words `and`, `or`, `gt`, `gte`, `lt`, `lte`; Python-only syntax (`not x`, `x in [...]`) does not
work there. `invisible`/`readonly`/`required` attributes stay **Python** expressions on the record
(`invisible="not partner_id"`).

Source: addons/web/static/src/views/card/card_renderer.js:24-75,128-160, addons/web/static/src/views/kanban/kanban_record.js:91-96, addons/web/static/lib/owl/owl.js:5071-5078, addons/maintenance/views/maintenance_views.xml:150-155, addons/crm/views/crm_lead_views.xml:536-541

## Action links inside cards

`<a>` or `<button>` with `type=`:

| `type` | Effect |
|---|---|
| `open` | open the record (form) |
| `delete` | delete (with confirmation) |
| `archive` / `unarchive` | toggle `active` |
| `set_cover` | pick a cover image; `data-field="displayed_image_id"`, `auto-open` |
| `url` | follow `href` |
| `object` / `action` | call a method / run an action with `name=`; debounced 300 ms in cards |

```xml
<a t-if="record.active.raw_value" role="menuitem" type="archive" class="dropdown-item">Archive</a>
<button name="action_open_document" type="object" class="btn btn-secondary" string="View"/>
```

Source: addons/web/static/src/views/card/card_compiler.js:11-80, addons/hr/views/hr_department_views.xml:108

## Reusable `card` views (`card_id`)

A `card` view is an `ir.ui.view` whose arch root is `<card>`; it is **not** a view mode (never in
`view_mode`). Consumers:

- `<kanban card_id="%(module.xmlid)d">`: the card arch is appended to the kanban arch by
  `get_views`, so the kanban itself can be reduced to its root attributes and `<progressbar>`.
- calendar `<popover card_id="%(module.xmlid)d">`: when the popover defines no `popover-body`, the
  card's `card` template becomes the popover body (see [other-views.md](other-views.md)).

```xml
<record id="hr_equipment_request_view_card" model="ir.ui.view">
    <field name="name">equipment.request.card</field>
    <field name="model">maintenance.request</field>
    <field name="arch" type="xml">
        <card>
            <templates>
                <t t-name="menu">...</t>
                <t t-name="card">
                    <main>
                        <field name="name" class="fw-bold fs-5"/>
                        <field name="schedule_date"/>
                        <footer>
                            <field name="priority" widget="priority"/>
                            <field name="user_ids" widget="many2many_avatar_user" class="ms-auto"/>
                        </footer>
                    </main>
                </t>
            </templates>
        </card>
    </field>
</record>

<record id="hr_equipment_request_view_kanban" model="ir.ui.view">
    <field name="name">equipment.request.kanban</field>
    <field name="model">maintenance.request</field>
    <field name="arch" type="xml">
        <kanban card_id="%(hr_equipment_request_view_card)d" highlight_color="color"
                default_group_by="stage_id" sample="1">
            <progressbar field="state" colors='{"done": "success", "cancelled": "danger"}'/>
        </kanban>
    </field>
</record>
```
- Variants: inherit the card with `mode=primary` (`project.view_task_card_subtask_mobile`).
- The card is post-processed as a nested sub-view, so fields auto-added for modifiers land inside `<card>`.
- Inspect what the client receives with `odoo_views("maintenance.hr_equipment_request_view_kanban",
  resolve="db")`.

Source: odoo/addons/base/models/ir_ui_view.py:157-165,1757-1767,1790-1794, addons/maintenance/views/maintenance_views.xml:139-181, addons/project/views/project_task_views.xml:677-800, addons/web/static/src/views/card/card_popover/card_popover.js:125-160

## Widgets in cards

- Field widgets are looked up as `card.<widget>` first, then `<widget>`: e.g. `card.many2many_tags`,
  `card.many2one_avatar`, `card.many2many_avatar_user` (mail), `card.properties`.
- A many2many field **without** `widget` is rendered as `many2many_tags` in cards.
- Common card widgets: `priority`, `kanban_activity` (mail), `many2one_avatar_user` (mail),
  `many2many_avatar_user` (mail), `kanban_color_picker` (in `menu`), `image` (`background_image` is hr's),
  `handle` (sets default order), `boolean_favorite`, `label_selection`. Full list: [widgets.md](widgets.md).

Source: addons/web/static/src/views/fields/field.js:115-136, addons/web/static/src/views/card/card_arch_parser.js:22-27, addons/mail/static/src/views/web/fields

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `<t t-name="kanban-box">` | `<t t-name="card">` (+ `menu`) (XML009) | addons/web/static/src/views/card/card_arch_parser.js:6 |
| widget keys `kanban.many2many_tags`, `kanban.many2one_avatar`, `kanban.progressbar`... | `card.*` keys (JS009) | addons/web/static/src/views/fields/many2many_tags/many2many_tags_field.js |
| same card copy-pasted in several kanbans | one `card` view + `card_id` | odoo/addons/base/models/ir_ui_view.py:1790 |
| calendar popover = only `<field>` children | `<popover>` with templates or `card_id` | odoo/addons/base/rng/calendar_view.rng:45-64 |
| `t-esc` in kanban templates | `t-out` (others are rejected) | odoo/addons/base/models/ir_ui_view.py:2438 |
| `fa fa-*` icons in cards | `<i class="oi" data-icon="..."/>` (XML004) | odoo/upgrade_code/19.5-00-material-symbols-icons.py |
