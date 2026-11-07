# PDF engines, report assets and company layouts (Odoo 20)

Odoo 20 made the PDF engine pluggable: base only dispatches, `base_report_wkhtmltox` (auto-installed)
and `base_report_paper_muncher` implement engines, selected per report (`qweb-pdf-<engine>`) or
globally (`report.pdf_engine_default`). This file covers engine selection and states, hooks for a
custom engine, the report asset bundles, the company document layouts shipped in 20, and layout/CSS
rules that both engines rely on. Report records and templates: [reports.md](reports.md).

## Contents
- Engine selection
- The two shipped engines
- Engine state and the HTML fallback
- Writing or extending an engine
- Report asset bundles
- Company layouts (`report.layout`)
- Writing a custom external layout
- Layout and CSS rules for both engines
- v19 habit -> Odoo 20

## Engine selection

`ir.actions.report._get_pdf_engine(report=None, default_engine='wkhtmltopdf')`:

1. `report_type` starting with `qweb-pdf-` -> the suffix (`qweb-pdf-paper-muncher` -> `paper-muncher`);
2. else (`qweb-pdf`) -> `ir.config_parameter` `report.pdf_engine_default`;
3. empty or `html` -> `default_engine` (`wkhtmltopdf`).

```python
# global default (what base_report_wkhtmltox's post_init_hook does)
self.env['ir.config_parameter'].sudo().set_str('report.pdf_engine_default', 'paper-muncher')
```
```xml
<!-- one report on a given engine (requires that engine's module) -->
<field name="report_type">qweb-pdf-paper-muncher</field>
```
The web client reads the engine from `report_type` the same way and sends it to
`/report/get_pdf_engine_state`.

Source: odoo/addons/base/models/ir_actions_report.py:788-799, addons/base_report_wkhtmltox/__init__.py:6-7, addons/web/static/src/webclient/actions/action_plugin.js:1445-1470

## The two shipped engines

| | base_report_wkhtmltox | base_report_paper_muncher |
|---|---|---|
| install | `auto_install: True`; post-init sets `report.pdf_engine_default = wkhtmltopdf` | manual; depends on `base_setup` |
| `report_type` added | `qweb-pdf-wkhtmltopdf` (`ondelete: set qweb-pdf`) | `qweb-pdf-paper-muncher` (`ondelete: set default`) |
| engine name | `wkhtmltopdf` | `paper-muncher` |
| binary | `wkhtmltopdf` on PATH (>= 0.12.0, else `upgrade`) | `paper-muncher` >= 0.6 on PATH or `/opt/paper-muncher/bin/paper-muncher` |
| states returned | `install`, `ok`, `upgrade`, `workers` (only 1 worker), `broken` | `install`, `ok` |
| extras | `wkhtmltoimage` (`_run_image_engine`), ICP `report.print_delay` (ms, default 1000) for `--javascript-delay`, splits tables > 500 rows in bodies > 4 MiB | serves pages to the binary through an in-process HTTP bridge |

Source: addons/base_report_wkhtmltox/__manifest__.py, addons/base_report_wkhtmltox/models/ir_actions_report.py:27-160,240-320,440-520, addons/base_report_paper_muncher/__manifest__.py, addons/base_report_paper_muncher/README.md, addons/base_report_paper_muncher/paper_muncher.py:34-40,365-408, addons/base_report_paper_muncher/models/ir_actions_report.py:19-190

## Engine state and the HTML fallback

- `get_pdf_engine_state(engine_name)` returns `install` in base; each engine module answers for its name.
- Client: before downloading, `/report/get_pdf_engine_state`; unless `ok`/`upgrade` it shows a sticky
  message ("Unable to find the PDF engine on this system...") and opens the report as **HTML**.
- Server `_render_qweb_pdf` raises `UserError` on `install`, `broken` or `workers` (e.g. a PDF attached
  by a mail template on a server without the binary).
- Tests render HTML instead of PDF unless `force_report_rendering=True` in the context.

Source: odoo/addons/base/models/ir_actions_report.py:170-183,493-536,663-675, addons/web/static/src/webclient/actions/reports/utils.js:33-90, addons/web/controllers/report.py:161-166

## Writing or extending an engine

Override on `ir.actions.report`, always delegating other engine names to `super()`:

