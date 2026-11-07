# Server QWeb directives (Odoo 20)

The Python QWeb engine (`ir.qweb`) renders reports, website/portal pages, mail bodies and `<template>`
records. This file lists every directive it compiles in Odoo 20, the new `t-call` parameter syntax and
scoping, the `t-options` widgets (`ir.qweb.field.*`) and output safety. OWL templates in `static/` are a
different engine (see the owl skill). Escaping rules and `Markup` usage:
[security guidelines](../../odoo-security/SKILL.md#prevent-xss-escape-on-the-way-into-the-dom).

## Contents
- Directive list and evaluation order
- Output: `t-out`, `t-field`
- Conditions and loops
- Variables: `t-set`
- Attributes: `t-att`, `t-att-*`, `t-attf-*`
- `t-call`: parameters, body and scoping
- `t-lang`, `t-options`, `groups`, misc directives
- `t-options` widgets (`ir.qweb.field.*`)
- Values available in every template
- Rendering from Python
- v19 habit -> Odoo 20

## Directive list and evaluation order

Compiled directives, in the order applied on one element: `t-elif`, `t-else`, `t-debug`, `t-log`,
`t-groups`/`groups`, `t-foreach` + `t-as`, `t-if`, `t-call-assets`, `t-lang`, `t-options`/`t-options-*`,
`t-call`, `t-att*`, `t-field`, `t-out`, `t-set`. So `<li t-foreach="lines" t-as="l" t-if="l.qty">` loops
first, then tests. Any other `t-*` attribute (`t-esc`, `t-raw`, `t-call-options`...) only logs
"Unknown directives or unused attributes": the element still renders but the value is **not** output.
There is no dynamic-tag directive (`t-tag` is OWL only). `t-translation="off"` disables translation
of a node.

Source: odoo/addons/base/models/ir_qweb.py:118-345,487,1719-1758,1890-1930

## Output: `t-out`, `t-field`

```xml
<span t-out="doc.name"/>                                  <!-- escaped text -->
<t t-out="doc.note">No note</t>                           <!-- body = default when falsy -->
<span t-field="doc.date_order" t-options='{"widget": "date"}'/>
<div t-field="doc.partner_id" t-options='{"widget": "contact", "fields": ["address", "name"], "no_marker": True}'/>
<span t-out="amount" t-options="{'widget': 'monetary', 'display_currency': doc.currency_id}"/>
```
- `t-out` escapes `str`; a `markupsafe.Markup` value (e.g. an `Html` field value, a rendered template)
  is output as HTML. Falsy `None`/`False` renders the body (default content) or nothing.
- `t-field="record.field"` formats through `ir.qweb.field.<type or widget>`; it must be on a real HTML
  element (not `<t>`), not on `table`, `tr`, `td`, `li`, `ul`, `ol`, `dl`, `dt`, `dd`, and the expression
  needs a dot.
- `t-out` + `t-options` with a `widget` formats any value with the same converters.

Source: odoo/addons/base/models/ir_qweb.py:2459-2630, addons/sale/report/ir_actions_report_templates.xml:6-67

## Conditions and loops

```xml
<p t-if="doc.state == 'draft'">Quotation</p>
<p t-elif="doc.state == 'sale'">Order</p>
<p t-else="">Other</p>

<tr t-foreach="doc.order_line" t-as="line" t-att-class="'bg-light' if line_odd else None">
    <td t-out="line_index + 1"/><td t-field="line.name"/>
</tr>
```
Loop variables for `t-as="x"`: `x`, `x_value` (dict value, else the item), `x_index`, `x_size` (if
sized), `x_first`, `x_last` (if sized), `x_odd`, `x_even`, `x_parity` (`'odd'`/`'even'`).
`t-foreach` accepts an iterable, a dict (`x` = key, `x_value` = value) or an int (`range`).

Source: odoo/addons/base/models/ir_qweb.py:2252-2347,2368-2447

## Variables: `t-set`

| Form | Value |
|---|---|
| `<t t-set="x" t-value="expr"/>` | python expression |
| `<t t-set="x" t-valuef="Order {{doc.name}}"/>` | format string (`{{ }}` or `#{ }`) |
| `<t t-set="x" t-valuef.translate="Total {{n}}"/>` | translatable format string |
| `<t t-set="x">...markup...</t>` | rendered body as `Markup` |

`t-set="0"` cannot use `t-value`/`t-valuef`.

Source: odoo/addons/base/models/ir_qweb.py:2136-2215, odoo/tools/translate.py:166

## Attributes: `t-att`, `t-att-*`, `t-attf-*`

```xml
<div t-att-class="'text-danger' if late else None" t-attf-id="line_{{line.id}}"
     t-att="{'data-oe-id': doc.id}" t-attf-title.translate="Order {{doc.name}}"/>
```
- `t-att-name="expr"`: value of an expression; `t-attf-name="..."`: format string (`.translate`
  suffix makes the literal translatable); `t-att="..."`: a dict, a `(name, value)` pair or a list of pairs.
- An attribute whose value is falsy and not a string (`None`, `False`, `0`) is **omitted**; `''` is kept.

Source: odoo/addons/base/models/ir_qweb.py:1990-2078,2835-2847

## `t-call`: parameters, body and scoping

```xml
<t t-call="web.external_layout"
   company="doc.company_id.sudo()"
   layout_document_title="layout_document_title"
   body_classname.f="o_my_report"
   _message.translate="Thanks for your order">
    <div class="page">...</div>      <!-- body: available to the callee as 0 -->
</t>
```
| Parameter form | Callee receives |
|---|---|
| `name="expr"` | value of the python expression |
| `name.f="text {{expr}}"` | formatted string |
| `name.translate="literal"` | translatable string |
| `t-args="dict_or_pairs"` | several values at once |

Scoping rules (changed after 19.0, see upgrade script `19.1-00-t-call`):
- `t-call` must be on a `<t>` element; the template name is a format string (`t-call="{{tpl}}"`) or an id.
- The callee gets a **copy** of the caller's values plus the parameters; its own `t-set`s do not leak back.
- The body is rendered **lazily where the callee does `<t t-out="0"/>`**, with the caller's values at
  call time. A `<t t-set>` inside the body is visible to the body only, **not to the callee**: pass
  values as attributes (rule XML012, script `19.1-00-t-call`).

```xml
<!-- wrong in 20: the layout never sees `title` -->
<t t-call="my_module.layout"><t t-set="title" t-value="doc.name"/>...</t>
<!-- right -->
<t t-call="my_module.layout" title="doc.name">...</t>
```

Source: odoo/addons/base/models/ir_qweb.py:227-247,2632-2734,800-845, odoo/upgrade_code/19.1-00-t-call.py, addons/web/views/webclient_templates.xml:103-113

## `t-lang`, `t-options`, `groups`, misc directives

| Directive | Notes |
|---|---|
| `t-lang="expr"` | only on a `t-call` node (else `SyntaxError`); renders the callee in that language: `<t t-call="sale.report_saleorder_document" t-lang="doc.partner_id.lang"/>` |
| `t-options="{...}"`, `t-options-<key>="expr"` | must sit on a `t-out`, `t-field` or `t-call` node; merged into one dict |
| `groups="base.group_user"` / `t-groups` | render only for users in the groups (`!group` = not) |
| `t-call-assets="bundle"` | asset tags; `t-js`, `t-css`, `t-autoprefix` booleans; no children allowed |
| `t-debug=""` | breakpoint (dev mode) |
| `t-log="expr"` | logs the value when `--dev=qweb` |
| `t-translation="off"` | do not translate this node |

Source: odoo/addons/base/models/ir_qweb.py:249-262,1960-1988,2348-2366,2736-2795, [reports guidelines](../../odoo-guidelines/guidelines/reports.md#qweb-pdf-reports)

## `t-options` widgets (`ir.qweb.field.*`)

| `widget` | Key options |
|---|---|
| `integer` | `format_decimalized_number`, `precision_digits` |
| `float` | `precision`, `decimal_precision` (e.g. `'Product Price'`), `min_precision` |
| `monetary` | `display_currency` (required when the value is not a monetary field), `from_currency`, `date`, `company_id` |
| `date` | `format` (babel pattern) |
| `datetime` | `format`, `tz_name`, `time_only`, `date_only`, `hide_seconds` |
| `time`, `float_time` | `format` (`short` default) / time of day from a float |
| `duration` | `unit` (`second`...), `round`, `digital`, `format`, `add_direction` |
| `relative` | `now` (reference datetime) |
| `selection`, `many2one`, `many2many`, `one2many`, `text`, `html` | field-type formatters |
| `image` | `class`, `alt`/`alt-field`, `style`, `width`, `height`, `resize` or `max_width`/`max_height`, `preview_image`, `zoom`, `qweb_img_responsive` (default on), `qweb_img_raw_data` (embed data URI) |
| `image_url` | value is an URL |
| `contact` | `fields` (`name`, `address`, `phone`, `email`, `vat`...), `separator`, `no_marker`, `no_tag_br`, `phone_icons`, `country_image` |
| `barcode` | `symbology` (`Code128` default, `EAN13`, `QR`...), `width`, `height`, `humanreadable`, `quiet`, `mask` |
| `qweb` | renders the `ir.ui.view` in the field with `values` |

```xml
<span t-field="attendee.barcode" t-options="{'widget': 'barcode', 'width': 200, 'height': 84, 'quiet': 0, 'humanreadable': 1}"/>
<span t-out="qty" t-options="{'widget': 'float', 'decimal_precision': 'Product Unit'}"/>
```

Source: odoo/addons/base/models/ir_qweb_fields.py:180-920, addons/web/models/ir_qweb_fields.py:14-160, addons/sale/report/ir_actions_report_templates.xml:229-337, addons/event/report/event_event_templates.xml:53

## Values available in every template

`env`, `user_id`, `company` / `res_company` (sudo), `lang`, `request` (may be unbound), `debug`,
`json`, `time`, `datetime`, `relativedelta`, `image_data_uri(binary)`, `floor`, `ceil`, `quote_plus`,
`keep_query`, `true`/`false`, `test_mode_enabled`. Reports add `docs`, `doc_ids`, `doc_model`,
`user`, `context_timestamp(dt)`, `web_base_url`, `is_html_empty` (see [reports.md](reports.md)).

Source: odoo/addons/base/models/ir_qweb.py:1362-1398, odoo/addons/base/models/ir_actions_report.py:402-421,769-786

## Rendering from Python

```python
html = self.env['ir.qweb']._render('my_module.my_template', {'records': records})   # Markup
html = self.env['ir.ui.view']._render_template('my_module.my_template', values)    # same, via the view
```
Pass `Markup` only for trusted HTML: build it with `Markup("<b>{}</b>").format(value)` (auto-escapes
`value`), never `Markup(f"...")` with user data.

At work time: `odoo_views(xmlid="web.external_layout")` lists a template's extensions **and its t-call
callers**; `odoo_validate(<module>)` flags XML003/XML011/XML012; try a render with
`odoo_shell(db, "result = env['ir.qweb']._render('my_module.tpl', {...})")`.

Source: odoo/addons/base/models/ir_qweb.py:711-730, odoo/addons/base/models/ir_ui_view.py:2627-2628

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `t-esc="x"` / `t-raw="x"` (server QWeb) | `t-out="x"` (raw HTML = a `Markup` value) (XML003) | odoo/addons/base/models/ir_qweb.py:1927 |
| `<t t-call="x"><t t-set="a" t-value="v"/></t>` to pass `a` | `<t t-call="x" a="v"/>` (XML012) | odoo/upgrade_code/19.1-00-t-call.py |
| `<t t-set="t" t-value="'Text'"/>` before t-call | `t.f="Text"` or `t.translate="Text"` | odoo/upgrade_code/19.1-00-t-call.py:44-58 |
| `t-call-options="{...}"` | `t-options` on the `t-call` node (XML011) | odoo/addons/base/models/ir_qweb.py:1927,1960-1985 |
| `t-lang` on any element | only with `t-call` | odoo/addons/base/models/ir_qweb.py:2736-2740 |
| `fa fa-*` icons in templates | `<i class="oi" data-icon="..."/>` (XML004) | odoo/upgrade_code/19.5-00-material-symbols-icons.py |
