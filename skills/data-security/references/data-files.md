# XML and CSV data files (Odoo 20)

Every tag, attribute and value form the v20 loader accepts in module data files, as defined by
`odoo/import_xml.rng` (validated on every XML load) and implemented in `odoo/tools/convert.py`,
plus CSV data files, `noupdate`, demo data, the eval context and load order. Naming and record
layout conventions are in the official [xml guidelines](../../odoo-guidelines/guidelines/xml.md)
and [module structure](../../odoo-guidelines/guidelines/module_structure.md); do not repeat them here.

## Contents
- [File kinds and load order](#file-kinds-and-load-order)
- [Root element](#root-element)
- [record](#record)
- [field values](#field-values)
- [Eval context](#eval-context)
- [function](#function)
- [delete](#delete)
- [menuitem](#menuitem)
- [template](#template)
- [asset](#asset)
- [noupdate, forcecreate and removed records](#noupdate-forcecreate-and-removed-records)
- [CSV data files](#csv-data-files)
- [Demo data](#demo-data)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## File kinds and load order

`convert_file` dispatches on the extension: `.xml` (RNG-validated, then parsed), `.csv`
(`Model.load`), `.sql` (executed raw with `cr.execute`), `.js` (ignored); anything else raises.

Manifest keys: `data` (always loaded, install and update), `demo` (see [Demo data](#demo-data)),
`other_files` (shipped with the module, never loaded by the module loader, e.g.
`addons/hr/__manifest__.py:59`). `demo_xml`/`init_xml`/`update_xml` are gone (MAN001).

Per module, in dependency order (`depends`), the loader does:

1. `pre` migration scripts (on upgrade), import the Python package, `pre_init_hook` (install).
2. Register models and create/alter tables.
3. Load every `data` file **in manifest order** (mode `init` on install, `update` on `-u`).
4. Load `demo` files if the module has demo.
5. `post` migration scripts, reflect field `groups`, update translations.
6. `post_init_hook` (install) or re-validate views (upgrade).

Inside a module, a record can only `ref()` what is already loaded: groups before views and menus,
actions before menus, `security/ir.access.csv` last (see [ir-access.md](ir-access.md#manifest-order)).
Migration scripts: [migration-scripts.md](migration-scripts.md).

Source: odoo/tools/convert.py:692-723, odoo/modules/loading.py:44-60,165-245, odoo/modules/module.py:75-86, addons/hr/__manifest__.py:59

## Root element

`<odoo>`, `<data>` or legacy `<openerp>`; they nest. Attributes on any of them:

| Attribute | Effect |
|---|---|
| `noupdate="1"` | Records inside are created once, then left alone on `-u` (see below) |
| `auto_sequence="1"` | Records whose model has a `sequence` field and none given get 10, 20, 30 ... in file order |
| `uid="xmlid"` | Run the children as that user |
| `context="{...}"` | Extra context (evaluated with `ref` only) |

If the whole file is non-updatable, put `noupdate="1"` on `<odoo>` and drop `<data>`.

Source: odoo/import_xml.rng:4-7,283-306, odoo/tools/convert.py:238-252,620-665

## record

```xml
<record id="tax_report" model="account.report">
    <field name="name">P.P. 30 - VAT Report</field>
    <field name="name@th">รายงานภาษี</field>
    <field name="country_id" ref="base.th"/>
    <field name="allow_foreign_vat" eval="True"/>
    <field name="column_ids">
        <record id="tax_report_balance" model="account.report.column">
            <field name="name">Balance</field>
            <field name="expression_label">balance</field>
        </record>
    </field>
</record>
```

| Attribute | Notes |
|---|---|
| `id` | xmlid; `name` alone = current module, `module.name` = another module (must be installed) |
| `model` | required |
| `forcecreate` | only with `id`; default True. `forcecreate="0"` on a noupdate record: skip if missing. On a foreign xmlid: allows creating it |
| `uid`, `context` | as on the root |

- Updating another module's record: `<record id="other_module.xmlid" model="...">` with only the fields
  to change; raises `Cannot update missing record` if it does not exist.
- One2many children: nest `<record>` elements inside the `<field>`; the inverse field is filled
  automatically (`_tag_record` with `extra_vals`).
- `name@<lang>` fields are skipped at load and imported as translations when that language is
  loaded or updated (`XMLDataFileReader`); see [i18n.md](i18n.md).

Source: odoo/import_xml.rng:144-158, odoo/tools/convert.py:254-268,357-489, odoo/tools/translate.py:1346-1371,2441-2448, addons/l10n_th/data/account_tax_report_data.xml:1-15

## field values

Exactly one value form per `<field>` (RNG choice):

| Form | Example | Result |
|---|---|---|
| text | `<field name="operation">cu</field>` | string, then coerced by field type (below) |
| `eval` | `eval="[Command.link(ref('base.group_user'))]"` | `safe_eval` in the [eval context](#eval-context); `model=` adds `obj` |
| `ref` | `ref="base.group_portal"` | record id; for a `reference` field `"model,id"`. Unresolvable + `forcecreate="0"` skips the record |
| `search` | `search="[('code','=','EUR')]" model="res.currency" use="id"` | many2many: `Command.set(all)`; otherwise first match |
| `type="int"` | `<field name="x" type="int">3</field>` or `None` | int |
| `type="float"` | | float |
| `type="char"` | default | string |
| `type="list"`/`"tuple"` | children `<value>` | list / tuple |
| `type="xml"` | view `arch` | serialized XML; `%(xmlid)d` / `%(xmlid)s` are replaced by ids, `%%` by `%` |
| `type="html"` | `body_html` | serialized HTML, same `%(xmlid)d` substitution |
| `type="bytes" file="module/path"` | images, PDFs | `BinaryBytes` read from the file (v20 way) |
| `type="base64" file=...` | | deprecated: DeprecationWarning, use `bytes` (XML006) |
| `file="module/path"` (char) | | text content of the file |
| `type="file"` | path relative to the module as text | returns the string `"module,path"` after checking the file exists |

`bytes`/`base64` without `file=` raise `ValueError`. Coercions after evaluation: many2one -> `int`
or False, integer -> `int`, float/monetary -> `float`, boolean from text -> `False` for
`0`/`false`/`off` (anything else True), html field with `type="xml"` logs a warning.

Source: odoo/import_xml.rng:30-142, odoo/tools/convert.py:82-180,412-470, addons/account/data/onboarding_data.xml:12, addons/account/data/mail_template_data.xml:17

## Eval context

Used by `eval=`, `search=` and `<function eval>`:

| Name | Value |
|---|---|
| `ref` | `xmlid -> id` (raises if missing) |
| `Command` | `odoo.fields.Command` |
| `time` | safe `time` module wrapper |
| `datetime`, `DateTime` | `datetime.datetime` |
| `timedelta`, `relativedelta` | |
| `version` | `release.major_version` |
| `pytz` | **shim** `Pytz(timezone=zoneinfo.ZoneInfo, utc=UTC, UTC=UTC)`: `pytz.timezone(tz)` returns a `ZoneInfo`, so `.localize()`/`.normalize()` do not exist (XML014). Use `dt.replace(tzinfo=pytz.timezone(tz))` |
| `obj` | `env[model].browse`, only when the node has `model=` |

`safe_eval` forbids imports, dunder access and unsafe attributes. Typical values:
`eval="DateTime.now() - relativedelta(days=8)"`, `eval="(DateTime.today() - relativedelta(months=2)).strftime('%Y-%m-%d %H:%M')"`.

Source: odoo/tools/convert.py:39-60, addons/crm/data/crm_lead_demo.xml:6,22

## function

Calls a model method at load time:

```xml
<function model="ir.default" name="set" eval="('res.partner', 'trust', 'normal')"/>

<function model="res.users" name="write">
    <value eval="[ref('base.user_root'), ref('base.user_admin')]"/>
    <value eval="{'company_ids': [(4, ref('base.demo_company_th'))]}"/>
</function>
```

- Arguments: either `eval="(tuple)"` or child `<value>`/`<function>` nodes (positional); a
  `<value name="kw">` becomes a keyword argument; a `context` keyword is applied with `with_context`.
- `@api.model` methods are called on the empty model; any other method takes the **record ids as the
  first argument** (falsy ids dropped).
- Method names containing `__` or unsafe attributes raise `NameError`.
- Inside `noupdate="1"` it runs only at install (mode `init`), never on `-u`.

Source: odoo/import_xml.rng:49-66, odoo/tools/convert.py:182-221,290-294, addons/account/data/account_data.xml:303, addons/l10n_th/demo/demo_company.xml:21-34

## delete

`<delete model="res.partner.category" id="module.xmlid"/>` or `search="[('name','=','X')]"`
(exactly one of `id`/`search`). Missing xmlids and failed searches are logged and skipped. Prefer
deactivating (`active=False`) records owned by other modules.

Source: odoo/import_xml.rng:227-235, odoo/tools/convert.py:269-288

## menuitem

```xml
<menuitem id="menu_maintenance_title" name="Maintenance"
          groups="base.group_user_regular"
          web_icon="maintenance,static/description/icon.png" sequence="160"/>
<menuitem id="menu_m_request_form" name="Maintenance Requests" parent="menu_m_request"
          action="hr_equipment_request_action" groups="group_equipment_manager,base.group_user" sequence="1"/>
```

| Attribute | Notes |
|---|---|
| `id` | required |
| `name` | default: the action's name, else the id |
| `sequence` | int |
| `groups` | comma list of xmlids; `-module.group` unlinks a group (when editing another module's menu) |
| `active` | default True |
| `parent` | non-root menus; omitted = root menu |
| `action` | xmlid of an act_window/server/client/report/url action |
| `web_icon` | root menus only (`module,path`) |

Menus may be nested (child `<menuitem>` gets the parent automatically). Visibility rules:
[groups-privileges.md](groups-privileges.md#using-groups).

Source: odoo/import_xml.rng:237-281, odoo/tools/convert.py:296-355, addons/maintenance/views/maintenance_views.xml:946-976

## template

Sugar for an `ir.ui.view` of type `qweb` (`theme.ir.ui.view` in `theme_*` modules). Attributes
accepted by the RNG: `id`, `t-name`, `name`, `forcecreate`, `context`, `priority`, `key`,
`website_id`, `technical_usage`, `track`, `inherit_id` (+ `primary="True"` for a primary copy),
`groups`, `active`, `customize_show`, and website snippet `data-*` options.

```xml
<template id="crm_lead_merge_summary" name="crm_lead_merge_summary" technical_usage="mail_post_source">
    ...
</template>
```

- `technical_usage` (new in the v20 RNG) is a Selection on `ir.ui.view` that modules extend; mail uses
  `mail_post_source`, mass_mailing `mass_mailing`.
- `active` on `<template>`/`<asset>` is applied only at create and install, not on `-u`.
- `groups` becomes `group_ids` on the view.
- Server QWeb syntax (`t-out`, `t-call` attributes): see the views/qweb skill references.

Source: odoo/import_xml.rng:160-205, odoo/tools/convert.py:491-568, odoo/addons/base/models/ir_ui_view.py:219, addons/mail/models/ir_ui_view.py:9, addons/crm/data/crm_lead_merge_template.xml:4

## asset

```xml
<asset id="theme_default.test_asset_tag_aia" name="Test asset tag">
    <bundle>test_asset_bundle</bundle>
    <path>theme_default/tests/something.scss</path>
    <field name="active">True</field> <!-- a <field> is applied on update too -->
</asset>
```
`<bundle directive="prepend">` is optional.

Creates an `ir.asset` (`theme.ir.asset` in themes). `id`, `name`, `<bundle>` (optional `directive`)
and `<path>` are required; `active` as for templates; extra `<field>` children allowed. Static bundles
belong in the manifest `assets` key.

Source: odoo/import_xml.rng:207-225, odoo/tools/convert.py:570-608, addons/test_website/tests/asset_tag.xml:4-16

## noupdate, forcecreate and removed records

| Situation | Behaviour |
|---|---|
| Install (`-i`, mode `init`) | Every record is created/written, noupdate or not |
| Update (`-u`), normal record | Re-written from the file |
| Update, record in `noupdate="1"` whose xmlid exists | Skipped entirely (user edits are kept) |
| Update, noupdate record missing in DB | Re-created unless `forcecreate="0"` |
| Update, record removed from the file (noupdate False) | **Deleted** at the end of loading (`ir.model.data._process_end`) |
| `--reinit module` | Mode `init` again: noupdate records are rewritten |

`ir.model.data.noupdate` stores the flag per xmlid; to change data shipped as noupdate use a
migration script ([migration-scripts.md](migration-scripts.md)) or `<function>` at install.

Source: odoo/tools/convert.py:377-410, odoo/orm/models.py:4625-4690, odoo/addons/base/models/ir_model.py:2326,2724-2745, odoo/tools/config.py:259

## CSV data files

- The model is the file name before the first `-`, extension removed: `res.country.state.csv`,
  `ir.access.csv`, `account.tax.group-th.csv` -> `account.tax.group`.
- Comma separated, `"` quoted, UTF-8, first row = field names in `Model.load` syntax: `field`,
  `field/id` (xmlid), `field/.id` (database id); a relational column without suffix is matched by
  exact `name_search`.
- An `id` column (xmlid) is required except in install mode; always include it.
- Columns `field@lang` (e.g. `name@th_TH`) are removed before loading and imported as translations.
- CSV files are noupdate only when listed in `demo`.

```csv
id,name,sic_group,division_id/id,sequence
"crm_iap_mine_industry_01","Crop Farming",1,"crm_iap_mine_division_a"
```

Source: odoo/tools/convert.py:725-780, odoo/addons/base/models/ir_fields.py:491-560, odoo/tools/translate.py:1312-1343, addons/crm_iap_mine/data/crm.iap.lead.industry.csv:1-2, addons/l10n_th/data/template/account.tax.group-th.csv:1

## Demo data

- Files in the manifest `demo` key, loaded as superuser with `install_demo=True` in the context and
  `noupdate=True`.
- New databases get demo only with `--with-demo` (`--without-demo` is the default). A module gets
  demo only if all its dependencies have it (`demo_installable`).
- A failing demo file does not abort the install: the module is installed without demo and an
  `ir.demo_failure` record is created.
- Large or benchmark datasets belong to `populate/` blueprints, not demo (see [populate.md](populate.md)).

Source: odoo/modules/loading.py:44-85,210-221, odoo/tools/config.py:261-265, odoo/modules/module_graph.py:202-203

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `<field name="image_1920" type="base64" file="m/static/img.png"/>` | `type="bytes" file=...` (XML006, upgrade script `19.3-00-base64-in-xml`) | odoo/tools/convert.py:139-145 |
| `pytz` module in `eval` (`.localize()`) | `zoneinfo`-backed shim; use `dt.replace(tzinfo=...)` (XML014) | odoo/tools/convert.py:39-42,58 |
| `security/ir.model.access.csv` and `<record model="ir.rule">` | `security/ir.access.csv` / `<record model="ir.access">` (SEC001, SEC002) | odoo/addons/base/models/ir_access.py:64 |
| `<template>` without `technical_usage` attribute in RNG | `technical_usage="..."` allowed | odoo/import_xml.rng:170 |
| `demo_xml`, `init_xml`, `update_xml` manifest keys | `data` / `demo` (MAN001) | odoo/modules/module.py:75-76 |
| `convert_file(..., kind=...)` | `kind` deprecated, ignored | odoo/tools/convert.py:702-707 |

Check a file before installing with `odoo_validate` (Odoo RNG + legacy rules), resolve xmlids with
`odoo_xmlid`, and install it on a throwaway database with `odoo_test`.
