# Odoo 19 -> 20 porting matrix

Layer-by-layer list of what an addon written for Odoo 19 (or older) must change for Odoo 20.
Each row: old pattern, Odoo 20 replacement, what rewrites it automatically ("manual" = nothing),
the `odoo_validate` rule that detects it, and the v20 source proving the change. Use it after the
`upgrade_code` pass ([upgrade-code.md](upgrade-code.md)); removed modules are in
[removed-modules.md](removed-modules.md). Stable-branch rules: [stable.md](../../odoo-guidelines/guidelines/stable.md).

## Contents

- Workflow
- Python ORM
- Security (ir.access)
- HTTP / controllers / external API
- Data files (XML / CSV) and models data
- Views and search
- QWeb and reports
- Mail
- JS / OWL
- Public / website JS
- POS
- SCSS and icons
- Tests
- Manifest
- CLI / runtime

## Workflow

1. `odoo_upgrade_code(path)` dry run -> review diff -> `apply=true` (scripts listed in "Automated by").
2. `odoo_validate(path)` -> fix every rule id below that still fires (the "manual" rows).
3. `odoo_test(modules)` on a throwaway database; then Hoot / tours (see testing skill).

"19.4 ir-access" etc. abbreviate the scripts in `odoo/upgrade_code/` (`19.4-00-ir-access.py`).

## Python ORM

| v19 / older | Odoo 20 | Automated by | Rule | v20 source |
|---|---|---|---|---|
| `env['ir.config_parameter'].get_param(k, d)` / `set_param(k, v)` | typed `get_str/get_int/get_float/get_bool(k, default)`, `set_str/set_int/set_float/set_bool(k, v)` | manual | ORM001 | odoo/addons/base/models/ir_config_parameter.py:66-124 |
| `from odoo.tools import ormcache`, `tools.ormcache` | `from odoo.api import ormcache` / `@api.ormcache(...)` (tools import warns) | manual | ORM003 | odoo/api/__init__.py:5 |
| `@tools.ormcache_context(..., keys=(...))` | `@api.ormcache('self.env.context.get("lang")', ...)` | manual | ORM002 | odoo/orm/cache.py |
| `self.env.registry.clear_cache('x')`, `clear_all_caches()`, `registry.signal_changes` | `self.env.transaction.invalidate_ormcache('x')`; declare `_clear_cache_name` / `_clear_cache_on_fields` on the model; caches are per transaction | 19.4 ormcache (only the `registry.clear_cache` text) | ORM004 | odoo/orm/environments.py:833, odoo/orm/models.py:486-488 |
| `_sql_constraints = [(name, sql, msg)]` | `_name_uniq = models.Constraint('UNIQUE(name)', msg)`, `models.Index(...)`, `models.UniqueIndex(...)` | 18.1 sql-constraint | ORM012 | odoo/orm/table_objects.py:88-221 |
| `_rec_names_search = ['name', 'ref']` | tuple `('name', 'ref')` | 19.5 rec_names (files under a `models/` dir, 4-space indent, literal strings) | ORM011 | odoo/upgrade_code/19.5-00-tuple-rec_names_search.py |
| `read_group(domain, fields, groupby, lazy=...)` returning dicts | `read_group(domain, groupby, aggregates, having, offset, limit, order)` returns tuples (same as `_read_group`); UI-style dicts: `formatted_read_group` | manual | ORM013 | odoo/orm/models.py:1932, addons/web/models/models.py:1022 |
| `records.toggle_active()`, `name="toggle_active"` buttons | `action_archive()` / `action_unarchive()` | manual | ORM005 | odoo/orm/models.py:5282-5293 |
| `self._check_recursion()`, `_check_m2m_recursion(f)` | `self._has_cycle(field_name)` in the constraint | manual | ORM006 | odoo/orm/models.py:5125 |
| `@api.deprecated`, `api.Self` | `odoo.tools.func.deprecated`, `typing.Self` | manual | ORM007 | odoo/tools/func.py:267-270 |
| `_table_query = "SELECT ..."` | `@property def _table_sql(self) -> SQL` | manual | ORM008 | odoo/orm/models.py:531 |
| `name_get()` | `@api.depends(...) _compute_display_name` | manual | ORM009 | odoo/orm/models.py |
| `fields.X(group_operator='sum')` | `aggregator='sum'` (no longer mapped) | manual | ORM010 | odoo/orm/fields.py |
| `from odoo.osv import expression` | `from odoo.fields import Domain` (`Domain.AND/OR`, `&`, `|`, `~`) | manual | ORM016 | odoo/fields/__init__.py:20, odoo/orm/domains.py |
| `from odoo.tools import Query, create_index, pycompat, convert_xml_import ...` | `odoo.models.Query`, `odoo.tools.sql`, `odoo.tools.convert` | manual | ORM017 | odoo/models/__init__.py:26, odoo/tools/__init__.py |
| `env.flush_query(...)` | `env.execute_query(SQL(...))` (flushes what it needs) | manual | ORM018 | odoo/orm/environments.py:548 |
| `self._cr`, `self._uid`, `self._context` | `self.env.cr`, `self.env.uid`, `self.env.context` (properties still exist, deprecated) | 18.5 deprecated-properties | - | odoo/orm/models.py:5396-5410 |
| `attachment.datas` | `attachment.raw` (bytes); Binary field values are `BinaryValue` | manual | ORM014 | odoo/addons/base/models/ir_attachment.py, odoo/tools/binary.py:9 |
| `import pytz` / `xlwt` | `zoneinfo.ZoneInfo`, `self.env.tz`; xlsxwriter/openpyxl | manual | ORM015 | requirements.txt, odoo/orm/environments.py:315 |
| `load_manifest(name)` | `Manifest.for_addon(name)` / `get_manifest(name)` | manual | ORM019 | odoo/modules/module.py:338, 507 |
| `record.get_formview_action()` | `get_record_default_action()` | manual | ORM020 | odoo/addons/base/models/ir_ui_view.py:3307 |
| (new) | field params `compute_sql=`, `init_storage=`; `models.CachedModel` | - | - | odoo/orm/fields.py:251, 299-305; odoo/orm/models_cached.py |

