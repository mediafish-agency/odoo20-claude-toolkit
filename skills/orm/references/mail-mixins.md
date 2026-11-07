# Mail, activity, portal and UTM mixins (Odoo 20)

Python side of the communication mixins: which mixin to inherit, field tracking (rewritten hooks in
v20), `message_post` and friends, followers, the mail gateway, activities, aliases, `portal.mixin`
and `utm.mixin`. XML data (templates, activity types, subtypes, layouts) lives in
[mail-data.md](../../data-security/references/mail-data.md).

## Contents

- [Pick the mixin](#pick-the-mixin)
- [Minimal chatter-enabled model](#minimal-chatter-enabled-model)
- [Field tracking](#field-tracking)
- [Posting and logging messages](#posting-and-logging-messages)
- [Followers](#followers)
- [Mail gateway and class options](#mail-gateway-and-class-options)
- [Activities](#activities)
- [Aliases](#aliases)
- [portal.mixin](#portalmixin)
- [utm.mixin](#utmmixin)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## Pick the mixin

| `_inherit` | Module | Gives you |
|---|---|---|
| `mail.thread` | mail | chatter messages, followers, tracking, mail gateway (inherits `mail.track.mixin`, `bus.listener.mixin`) |
| `mail.activity.mixin` | mail | `activity_ids` + status fields, `activity_schedule()` API; add with `mail.thread` |
| `mail.track.mixin` | mail | **new in 20**: value tracking only (`tracking=` fields, `_track_*`), no messages |
| `mail.thread.blacklist` | mail | `email_normalized`, `is_blacklisted`, bounce counter (needs `_primary_email`) |
| `mail.thread.main.attachment` | mail | `message_main_attachment_id` set from posted attachments |
| `mail.thread.subject.suggested` | mail | **new in 20**: composer shows a suggested subject (used by `sale.order`, `crm.lead`) |
| `mail.tracking.duration.mixin` | mail | `duration_tracking` Json + rotting fields for a stage-like many2one |
| `mail.alias.mixin` / `mail.alias.mixin.optional` | mail | one alias per record (mandatory / only when `alias_name` is set) |
| `portal.mixin` | portal | `access_url`, `access_token`, `get_portal_url()` |
| `utm.mixin` | utm | `campaign_id`, `source_id`, `medium_id`, `utm_reference` filled from UTM cookies |

Add the module to `depends` (`mail`, `portal`, `utm`). Check what a mixin contributes to your
model with `odoo_model <model>` (merged fields and MRO) before overriding.

Source: addons/mail/models/mail_thread.py:139, addons/mail/models/mail_track_mixin.py:19,
addons/mail/models/mail_thread_subject_suggested.py, addons/mail/models/mail_thread_blacklist.py:29,
addons/mail/models/mail_thread_main_attachment.py:11, addons/mail/models/mail_tracking_duration_mixin.py:10,
addons/sale/models/sale_order.py:38

## Minimal chatter-enabled model

```python
from odoo import api, fields, models

class MaintenanceRequest(models.Model):
    _name = 'maintenance.request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Maintenance Request'

    name = fields.Char('Subjects', required=True)
    stage_id = fields.Many2one('maintenance.stage', tracking=True)
    user_ids = fields.Many2many('res.users', string='Technicians', tracking=True)

    def _creation_subtype(self):
        return self.env.ref('maintenance.mt_req_created')
```

```xml
<form>
    <sheet>
        <!-- fields -->
    </sheet>
    <chatter/>
</form>
```

- `<chatter/>` is the last child of `<form>`, after `<sheet>`. Supported attributes: `reload_on_post`,
  `reload_on_follower`, `reload_on_attachment`, `reload_on_activity`, `open_attachments`, plus `groups`.
  The activity button appears when the model inherits `mail.activity.mixin`. Not rendered in dialogs.
- `<div class="oe_chatter">` with `message_ids`/`message_follower_ids` widgets is the old markup
  (flagged by `odoo_validate` rule XML010).
- List/kanban: `<field name="activity_ids" widget="list_activity"/>` /
  `widget="kanban_activity"`, `<field name="activity_exception_decoration" widget="activity_exception"/>`.

Source: addons/maintenance/models/maintenance.py:240, addons/maintenance/views/maintenance_views.xml:134,
addons/mail/static/src/chatter/web/form_compiler.js:7, addons/mail/models/mail_thread.py:493

## Field tracking

Declare with the field parameter `tracking` (accepted on any model inheriting `mail.track.mixin`):

| Value | Meaning |
|---|---|
| `tracking=True` | tracked, display sequence 100 |
| `tracking=<int>` | tracked, lower numbers shown first (e.g. `amount_total ... tracking=4`) |
| `tracking=False` on a properties field | opt out of automatic properties tracking |

Initial values are collected in `cr.precommit` and processed just before commit: one
`message_type='tracking'` message per changed record. Values are rendered into the message body; `mail.tracking.value` records and
`mail.message.tracking_value_ids` are only stored when the separate **`mail_tracking`** module is
installed (depend on it before reading them).

Override hooks (v20 names):

| Hook | Purpose |
|---|---|
| `_track_log_get_default_subtype(self, track_init_values)` | return a `mail.message.subtype` to post (and notify followers) instead of a silent log |
| `_track_log_get_default_body(self, track_init_values)` | body text added above the tracking values |
| `_track_template_parameters(self, tracked_fields)` | `{'stage_id': (template, post_kwargs)}`: send a template when a field changes |
| `_creation_subtype()` / `_creation_message()` | subtype / body of the "created" message |
| `_track_set_log_author(partner)`, `_track_set_log_message(body)` | customize the next tracking message |
| `_track_add(...)`, `_track_record(records, fnames, ...)` | manual tracking / report line changes on a parent |
| `_track_discard()`, `_track_clear()` | drop pending tracking for `self` |

```python
def _track_log_get_default_subtype(self, track_init_values):
    self.ensure_one()
    if 'stage_id' in track_init_values:
        return self.env.ref('project.mt_task_stage')
    return super()._track_log_get_default_subtype(track_init_values)

def _track_template_parameters(self, tracked_fields):
    res = super()._track_template_parameters(tracked_fields)
    task = self[0]
    if 'stage_id' in tracked_fields and task.stage_id.mail_template_id:
        res['stage_id'] = (task.stage_id.mail_template_id, {
            'auto_delete_keep_log': False,
            'subtype_id': self.env['ir.model.data']._xmlid_to_res_id('mail.mt_note'),
        })
    return res
```

Context keys: `tracking_disable` (no tracking, no auto-subscribe), `mail_notrack` (no tracking),
`mail_create_nolog` (no "created" message), `mail_create_nosubscribe` (creator not added as follower).

Source: addons/mail/models/mail_track_mixin.py:39, addons/mail/models/mail_track_mixin.py:437,
addons/mail/models/mail_thread.py:550-790, addons/mail/models/mail_thread.py:110,
addons/project/models/project_task.py:1653, addons/mail_tracking/models/mail_message.py,
addons/mail_tracking/models/mail_tracking_value.py, addons/mail/models/mail_message.py:234

## Posting and logging messages

`message_post` is keyword-only:

```python
def message_post(self, *, body='', subject=None, message_type='notification',
                 email_from=None, author_id=None, parent_id=False,
                 subtype_xmlid=None, subtype_id=False,
                 partner_ids=None, partner_cc_ids=None, outgoing_email_to=False,
                 incoming_email_to=False, incoming_email_cc=False,
                 attachments=None, attachment_ids=None, body_is_html=False,
                 tracking_values=None, **kwargs)
```

- Single record only (`ensure_one`); not on new records. For user notifications without a document
  use `message_notify(...)`; `message_type='user_notification'` raises.
- `body`: a `str` is **escaped**; pass `markupsafe.Markup` (or `self.env._()` result with
  `Markup` args) for HTML. `body_is_html=True` is for RPC only.
- `subtype_xmlid='mail.mt_comment'` notifies followers; default (nothing given) is `mail.mt_note`
  (internal note).
- `partner_ids` / `partner_cc_ids` / `attachment_ids`: lists of **ints**. `attachments`: list of
  `(name, raw_bytes)` or `(name, raw_bytes, info_dict)` (not base64).
- `tracking_values` only with `message_type='tracking'`. `model`, `res_id`, `subtype` kwargs are
  rejected; other kwargs become `mail.message` values or notification parameters.

| Helper | Use |
|---|---|
| `record._message_log(body=..., message_type='notification', ...)` | note without notification; `_message_log_batch(bodies={id: body})` for many |
| `records.message_post_with_source(source_ref, render_values=..., subtype_xmlid=...)` | render a QWeb view xmlid or a `mail.template` record and post |
| `records.message_mail_with_source(source_ref, ...)` | same, sent as mass mail |
| `self.env['mail.thread'].message_notify(partner_ids=..., body=..., subject=...)` | inbox/email notification not linked to a thread |

```python
order.message_post(body=self.env._("Invoice %s paid", name))
invoice.message_post_with_source(
    "mail.message_origin_link",
    render_values={"self": invoice, "origin": order},
    subtype_xmlid="mail.mt_note",
)
```

Source: addons/mail/models/mail_thread.py:2270, addons/mail/models/mail_thread.py:2647,
addons/mail/models/mail_thread.py:2738, addons/mail/models/mail_thread.py:2829,
addons/mail/models/mail_thread.py:3007, addons/sale/models/account_move.py:189,
addons/sale/wizard/sale_make_invoice_advance.py:220, addons/mail/data/mail_message_subtype_data.xml

## Followers

| API | Notes |
|---|---|
| `records.message_subscribe(partner_ids=None, subtype_ids=None)` | public; checks `write` (or `read` when subscribing yourself); skips inactive partners |
| `records._message_subscribe(partner_ids, subtype_ids, customer_ids=None)` | no access check, for trusted code |
| `records.message_unsubscribe(partner_ids=None)` | checks `write` unless removing yourself |
| `message_partner_ids` | computed/searchable followers; usable in `ir.access` domains |
| `_message_auto_subscribe_followers(updated_values, default_subtype_ids)` | override to auto-follow on write; default follows a tracked `user_id` many2one to `res.users` |

The creator follows automatically (unless `mail_create_nosubscribe`). Example access row using
followers: `addons/maintenance/security/ir.access.csv:5`.

Source: addons/mail/models/mail_thread.py:4877, addons/mail/models/mail_thread.py:4903,
addons/mail/models/mail_thread.py:4932, addons/mail/models/mail_thread.py:4950

## Mail gateway and class options

| Class attribute | Default | Meaning |
|---|---|---|
| `_mail_post_access` | `'write'` | access needed on the document to post (`'read'` lets readers chat) |
| `_mail_flat_thread` | `True` | messages without parent attach to the first message |
| `_mail_thread_customer` | `False` | auto-follow the customer when they are a recipient |
| `_primary_email` | `'email'` | field holding the email, for alias-created records and blacklist |

Incoming email hooks (call `super()`): `message_new(self, msg_dict, custom_values=None)`
(`@api.model`, creates the record) and `message_update(self, msg_dict, update_vals=None)`. Partner
fields used for recipients default to `partner_id` / `partner_ids` (`_mail_get_partner_fields`).

Source: addons/mail/models/mail_thread.py:145-148, addons/mail/models/mail_thread.py:1571,
addons/mail/models/mail_thread.py:1604, addons/project/models/project_task.py:1768,
addons/mail/models/models.py:164

## Activities

`mail.activity.mixin` adds `activity_ids`, `activity_state` (computed, with `compute_sql`),
`activity_user_id`, `activity_type_id`, `activity_date_deadline`, `my_activity_date_deadline`,
`activity_summary`, `activity_exception_decoration`, `activity_exception_icon`, `activity_type_icon`,
`activity_plans_ids` (most `groups="base.group_user"`).

```python
order.activity_schedule(
    'mail.mail_activity_data_todo',          # activity type xmlid
    date_deadline=fields.Date.context_today(self),  # a date, not a datetime
    user_id=order.user_id.id,
    note=self.env._("Upsell %(order)s", order=order._get_html_link()),
)
records.activity_feedback(['my_module.mail_act_approval'], feedback="Done")
records.activity_unlink(['mail.mail_activity_data_todo'])
records.activity_reschedule(['my_module.mail_act_approval'], date_deadline=new_date)
```

- Signature: `activity_schedule(act_type_xmlid='', date_deadline=None, summary='', note='',
  activity_user_id_fname='', **act_values)`; `activity_user_id_fname` (new) names a `res.users`
  field path on the record used as assignee.
- `activity_feedback/unlink/reschedule/search` only touch `automated` activities by default
  (`only_automated=True`).
- Context `mail_activity_automation_skip` turns all of them into no-ops (imports).
- Activity types are data: see [mail-data.md](../../data-security/references/mail-data.md).

Source: addons/mail/models/mail_activity_mixin.py:49-100, addons/mail/models/mail_activity_mixin.py:428,
addons/mail/models/mail_activity_mixin.py:465-520, addons/sale/models/sale_order.py:2488

## Aliases

| Mixin | Alias lifecycle |
|---|---|
| `mail.alias.mixin` | `_inherits = {'mail.alias': 'alias_id'}`, `alias_id` required; existing rows get aliases at install through the field's `init_storage=` hook |
| `mail.alias.mixin.optional` | `alias_id` optional, created only when `alias_name` is given |

Override `_alias_get_creation_values()` to choose the model receiving emails and the defaults:

```python
def _alias_get_creation_values(self):
    values = super()._alias_get_creation_values()
    values['alias_model_id'] = self.env['ir.model']._get('project.task').id
    if self.id:
        values['alias_defaults'] = defaults = ast.literal_eval(self.alias_defaults or "{}")
        defaults['project_id'] = self.id
    return values
```

The target model must inherit `mail.thread` (and usually override `message_new`).

Source: addons/mail/models/mail_alias_mixin.py:10-50, addons/mail/models/mail_alias_mixin_optional.py:17,
addons/mail/models/mail_alias_mixin_optional.py:186, addons/project/models/project_project.py:872,
addons/maintenance/models/maintenance.py:547

## portal.mixin

| Member | Notes |
|---|---|
| `access_url` | compute; override `_compute_access_url` (call `super()`) to return `/my/<things>/<id>` |
| `access_token` | `copy=False`; created lazily by `_portal_ensure_token()` |
| `get_portal_url(suffix=None, report_type=None, download=None, query_string=None, anchor=None, share_token=True)` | URL with token |
| `_get_share_url(redirect=False, signup_partner=False, pid=None, share_token=True)` | link used in emails |
| `_get_access_action(access_uid=None, force_website=False)` | portal users are redirected to the portal page |

```python
def _compute_access_url(self):
    super()._compute_access_url()
    for order in self:
        order.access_url = f"/my/orders/{order.id}"
```

Controllers use `CustomerPortal._document_check_access(model_name, document_id, access_token=None)`:
it tries `check_access('read')` and falls back to a constant-time token comparison, returning the
record **sudoed**; keep everything after it read-only or re-check. Portal read rights still come from
`ir.access` rows for `base.group_portal` (e.g. `[('partner_id', 'child_of', [user.commercial_partner_id.id])]`).

Source: addons/portal/models/portal_mixin.py:9-140, addons/portal/controllers/portal.py:1090,
addons/sale/models/sale_order.py:1217, addons/sale/security/ir.access.csv:29

## utm.mixin

- Fields: `campaign_id` (`utm.campaign`), `source_id` (`utm.source`), `medium_id` (`utm.medium`),
  all `index='btree_not_null'`, and **new in 20** `utm_reference` (Reference to any non-transient model).
- `default_get` reads the `odoo_utm_*` cookies from the current request (strings are
  found-or-created), except for salesmen (`sales_team.group_sale_salesman`) outside superuser mode.
- The list of tracked params is `self.env['utm.mixin'].tracking_fields()`; extend it on `utm.mixin`
  itself, not on your model.

Source: addons/utm/models/utm_mixin.py:15-90

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `_track_subtype(self, init_values)` | `_track_log_get_default_subtype(self, track_init_values)` | addons/mail/models/mail_thread.py:704 |
| `_track_template(self, changes)` | `_track_template_parameters(self, tracked_fields)` | addons/mail/models/mail_thread.py:778 |
| `_track_get_default_log_message(tracked_fields)` | `_track_log_get_default_body(track_init_values)` | addons/mail/models/mail_thread.py:692 |
| `_track_set_author(author)` | `_track_set_log_author(author)` | addons/mail/models/mail_thread.py:569 |
| `_message_track(...)` | `_mail_track(...)` in `mail.track.mixin` | addons/mail/models/mail_track_mixin.py:349 |
| `mail.tracking.value` always present in `mail` | defined by module `mail_tracking` | addons/mail_tracking/__manifest__.py |
| tracking messages with `message_type='notification'` | `message_type='tracking'` | addons/mail/models/mail_message.py:234 |
| `message_post/_message_log(tracking_value_ids=[...])` | `tracking_values=[vals, ...]` with `message_type='tracking'` | addons/mail/models/mail_thread.py:2277 |
| `activity_schedule(xmlid, ..., **act_values)` only | extra `activity_user_id_fname='user_id'` option | addons/mail/models/mail_activity_mixin.py:428 |
| `<div class="oe_chatter">...</div>` | `<chatter/>` (XML010) | addons/mail/static/src/chatter/web/form_compiler.js |
| `_init_column('alias_id')` override | field `init_storage=` callable | addons/mail/models/mail_alias_mixin.py:19 |

None of the tracking renames is covered by `odoo_upgrade_code` or `odoo_validate`: grep your addons
for `_track_subtype` / `_track_template(` when porting.
