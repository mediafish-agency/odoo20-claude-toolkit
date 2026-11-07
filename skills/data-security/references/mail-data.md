# Mail data: templates, activity types, layouts, subtypes (Odoo 20)

Declarative mail records in Odoo 20: `mail.template` (fields, the two render engines, report
attachments), `mail.activity.type`, notification layouts (`email_layout_xmlid`) and
`mail.message.subtype`, plus the tracking hooks that pick subtypes and templates. For `mail.thread`,
`message_post` and the mixins in Python see [mail-mixins.md](../../orm/references/mail-mixins.md).

## Contents

- [mail.template fields](#mailtemplate-fields)
- [Render engines: inline_template vs qweb](#render-engines-inline_template-vs-qweb)
- [mail.template XML record](#mailtemplate-xml-record)
- [Sending a template from Python](#sending-a-template-from-python)
- [Notification layouts](#notification-layouts)
- [QWeb views as message bodies](#qweb-views-as-message-bodies)
- [mail.activity.type](#mailactivitytype)
- [mail.message.subtype and tracking hooks](#mailmessagesubtype-and-tracking-hooks)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## mail.template fields

`mail.template` inherits `mail.render.mixin` and `template.reset.mixin` (`template_fs`).

| Field | Type | Notes |
|---|---|---|
| `name`, `description` | Char / Text, translated | `description` = internal usage note |
| `model_id` / `model` | M2o `ir.model` / related Char (stored) | set `model_id` in XML (`ref="sale.model_sale_order"`) |
| `subject` | Char, translated | inline_template |
| `email_from`, `reply_to` | Char | inline_template; empty `email_from` is dropped (author default) |
| `use_default_to` | Boolean, default True | recipients from the record (`partner_id` / email fields) |
| `partner_to`, `email_to` | Char | comma-separated partner ids / emails, inline_template |
| `partner_cc` (new in 20), `email_cc` | Char | `partner_cc` renders to `partner_cc_ids` / `recipient_cc_ids` |
| `body_html` | Html, translated, `render_engine='qweb'`, `sanitize='email_outgoing'` | QWeb, `t-out` only |
| `lang` | Char (from the mixin) | inline_template, e.g. `{{ object.partner_id.lang }}` |
| `attachment_ids` | M2m `ir.attachment` | static attachments |
| `report_template_ids` | M2m `ir.actions.report` (`domain="[('model', '=', model)]"`) | rendered per record and attached |
| `email_layout_xmlid` | Char | layout used by `send_mail` / composer |
| `email_layout_force_header`, `email_layout_force_footer` (new in 20) | Boolean | force the layout header/footer (composer and preview) |
| `mail_server_id`, `scheduled_date` (Char, may be dynamic), `auto_delete` (default True) | | |
| `user_id` | M2o `res.users` | template owner |
| `ref_ir_act_window` | M2o | contextual "Send Mail" action created by `create_action()` |
| `template_category` | computed selection `base_template` / `hidden_template` / `custom_template` | |

Report attachments: each report in `report_template_ids` is rendered (`qweb-html` and every
`qweb-pdf*` engine through `_render_qweb_pdf`), named with the report's `print_report_name`
(evaluated with `object` and `time`) or "Report", and stored as `BinaryBytes` (no base64).

Access: `base.group_user` reads all templates and may create/write/unlink only its own
(`create_uid` or `user_id`); `mail.group_mail_template_editor` edits all. Saving dynamic expressions
judged unsafe requires `mail.group_mail_template_editor` (`_check_access_right_dynamic_template`).

Source: addons/mail/models/mail_template.py:17-112, addons/mail/models/mail_template.py:338-410,
addons/mail/models/mail_render_mixin.py:60-75, addons/mail/models/mail_render_mixin.py:291-337,
addons/mail/security/ir.access.csv:123-126

## Render engines: inline_template vs qweb

| Engine | Used for | Syntax |
|---|---|---|
| `inline_template` (default for any field without `render_engine`) | `subject`, `email_from`, `partner_to`, `partner_cc`, `email_to`, `email_cc`, `reply_to`, `lang`, `scheduled_date` | `{{ expression }}` and `{{ expression \|\|\| default }}` |
| `qweb` | `body_html` (`render_engine='qweb'`) | server QWeb: `t-out`, `t-if`, `t-foreach`, `t-set`, `t-att-*`, `t-attf-*` |
| `qweb_view` | rendering an `ir.ui.view` by xmlid (layouts, `message_post_with_source` with a view) | a `<template>` record |

- Evaluation context (`_render_eval_context`): `object` (the record), `ctx`, `user`, `env`,
  `format_addr`, `format_date`, `format_datetime`, `format_time`, `format_amount(amount, currency)`,
  `format_duration`, `is_html_empty`, `slug`, plus `template_env_globals` (`str`, `len`, `abs`,
  `min`, `max`, `sum`, `filter`, `map`, `reduce`, `round`, `hasattr`, `datetime`, `relativedelta`,
  `quote`, `urlencode`).
- **Server QWeb has no `t-esc` / `t-raw`** in 20: they are reported as unknown directives and render
  nothing. Use `t-out` (escapes; a `Markup` value is output as HTML). Flagged by `odoo_validate` rule
  XML003.
- Put sample text inside `t-out` nodes (`<t t-out="object.name or ''">S00052</t>`): it is shown in
  the editor, replaced at render time.
- A custom model can declare its own rendered fields with the `render_engine` / `render_options`
  field parameters, allowed only on models inheriting `mail.render.mixin`.

Source: addons/mail/models/mail_render_mixin.py:104-108, addons/mail/models/mail_render_mixin.py:343-364,
addons/mail/models/mail_render_mixin.py:690-750, odoo/tools/rendering_tools.py:13-36,
odoo/addons/base/models/ir_qweb.py:1719-1760, odoo/addons/base/models/ir_qweb.py:1927

## mail.template XML record

```xml
<!-- condensed from addons/sale/data/mail_template_data.xml:4-65 and addons/auth_signup/data/mail_template_data.xml:5-42 -->
<odoo>
    <data noupdate="1">
        <record id="mail_template_my_doc_send" model="mail.template">
            <field name="name">My Doc: Send by email</field>
            <field name="model_id" ref="my_module.model_my_doc"/>
            <field name="subject">{{ object.company_id.name }} Document {{ object.name or 'n/a' }}</field>
            <field name="email_from">{{ (object.user_id.email_formatted or object.company_id.email_formatted or user.email_formatted) }}</field>
            <field name="partner_to" eval="False"/>
            <field name="use_default_to" eval="True"/>
            <field name="description">Sent to the customer when the document is confirmed</field>
            <field name="email_layout_xmlid">mail.mail_notification_layout_with_responsible_signature</field>
            <field name="body_html" type="html">
<div style="margin: 0px; padding: 0px;">
    <p style="margin: 0px; padding: 0px; font-size: 13px;">
        Hello <t t-out="object.partner_id.name or ''">Marc Demo</t>,<br/><br/>
        Your document <span style="font-weight: bold;" t-out="object.name or ''">DOC001</span>
        amounting to <t t-out="format_amount(object.amount_total, object.currency_id) or ''">$ 10.00</t> is ready.
        <t t-if="not is_html_empty(object.user_id.signature)">
            <div>--<br/><t t-out="object.user_id.signature or ''">Mitchell Admin</t></div>
        </t>
    </p>
</div>
            </field>
            <field name="report_template_ids" eval="[Command.link(ref('my_module.action_report_my_doc'))]"/>
            <field name="lang">{{ object.partner_id.lang }}</field>
            <field name="auto_delete" eval="True"/>
        </record>
    </data>
</odoo>
```

- Ship templates in `noupdate="1"` so user edits survive `-u` (core does); `template_fs` lets users
  reset a broken template from the file.
- `type="html"` keeps the body as markup. `eval="[(4, ref(...))]"` (seen in sale) and
  `Command.link(ref(...))` are equivalent in XML eval. Tag rules: [data-files.md](data-files.md),
  naming: [official XML guidelines](../../odoo-guidelines/guidelines/xml.md).
- Verify the model / report xmlids with `odoo_xmlid`, the fields with `odoo_model mail.template`.

Source: addons/sale/data/mail_template_data.xml:1-66, addons/auth_signup/data/mail_template_data.xml:1-42,
addons/mail/models/template_reset_mixin.py:17-22

## Sending a template from Python

```python
template = self.env.ref('my_module.mail_template_my_doc_send')
# queue one mail.mail per record (force_send=False uses the mail queue)
template.send_mail(record.id, force_send=False, email_layout_xmlid='mail.mail_notification_light')
template.send_mail_batch(records.ids, force_send=False)
# or post it in the chatter (recommended on mail.thread models)
record.message_post_with_source(template, subtype_xmlid='mail.mt_comment')
```

- `send_mail(res_id, force_send=False, raise_exception=False, email_values=None, email_layout_xmlid=False)`
  returns the `mail.mail` id; `send_mail_batch(res_ids, ...)` returns the `mail.mail` records. Both
  check `read` access on the target records; `email_layout_xmlid` falls back to the template's.
- `message_post_with_source(source_ref, *, render_values=None, message_type='notification', subtype_xmlid=False, subtype_id=False, **kwargs)`:
  `source_ref` = a `mail.template`, an `ir.ui.view`, or the xmlid of either (sale example:
  `addons/sale/models/sale_order.py:1727-1731`).

Source: addons/mail/models/mail_template.py:700-835, addons/mail/models/mail_thread.py:2738-2770,
addons/auth_signup/models/res_users.py:289

## Notification layouts

`email_layout_xmlid` names a QWeb template that wraps the rendered body. Core layouts:

| xmlid | Look |
|---|---|
| `mail.mail_notification_layout` | full layout (header with access button, footer); the default when a message has no layout |
| `mail.mail_notification_light` | light layout, most used by transactional mails |
| `mail.mail_notification_layout_with_responsible_signature` | full layout + signature of the record's `user_id` (primary view of the full layout) |

- Variables used by the layouts include `message`, `record`, `company`, `model_description`,
  `subtype`, `has_button_access`, `button_access`, `email_notification_force_header`,
  `email_notification_force_footer`, `email_add_signature`, `lang`.
- A custom layout should be a **primary** copy (`inherit_id="mail.mail_notification_layout" primary="True"`)
  like `mail_notification_layout_with_responsible_signature`; a non-primary inheriting template
  changes the base layout for every mail.

Source: addons/mail/data/mail_templates_email_layouts.xml:4-30, addons/mail/data/mail_templates_email_layouts.xml:94-100,
addons/mail/data/mail_templates_email_layouts.xml:177-186, addons/mail/models/mail_thread.py:4003

## QWeb views as message bodies

```xml
<!-- addons/mail/data/mail_templates_chatter.xml:52-60 -->
<template id="message_origin_link" technical_usage="mail_post_source">
    <p>... <t t-foreach="origin" t-as="o">
        <a href="#" t-att-data-oe-model="o._name" t-att-data-oe-id="o.id"> <t t-out="o.display_name"/></a>
    </t></p>
</template>
```

```python
# addons/sale/models/sale_order.py:2175-2179
move.message_post_with_source(
    "mail.message_origin_link",
    render_values={"self": move, "origin": move.line_ids.sale_line_ids.order_id},
    subtype_xmlid="mail.mt_note",
)
```

- New in 20: `<template technical_usage="...">` (`import_xml.rng`, `convert.py`); mail adds the
  value `mail_post_source`. The `mail_tracking` module logs a warning when an untagged view is used
  as a message source, so tag such templates.

Source: odoo/import_xml.rng:170, odoo/tools/convert.py:532-533, addons/mail/models/ir_ui_view.py:9,
addons/mail_tracking/models/mail_thread.py:36-42

## mail.activity.type

| Field | Notes |
|---|---|
| `name` (required, translated), `summary` (translated), `sequence`, `active` | |
| `icon` | **Material Symbols name** (`mail`, `phone`, `calendar_today`, `check`, `upload`, `warning`, `build`), not `fa-*` |
| `decoration_type` | `warning` / `danger` |
| `res_model` | selection of non-transient mail.thread models; empty = all models |
| `delay_count`, `delay_unit` (`days`/`weeks`/`months`), `delay_from` (`current_date`/`previous_activity`) | default deadline |
| `category` | `default`, `upload_file`, `phonecall` |
| `suggested_next_type_id` | M2o (new in 20): after "Done & Schedule Next" the scheduler opens prefilled with it |
| `previous_type_ids` | M2m, preceding activities |
| `mail_template_ids`, `default_user_id`, `default_role_id` (M2o `res.role`), `default_note` (Html, translated) | |
| `kpi_provider_visibility` | `none` / `own` / `all` |

```xml
<!-- addons/maintenance/data/mail_activity_type_data.xml -->
<data noupdate="1">
    <record id="mail_act_maintenance_request" model="mail.activity.type">
        <field name="name">Maintenance Request</field>
        <field name="summary">Maintenance Request</field>
        <field name="icon">build</field>
        <field name="res_model">maintenance.request</field>
    </record>
</data>
```

```xml
<!-- chaining in v20: one suggested follow-up type -->
<field name="suggested_next_type_id" ref="mail.mail_activity_data_call"/>
```

```python
# scheduling from code: addons/sale/models/sale_order.py:2488-2496
order.activity_schedule("mail.mail_activity_data_todo", user_id=order.user_id.id, note=...)
```

- Core types: `mail.mail_activity_data_email`, `_call`, `_meeting`, `_todo`,
  `_upload_document`, `_warning` (`addons/mail/data/mail_activity_type_data.xml`). Some master types
  cannot change `res_model` or be deleted (`_get_model_info_by_xmlid`).
- `odoo-bin upgrade_code` (19.5 material-symbols script) does not convert icon names stored in data:
  map them by hand using `odoo/upgrade_code/material_symbols_icons_mapping.py` (`FA_TO_MATERIAL`).

Source: addons/mail/models/mail_activity_type.py:9-90, addons/mail/models/mail_activity_type.py:163, addons/mail/data/mail_activity_type_data.xml,
addons/mail/models/mail_activity.py:668-687, addons/mail/models/mail_activity_mixin.py:428,
odoo/upgrade_code/19.5-00-material-symbols-icons.py:1-7

## mail.message.subtype and tracking hooks

| Field | Notes |
|---|---|
| `name` (required, translated), `description` (translated) | `description` is posted as message text |
| `res_model` | model the subtype applies to; empty = all models |
| `internal` | only internal users see these messages |
| `default` (default True) | checked by default when following |
| `hidden` | hidden in follower options |
| `parent_id` + `relation_field` | auto-subscription: following the parent record (e.g. a team) follows this subtype on children linked by `relation_field` |
| `sequence`, `track_recipients` | |

```xml
<!-- addons/maintenance/data/mail_message_subtype_data.xml (noupdate="1") -->
<record id="mt_req_status" model="mail.message.subtype">
    <field name="name">Status Changed</field>
    <field name="res_model">maintenance.request</field>
    <field name="default" eval="True"/>
    <field name="description">Status changed</field>
</record>
<record id="mt_cat_req_created" model="mail.message.subtype">
    <field name="name">Maintenance Request Created</field>
    <field name="res_model">maintenance.equipment.category</field>
    <field name="parent_id" ref="mt_req_created"/>
    <field name="relation_field">category_id</field>
</record>
```

Tracking hooks (renamed in 20; the v19 names are no longer called):

```python
# addons/maintenance/models/maintenance.py:254-258
def _track_log_get_default_subtype(self, track_init_values):
    self.ensure_one()
    if 'stage_id' in track_init_values:
        return self.env.ref('maintenance.mt_req_status')
    return super()._track_log_get_default_subtype(track_init_values)

# adapted from addons/project/models/project_task.py:1653-1664
def _track_template_parameters(self, tracked_fields):
    res = super()._track_template_parameters(tracked_fields)
    if 'stage_id' in tracked_fields and self[0].stage_id.mail_template_id:
        res['stage_id'] = (self[0].stage_id.mail_template_id, {
            'auto_delete_keep_log': False,
            'subtype_id': self.env['ir.model.data']._xmlid_to_res_id('mail.mt_note'),
        })
    return res

def _creation_subtype(self):
    return self.env.ref('project.mt_task_new')
```

- Base subtypes: `mail.mt_comment` (messages), `mail.mt_note` (internal notes), `mail.mt_activities`.
- `_track_log_get_default_body(track_init_values)` returns an extra body for the tracking message.

Source: addons/mail/models/mail_message_subtype.py:15-44, addons/mail/data/mail_message_subtype_data.xml:5-21,
addons/mail/models/mail_thread.py:509-515, addons/mail/models/mail_thread.py:628-790,
addons/maintenance/data/mail_message_subtype_data.xml, addons/sale/models/sale_order.py:2274-2280

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `t-esc` / `t-raw` in `body_html` or layouts | `t-out` (validator XML003) | odoo/addons/base/models/ir_qweb.py |
| `def _track_subtype(self, init_values)` | `def _track_log_get_default_subtype(self, track_init_values)` (not flagged by `odoo_validate` yet: grep with `odoo_grep`) | addons/mail/models/mail_thread.py:704 |
| `def _track_template(self, changes)` | `def _track_template_parameters(self, tracked_fields)` | addons/mail/models/mail_thread.py:778 |
| `triggered_next_type_id`, `chaining_type`, `suggested_next_type_ids` | `suggested_next_type_id` (M2o, validator ORM023) | addons/mail/models/mail_activity_type.py:51-54 |
| activity type `icon` = `fa-tasks` | Material Symbols name (`checklist`), converted by hand | addons/mail/models/mail_activity_type.py:43 |
| Cc partners only through `email_cc` | `partner_cc` (`partner_cc_ids` / `recipient_cc_ids`) | addons/mail/models/mail_template.py:65 |
| Report attachment content base64-encoded | `BinaryBytes` raw content | addons/mail/models/mail_template.py:379 |
| Untagged `<template>` used with `message_post_with_source` | `<template technical_usage="mail_post_source">` | addons/mail/models/ir_ui_view.py:9 |
| Server action `mail_post_method` | `state` `mail_post` or `log_note` (ORM024); see [cron-sequences-actions.md](cron-sequences-actions.md#iractionsserver) | addons/mail/models/ir_actions_server.py:23-37 |