Check merged fields and overrides with `odoo_model` / `odoo_method` before porting an override.

## Security (ir.access)

| v19 / older | Odoo 20 | Automated by | Rule | v20 source |
|---|---|---|---|---|
| `security/ir.model.access.csv` (`perm_read,...`) | `security/ir.access.csv`, header `id,name,model_id,group_id/id,operation,domain`, `model_id` = model name, `operation` in `crud`-ordered subsets; last in manifest `data` | 19.4 ir-access (review!) | SEC002, MAN002 | addons/sale/security/ir.access.csv, odoo/addons/base/models/ir_access.py:71-120 |
| `<record model="ir.rule">` with `groups` | `ir.access` row with that group, operations and `domain` (permissions are OR-ed) | 19.4 ir-access | SEC001 | odoo/addons/base/models/ir_access.py |
| global `ir.rule` (no group) | `ir.access` row without group (restriction, AND-ed) | 19.4 ir-access | SEC001 | odoo/addons/base/models/ir_access.py |
| ACL row without group | row for `base.group_everyone` | 19.4 ir-access | - | odoo/addons/base/security/base_groups.xml:92 |
| `check_access_rights(op)` + `check_access_rule(op)` | `records.check_access(op)` (raises) / `has_access(op)` (bool) | manual | SEC003 | odoo/orm/models.py:3443, 3464 |
| `_filter_access_rules(op)` / `_python` | `_filtered_access(op)` | manual | SEC004 | odoo/orm/models.py:3506 |
| override `_check_access(...)` | override `_access_domain(self, operation) -> Domain` | manual | SEC005 | odoo/orm/models.py:3603, addons/mail/models/mail_mail.py |
| `res.groups.model_access`, `rule_groups` | `access_ids` (One2many `ir.access`) | manual | SEC006 | odoo/addons/base/models/res_groups.py:30 |
| deactivate another module's `ir.rule` | `<record id="other.xmlid" model="ir.access"><field name="active" eval="False"/></record>` | manual | - | odoo/addons/base/models/ir_access.py:72 |

Verify the effective rows with `odoo_access(model)`; recipes live in the data-security skill.

## HTTP / controllers / external API

