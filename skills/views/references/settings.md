# Settings pages (res.config.settings) in Odoo 20

How to add options to Settings: a `res.config.settings` field (stored as a config parameter, a group, a
module to install, or a company field) plus an inherited settings form using the `<app>` / `<block>` /
`<setting>` elements compiled by the web client.

## Python: the settings fields

`res.config.settings` is a TransientModel; extend it with `_inherit = 'res.config.settings'`. The field
name/parameter decides what saving does (`execute()` in `odoo/addons/base/models/res_config.py`):

| Field | Saving does | Core example |
|---|---|---|
| `x = fields.Boolean(config_parameter='my_module.key')` (or Char/Integer/Float/Selection/Many2one) | stores the value in `ir.config_parameter` (read it with `get_bool/get_str/...`) | `addons/sale_stock/models/res_config_settings.py:15-17` |
| `group_x = fields.Boolean(implied_group='my_module.group_x')` | adds/removes the implied group to `base.group_user` (option `group=` to target another group) | `addons/account/models/res_config_settings.py:87` |
| `module_x = fields.Boolean()` | installs/uninstalls module `x` | `addons/account/models/res_config_settings.py:86` |
| `x = fields.Integer(related='company_id.x', readonly=False)` | writes the company field (company-dependent setting) | `addons/sale_stock/models/res_config_settings.py:14` |

```python
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    library_max_loans = fields.Integer(config_parameter='library.max_loans', default=3)
    group_library_fines = fields.Boolean(implied_group='library.group_fines')
    module_library_barcode = fields.Boolean(string="Barcode scanning")
```

Read a config-parameter setting elsewhere with the typed API (v20):
`self.env['ir.config_parameter'].sudo().get_int('library.max_loans', 3)` (not `get_param`, rule ORM001).

Source: odoo/addons/base/models/res_config.py, addons/sale_stock/models/res_config_settings.py,
addons/account/models/res_config_settings.py

## XML: the settings form

Inherit `base.res_config_settings_view_form` (model `res.config.settings`). One `<app>` per application
section, `<block>` groups, `<setting>` rows; the first boolean field inside a `<setting>` becomes its
checkbox, other content goes in the right column.

```xml
<record id="res_config_settings_view_form" model="ir.ui.view">
    <field name="name">res.config.settings.view.form.inherit.library</field>
    <field name="model">res.config.settings</field>
    <field name="priority" eval="90"/>
    <field name="inherit_id" ref="base.res_config_settings_view_form"/>
    <field name="arch" type="xml">
        <xpath expr="//form" position="inside">
            <app data-string="Library" string="Library" name="library" groups="base.group_system">
                <block title="Loans" name="library_loans_settings">
                    <setting string="Maximum loans" help="Books a member can borrow at once" id="library_max_loans">
                        <field name="library_max_loans"/>
                    </setting>
                    <setting id="library_fines" help="Charge fines for late returns">
                        <field name="group_library_fines"/>
                    </setting>
                    <setting id="library_barcode" string="Barcode scanning" help="Requires the barcode module">
                        <field name="module_library_barcode"/>
                    </setting>
                </block>
            </app>
        </xpath>
    </field>
</record>
```

| Element | Attributes read in v20 |
|---|---|
| `<app>` | `string`, `data-string`, `name` (module technical name; anchors other modules' xpaths), `groups`, `logo` |
| `<block>` | `title`, `help`, `name` or `id`, `invisible`, `groups` |
| `<setting>` | `string`, `help`, `id`, `company_dependent="1"`, `documentation` (URL), `info`, `nolabel`, `invisible`, `groups` |

To add a setting to another module's app, anchor on names:
`<block name="..." position="inside">` or `<setting id="..." position="after">` (see
[inheritance.md](inheritance.md)); `addons/sale_management/views/res_config_settings_views.xml` extends the
`sale` app with `<app name="sale_management" position="attributes">`.

Source: addons/account/views/res_config_settings_views.xml:16-40,
addons/web/static/src/webclient/settings_form_view/settings_form_compiler.js,
addons/web/static/src/views/form/form_compiler.js:600-625,
addons/sale_management/views/res_config_settings_views.xml
