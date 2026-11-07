# Actions, menus and URLs (Odoo 20)

Window, server, client, URL and report actions as defined in Odoo 20, `<menuitem>`, action bindings,
returning actions from Python (`get_record_default_action`, `_get_records_action`, `_for_xml_id`) and
`/odoo/<path>` URL routing. Record id/name conventions:
[XML guidelines](../../odoo-guidelines/guidelines/xml.md#views-actions-and-data-records).

## Contents
- Fields shared by all actions
- `ir.actions.act_window`
- Embedded actions
- `ir.actions.server`
- `ir.actions.client`
- `ir.actions.act_url` and `act_window_close`
- Report actions and bindings
- `<menuitem>`
- Returning actions from Python
- URL routing with `path`
- v19 habit -> Odoo 20

## Fields shared by all actions (`ir.actions.actions`)

| Field | Notes |
|---|---|
| `name` | translatable, required |
| `path` | URL slug: `[a-z][a-z0-9_-]*`, not `new`, not starting with `m-` or `action-`, unique across **all** action tables |
| `help` | HTML shown on empty views |
| `explanation` | **new** text field: what the action does (technical note) |
| `binding_model_id` | model whose Action/Print menu shows the action |
| `binding_type` | `action` (default) or `report` |
| `binding_view_types` | default `list,form` |

Source: odoo/addons/base/models/ir_actions.py:54-105

## `ir.actions.act_window`

| Field | Notes |
|---|---|
| `res_model` | required, validated |
| `view_mode` | comma list without spaces/duplicates: `list`, `form`, `kanban`, `calendar`, `pivot`, `graph`, plus `activity` (mail) and `hierarchy` (web_hierarchy). `card`, `search`, `qweb` are not view modes |
| `view_id` | first view to use for its type |
| `view_ids` | `ir.actions.act_window.view` records (`sequence`, `view_mode`, `view_id`) to pin one view per mode |
| `views` | computed **Json** `[(view_id or False, mode), ...]` (order: `view_ids`, then `view_id`, then the rest of `view_mode`) |
| `search_view_id` | search view |
| `domain` | python expression string |
| `context` | python dict string (`search_default_*`, `default_*`, `*_view_ref`, `active_test`...) |
| `target` | `current` (default), `new` (dialog), `fullscreen`, `main` (clear breadcrumbs) |
| `res_id` | open this record (form) |
| `limit` | list page size (default 80) |
| `mobile_view_mode` | first view on small screens (default `kanban`) |
| `group_ids` | groups allowed to see the action |
| `usage`, `filter`, `cache` | misc. |
| `embedded_action_ids` | computed from `ir.embedded.actions` (below) |

```xml
<record id="action_orders" model="ir.actions.act_window">
    <field name="name">Sales Orders</field>
    <field name="res_model">sale.order</field>
    <field name="path">orders</field>
    <field name="view_mode">list,kanban,form,calendar,pivot,graph,activity</field>
    <field name="search_view_id" ref="sale_order_view_search_inherit_sale"/>
    <field name="context">{'search_default_sales': 1}</field>
    <field name="help" type="html"><p class="o_view_nocontent_smiling_face">Create a new quotation</p></field>
</record>
<record id="sale_order_action_view_order_tree" model="ir.actions.act_window.view">
    <field name="sequence" eval="1"/>
    <field name="view_mode">list</field>
    <field name="view_id" ref="sale.sale_order_list_with_dashboard"/>
    <field name="act_window_id" ref="action_orders"/>
</record>
<!-- or inline -->
<field name="view_ids" eval="[Command.clear(),
    Command.create({'view_mode': 'kanban'}),
    Command.create({'view_mode': 'list', 'view_id': ref('my_module.view_x_list')})]"/>
```

Source: odoo/addons/base/models/ir_actions.py:243-404, addons/mail/models/ir_action_act_window.py, addons/web_hierarchy/models/ir_actions.py, addons/sale/views/sale_order_views.xml:1214-1235, addons/sale/views/product_views.xml:140-144

## Embedded actions

`ir.embedded.actions` adds tabs on top of a window action shown for a parent record:
`parent_action_id` (act_window), `parent_res_model`, `action_id` **or** `python_method` (method of the
parent model returning an action), `sequence`, `name`, `domain` (on the parent record), `context`,
`groups_ids`, `default_view_mode`, `filter_ids`, `user_id` (personal tab).

```xml
<record id="project_embedded_action_project_milestones" model="ir.embedded.actions">
    <field name="parent_res_model">project.project</field>
    <field name="sequence">10</field>
    <field name="name">Milestones</field>
    <field name="parent_action_id" ref="project.act_project_project_2_project_task_all"/>
    <field name="action_id" eval="False"/>
    <field name="python_method">action_get_list_view</field>
    <field name="domain">[('allow_milestones', '=', True)]</field>
    <field name="groups_ids" eval="[(4, ref('project.group_project_milestone'))]"/>
</record>
```

Source: odoo/addons/base/models/ir_embedded_actions.py:9-29, addons/project/views/project_milestone_views.xml:130-139

## `ir.actions.server`

| `state` | Module | Does |
|---|---|---|
| `object_write` | base | update fields (`update_path`, `evaluation_type`, `value`...) |
| `object_create` / `object_copy` | base | create / duplicate a record |
| `code` | base | run python (`code`, `base.group_system` only) |
| `webhook` | base | POST `webhook_field_ids` to `webhook_url` |
| `multi` | base | run `child_ids` in sequence |
| `next_activity`, `mail_post`, `log_note`, `followers`, `remove_followers` | mail | activity, message, note, followers |
| `sms` | sms | send SMS |

`code` evaluation context: `env`, `model`, `record`, `records` (from `active_id(s)` of the same model),
`log(message, level)`, `_logger`, `UserError`, `Command`, `uid`, `user`, `time`, `datetime`, `dateutil`,
`timezone` (`ZoneInfo`), `float_compare`, `b64encode`, `b64decode`, `BinaryBytes`. Assign `action = {...}`
to return an action. `usage` is `ir_actions_server` or `ir_cron`.

```xml
<record id="model_sale_order_action_quotation_confirm" model="ir.actions.server">
    <field name="name">Confirm Orders</field>
    <field name="model_id" ref="sale.model_sale_order"/>
    <field name="binding_model_id" ref="sale.model_sale_order"/>
    <field name="binding_view_types">list</field>
    <field name="state">code</field>
    <field name="code">records.action_confirm()</field>
</record>
```

Source: odoo/addons/base/models/ir_actions.py:124-140,586-700,1125-1167,1015-1019, addons/mail/models/ir_actions_server.py:23-35, addons/sms/models/ir_actions_server.py:11-13, addons/sale/views/sale_order_views.xml:1372-1379

## `ir.actions.client`

Fields: `tag` (key of the JS `actions` registry), `target`, `res_model`, `context`, `params` (**Json**; in
XML use `eval`). Built-in tags in web: `display_notification`, `display_exception`, `reload`,
`soft_reload`, `reload_context`, `home`.

```xml
<record id="mail.action_discuss" model="ir.actions.client">
    <field name="name">Discuss</field>
    <field name="tag">mail.action_discuss</field>
    <field name="path">discuss</field>
    <field name="params" eval="&quot;{ 'default_active_id': 'mail.box_inbox' }&quot;"/>
</record>
```
```python
return {
    'type': 'ir.actions.client',
    'tag': 'display_notification',
    'params': {
        'title': _('Batch transfers have been merged'),
        'message': '%s',
        'links': [{'label': batch.name, 'url': f"/odoo/action-stock.stock_picking_batch_action/{batch.id}"}],
        'sticky': False,
        'next': {'type': 'ir.actions.act_window_close'},
    },
}
```
Writing the JS side (registry `actions`, OWL component): see the owl skill.

Source: odoo/addons/base/models/ir_actions.py:1463-1500, addons/web/static/src/webclient/actions/client_actions.js:9-103, addons/mail/views/discuss_channel_views.xml:217-221, addons/stock/models/stock_picking_batch.py:343-356

## `ir.actions.act_url` and `act_window_close`

- `ir.actions.act_url`: `url` (required), `target` = `new` (default tab), `self`, `download`.
- `{'type': 'ir.actions.act_window_close'}` closes the current dialog; a button method returning a
  falsy value has the same effect.

```xml
<record id="action_open_discuss_settings" model="ir.actions.act_url">
    <field name="name">Settings</field>
    <field name="url" eval="'/odoo/settings#discuss_setting'"/>
    <field name="target">self</field>
</record>
```

Source: odoo/addons/base/models/ir_actions.py:407-440, addons/mail/data/ir_actions_data.xml:16-20, addons/web/static/src/webclient/actions/action_plugin.js:1630-1640

## Report actions and bindings

A report shows in the Print menu when `binding_model_id` (and `binding_type` = `report`, which is the
default of `ir.actions.report`) is set. Fields and rendering: [reports.md](../../qweb-reports/references/reports.md).

```xml
<record id="action_report_saleorder" model="ir.actions.report">
    <field name="name">Quotation / Order</field>
    <field name="model">sale.order</field>
    <field name="report_type">qweb-pdf</field>
    <field name="report_name">sale.report_saleorder</field>
    <field name="binding_model_id" ref="model_sale_order"/>
    <field name="binding_type">report</field>
</record>
```

Source: odoo/addons/base/models/ir_actions_report.py:44-70, addons/sale/report/ir_actions_report.xml:4-12

## `<menuitem>`

| Attribute | Notes |
|---|---|
| `id` | required |
| `name` | defaults to the action name, else the id |
| `action` | xmlid (module prefix optional for the current module); any `ir.actions.*` |
| `parent` | parent menu xmlid (omit when nested) |
| `sequence` | int |
| `groups` | comma list; prefix `-` **removes** a group from the menu's `group_ids` |
| `active` | `False` hides it |
| `web_icon` | root menus only: `module,path/icon.png` or `icon_class,icon_color,background_color` |

Nest `<menuitem>` elements to build the tree (a nested menu cannot take `parent` or `web_icon`).

```xml
<menuitem id="sale_menu_root" name="Sales" web_icon="sale_management,static/description/icon.png" sequence="30">
    <menuitem id="sale_order_menu" name="Orders" sequence="10">
        <menuitem id="menu_sale_order" name="Orders" action="action_orders"
                  groups="sales_team.group_sale_salesman" sequence="20"/>
    </menuitem>
</menuitem>
```

Source: odoo/import_xml.rng:237-281, odoo/tools/convert.py:296-350, odoo/addons/base/models/ir_ui_menu.py:23-41,159-172, addons/sale/views/sale_menus.xml:4-40

## Returning actions from Python

| Need | Code |
|---|---|
| open one record with its default form | `return record.get_record_default_action()` (override `get_formview_id()` to pick the view) |
| open records (form if one, list+form otherwise) | `return records._get_records_action(name=self.env._("Generated Orders"))` (kwargs override keys) |
| reuse an XML action and tweak it | `action = self.env["ir.actions.act_window"]._for_xml_id("sale.action_orders")` then set `domain`, `views`, `res_id`, `context` |
| print a report | `return self.env.ref("sale.action_report_saleorder").report_action(self)` |
| close a dialog | `return {'type': 'ir.actions.act_window_close'}` |

```python
def action_view_source_sale_orders(self):
    self.ensure_one()
    orders = self.line_ids.sale_line_ids.order_id
    action = self.env["ir.actions.act_window"]._for_xml_id("sale.action_orders")
    if len(orders) > 1:
        action["domain"] = [("id", "in", orders.ids)]
    elif orders:
        action["views"] = [(self.env.ref("sale.view_order_form").id, "form")]
        action["res_id"] = orders.id
    else:
        action = {"type": "ir.actions.act_window_close"}
    return action
```
`_for_xml_id` returns only the fields the web client may read (`_get_readable_fields`), as a dict.

Source: odoo/addons/base/models/ir_ui_view.py:3296-3345, odoo/addons/base/models/ir_actions.py:205-241, odoo/addons/base/models/ir_actions_report.py:863-894, addons/sale/models/account_move.py:202-213, addons/sale/models/sale_order.py:2379

## URL routing with `path`

Web client URLs are `/odoo/<part>[/<id>|/new][/<part>[/<id>]]...`; each part resolves to an action:

| Part | Resolves to |
|---|---|
| `orders` | action whose `path` is `orders` |
| `action-<id>` / `action-<module.xmlid>` | action by database id / xmlid |
| `m-<model>` or `<model.name>` | first act_window on that model, else `get_record_default_action()` |

Examples: `/odoo/orders/42`, `/odoo/action-stock.stock_picking_batch_action/7`, `/odoo/sale.order/42`,
`/odoo/all-tasks/5/project.project/1/tasks` (nested record actions). Set `path` on the main actions of
your app; check uniqueness with `odoo_grep('name="path"')`.

Source: addons/web/controllers/utils.py:160-240, addons/web/controllers/home.py:49, odoo/addons/base/models/ir_actions.py:83-101

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `record.get_formview_action()` | `record.get_record_default_action()` (ORM020) | odoo/addons/base/models/ir_ui_view.py:3307 |
| `views` / client `params` as Binary | Json fields | odoo/addons/base/models/ir_actions.py:307,1480 |
| no description field | `explanation` | odoo/addons/base/models/ir_actions.py:74 |
| `mail_post_method` on server actions | states `mail_post` / `log_note` (ORM024) | addons/mail/models/ir_actions_server.py |
| `view_mode="tree,form"` | `list,form` (XML001) | odoo/upgrade_code/17.5-01-tree-to-list.py |
| `report_file` on report actions | removed (REP002) | odoo/addons/base/models/ir_actions_report.py |