```python
class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    report_type = fields.Selection(
        selection_add=[('qweb-pdf-myengine', 'PDF (My Engine)')],
        ondelete={'qweb-pdf-myengine': 'set qweb-pdf'},
    )

    @api.model
    def get_pdf_engine_state(self, engine_name):
        if engine_name != 'myengine':
            return super().get_pdf_engine_state(engine_name)
        return 'ok'  # 'install' | 'ok' | 'upgrade' | 'workers' | 'broken'

    def _run_pdf_engine(self, engine_name, html, report_ref=False, landscape=False, **kwargs):
        if engine_name != 'myengine':
            return super()._run_pdf_engine(engine_name, html, report_ref, landscape, **kwargs)
        report_sudo = self._get_report(report_ref).with_context(debug=False)
        bodies, html_ids, header, footer, paperformat_args = report_sudo._prepare_html(
            html, report_model=report_sudo.model)
        pdf = self._run_pdf_engine_without_processing(
            engine_name, bodies, report_ref, header=header, footer=footer,
            landscape=landscape, specific_paperformat_args=paperformat_args)
        return pdf, html_ids   # html_ids: record id per body, used to split attachments
```
| Hook | Signature / contract |
|---|---|
| `_run_pdf_engine` | `(engine_name, html, report_ref=False, landscape=False, **kwargs) -> (bytes, list[int])` |
| `_run_pdf_engine_without_processing` | `(engine_name, bodies, report_ref=False, *, header=None, footer=None, landscape=False, specific_paperformat_args=None, **kwargs) -> bytes` |
| `_run_image_engine` | `(engine_name, bodies, width, height, image_format="jpg") -> list[bytes or None]` |
| `_prepare_html` | `(html, report_model=False) -> (bodies, res_ids, header, footer, specific_paperformat_args)` |
| `get_pdf_engine_state` | `(engine_name) -> 'install' / 'ok' / 'upgrade' / 'workers' / 'broken'` |

Removed from base (REP001): `_run_wkhtmltopdf`, `_run_wkhtmltoimage`, `get_wkhtmltopdf_state`.

Source: odoo/addons/base/models/ir_actions_report.py:170-183,198-280,802-853, addons/base_report_paper_muncher/models/ir_actions_report.py:23-32,139-187, addons/base_report_wkhtmltox/models/ir_actions_report.py:151-155,491-510

## Report asset bundles

| Bundle | Loaded in | Content |
|---|---|---|
| `web.report_assets_common` | HTML report page (`web.report_layout`) and every PDF page (`web.minimal_layout`) | Bootstrap + Odoo report SCSS (`report.scss`, `report_tables.scss`, `report_layouts.scss`), icon fonts (`web.icons_fonts`), fonts, `web/static/asset_styles_company_report.scss` (company colours/font) |
| `web.report_assets_pdf` | PDF only (`web.minimal_layout`) | `reset.min.css` |

```python
'assets': {
    'web.report_assets_common': ['account/static/src/css/report_invoice.css'],
    'web.report_assets_pdf': ['account/static/src/css/report_invoice.css'],
},
```
Check the final file list with `odoo_assets("web.report_assets_common", resolve="db")`.

Source: addons/web/__manifest__.py:244-306, addons/account/__manifest__.py:136-145, addons/web/views/report_templates.xml:6-30,287-334

## Company layouts (`report.layout`)

`report.layout` (`name`, `sequence`, `view_id`, `image`, `pdf`) lists the choices of the document layout
wizard; the company stores its choice in `external_report_layout_id` (an `ir.ui.view`).

| Record (web) | Name | Template |
|---|---|---|
| `web.report_layout_standard` | Light | `web.external_layout_standard` |
| `web.report_layout_bubble` | Bubble | `web.external_layout_bubble` |
| `web.report_layout_wave` | Wave | `web.external_layout_wave` |
| `web.report_layout_folder` | Folder | `web.external_layout_folder` |
| `web.report_layout_center` | Center (**new**) | `web.external_layout_center` |
| `web.report_layout_dual` | Dual (**new**) | `web.external_layout_dual` |
| `web.report_layout_lines` | Lines (**new**) | `web.external_layout_lines` |
| `web.report_layout_compact` | Compact (**new**) | `web.external_layout_compact` |