| v19 / older | Odoo 20 | Automated by | Rule | v20 source |
|---|---|---|---|---|
| `from odoo.http import content_disposition, Stream, ...` | `from odoo.http.stream import Stream, content_disposition`; `odoo.http` exports `request`, `Response`, `Controller`, `route` | manual | HTTP001 | odoo/http/__init__.py, odoo/http/stream.py:34, 53 |
| `request.session.authenticate(...)`, `session.finalize/touch` | `from odoo.http import session as http_session`; `http_session.authenticate(request.session, env, credential)`, `finalize`, `logout`, `touch` | manual | HTTP002 | odoo/http/session.py:225-303 |
| `odoo.service.db`, `odoo.service.security` | `odoo.modules.db`; `odoo.http.session.check(session, request_or_env)` | manual | HTTP003 | odoo/modules/db.py, odoo/http/session.py:409 |
| `@route(type='json')` | `type='jsonrpc'` (deprecated alias still accepted), API endpoints `type='json2', auth='bearer', bearer_scope='rpc'` | 18.1 route-jsonrpc (`controllers/*.py`, only `type="json",` with a trailing comma) | HTTP004 | odoo/http/routing_map.py:189-206, addons/api_doc/controllers/api_doc.py:49 |
| `def _auth_method_x(cls)` | `def _auth_method_x(cls, routing)` | manual | HTTP005 | odoo/addons/base/models/ir_http.py:319-374 |
| XML-RPC / JSON-RPC external clients | JSON-2: `POST /json/2/<model>/<method>`, `Authorization: Bearer <api key>`, body `{ids, context, ...kwargs}` (old protocols deprecated) | manual | - | addons/rpc/controllers/json2.py |

## Data files (XML / CSV) and models data

| v19 / older | Odoo 20 | Automated by | Rule | v20 source |
|---|---|---|---|---|
| `<field name="x" type="base64" file="m/p.png"/>` | `type="bytes"` | 19.3 base64-in-xml | XML006 | odoo/tools/convert.py:139-145 |
| `pytz.timezone(tz).localize(dt)` in XML `eval` | `pytz` is a ZoneInfo shim (no `.localize`); compute in Python | manual | XML014 | odoo/tools/convert.py:59 |
| `res.bank` records / `bank_id` | removed; `res.partner.bank.bank_name`, `bank_bic` | manual | ORM022 | odoo/addons/base/models/res_partner_bank.py:59-67 |
| `acc_number`, `acc_holder_name`, `acc_type` | `account_number`, `holder_name`, `account_type` | manual | ORM021 | odoo/addons/base/models/res_partner_bank.py:24-36 |
| `res.partner.company_type` | removed; `is_company` is computed (stored) from `commercial_partner_id == self` and `has_vat` | manual | - | odoo/addons/base/models/res_partner.py:371, 950-960 |
| `l10n_*/data/template/account.group-<coa>.csv` | `account.group` removed: groups become inactive `account.account` rows with `parent_id` | 19.3 account-groups (listed Odoo CoAs only) | - | addons/account/models/account_account.py:134 |
| `account.report.line` `foldable` boolean | `foldability` selection (dropped when the compute matches) | 19.3 account-report-foldable | - | addons/account/models/account_report.py:443 |

## Views and search

| v19 / older | Odoo 20 | Automated by | Rule | v20 source |
|---|---|---|---|---|
| `<tree>`, `view_mode="tree,form"` | `<list>`, `list` | 17.5 tree-to-list | XML001 | odoo/addons/base/rng/list_view.rng |
| `attrs="{...}"`, `states="..."` | `invisible="state != 'draft'"`, `readonly=`, `required=`, `column_invisible=` | manual | XML002 | odoo/addons/base/models/ir_ui_view.py:508 |
| kanban `<t t-name="kanban-box">` | `<templates><t t-name="card">...</t></templates>` (+ `menu`); reusable `card` views via `<kanban card_id="%(x)d">` | manual | XML009 | addons/web/static/src/views/card/card_arch_parser.js, odoo/addons/base/models/ir_ui_view.py:1791 |
| `<div class="oe_chatter">...` | `<chatter/>` | manual | XML010 | addons/mail/static/src/chatter/web/form_compiler.js |
| calendar `date_delay=` | `date_stop=` (+ `all_day`) | manual | XML008 | odoo/addons/base/rng/calendar_view.rng |
| search `<filter date="d" start_month=... end_year=...>` | attributes removed; `end_date=`, `default_period=` | 20.0 search-date-filters | XML007 | odoo/addons/base/rng/common.rng:377-378 |
| domains with `context_today()` arithmetic | dynamic dates `'today -30d'`, `'=week_start'`, `'now -24H'` | 18.5 domain-dynamic-dates | XML013 | odoo/tools/date_utils.py |
| `widget="selection_badge"`, `widget="remaining_days"` | `badges_selection`, `relative_date` | manual | XML015 | addons/web/static/src/views/fields/badges_selection/badges_selection_field.js:101 |
| field registry keys `kanban.many2many_tags`, `kanban.many2one_avatar`, ... | `card.*` | manual | JS009 | addons/web/static/src/views/fields/many2many_tags/kanban_many2many_tags_field.js:17 |
| `<button icon="fa-star"/>` | `<button icon="star" icon_class="oi-filled"/>` (Material Symbols names) | 19.5 material-symbols | XML005 | addons/web/static/src/views/view_button/view_button.js |

