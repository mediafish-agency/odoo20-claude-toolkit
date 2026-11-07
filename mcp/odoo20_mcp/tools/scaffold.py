"""odoo_scaffold: generate an Odoo 20 module skeleton (templates proven by installing + testing them).

Differences from `odoo-bin scaffold`: security uses `security/ir.access.csv` (v20), views use `<list>`,
`<chatter/>`, Material icons, an action `path`, OWL 3 `useProps`, Hoot tests.
"""
from __future__ import annotations

import keyword
import re
from pathlib import Path

from .. import context as ctx
from ..util import ToolError

FEATURES = ("views", "mail", "owl", "report", "controller", "wizard", "interaction", "tests")
DEFAULT_FEATURES = ("views", "tests")


def _class_name(model: str) -> str:
    return "".join(p.capitalize() for p in re.split(r"[._]", model) if p)


def _files(module: str, model: str, label: str, features: set[str]) -> dict[str, str]:
    cls = _class_name(model)
    model_us = model.replace(".", "_")
    depends = ["mail"] if "mail" in features else ["base"]
    if {"owl", "views"} & features and "mail" not in features:
        depends = ["web"]
    if "interaction" in features:
        depends = sorted(set(depends) | {"website"})
    data = []
    files: dict[str, str] = {}

    # -- models -----------------------------------------------------------
    inherit = "\n    _inherit = ['mail.thread', 'mail.activity.mixin']" if "mail" in features else ""
    tracking = ", tracking=True" if "mail" in features else ""
    files["models/__init__.py"] = f"from . import {model_us}\n"
    files[f"models/{model_us}.py"] = f'''from odoo import api, fields, models


class {cls}(models.Model):
    _name = '{model}'
    _description = "{label}"{inherit}
    _order = 'sequence, id'

    name = fields.Char(required=True{tracking})
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    state = fields.Selection(
        [('draft', "Draft"), ('done', "Done")],
        default='draft', required=True{tracking},
    )
    note = fields.Html()
    amount = fields.Float()
    is_large = fields.Boolean(compute='_compute_is_large', store=True)

    _name_company_uniq = models.Constraint(
        'UNIQUE(name, company_id)',
        "The name must be unique per company.",
    )

    @api.depends('amount')
    def _compute_is_large(self):
        for record in self:
            record.is_large = record.amount > 1000

    def action_done(self):
        self.write({{'state': 'done'}})
'''
    # -- security ---------------------------------------------------------
    files["security/ir.access.csv"] = (
        "id,name,model_id,group_id/id,operation,domain\n"
        f"access_{model_us}_user,{label} (user),{model},base.group_user,crud,\n"
        f"rule_{model_us}_company,{label} multi-company,{model},,crud,\"[('company_id', 'in', company_ids)]\"\n"
    )

    # -- views ------------------------------------------------------------
    if "views" in features:
        chatter = "\n                <chatter/>" if "mail" in features else ""
        widget = ' widget="' + module + '_badge"' if "owl" in features else ""
        files[f"views/{model_us}_views.xml"] = f'''<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="{model_us}_view_list" model="ir.ui.view">
        <field name="name">{model}.list</field>
        <field name="model">{model}</field>
        <field name="arch" type="xml">
            <list string="{label}" decoration-muted="state == 'done'">
                <field name="sequence" widget="handle"/>
                <field name="name"/>
                <field name="amount" optional="show"/>
                <field name="state"{widget}/>
                <field name="company_id" groups="base.group_multi_company" optional="hide"/>
            </list>
        </field>
    </record>

    <record id="{model_us}_view_form" model="ir.ui.view">
        <field name="name">{model}.form</field>
        <field name="model">{model}</field>
        <field name="arch" type="xml">
            <form string="{label}">
                <header>
                    <button name="action_done" type="object" string="Mark as Done" class="btn-primary"
                            icon="check" invisible="state != 'draft'"/>
                    <field name="state" widget="statusbar"/>
                </header>
                <sheet>
                    <widget name="web_ribbon" title="Archived" bg_color="text-bg-danger" invisible="active"/>
                    <div class="oe_title">
                        <h1><field name="name" placeholder="Name"/></h1>
                    </div>
                    <group>
                        <group>
                            <field name="amount"/>
                            <field name="is_large"/>
                        </group>
                        <group>
                            <field name="company_id" groups="base.group_multi_company"/>
                            <field name="active" invisible="1"/>
                        </group>
                    </group>
                    <notebook>
                        <page name="notes" string="Notes">
                            <field name="note"/>
                        </page>
                    </notebook>
                </sheet>{chatter}
            </form>
        </field>
    </record>

    <record id="{model_us}_view_search" model="ir.ui.view">
        <field name="name">{model}.search</field>
        <field name="model">{model}</field>
        <field name="arch" type="xml">
            <search>
                <field name="name"/>
                <filter name="draft" string="Draft" domain="[('state', '=', 'draft')]"/>
                <filter name="large" string="Large" domain="[('is_large', '=', True)]"/>
                <separator/>
                <filter name="archived" string="Archived" domain="[('active', '=', False)]"/>
                <filter name="group_state" string="Status" context="{{'group_by': 'state'}}"/>
            </search>
        </field>
    </record>

    <record id="{model_us}_action" model="ir.actions.act_window">
        <field name="name">{label}</field>
        <field name="res_model">{model}</field>
        <field name="path">{module.replace("_", "-")}</field>
        <field name="view_mode">list,form</field>
    </record>
</odoo>
'''
        files["views/menus.xml"] = f'''<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <menuitem id="{module}_menu_root" name="{label}" sequence="90">
        <menuitem id="{model_us}_menu" name="{label}" action="{model_us}_action" sequence="10"/>
    </menuitem>
</odoo>
'''
        data += [f"views/{model_us}_views.xml", "views/menus.xml"]

    # -- wizard -----------------------------------------------------------
    if "wizard" in features:
        files["wizard/__init__.py"] = f"from . import {model_us}_wizard\n"
        files[f"wizard/{model_us}_wizard.py"] = f'''from odoo import fields, models


class {cls}Wizard(models.TransientModel):
    _name = '{model}.wizard'
    _description = "{label} Wizard"

    record_ids = fields.Many2many('{model}', default=lambda self: self.env.context.get('active_ids'))
    amount = fields.Float(required=True)

    def action_apply(self):
        self.record_ids.write({{'amount': self.amount}})
        return {{'type': 'ir.actions.act_window_close'}}
'''
        files[f"wizard/{model_us}_wizard_views.xml"] = f'''<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="{model_us}_wizard_view_form" model="ir.ui.view">
        <field name="name">{model}.wizard.form</field>
        <field name="model">{model}.wizard</field>
        <field name="arch" type="xml">
            <form>
                <group>
                    <field name="record_ids" widget="many2many_tags"/>
                    <field name="amount"/>
                </group>
                <footer>
                    <button name="action_apply" type="object" string="Apply" class="btn-primary"/>
                    <button special="cancel" string="Cancel"/>
                </footer>
            </form>
        </field>
    </record>

    <record id="{model_us}_wizard_action" model="ir.actions.act_window">
        <field name="name">Set Amount</field>
        <field name="res_model">{model}.wizard</field>
        <field name="view_mode">form</field>
        <field name="target">new</field>
        <field name="binding_model_id" ref="model_{model_us}"/>
    </record>
</odoo>
'''
        files["security/ir.access.csv"] += f"access_{model_us}_wizard_user,{label} wizard,{model}.wizard,base.group_user,crud,\n"
        data.insert(0, f"wizard/{model_us}_wizard_views.xml")

    # -- report -----------------------------------------------------------
    if "report" in features:
        files[f"report/{model_us}_reports.xml"] = f'''<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="action_report_{model_us}" model="ir.actions.report">
        <field name="name">{label}</field>
        <field name="model">{model}</field>
        <field name="report_type">qweb-pdf</field>
        <field name="report_name">{module}.report_{model_us}</field>
        <field name="print_report_name">'{label} - %s' % object.name</field>
        <field name="binding_model_id" ref="model_{model_us}"/>
        <field name="binding_type">report</field>
    </record>
</odoo>
'''
        files[f"report/{model_us}_templates.xml"] = f'''<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <template id="report_{model_us}_document">
        <t t-call="web.external_layout">
            <div class="page">
                <h2 t-out="doc.name"/>
                <p>Amount: <span t-field="doc.amount"/></p>
                <div t-field="doc.note"/>
            </div>
        </t>
    </template>

    <template id="report_{model_us}">
        <t t-call="web.html_container">
            <t t-foreach="docs" t-as="doc">
                <t t-call="{module}.report_{model_us}_document"/>
            </t>
        </t>
    </template>
</odoo>
'''
        data += [f"report/{model_us}_reports.xml", f"report/{model_us}_templates.xml"]

    # -- controller -------------------------------------------------------
    if "controller" in features:
        files["controllers/__init__.py"] = "from . import main\n"
        files["controllers/main.py"] = f'''from odoo.http import Controller, request, route


class {cls}Controller(Controller):

    @route('/{module}/summary', type='jsonrpc', auth='user', readonly=True)
    def summary(self):
        records = request.env['{model}'].search([('state', '=', 'draft')])
        return {{'count': len(records), 'names': records.mapped('name')}}
'''

    # -- OWL field widget + Hoot test --------------------------------------
    assets: dict[str, list[str]] = {}
    if "owl" in features:
        comp = f"{_class_name(module)}Badge"
        files["static/src/badge_field/badge_field.js"] = f'''import {{ _t }} from "@web/core/l10n/translation";
import {{ registry }} from "@web/core/registry";
import {{ standardFieldProps }} from "@web/views/fields/standard_field_props";

import {{ Component, useProps }} from "@odoo/owl";

export function badgeClass(state) {{
    return state === "done" ? "text-bg-success" : "text-bg-secondary";
}}

export class {comp} extends Component {{
    static template = "{module}.{comp}";
    props = useProps({{ ...standardFieldProps }});

    value() {{
        return this.props.record.data[this.props.name];
    }}

    cssClass() {{
        return badgeClass(this.value());
    }}
}}

export const {module}BadgeField = {{
    component: {comp},
    displayName: _t("State badge"),
    supportedTypes: ["selection"],
}};

registry.category("fields").add("{module}_badge", {module}BadgeField);
'''
        files["static/src/badge_field/badge_field.xml"] = f'''<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    <t t-name="{module}.{comp}">
        <span class="badge rounded-pill o_{module}_badge" t-att-class="this.cssClass()" t-out="this.value()"/>
    </t>
</templates>
'''
        files["static/tests/badge_field.test.js"] = f'''import {{ expect, test }} from "@odoo/hoot";

import {{ badgeClass }} from "@{module}/badge_field/badge_field";

test("badgeClass maps states to Bootstrap classes", () => {{
    expect(badgeClass("done")).toBe("text-bg-success");
    expect(badgeClass("draft")).toBe("text-bg-secondary");
}});
'''
        assets["web.assets_backend"] = [f"{module}/static/src/badge_field/**/*"]
        assets["web.assets_unit_tests"] = [f"{module}/static/tests/**/*"]

    if "interaction" in features:
        files["static/src/interactions/highlight.js"] = f'''import {{ Interaction }} from "@web/public/interaction";
import {{ registry }} from "@web/core/registry";

export class {_class_name(module)}Highlight extends Interaction {{
    static selector = ".o_{module}_highlight";
    dynamicContent = {{
        _root: {{
            "t-on-click": this.onClick,
            "t-att-class": () => ({{ "o_{module}_active": this.active }}),
        }},
    }};

    setup() {{
        this.active = false;
    }}

    onClick() {{
        this.active = !this.active;
    }}
}}

registry.category("public.interactions").add("{module}.highlight", {_class_name(module)}Highlight);
'''
        assets["web.assets_frontend"] = [f"{module}/static/src/interactions/**/*"]

    # -- python tests -----------------------------------------------------
    if "tests" in features:
        files["tests/__init__.py"] = f"from . import test_{model_us}\n"
        files[f"tests/test_{model_us}.py"] = f'''from psycopg2 import IntegrityError

from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class Test{cls}(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.record = cls.env['{model}'].create({{'name': "First", 'amount': 1500}})

    def test_compute_and_action(self):
        self.assertTrue(self.record.is_large)
        self.record.action_done()
        self.assertEqual(self.record.state, 'done')

    def test_unique_name_per_company(self):
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'), self.env.cr.savepoint():
            self.env['{model}'].create({{'name': "First"}})
            self.env.flush_all()

    def test_user_access(self):
        user = new_test_user(self.env, login='{module}_user', groups='base.group_user')
        self.assertTrue(self.env['{model}'].with_user(user).has_access('write'))
'''

    # -- module files -----------------------------------------------------
    packages = ["models"] + (["wizard"] if "wizard" in features else []) + (["controllers"] if "controller" in features else [])
    files["__init__.py"] = "".join(f"from . import {p}\n" for p in sorted(packages))
    data.append("security/ir.access.csv")  # last: models and groups exist before access rows
    manifest_assets = ""
    if assets:
        manifest_assets = "    'assets': {\n" + "".join(
            f"        '{bundle}': [\n" + "".join(f"            '{p}',\n" for p in paths) + "        ],\n"
            for bundle, paths in assets.items()) + "    },\n"
    files["__manifest__.py"] = (
        "{\n"
        f"    'name': \"{label}\",\n"
        f"    'summary': \"{label} management\",\n"
        "    'version': '1.0',\n"
        "    'category': 'Uncategorized',\n"
        f"    'depends': {depends!r},\n"
        "    'data': [\n" + "".join(f"        '{d}',\n" for d in data) + "    ],\n"
        + manifest_assets +
        "    'application': True,\n"
        "    'author': \"Your Company\",\n"
        "    'license': 'LGPL-3',\n"
        "}\n"
    )
    return files


