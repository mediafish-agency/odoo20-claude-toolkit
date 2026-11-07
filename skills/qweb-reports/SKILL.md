---
name: qweb-reports
description: >-
  Default for any Odoo work in this Odoo 20.0 tree even when no version is named; takes priority over generic odoo-* skills (17-19 advice such as t-esc, t-raw, report_file is wrong in 20). PDF / print report, invoice or document layout, website/portal page template - Odoo 20 server-side QWeb: directives (t-out only, t-call with attribute parameters .f and
  .translate, t-options widgets, t-field, t-lang), Markup safety, ir.actions.report definitions, report
  templates (web.html_container, web.external_layout), _get_report_values, paper formats, report layouts,
  and the pluggable PDF engines (base_report_wkhtmltox, base_report_paper_muncher).
when_to_use: >-
  Writing <template> records (report/*.xml, views/*templates*.xml), website/portal page templates, email QWeb bodies, or report/*.xml in an Odoo 20
  addon; printing PDFs from Python; fixing templates that render nothing (t-esc/t-raw) or t-call parameters.
---

# Odoo 20 QWeb and reports

## Workflow

1. Find the template to call or inherit: `odoo_views(xmlid="web.external_layout")` (tree + t-call callers);
   real final template: `resolve="db"`.
2. Write templates with the directive rules below; reports follow Odoo's
   [reports guideline](../odoo-guidelines/guidelines/reports.md); HTML safety per
   [odoo-security](../odoo-security/SKILL.md) (Markup, no f-strings).
3. `odoo_validate` (flags t-esc/t-raw, removed layouts, report_file); render a PDF in a test or via
   `odoo_shell` with `env['ir.actions.report']._render_qweb_pdf(...)`.

## Odoo 20 rules

- Server QWeb supports **only `t-out`** for output; `t-esc`/`t-raw` render nothing.
- Pass parameters on the call: `<t t-call="mod.tpl" partner="doc.partner_id" title.f="Invoice {{doc.name}}"
  note.translate="Thank you"/>`. A `t-set` inside the `t-call` body is visible to the body (rendered by the
  callee's `t-out="0"`) but not to the callee itself. `t-call-options` is gone (use `t-options`).
- `t-lang` is only valid on a `t-call` node.
- `ir.actions.report` lost `report_file` and gained `save_as_attachment`; engines are chosen with
  `report_type` `qweb-pdf-wkhtmltopdf` / `qweb-pdf-paper-muncher` or the `report.pdf_engine_default` parameter.
- Layouts `external_layout_bold/boxed/striped` were removed (center, dual, lines, compact were added).

## References

- [qweb-directives.md](references/qweb-directives.md) - every server QWeb directive and t-options widget
- [reports.md](references/reports.md) - report actions, templates, _get_report_values, rendering from Python
- [engines-layouts.md](references/engines-layouts.md) - PDF engines, report assets, company layouts