Check the combined arch with `odoo_views(resolve="db")` after porting an inherited view.

## QWeb and reports

| v19 / older | Odoo 20 | Automated by | Rule | v20 source |
|---|---|---|---|---|
| server `t-esc`, `t-raw` | `t-out` (pass `Markup` for trusted HTML); `t-esc`/`t-raw` are not directives any more | manual (owl3-migration only touches `static/`) | XML003 | odoo/addons/base/models/ir_qweb.py:2459 |
| `<t t-call="x"><t t-set="a" t-value="v"/></t>` | `<t t-call="x" a="v" b.f="literal" c.translate="Text"/>`; body `t-set` no longer reaches the callee | 19.1 t-call (server XML) | XML012 | odoo/upgrade_code/19.1-00-t-call.py |
| `t-call-options` | `t-options` | manual | XML011 | odoo/addons/base/models/ir_qweb.py |
| `<i class="fa fa-user"/>` | `<i class="oi" data-icon="person"/>` | 19.5 material-symbols | XML004 | odoo/upgrade_code/material_symbols_icons_mapping.py |
| `ir.actions.report.report_file` | removed (`save_as_attachment` exists) | manual | REP002 | odoo/addons/base/models/ir_actions_report.py:65 |
| `external_layout_bold/boxed/striped` | `standard`, `bubble`, `wave`, `folder`, `center`, `dual`, `lines`, `compact` | manual | REP003 | addons/web/views/report_templates.xml |
| `_run_wkhtmltopdf`, `get_wkhtmltopdf_state` | `get_pdf_engine_state(engine)`; engines `base_report_wkhtmltox` (auto-install) / `base_report_paper_muncher`; per report `report_type='qweb-pdf-<engine>'` | manual | REP001 | odoo/addons/base/models/ir_actions_report.py:170, 796; addons/base_report_wkhtmltox/models/ir_actions_report.py:131 |

## Mail

| v19 / older | Odoo 20 | Automated by | Rule | v20 source |
|---|---|---|---|---|
| `mail.activity.type` `triggered_next_type_id`, `chaining_type`, `suggested_next_type_ids` | `suggested_next_type_id` (Many2one) | manual | ORM023 | addons/mail/models/mail_activity_type.py |
| `ir.actions.server.mail_post_method` | states `mail_post` / `log_note` | manual | ORM024 | addons/mail/models/ir_actions_server.py:28 |
| overrides of `_track_subtype(init_values)`, `_track_template(changes)`, `_track_set_author(author)`, `_message_track(...)` (silently never called) | `_track_log_get_default_subtype(track_init_values)`, `_track_template_parameters(tracked_fields)`, `_track_set_log_author(author)`, `_mail_track(...)` (mail_track_mixin) | manual | ORM025 | addons/mail/models/mail_thread.py:569, 704, 778; addons/mail/models/mail_track_mixin.py:349 |
| `mail.activity.type` `<field name="icon">fa-tasks</field>` | Material Symbols name, e.g. `checklist`, `phone` | manual | XML016 | addons/mail/models/mail_activity_type.py:43, addons/mail/data/mail_activity_type_data.xml:7 |

## JS / OWL