def scaffold(name: str, dest: str, model: str | None, label: str | None, features: str) -> str:
    cfg = ctx.config()
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name) or keyword.iskeyword(name):
        raise ToolError("module name must be snake_case: lowercase letters, digits, underscores, starting with a letter")
    dest_path = Path(dest).expanduser().resolve()
    if not dest_path.is_dir():
        raise ToolError(f"destination folder not found: {dest_path}")
    if cfg.is_core_path(dest_path):
        raise ToolError("refusing to scaffold inside the Odoo source tree; use your own addons folder")
    target = dest_path / name
    if target.exists():
        raise ToolError(f"{target} already exists; choose another name or folder")
    model = model or f"{name.replace('_', '.')}"
    if not re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z0-9_]+)+", model):
        raise ToolError("model must look like 'library.book' (dotted lowercase)")
    feats = {f.strip() for f in features.split(",") if f.strip()} if features else set(DEFAULT_FEATURES)
    unknown = feats - set(FEATURES)
    if unknown:
        raise ToolError(f"unknown features {sorted(unknown)}; choose from {FEATURES}")
    label = label or model.split(".")[-1].replace("_", " ").title()
    files = _files(name, model, label, feats)
    for rel, content in sorted(files.items()):
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    in_paths = cfg.in_known_roots(target)
    lines = [f"## Created `{target}` ({len(files)} files; features: {', '.join(sorted(feats))})", ""]
    lines += [f"- {rel}" for rel in sorted(files)]
    lines += ["", "Next steps:",
              f"1. {'Already in an indexed addons path.' if in_paths else 'Add ' + str(dest_path) + ' to the plugin option extra_addons_paths so it is indexed/validated/installable.'}",
              f"2. Adapt fields/views to the real need, then odoo_validate(\"{target}\").",
              f"3. odoo_test(\"{name}\") installs it on a throwaway database and runs its tests."]
    return "\n".join(lines)
