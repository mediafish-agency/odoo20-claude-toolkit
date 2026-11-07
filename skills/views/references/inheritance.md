# View and template inheritance (Odoo 20)

How Odoo 20 combines views: `inherit_id`, `mode` (extension vs primary), `priority`, spec nodes
(`xpath`, shorthand), positions (`inside`, `after`, `before`, `replace`, `attributes`, `move`),
`<attribute add/remove separator>`, x2many sub-views, `groups`, QWeb `<template inherit_id>`, and
how to check the result. The house rule (anchor on names, never on position) is in
[XML guidelines](../../odoo-guidelines/guidelines/xml.md#anchor-view-inheritance-on-names-never-on-position);
this file covers the mechanics.

## Contents
- Records: `inherit_id`, `mode`, `priority`
- Locating the target node
- Positions
- `position="attributes"`
- Moving nodes
- Inheriting x2many sub-views and other view types
- `groups` and inherited views
- QWeb template inheritance
- Checking the result
- Pitfalls

## Records: `inherit_id`, `mode`, `priority`

```xml
<record id="view_order_form_inherit_my_module" model="ir.ui.view">
    <field name="name">sale.order.form.inherit.my_module</field>
    <field name="model">sale.order</field>
    <field name="inherit_id" ref="sale.view_order_form"/>
    <field name="arch" type="xml">
        <field name="partner_id" position="after">
            <field name="x_delivery_instructions"/>
        </field>
        <xpath expr="//page[@name='other_information']//field[@name='user_id']" position="attributes">
            <attribute name="readonly">state == 'sale'</attribute>
        </xpath>
    </field>
</record>
```
| `mode` | Meaning |
|---|---|
| `extension` (default when `inherit_id` is set) | patches the parent everywhere the parent is used |
| `primary` (default without `inherit_id`) | a new view = resolved parent + this view's specs; used only when selected (`view_id`, action `views`, `*_view_ref`); extensions of the parent still apply |

- Several root specs are allowed in `arch` (they are wrapped in `<data>` automatically).
- `priority` (default 16): extensions are applied in `priority, id` order; the default view of a
  model/type is the **primary** view with the lowest priority. Give alternative primary views a high
  priority so they do not become the default (`sale.sale_order_tree` uses `1000`).
- Constraint: `mode='extension'` requires `inherit_id`; inheritance cycles are rejected.

Source: odoo/addons/base/models/ir_ui_view.py:149-197,552-582,700-800, odoo/tools/convert.py:64-80, addons/sale/views/sale_order_views.xml:113-200

## Locating the target node

| Spec | Matches |
|---|---|
| `<xpath expr="..."/>` | first node returned by the XPath (lxml ETXPath) |
| `<field name="x"/>` | first `field` named `x`, in document order, at **any depth** (also inside x2many sub-views) |
| any other tag, e.g. `<page name="other_information"/>`, `<filter name="my_quotation"/>`, `<div name="button_box"/>` | first node with that tag whose attributes equal **all** the spec's attributes (`position` excepted) |

- Translated attributes cannot be selectors (raises "View inheritance may not use attribute ..."):
  `string`, `help`, `sum`, `avg`, `confirm`, `placeholder`, `title`, `alt`, `aria-label`, `label`,
  `confirm-title`, `confirm-label`, `cancel-label`, `add-label`, `data-tooltip`, `value_label` ...
- Classes: use the `hasclass()` XPath function, `//div[hasclass('oe_title')]`; `@class` comparisons
  log a warning.
- A spec that matches nothing raises "Element ... cannot be located in parent view" at install.

Source: odoo/tools/template_inheritance.py:71-107,320-345, odoo/addons/base/models/ir_ui_view.py:85-90,137-145,420-440, odoo/tools/translate.py:85-91

## Positions

| `position` | Effect |
|---|---|
| `inside` (default) | append children at the end of the target |
| `after` / `before` | insert as next / previous siblings |
| `replace` | replace the target (default `mode="outer"`); an element of the spec whose text is exactly `$0` gets a copy of the original node appended as its last child; `mode="inner"` replaces only the children |
| `attributes` | edit attributes with `<attribute>` children |
| `move` | on a node **inside** another spec: move an existing node there (see below) |

```xml
<!-- wrap the original node -->
<xpath expr="//field[@name='date_order']" position="replace">
    <div class="d-flex" name="date_order_wrapper">$0</div>
</xpath>
<!-- replace content only -->
<xpath expr="//button[hasclass('o_form_button_save')]" position="replace" mode="inner">
    <span>Save</span>
</xpath>
```

Source: odoo/tools/template_inheritance.py:152-343, addons/mail/static/src/views/web/view_dialog/avatar_user_form_view_dialog.xml:4

## `position="attributes"`

```xml
<xpath expr="//field[@name='partner_id']" position="attributes">
    <attribute name="readonly">state != 'draft'</attribute>     <!-- set / replace -->
    <attribute name="widget"></attribute>                       <!-- empty text removes it -->
    <attribute name="invisible" add="res_model == 'hr.leave'" separator="or"/>
    <attribute name="class" add="btn-group" remove="gap-1" separator=" "/>
    <attribute name="context">{'default_type': 'invoice', 'show_address': False}</attribute>  <!-- dicts: rewrite whole -->
</xpath>
```
- Allowed `<attribute>` keys: `name`, `add`, `remove`, `separator` (plus `data-oe-*`); `add`/`remove`
  cannot be combined with text.
- On python-expression attributes (`invisible`, `readonly`, `required`, `column_invisible`, `t-if`,
  `t-elif`, `decoration-*`) `separator` must be `and` or `or` (surrounding spaces allowed): `add` becomes
  `(old) or (new)`, `remove` strips that operand.
- On other attributes the value is treated as a list: default separator `,` (e.g. `groups`),
  `separator=" "` for space-separated values such as `class`. Do not use `add` on `context`/`options`
  dicts (the item would land after the closing brace): rewrite the whole value.

Source: odoo/tools/template_inheritance.py:20,235-310, addons/calendar/views/mail_activity_views.xml:22-31, addons/hr_holidays/views/calendar_views.xml:8-13, addons/account/static/src/components/account_document_tax_mode_selector/account_document_tax_mode_selector.xml:5

## Moving nodes

```xml
<xpath expr="//field[@name='date_to']" position="replace">
    <field name="company_id" column_invisible="True"/>
    <xpath expr="//field[@name='calendar_id']" position="move"/>
</xpath>
```
The inner spec (`xpath` or shorthand) must have **no children**; the located node is removed from its
place and inserted where the inner spec stands (works inside `inside`, `after`, `before`, `replace`).

Source: odoo/tools/template_inheritance.py:23-50,130-149, addons/hr_holidays/views/resource_views.xml:60-63, addons/hr/views/mail_activity_plan_views.xml:32-34

## Inheriting x2many sub-views and other view types

```xml
<!-- a column in the order lines list, not the form's partner field -->
<xpath expr="//field[@name='order_line']/list/field[@name='price_unit']" position="after">
    <field name="x_margin" optional="hide"/>
</xpath>
<!-- a <column> group in a list -->
<column name="product_and_description" position="after">...</column>
<!-- a search filter by name -->
<filter name="my_sale_orders_filter" position="after">
    <filter name="to_upsell" string="To Upsell" domain="[('invoice_status', '=', 'upselling')]"/>
</filter>
<!-- root attributes of any view -->
<list position="attributes"><attribute name="js_class">sale_dashboard_list</attribute></list>
```
- The shorthand `<field name="price_unit">` would hit the first `price_unit` anywhere, which may be a
  sub-view: prefer full xpaths for sub-views.
- Kanban cards: target nodes inside the template, e.g. `//t[@t-name='card']//field[@name='name']`;
  when the kanban uses `card_id`, inherit the **card** view instead.

Source: addons/sale/views/sale_order_views.xml:1143-1200, addons/purchase_product_matrix/views/purchase_views.xml:26, addons/project/views/project_task_views.xml:795-805

## `groups` and inherited views

- An **extension** view cannot have `group_ids` on its record ("Inherited view cannot have 'groups'
  defined on the record"): put `groups="module.group"` on the nodes you add.
- A **primary** view may carry `group_ids`, but backend view combination does not filter on them
  (`_get_inheriting_views_domain` only checks `active`; `group_ids` is enforced by `_check_view_access`
  for public asset rendering). Restrict content with `groups=` on nodes, or set `active` and enable the
  view from Python.
- `groups` values: comma = OR, `!` = not; each group xmlid must exist (validated). Nodes the user may
  not see are removed server-side when the view is loaded.

Source: odoo/addons/base/models/ir_ui_view.py:552-558,724-731,819-832,1895-1903,1355-1368,2622-2625

## QWeb template inheritance

```xml
<template id="delivery_report_saleorder_document" inherit_id="sale.report_saleorder_document">
    <span name="order_note" position="before">
        <p t-if="doc.carrier_id.carrier_description" id="carrier_description">
            <span t-out="doc.carrier_id.carrier_description"/>
        </p>
    </span>
</template>

<!-- a new template derived from another one -->
<template id="report_saleorder_document_brazil" inherit_id="sale.report_saleorder_document" primary="True">
    <t t-set="hide_taxes_details" position="attributes">
        <attribute name="t-value">True</attribute>
    </t>
    <xpath expr="//t[@t-call='sale.document_tax_totals']" position="replace">
        <t t-call="l10n_br_sales.document_tax_totals_brazil" tax_totals="doc.tax_totals" currency="doc.currency_id"/>
    </xpath>
</template>
```
- Same positions and `<attribute>` rules as views; anchor on `name`, `id`, `t-call`, `t-set` values.
- `primary="True"` gives a separate template whose `t-name` is its own xmlid.
- `active="False"` creates an optional extension (enable it later); `-u` never changes `active`.
- Add attributes to an existing `t-call` (new t-call parameters) with `position="attributes"`.

Source: addons/delivery/report/ir_actions_report_templates.xml:4-11, addons/l10n_br_sales/report/sale_order_templates.xml:13-21, odoo/tools/convert.py:490-568

## Checking the result

- `odoo_views(xmlid="sale.view_order_form")`: inheritance tree (priority, mode, groups, specs, file:line)
  from the source index.
- `odoo_views(xmlid=..., resolve="db")`: the exact combined arch Odoo computes in an allowlisted database
  where your module is installed.
- `odoo_validate(<module>)`: RNG on combined list/search/calendar/graph/pivot views, legacy patterns,
  fields that do not exist on the model.
- `odoo_test(<module>)`: installing the module raises on unlocatable specs.

Source: odoo20 MCP server tool descriptions (mcp/odoo20_mcp/server.py)

## Pitfalls

| Symptom | Cause / fix |
|---|---|
| "Element ... cannot be located in parent view" | target renamed/moved in v20 or matched by translated text; anchor on `name` |
| change lands in the wrong place | shorthand `<field>` matched a sub-view field; use a full xpath |
| onchange value not saved | the field is only referenced in modifiers, so Odoo auto-added it readonly; declare it (`invisible="1"` / `column_invisible="True"`) or use `force_save="1"` on a readonly field |
| your extension applied before another module's | add that module to `depends` (id order) or raise `priority` |
| new default view chosen unexpectedly | your primary view has a lower `priority` than the original |
| `attrs`/`states` in an inherited spec | rejected on the combined arch (XML002) |