| v19 / older | Odoo 20 | Automated by | Rule | v20 source |
|---|---|---|---|---|
| `static props = {...}`, `static defaultProps` | `props = useProps({ a: t.string().optional(def) })` (static ones throw) | manual | JS001 | addons/web/static/src/owl2/owl3_compatibility_layer.js, addons/web/static/src/views/fields/badge/badge_field.js |
| `useState(...)`, `reactive(...)` | `proxy(...)` | owl3-migration | JS002 | addons/web/static/lib/owl/owl.js:62 (exports) |
| `useEffect(fn, () => [deps])` | `useEffect(fn)` auto-tracks; explicit deps: `useLayoutEffect` from `@web/owl2/utils` or `useOnChange(() => [deps], cb)` | owl3-migration (renames every `useEffect` to `useLayoutEffect`) | JS004 | addons/web/static/src/owl2/utils.js:14 |
| `onWillRender`, `useEnv`, `useSubEnv` from `@odoo/owl` | import from `@web/owl2/utils` | owl3-migration | JS003 | addons/web/static/src/owl2/utils.js:13-16 |
| `useRef("x")` + `t-ref="x"` | `signal.ref()` + `t-ref="this.x"` | manual (owl3-migration imports `useRef` from `@web/owl2/utils`, which does not export it, and rewrites `t-ref` to an unregistered `t-custom-ref`) | JS002 | addons/web/static/src/owl2/utils.js |
| `useExternalListener(target, ev, fn)` | `useListener(target, ev, fn)` | manual (script imports it from `@web/owl2/utils`: not exported) | JS002 | addons/web/static/lib/owl/owl.js |
| `onRendered`, `useComponent`, `useChildSubEnv` | no direct equivalent (`useScope()`) | manual (script imports from `@web/owl2/utils`: not exported) | JS002, JS003 | addons/web/static/src/owl2/utils.js |
| OWL `t-esc` | `t-out` | owl3-migration | OWL001 | odoo/upgrade_code/owl3-migration.py:852 |
| OWL `t-raw` | `t-out` with `markup()` | manual | OWL002 | addons/web/static/lib/owl/owl.js |
| `t-slot="x"` | `t-call-slot="x"` | owl3-migration | OWL003 | odoo/upgrade_code/owl3-migration.py:1259 |
| `t-portal="sel"` | `<Portal target="...">` or compat `t-custom-portal` | owl3-migration (to `t-custom-portal`) | OWL004 | addons/web/static/src/owl2/owl3_compatibility_layer.js:239-266 |
| `t-model="state.x"` | `t-model` on signals (compat: `t-custom-model`) | owl3-migration (to `t-custom-model`, not registered in v20: verify) | - | addons/web/static/src/owl2/owl3_compatibility_layer.js:14 |
| bare `props.x`, `state.y` in component templates | `this.props.x`, `this.state.y` | owl3-migration | OWL005 | odoo/upgrade_code/owl3-migration.py:1159 |
| `useService("ui")`, `useService("notification")`, ... | `usePlugin(UIPlugin)`, `usePlugin(NotificationPlugin)` (`useService` still works) | owl3-migration (map is partly stale: `action` -> real class `ActionPlugin`, `sortable` path is `@web/core/utils/sortable_plugin`) | - | addons/web/static/src/webclient/actions/action_plugin.js:1983, addons/web/static/src/core/utils/sortable_plugin.js:16 |
| `env.debug`, `env.isSmall` | `usePlugin(DebugModePlugin)` / `odoo.debug`; `useService("ui").isSmall` | manual | JS008 | addons/web/static/src/env.js:17-23, addons/web/static/src/core/debug_mode_plugin.js:4 |
| `useChildRef`, `useForwardRefToParent`, `useRefListener` | signal ref prop (`t.signal(t.ref())`), `useListener` | manual | JS013 | addons/web/static/src/core/utils/hooks.js |
| `odoo.define(...)` modules | ES modules (`static/src`, `static/tests` are transpiled automatically) | manual | JS016 | odoo/tools/js_transpiler.py |

Find registries and patch targets with `odoo_js`; check bundles with `odoo_assets`.

## Public / website JS

| v19 / older | Odoo 20 | Automated by | Rule | v20 source |
|---|---|---|---|---|
| `publicWidget.Widget.extend({...})`, `@web/legacy/...` | `class X extends Interaction` registered in `registry.category("public.interactions")` | manual | JS005 | addons/web/static/src/public/interaction.js:19, addons/website/static/src/interactions/full_screen_height.js:96 |
| `$(...)`, `$.ajax`, `.modal('show')` | DOM APIs, `rpc`, Interaction helpers (jQuery not shipped) | manual | JS006, JS017 | addons/web/__manifest__.py |
| `t-on-click.withTarget` in Interactions | read `ev.currentTarget` | manual | JS014 | addons/web/static/src/public/colibri.js |
| website snippet options (old editor) | `html_builder` options: `registry.category("builder-options")` | manual | - | addons/website/static/src/builder/plugins/options/clickable_card_option.js |

## POS

| v19 / older | Odoo 20 | Automated by | Rule | v20 source |
|---|---|---|---|---|
| `register_payment_method("x", Cls)` | `registry.category("pos_payment_providers").add("x", Cls)` | manual | JS010 | addons/point_of_sale/static/src/app/utils/payment/payment_interface.js:10 |
| POS services | plugins (`point_of_sale/static/src/app/plugins/*_plugin.js`); `patch(PosStore.prototype, { async setup() {...} })` still valid | manual | - | addons/pos_restaurant/static/src/app/services/pos_store.js:13 |
| removed POS bridge modules (`pos_restaurant_adyen`, ...) | merged into the payment module | - | - | [removed-modules.md](removed-modules.md) |