Removed: `external_layout_striped`, `external_layout_boxed`, `external_layout_bold` (REP003). Table looks
are now a separate company setting `report_tables_id`: `light`, `boxed`, `bold`, `striped`, `bubble`,
`column`, `compact` (classes `o_table_*` added by `web.external_layout_body`). Other company settings
used by layouts: `font`, `primary_color`, `secondary_color`, `paperformat_id`.

Source: odoo/addons/base/models/report_layout.py:8-17, addons/web/data/report_layout.xml:5-52, addons/web/views/report_templates.xml:443-808, odoo/addons/base/models/res_company.py:130-142

## Writing a custom external layout

Follow `web.external_layout_standard`: a `div.header`, the body through `web.external_layout_body`
(which builds the `div.article` with `data-oe-*`, the address block and the title), a `div.footer`; then
register it as a `report.layout`.

```xml
<template id="external_layout_mycompany">
    <div t-attf-class="o_company_#{company.id}_layout header">
        <img t-if="company.logo" t-att-src="image_data_uri(company.logo)" alt="Logo" style="max-height: 45px;"/>
    </div>
    <t t-call="web.external_layout_body">
        <t t-out="0"/>
    </t>
    <div t-attf-class="footer o_company_#{company.id}_layout">
        <t t-call="web.external_layout_footer_content" is_centered_footer="True"/>
    </div>
</template>

<record id="report_layout_mycompany" model="report.layout">
    <field name="name">My Company</field>
    <field name="sequence">20</field>
    <field name="view_id" ref="external_layout_mycompany"/>
</record>
```

Source: addons/web/views/report_templates.xml:400-497,782-808, addons/web/data/report_layout.xml

## Layout and CSS rules for both engines

Verified in the shared HTML preparation (`_prepare_html` and wkhtmltox's copy):
- Headers/footers/bodies are found by **`div` elements whose class list contains `header`, `footer` or
  `article`**; headers/footers are moved out of the body and rendered in `web.minimal_layout`. Put any
  repeated header/footer content in those divs, and never reuse those class names for other divs.
- One `div.article` per record with `data-oe-model`/`data-oe-id` is required to store per-record
  attachments.
- `data_report_*` `t-set`s on the page (`margin_top`, `margin_bottom`, `header_spacing`, `dpi`,
  `landscape`) override the paper format for that render.
- Use `image_data_uri(binary)` for logos and images (as the core layouts do) instead of URLs.
- `.d-print-none` is hidden in report CSS; core uses `style="page-break-after: always;"` and
  `page-break-inside: avoid` for pagination.
- Page numbers `<span class="page"/>` / `<span class="topage"/>` are filled by the `subst()` script of
  `web.minimal_layout` from wkhtmltopdf's page variables (support in paper-muncher: unverified).
- Debug the HTML first through `/report/html/<report_name>/<ids>`.

Source: odoo/addons/base/models/ir_actions_report.py:198-280, addons/base_report_wkhtmltox/models/ir_actions_report.py:157-240, addons/web/views/report_templates.xml:287-334,809-846, addons/web/static/src/webclient/actions/reports/bootstrap_review_report.scss:36-45, addons/stock/report/report_package_barcode.xml:12

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `ir.actions.report._run_wkhtmltopdf(...)`, `get_wkhtmltopdf_state()` | `_run_pdf_engine(engine_name, ...)`, `get_pdf_engine_state(engine_name)` (REP001) | odoo/addons/base/models/ir_actions_report.py:170,815 |
| wkhtmltopdf always present in base | `base_report_wkhtmltox` (auto_install) or `base_report_paper_muncher` | addons/base_report_wkhtmltox/__manifest__.py |
| one engine for every report | `report_type="qweb-pdf-<engine>"` per report | addons/base_report_paper_muncher/models/ir_actions_report.py:23 |
| layouts Striped/Boxed/Bold | layouts Center/Dual/Lines/Compact + table design `report_tables_id` (REP003) | addons/web/data/report_layout.xml, odoo/addons/base/models/res_company.py:132 |
| `ir.config_parameter.get_param('report.url')` | `get_str('report.url')` (ORM001) | odoo/addons/base/models/ir_actions_report.py:194-196 |
