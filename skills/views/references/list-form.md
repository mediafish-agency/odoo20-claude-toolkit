# List and form views (Odoo 20)

How to write `<list>` and `<form>` archs that pass Odoo 20 validation: root attributes, children,
field attributes, modifiers, x2many sub-views, buttons, button box, ribbons and chatter.
Read this before writing or reviewing any list/form arch. Naming and record conventions live in
[XML guidelines](../../odoo-guidelines/guidelines/xml.md#views-actions-and-data-records).

## Contents
- Validation model
- `<list>` root attributes
- `<list>` children (incl. `<column>`)
- Field attributes (list and form)
- Modifiers and the evaluation context
- `<form>` structure
- x2many fields and inline sub-views
- Buttons
- Button box, stat buttons, ribbons, chatter
- v19 habit -> Odoo 20

## Validation model

| View | Checked by | Consequence |
|---|---|---|
| top-level `<list>` | RNG `list_view.rng` + Python `_validate_tag_list` | unknown attribute or child = install error |
| `<list>` inline in a form x2many | Python only (`editable` must be `top`/`bottom`; children limited to `field, button, control, groupby, widget, header, column`) | RNG-only attributes are tolerated |
| `<form>` | Python `_validate_tag_*` only (no RNG) | `<page>` must be a direct child of `<notebook>`; `<label>` needs `for` |
| any view | `attrs=` / `states=` anywhere | hard `ValidationError` ("Since 17.0 ...") |
| kanban/card/calendar | only `t-name t-out t-set t-value t-if t-elif t-else t-foreach t-as t-key t-att* t-call t-debug` | other `t-*` = "Forbidden owl directive" |
| list/form | only `t-translation` | any other `t-*` is rejected |

Fields used in `invisible`/`readonly`/`required`/`column_invisible`/`decoration-*`/`context`/`domain`
are added automatically as invisible **readonly** fields. Declare them yourself (`column_invisible="True"`
in lists, `invisible="1"` in forms) when the value must be sent back on save or onchange.
Validate with `odoo_validate(<module>)` (rules XML001, XML002, XML010) and inspect the merged arch with
`odoo_views(xmlid, resolve="db")`.

Source: odoo/tools/view_validation.py:314, odoo/addons/base/models/ir_ui_view.py:508,1563,1929,2180,2432

## `<list>` root attributes

| Attribute | Value | Effect |
|---|---|---|
| `editable` | `top` / `bottom` | inline edition, new rows at top/bottom |
| `multi_edit` | `1` | edit a column for all selected records |
| `open_form_view` | `True` | with `editable`: extra button to open the record form |
| `create` `edit` `delete` `duplicate` `import` `export_xlsx` | `0`/`false` | disable the action |
| `group_create` `group_edit` `group_delete` | `0` | disable group actions when grouped |
| `default_order` | `"date desc, id"` | default sort (else the `handle` field, else `_order`) |
| `default_group_by` | `"stage_id"` or `"a,b"` | grouped on open |
| `expand` | python expr | expand groups by default (`account.move.line`: `expand="context.get('expand', False)"`) |
| `limit` / `count_limit` / `groups_limit` | int | page size, count cap, groups per page |
| `decoration-{bf,it,danger,info,muted,primary,success,warning}` | python expr | row style |
| `sample` | `1` | sample data when empty |
| `js_class` | registry key | custom JS view |
| `class` | css | root class |
| `dialog_size` | `sm md lg xl fs fullscreen` | size of the dialog when this list opens in one (search more) |
| `action` + `type` | name + `object`/`action` | what a row click runs (`mail.discuss_channel` list) |
| `string` | - | RNG comment: "deprecated, has no effect anymore" |

`no_open` is read by the JS parser but is **not in the RNG**: use it only on inline lists
(`account_payment_term_views.xml:67`).

Source: odoo/addons/base/rng/list_view.rng:23-87, addons/web/static/src/views/list/list_arch_parser.js:240-280, addons/web/static/src/views/view.js:376, addons/web/static/src/core/dialog/dialog.js:46

## `<list>` children

| Child | Purpose |
|---|---|
| `<field>` | a column (see field attributes) |
| `<column name string width column_invisible>` | **new**: one header over several stacked `<field>`s (only `field` children) |
| `<button>` | row button; consecutive buttons share one column unless `width` is set |
| `<widget name="...">` | view widget column (`width`, `invisible`, `column_invisible`, `options`) |
| `<header><button/></header>` | buttons acting on the selection; `display="always"` shows it with no selection |
| `<groupby name="m2o_field">` | buttons/fields on group rows; field must be many2one; `type="edit"` opens the group record |
| `<control>` (x2many only) | replaces the "Add a line" link: `<create string name context invisible data-hotkey>`, `<button>`, `<delete invisible>` (`delete` is JS-only, not in RNG) |

```xml
<list editable="bottom" decoration-warning="is_late">
    <control>
        <create string="Add Line" name="add_product_control"/>
        <create string="Add Section" name="add_section_control"
                context="{'default_display_type': 'line_section'}"/>
    </control>
    <field name="sequence" widget="handle"/>
    <column name="product_and_description" string="Description">
        <field name="product_id"/>
        <field name="name" widget="text"/>
    </column>
    <field name="qty_delivered" column_invisible="parent.state != 'sale'" optional="show"/>
    <field name="price_subtotal" sum="Total"/>
</list>
```
`<column>`: RNG allows `name`, `string`, `column_invisible`, `width`; label defaults to the first field's
label; `optional` belongs on the inner fields. Inheriting modules anchor on `column[@name=...]`
(`purchase_product_matrix/views/purchase_views.xml:26`).

Source: odoo/addons/base/rng/list_view.rng:88-111, addons/web/static/src/views/list/list_arch_parser.js:150-235, addons/sale/views/sale_order_views.xml:649-800, addons/account/views/account_move_views.xml:204-211, addons/web/static/src/views/list/list_controller.xml:11

## Field attributes

| Attribute | Where | Notes |
|---|---|---|
| `string`, `help`, `placeholder`, `nolabel`, `class` | all | `nolabel="1"` hides list header / form label |
| `widget`, `options="{...}"` | all | see [widgets.md](widgets.md); options is a python dict literal |
| `invisible` / `readonly` / `required` | all | python expressions (next section) |
| `column_invisible` | list | hides the whole column; evaluated once per list (only `parent.*`, `context`) |
| `optional` | list | `show` / `hide`: user-toggleable column |
| `sum` / `avg` | list | label of the aggregate in the footer (RNG has no `min`/`max`) |
| `width` | list | e.g. `80px` |
| `decoration-*` | list/field | per-cell style |
| `context` / `domain` | relational | `domain` on non-relational = error; identifiers validated |
| `force_save` | all | `1`: send a readonly field value on save |
| `filename` | binary | name of the char field holding the file name |
| `groups` | all | `module.group`, `!module.group`, comma = OR |
| `mode` | x2many | `list`, `kanban`, `list,kanban` |
| `default_focus` | form | `1` = autofocus |

Source: odoo/addons/base/rng/common.rng:196-300, addons/web/static/src/views/fields/field.js:222-290, addons/web/static/src/views/list/list_renderer.js:861,1506-1525

## Modifiers and the evaluation context

`invisible`, `readonly`, `required`, `column_invisible` and `decoration-*` are **python expressions**
evaluated client-side. Names available: every field of the record (declared or auto-added), `id`,
`context`, `uid`, `allowed_company_ids`, `current_company_id`, `parent` (the parent record inside an
x2many sub-view), plus builtins such as `context_today()`.

```xml
<field name="partner_id" readonly="state in ['cancel', 'sale']"/>
<field name="qty_delivered" invisible="display_type" readonly="qty_delivered_method != 'manual'"/>
<button name="action_cancel" type="object" invisible="state not in ['draft', 'sent'] or not id"/>
<field name="customer_lead" readonly="parent.state not in ['draft', 'sent', 'sale']"/>
```
Field-level `readonly=True`/`required=True` on the Python field are applied when the attribute is absent.

Source: addons/web/static/src/model/relational_model/utils.js:355-363, addons/web/static/src/model/relational_model/static_list.js:124-128, addons/web/static/src/views/fields/field.js:246-255, odoo/addons/base/models/ir_ui_view.py:34

## `<form>` structure

```xml
<form string="Sales Order" js_class="sale_order_form">
    <header>
        <button name="action_confirm" type="object" string="Confirm" class="btn-primary"
                invisible="state != 'draft'" data-hotkey="q"/>
        <field name="state" widget="statusbar" statusbar_visible="draft,sent,sale"/>
    </header>
    <sheet>
        <div class="oe_button_box" name="button_box">...</div>
        <widget name="web_ribbon" title="Archived" bg_color="text-bg-danger" invisible="active"/>
        <div class="oe_title"><h1><field name="name" readonly="1"/></h1></div>
        <group name="main">
            <group name="left"><field name="partner_id"/></group>
            <group name="right"><field name="date_order"/></group>
        </group>
        <notebook>
            <page string="Order Lines" name="order_lines">...</page>
            <page string="Other Info" name="other_information">...</page>
        </notebook>
    </sheet>
    <chatter/>
</form>
```
- Root attributes read in v20: `create`, `edit`, `delete`, `duplicate`, `js_class`, `class`,
  `disable_autofocus`, `dialog_size`. `string` is replaced by `view_header_get()` when the model defines it.
- Compiled tags: `header`, `sheet`, `group` (`col`, `colspan`, `string`), `notebook`/`page`
  (`string`, `name`, `invisible`), `label for=`, `separator`, `footer` (dialog buttons), `setting`,
  `div[name='button_box']`, `chatter` (mail), `widget`.
- Give every `group`/`page`/`div` you expect others to extend a `name`.
- Wizard dialogs: `<footer>` with `<button special="cancel"/>`; `special` must be `cancel`, `save` or `add`.

Source: addons/sale/views/sale_order_views.xml:264-470, addons/web/static/src/views/form/form_compiler.js:51-63, addons/web/static/src/views/form/form_arch_parser.js:8-11, odoo/addons/base/models/ir_ui_view.py:1740,2081-2090

## x2many fields and inline sub-views

```xml
<field name="order_line" mode="list,kanban" readonly="state == 'cancel'"
       context="{'default_order_id': id, 'list_view_ref': 'my_module.view_line_list'}">
    <list editable="bottom">
        <field name="product_id" context="{'partner_id': parent.partner_id}"/>
        <field name="product_uom_qty"/>
    </list>
    <form>
        <group><field name="product_id"/></group>
    </form>
</field>
```
- Sub-views are parsed on the comodel; `parent.<field>` reaches the form record.
- For a visible x2many without `widget` and without inline sub-views, the server embeds the comodel's
  default list (kanban on mobile, or the first type of `mode`); pick another view with
  `<view_type>_view_ref` keys in the field `context`.
- CRUD toggles are field attributes (python expressions) read by the x2many widget:
  `create`, `delete`, `link`, `unlink`, `write` (not in the RNG: fine in forms, which are not
  RNG-validated), plus `add-label` for the "Add a line" text.
- A field may appear several times (each occurrence gets its own `field_id`); when inheriting, the
  shorthand `<field name="x" position=...>` hits the **first** `x` at any depth, sub-views included,
  so use `xpath` to target a sub-view field ([inheritance.md](inheritance.md)).

Source: addons/web/static/src/views/fields/field.js:291-330, odoo/addons/base/models/ir_ui_view.py:1640-1665,1119-1131, addons/web/static/src/views/fields/x2many/x2many_field.js:332-345

## Buttons

| Attribute | Notes |
|---|---|
| `type="object"` + `name` | public model method; validated: must exist, not `_private`, not `@api.private`; a method needing arguments logs a warning |
| `type="action"` + `name` | `%(module.action_xmlid)d` or the xmlid string (`name="sale.action_report_saleorder"`); must exist |
| `special` | `cancel`, `save`, `add` |
| `string`, `class` (`btn-primary`, `btn-secondary`, `oe_highlight`, `oe_stat_button`), `title`, `aria-label` | |
| `icon` + `icon_class` | Material Symbols name, e.g. `icon="edit" icon_class="oi-filled"` ([buttons-icons.md](buttons-icons.md)) |
| `confirm`, `confirm-title`, `confirm-label`, `cancel-label` | confirmation dialog texts |
| `context` | merged into the call context |
| `args` | extra JSON positional args for `type="object"` |
| `close` | `1`: close the dialog after the call |
| `block-ui`, `debounce`, `effect`, `data-hotkey` | UI behaviour |
| `invisible`, `column_invisible`, `readonly`, `groups`, `display`, `width` | |

```xml
<button name="action_cancel" type="object" string="Cancel"
        confirm-title="Cancel Order"
        confirm="Cancelling this order will set its status to 'Cancelled'. Are you sure?"
        confirm-label="Yes, cancel order" cancel-label="No, go back"
        invisible="state not in ['draft', 'sent', 'sale'] or not id"/>
```
Python side: a button method may return an action dict (see [actions-menus.md](actions-menus.md));
returning `None` closes a dialog (`ir.actions.act_window_close`).

Source: odoo/addons/base/rng/common.rng:313-360, addons/web/static/src/views/utils.js:22-42,218-252, odoo/addons/base/models/ir_ui_view.py:2081-2122, addons/web/static/src/webclient/actions/action_plugin.js:1597-1650, addons/sale/views/sale_order_views.xml:365-375

## Button box, stat buttons, ribbons, chatter

```xml
<div class="oe_button_box" name="button_box">
    <button name="action_view_invoice" type="object" class="oe_stat_button"
            icon="edit_square" invisible="invoice_count == 0">
        <field name="invoice_count" widget="statinfo" string="Invoices"/>
    </button>
    <button name="action_lost_leads" type="object" class="oe_stat_button"
            icon="star" icon_class="oi-filled">
        <div class="o_stat_info">
            <field name="leads_count" class="o_stat_value"/>
            <span class="o_stat_text">Leads</span>
        </div>
    </button>
</div>
<widget name="web_ribbon" title="Archived" bg_color="text-bg-danger" invisible="active"/>
<chatter reload_on_post="True"/>
```
- The form compiler matches `div[name='button_box']`; extend it by name.
- `web_ribbon` attributes: `title` (text), `bg_color` (class, default `text-bg-success`), `tooltip`.
- `<chatter/>` (mail) attributes: `reload_on_post`, `reload_on_follower`, `reload_on_attachment`,
  `reload_on_activity`, `open_attachments`. Put it last in the form, on models inheriting `mail.thread`
  (core forms with `<chatter/>`: `sale.order`, `crm.lead`, `project.task`).

Source: addons/sale/views/sale_order_views.xml:430-447, addons/crm/views/crm_lost_reason_views.xml:21-30, addons/web/static/src/views/widgets/ribbon/ribbon.js:40-67, addons/mail/static/src/chatter/web/form_compiler.js:7-47, addons/crm/views/crm_lead_views.xml:300

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `<tree>` / `view_mode="tree"` | `<list>` / `list` (XML001) | odoo/addons/base/rng/list_view.rng |
| `attrs="{'invisible': [...]}"`, `states=` | python expressions (XML002) | odoo/addons/base/models/ir_ui_view.py:508 |
| several list columns for one concept | `<column name string>` grouping fields | odoo/addons/base/rng/list_view.rng:90 |
| no size control for x2many/search dialogs | `dialog_size` on `<list>`/`<form>` | addons/web/static/src/views/fields/relational_utils.js:790 |
| `<button icon="fa-star">` | `icon="star" icon_class="oi-filled"` (XML005) | odoo/addons/base/rng/common.rng:323 |
| confirm dialog without title | `confirm-title` | odoo/addons/base/rng/common.rng:333 |
| `<widget>` without modifiers | `<widget invisible column_invisible>` | odoo/addons/base/rng/common.rng:432 |
| `<div class="oe_chatter">` | `<chatter/>` (XML010) | addons/mail/static/src/chatter/web/form_compiler.js |
| `name="toggle_active"` button | `action_archive` / `action_unarchive` (ORM005) | odoo/orm/models.py |