## SCSS and icons

| v19 / older | Odoo 20 | Automated by | Rule | v20 source |
|---|---|---|---|---|
| `.fa-star`, `.fa` selectors | `.oi[data-icon='star']`, `.oi-filled`, `.oi-spin`, `.oi` | 19.5 material-symbols | SCSS001 | addons/web/static/src/webclient/icons.scss |
| `icon: "fa-star"`, `"fa fa-star"` strings in JS / Python dicts | Material names (`"star"`), `iconClass: "oi-filled"` where needed | 19.5 material-symbols | JS015, OWL006 | odoo/upgrade_code/19.5-00-material-symbols-icons.py:473-510 |
| `$o-touch-btn-padding`, `$o-touch-btn-with-icon-padding` | removed | manual | SCSS002 | addons/web/static/src/scss/primary_variables.scss |

## Tests

| v19 / older | Odoo 20 | Automated by | Rule | v20 source |
|---|---|---|---|---|
| `SingleTransactionCase` | `TransactionCase` / `BaseCommon` | manual | TEST001 | odoo/tests/common.py:1305 |
| `assertQueriesContain`, `registry_enter_test_mode()` | `assertQueries`, `with self.registry_test_mode():` | manual | TEST002 | odoo/tests/common.py:851, 1079 |
| `odoo.tools.test_reports` | `odoo.tests.reports` | manual | TEST003 | odoo/tests/reports.py |
| `BaseCommon` tests run as superuser | run as `test_user`; set `_test_user_groups` | manual | - | odoo/addons/base/tests/common.py:17-104 |
| QUnit tests | Hoot `*.test.js` | manual | JS007 | addons/web/static/lib/hoot/hoot.js |
| `makeMockEnv`, `asyncStep`, `waitForSteps` | `makeTestApp`, `expect.step`, `expect.waitForSteps` | manual | JS012 | addons/web/static/tests/web_test_helpers.js |
| `@web_tour/js/...` imports, tour keys `name`/`wait_for` | `@web_tour/tour_utils` etc.; only `steps` + `url` | manual | JS011 | addons/web_tour/static/src/tour_plugin.js:55-60 |

Details: [python-tests.md](../../testing/references/python-tests.md),
[hoot.md](../../testing/references/hoot.md), [tours.md](../../testing/references/tours.md).

## Manifest

| v19 / older | Odoo 20 | Automated by | Rule | v20 source |
|---|---|---|---|---|
| `demo_xml`, `init_xml`, `update_xml` | `data`, `demo` | manual | MAN001 | odoo/modules/module.py |
| `'security/ir.model.access.csv'` in `data` | `'security/ir.access.csv'`, listed last | 19.4 ir-access | MAN002 | odoo/upgrade_code/19.4-00-ir-access.py:375-404 |
| own bundle listing `web/static/lib/owl/owl.js` | add `web/static/src/owl2/owl3_compatibility_layer.js` and `web/static/src/owl2/utils.js` right after it, before `web/static/lib/owl/odoo_module.js` | manual | MAN003 | addons/web/__manifest__.py:466-471 |
| (new keys) | `iap_paid_service`, `other_files` | - | - | odoo/modules/module.py:80-86 |
| depends on a removed module (`base_vat`, `stock_picking_batch`, ...) | depend on the merge target | manual | - | [removed-modules.md](removed-modules.md) |

## CLI / runtime

| v19 / older | Odoo 20 | Automated by | Rule | v20 source |
|---|---|---|---|---|
| Python >= 3.10, PostgreSQL >= 13 | Python 3.12 to 3.14, PostgreSQL >= 16 | - | - | odoo/release.py:39-41 |
| `pytz`, `xlwt` in requirements | not shipped | manual | ORM015 | requirements.txt |
| `--http-interface` default `0.0.0.0` | `127.0.0.1` | - | - | odoo/tools/config.py:294 |
| `odoo-bin populate` (random generator) | `odoo-bin duplicate`; `populate` is now blueprint-based (from the `populate` addon) | - | - | odoo/cli/duplicate.py, addons/populate |
| `odoo-bin db ...` / `module ...` | subcommands `db init/load/dump/duplicate/rename/drop`, `module install/upgrade/uninstall/force-demo/list` | - | - | odoo/cli/db.py, odoo/cli/module.py |
