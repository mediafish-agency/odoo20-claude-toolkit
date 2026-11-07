# QWeb reports (Odoo 20)

Defining and rendering PDF/HTML/text reports in Odoo 20: `ir.actions.report` fields (engine-specific
`report_type`s, `save_as_attachment`), the template skeleton (`web.html_container`,
`web.external_layout`, `div.page`), custom `_get_report_values`, rendering from Python, paper formats,
barcodes/QR and per-partner translation. Engines and layouts: [engines-layouts.md](engines-layouts.md);
directives: [qweb-directives.md](qweb-directives.md); house rules:
[reports guidelines](../../odoo-guidelines/guidelines/reports.md#qweb-pdf-reports).

## Contents
- `ir.actions.report` fields
- Report template skeleton
- What the template receives
- Custom values: `report.<report_name>`
- Rendering from Python
- Routes
- Paper formats
- Barcodes and QR codes
- Translations
- Attachments and splitting multi-record PDFs
- v19 habit -> Odoo 20

## `ir.actions.report` fields

| Field | Notes |
|---|---|
| `name`, `model` | required |
| `report_type` | `qweb-pdf` (default; engine from `report.pdf_engine_default`), `qweb-html`, `qweb-text`, plus engine-specific `qweb-pdf-wkhtmltopdf` (base_report_wkhtmltox) and `qweb-pdf-paper-muncher` (base_report_paper_muncher) |
| `report_name` | QWeb template xmlid (`module.template`); also the lookup key for `report.<report_name>` |
| `print_report_name` | python expr for the downloaded file name; `object`, `time` available |
| `attachment` | python expr giving the attachment file name; **non-empty = printed PDFs are stored** as `ir.attachment` on the record |
| `attachment_use` | reprint returns the stored attachment instead of re-rendering |
| `save_as_attachment` | **new** UI toggle (form view) that makes `attachment` required; storage itself depends on `attachment` |
| `paperformat_id` | `report.paperformat`; default = company paper format |
| `binding_model_id`, `binding_type` (`report`), `binding_view_types` | Print menu |
| `group_ids` | who sees it |
| `domain` | only offered for records matching it |
| `multi` | hide from the form's Print menu |
| `explanation`, `path` | from `ir.actions.actions` |

```xml
<record id="action_report_saleorder" model="ir.actions.report">
    <field name="name">Quotation / Order</field>
    <field name="model">sale.order</field>
    <field name="report_type">qweb-pdf</field>
    <field name="report_name">sale.report_saleorder</field>
    <field name="print_report_name">(object.state in ('draft', 'sent') and 'Quotation - %s' % (object.name)) or 'Order - %s' % (object.name)</field>
    <field name="binding_model_id" ref="model_sale_order"/>
    <field name="binding_type">report</field>
</record>
<record id="action_account_original_vendor_bill" model="ir.actions.report">
    ...
    <field name="attachment">'original_vendor_bill.pdf'</field>
    <field name="attachment_use">True</field>
    <field name="domain" eval="[('move_type', 'in', ('in_invoice', 'in_refund'))]"/>
</record>
```

Source: odoo/addons/base/models/ir_actions_report.py:36-72,154-168, odoo/addons/base/views/ir_actions_views.xml:120-133, addons/base_report_wkhtmltox/models/ir_actions_report.py:130-133, addons/base_report_paper_muncher/models/ir_actions_report.py:23-26, addons/sale/report/ir_actions_report.xml, addons/account/views/account_report.xml:19-28

## Report template skeleton

```xml
<template id="report_saleorder_document">
    <t t-set="doc" t-value="doc.with_context(lang=doc.partner_id.lang)"/>
    <t t-call="web.external_layout" company="doc.company_id.sudo()" layout_document_title="layout_document_title">
        <div class="page">
            <div class="row mb-4" id="informations">
                <div t-if="doc.date_order" class="col" name="informations_date">
                    <strong>Order Date</strong>
                    <div t-field="doc.date_order" t-options='{"widget": "date"}'/>
                </div>
            </div>
        </div>
    </t>
</template>

<template id="report_saleorder">
    <t t-call="web.html_container">
        <t t-foreach="docs" t-as="doc">
            <t t-call="sale.report_saleorder_document" t-lang="doc.partner_id.lang"/>
        </t>
    </t>
</template>
```
- `web.html_container` -> `web.report_layout` (HTML document, `web.report_assets_common`).
- `web.external_layout` picks the company layout (`company.external_report_layout_id`, else
  `web.external_layout_standard`); it sets `o` from `doc`, resolves `company` (`company_id` param, the
  record's `company_id`, else `res_company`) and wraps the body in `div.article` with
  `data-oe-model`/`data-oe-id`/`data-oe-lang`.
- Parameters understood by the external layouts include `address`, `information_block`,
  `layout_document_title`, `hide_title`, `hide_recipient_address`, `forced_vat`; pass them as `t-call`
  attributes (not `t-set` in the body).
- `web.internal_layout` (date, company, page x/y header) and `web.basic_layout` (no header/footer) are
  the other layouts.
- Keep the `oe_structure` divs and named/id'd blocks so others can extend by name.

Source: addons/sale/report/ir_actions_report_templates.xml:3-70,477-498, addons/web/views/report_templates.xml:6-110,443-500,782-856

## What the template receives

Without a custom model: `docs` (records), `doc_ids`, `doc_model`, plus the `data` dict keys, and
`is_html_empty`, `time`, `context_timestamp(dt)`, `user`, `res_company`, `web_base_url`, and the
standard QWeb values (`env`, `company`, `lang`, `image_data_uri`...). `data['report_type']` is `pdf`,
`html` or `text`.

Source: odoo/addons/base/models/ir_actions_report.py:402-421,765-786, odoo/addons/base/models/ir_qweb.py:1362-1398

## Custom values: `report.<report_name>`

An AbstractModel named `report.` + `report_name` replaces the default values. It must return `docs`,
`doc_ids`, `doc_model` itself if the template uses them.

```python
class ReportAccountReport_Invoice(models.AbstractModel):
    _name = 'report.account.report_invoice'
    _description = 'Account report without payment lines'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['account.move'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'account.move',
            'docs': docs,
            'qr_code_urls': {...},
        }
```

Source: odoo/addons/base/models/ir_actions_report.py:765-786, addons/account/report/account_invoice_report.py:158-189, addons/hr_skills/report/hr_employee_cv_report.py:8-30

## Rendering from Python

| Call | Returns |
|---|---|
| `self.env['ir.actions.report']._render_qweb_pdf(report_ref, res_ids=None, data=None)` | `(pdf_bytes, 'pdf')` |
| `..._render_qweb_html(report_ref, docids, data=None)` | `(html_bytes, 'html')` |
| `..._render_qweb_text(report_ref, docids, data=None)` | `(bytes, 'text')` |
| `report.report_action(docids, data=None, config=True)` | action dict for the client (download) |

- `report_ref`: report record, id, xmlid (`'sale.action_report_saleorder'`) or `report_name`.
- `res_ids` may be an int or a list.
- In test mode (`--test-enable`) `_render_qweb_pdf` returns **HTML** `(html, 'html')` unless the context
  has `force_report_rendering=True`.
- `_render(report_ref, ids)` dispatches on `report_type` to `_render_<type>`; engine-specific types
  (`qweb-pdf-wkhtmltopdf`) have no such method: call `_render_qweb_pdf` for any `qweb-pdf*` (as
  `mail.template` does).
- `report_action(..., config=True)` opens the document layout configurator for an admin whose company
  has no layout yet; pass `config=False` to skip.

```python
pdf, _ = self.env['ir.actions.report']._render_qweb_pdf('sale.action_report_saleorder', self.ids)
self.env['ir.attachment'].create({'name': 'SO.pdf', 'raw': pdf, 'res_model': self._name, 'res_id': self.id})
```
Find a report's definition and every reference with `odoo_xmlid("sale.action_report_saleorder")`, the
template tree with `odoo_views(xmlid="sale.report_saleorder_document")`, and check rendering on a
throwaway database with `odoo_test(<module>)` (HTML in tests, see above).

Source: odoo/addons/base/models/ir_actions_report.py:291-318,663-764,855-902, addons/mail/models/mail_template.py:369-378

## Routes

| URL | |
|---|---|
| `/report/pdf/<report_name>/<ids>` | PDF (`ids` comma-separated) |
| `/report/html/<report_name>/<ids>` | HTML (handy to debug layout) |
| `/report/text/<report_name>/<ids>` | text |
| `/report/barcode/<type>/<value>?width=&height=&humanreadable=&quiet=&mask=&barLevel=` | PNG barcode |
| `/report/get_pdf_engine_state` | JSON-RPC used by the client before downloading |

Source: addons/web/controllers/report.py:20-170

## Paper formats

```xml
<record id="paperformat_my_label" model="report.paperformat">
    <field name="name">My Label</field>
    <field name="format">custom</field>
    <field name="page_width">100</field>
    <field name="page_height">50</field>
    <field name="orientation">Portrait</field>
    <field name="margin_top">5</field>
    <field name="margin_bottom">5</field>
    <field name="margin_left">5</field>
    <field name="margin_right">5</field>
    <field name="header_spacing">0</field>
    <field name="dpi">90</field>
</record>
<record id="action_report_my_label" model="ir.actions.report">
    ...
    <field name="paperformat_id" ref="paperformat_my_label"/>
</record>
```
Fields: `format` (`A0`-`A9`, `B0`-`B10`, `C5E`, `Comm10E`, `DLE`, `Executive`, `Folio`, `Ledger`,
`Legal`, `Letter`, `Tabloid`, `custom`), `page_width`/`page_height` (mm, only with `custom`),
`orientation` (`Portrait`/`Landscape`, default **Landscape**), `margin_*` (mm), `header_line`,
`header_spacing`, `dpi`, `disable_shrinking`, `css_margins`, `default`.
Per template overrides: `<t t-set="data_report_landscape" t-value="True"/>` (also
`data_report_margin_top`, `data_report_header_spacing`, `data_report_dpi`) become `data-report-*`
attributes that win over the paper format.

Source: odoo/addons/base/models/report_paperformat.py:150-210, odoo/addons/base/data/report_paperformat_data.xml:4-36, addons/web/views/report_templates.xml:6-12, odoo/addons/base/models/ir_actions_report.py:257-262, addons/hr_timesheet/report/report_timesheet_templates.xml:4

## Barcodes and QR codes

```xml
<span t-field="attendee.barcode" t-options="{'widget': 'barcode', 'width': 200, 'height': 84, 'quiet': 0, 'humanreadable': 1}"/>
<img t-attf-src="/report/barcode/QR/{{attendee.barcode}}?&amp;width=174&amp;height=174" alt="QR Code"/>
```
`self.env['ir.actions.report'].barcode(barcode_type, value, **kwargs)` returns PNG bytes; kwargs
default to `width=600, height=100, humanreadable=0, quiet=1, mask=None, barBorder=4, barLevel='L'`;
types include `Code128`, `EAN13`, `EAN8`, `UPCA`, `QR`... (`width * height` must stay <= 1 200 000).

Source: odoo/addons/base/models/ir_actions_report.py:319-400, addons/web/controllers/report.py:55-97, addons/event/report/event_event_templates.xml:53-60

## Translations

- Render each document in its partner language with `t-lang` **on the `t-call`** of the document
  template; `t-lang` anywhere else is a compile error.
- Inside the document, re-browse in that language only when translatable fields are printed:
  `<t t-set="doc" t-value="doc.with_context(lang=doc.partner_id.lang)"/>`.
- The article `data-oe-lang` attribute (set by the layouts) is used as context language when each body is
  wrapped in `web.minimal_layout` for the PDF engine.

Source: odoo/addons/base/models/ir_qweb.py:2736-2740, addons/sale/report/ir_actions_report_templates.xml:4,480, odoo/addons/base/models/ir_actions_report.py:235-240

## Attachments and splitting multi-record PDFs

- With `attachment` set, each record's PDF is stored; Odoo splits the merged PDF per record using the
  `div.article` elements carrying `data-oe-model` = report model and `data-oe-id` (provided by
  `web.external_layout` / `internal_layout` / `basic_layout`). A custom wrapper without them raises
  "Cannot separate file to save as attachment".
- Context `report_pdf_no_attachment=True` disables storing/reusing for one call.

Source: odoo/addons/base/models/ir_actions_report.py:447-624

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `<field name="report_file">` | removed: drop it (REP002) | odoo/addons/base/models/ir_actions_report.py |
| `attachment` labelled "Save as Attachment Prefix" only | `save_as_attachment` toggle + `attachment` name expr | odoo/addons/base/views/ir_actions_views.xml:121-131 |
| single global wkhtmltopdf | per report `qweb-pdf-<engine>` or global `report.pdf_engine_default` (REP001) | odoo/addons/base/models/ir_actions_report.py:788-799 |
| `external_layout_bold/boxed/striped` | `standard`, `bubble`, `wave`, `folder`, `center`, `dual`, `lines`, `compact` (REP003) | addons/web/data/report_layout.xml |
| `t-esc` / `t-raw` in report templates | `t-out` (XML003) | odoo/addons/base/models/ir_qweb.py |
| `t-set` in a `t-call` body to feed the layout | `t-call` attributes (XML012) | odoo/upgrade_code/19.1-00-t-call.py |
| `fa fa-*` in reports | `oi` + `data-icon` (XML004) | addons/web/static/src/webclient/actions/reports/icons_report.scss |
