# Odoo 20 module anatomy

Everything an Odoo 20 addon is made of: directory layout, `__init__.py` imports, every manifest key
accepted by 20 (`_DEFAULT_MANIFEST`), data-file load order, assets, and a minimal but complete module
(model + `ir.access.csv` + list/form/search views + action with `path` + menu + test) whose XML passes
Odoo's RNG schemas. Naming conventions: [module structure guidelines](../../odoo-guidelines/guidelines/module_structure.md)
and [manifest guidelines](../../odoo-guidelines/guidelines/manifest.md).

## Contents
- [Directory layout](#directory-layout)
- [Python packages and imports](#python-packages-and-imports)
- [Manifest keys](#manifest-keys)
- [Data files and load order](#data-files-and-load-order)
- [Assets](#assets)
- [Minimal complete module](#minimal-complete-module)
- [Install and test it](#install-and-test-it)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## Directory layout

```text
my_module/                     # name must match ^\w{1,256}$ (lowercase snake_case by convention)
|-- __init__.py                # from . import models, controllers, wizard
|-- __manifest__.py            # the only manifest file name read (MANIFEST_NAMES)
|-- models/                    # one model per file, models/__init__.py imports them
|-- wizard/                    # TransientModel + *_views.xml
|-- controllers/               # http.Controller subclasses (see odoo20:http)
|-- report/                    # ir.actions.report XML, QWeb report templates, SQL-view report models
|-- views/                     # *_views.xml (backend), *_templates.xml (QWeb pages), *_menus.xml
|-- security/                  # ir.access.csv (+ <module>_security.xml for groups/privileges)
|-- data/                      # *_data.xml / *.csv loaded on install+update; data/neutralize.sql
|-- demo/                      # demo data (manifest 'demo')
|-- populate/                  # populate.blueprint XML (not listed in the manifest)
|-- i18n/                      # my_module.pot + <lang>.po
|-- migrations/<version>/      # pre-*.py, post-*.py, end-*.py with migrate(cr, version)
|-- upgrades/<version>/        # same format, alternative location
|-- static/
|   |-- description/icon.png   # default module icon (else base's icon)
|   |-- src/                   # JS (ES modules), OWL XML templates, SCSS
|   `-- tests/                 # Hoot *.test.js, tours
`-- tests/                     # __init__.py + test_*.py (Python tests)
```

- `cli/<command>.py` may add an `odoo-bin` command (rare).
- Core keeps `security/ir.access.csv` last in `data` (213 of 227 community addons); it must at least come
  after the XML that defines the groups it references.

Source: odoo/modules/module.py:56-58,431-447, odoo/modules/migration.py:60-90, odoo/cli/command.py:68-90,
addons/sale/ (layout), addons/hr_skills/__manifest__.py

## Python packages and imports

```python
# my_module/__init__.py
from . import models
from . import controllers      # only if the folder exists

# my_module/models/__init__.py
from . import library_book
```

- Do **not** import `tests` from the root `__init__.py`: the test loader imports `my_module.tests` and
  collects the submodules whose name starts with `test_`, so `tests/__init__.py` must import each
  `test_*.py`.
- Hooks named in the manifest are looked up on the root package: `pre_init_hook(env)`,
  `post_init_hook(env)`, `uninstall_hook(env)`, `post_load()` (no argument, server-wide, at import).
- Use `from odoo import api, fields, models` (and `from odoo.fields import Command, Domain`).
- Typed relational annotations and `from __future__ import annotations` are supported; Odoo suggests
  them when a circular import breaks a comodel reference.

Source: odoo/tests/loader.py:47-66, odoo/modules/loading.py:176-180,236-241,547-549, odoo/modules/module.py:527-570

## Manifest keys

Required in practice: `name`, `author`, `license` (missing author/license only log a warning and default
to `''` / `LGPL-3`). All other keys and their defaults (`_DEFAULT_MANIFEST`):

| Key | Default | Meaning |
|---|---|---|
| `version` | `'1.0'` | 2-5 numeric parts; `x.y`/`x.y.z` are prefixed with `20.0.`; a version starting with another series (`19.0.1.0`) makes the module **not installable** |
| `depends` | `[]` -> `['base']` | direct dependencies (`base` is injected when empty) |
| `data` | `[]` | files loaded on install and update, in order |
| `demo` | `[]` | files loaded only when demo data is enabled |
| `assets` | `{}` | bundle -> list of globs/directives |
| `auto_install` | `False` | `True` (all `depends`) or a list subset of `depends`; `[]` = always |
| `application` | `False` | shows as an app |
| `installable` | `True` | |
| `category` | `'Uncategorized'` | `Parent/Child` path |
| `summary`, `description` | `''` | `description` defaults to `README.rst/.md/.txt` |
| `sequence` | 100 | order in the Apps menu |
| `website` | `''` | https URL |
| `images` | `[]` | screenshots (store) |
| `external_dependencies` | `{}` | `{'python': ['pkg>=1.0'], 'bin': ['wkhtmltopdf']}`, checked before install |
| `pre_init_hook`, `post_init_hook`, `uninstall_hook`, `post_load` | `''` | function names in the root package |
| `countries` | `[]` | ISO codes; one country -> flag icon (l10n modules) |
| `other_files` | `[]` | **new**: data files present in data dirs but loaded by code (e.g. `hr`'s scenario XML), declared so the "unused file" lint passes |
| `iap_paid_service` | `False` | **new**: module uses paid IAP services (stored on `ir.module.module`) |
| `cloc_exclude` | `[]` | globs excluded from `odoo-bin cloc` |
| `kpi_providers` | `[]` | `'module.path:function'` entries collected by `base_setup` |
| `bootstrap` | `False` | ship the module's translations to the login page / pre-session web client |
| `web` | `False` | legacy flag stored on `ir.module.module` |
| `test` | `[]` | legacy, unused |
| `configurator_snippets`, `configurator_snippets_addons`, `new_page_templates`, `theme_customizations`, `live_test_url` | | website themes |

Also tolerated by Odoo's manifest lint: `icon` (path, default `/<module>/static/description/icon.png`),
`contributors`, `maintainer`, `url`, `price`, `currency`, `support`. Removed in 20: `demo_xml`,
`init_xml`, `update_xml`, `images_preview_theme` (rule MAN001).

Source: odoo/modules/module.py:60-98,450-505,579-610, odoo/addons/test_lint/tests/test_manifests.py:15-31,
odoo/addons/base/models/ir_module.py:270-280,775-795, addons/base_setup/controllers/kpi.py:20-30,
addons/web/controllers/webclient.py:39-44, addons/hr/__manifest__.py:59-61

## Data files and load order

- Install: no migration script runs; Python imported, `pre_init_hook`, tables created, then each
  `data` file **in manifest order**, then `demo` files, `post_init_hook`. Update (`-u`): `pre`
  migrations, tables updated, `data` (mode `update`), `demo` if the module has demo, `post` migrations.
- File types: `.xml` (records, templates, menus), `.csv` (model = file name without extension, e.g.
  `ir.access.csv` -> `ir.access`, `res.partner.csv`), `.sql` (executed as is), `.js` ignored; anything
  else raises.
- A record can only reference xmlids already loaded: groups before access rows, actions before menus,
  views before actions that reference them.
- Demo files are loaded with `noupdate=True`; data XML uses `<odoo noupdate="1">` for records users
  may edit. Data file details: [data-files](../../data-security/references/data-files.md).

Source: odoo/modules/loading.py:44-86,160-245, odoo/tools/convert.py:700-722

## Assets

```python
{   # __manifest__.py excerpt
    'assets': {
        'web.assets_backend': [
            'my_module/static/src/backend/**/*',          # js, xml (OWL templates), scss
        ],
        'web.assets_frontend': [
            'my_module/static/src/interactions/**/*',     # public pages (Interactions)
        ],
        'web.assets_unit_tests': [
            'my_module/static/tests/**/*.test.js',        # Hoot
        ],
    },
}
```

Keep backend and frontend code in separate folders: a `static/src/**/*` glob in `web.assets_backend`
would also pull the Interactions into the backend bundle.

Files under `static/src` and `static/tests` are ES modules automatically (`@my_module/...` import
paths). Directives (`include`, `remove`, `prepend`, `before`, `after`, `replace`) and bundle names:
[assets](../../owl/references/assets.md). Check the resolved file list with `odoo_assets`.

Source: addons/web/__manifest__.py:46,159,459, addons/hr/__manifest__.py:62-75, odoo/tools/js_transpiler.py

## Minimal complete module

`my_library/__manifest__.py`

```python
{
    'name': "My Library",
    'summary': "Track the books of a small library",
    'version': '1.0',
    'category': 'Services',
    'depends': ['base'],
    'data': [
        'views/library_book_views.xml',
        'views/library_menus.xml',
        'security/ir.access.csv',
    ],
    'author': "My Company",
    'license': 'LGPL-3',
}
```

`__init__.py`: `from . import models`; `models/__init__.py`: `from . import library_book`.

`models/library_book.py`

```python
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class LibraryBook(models.Model):
    _name = 'my_library.book'
    _description = "Library Book"
    _order = 'name, id'

    name = fields.Char(required=True)
    isbn = fields.Char(string="ISBN")
    author_ids = fields.Many2many('res.partner', string="Authors")
    state = fields.Selection(
        [('draft', "Draft"), ('available', "Available"), ('lost', "Lost")],
        default='draft', required=True,
    )
    page_count = fields.Integer()
    is_long = fields.Boolean(compute='_compute_is_long', store=True)

    _isbn_uniq = models.Constraint('UNIQUE(isbn)', "The ISBN must be unique.")

    @api.depends('page_count')
    def _compute_is_long(self):
        for book in self:
            book.is_long = book.page_count > 500

    @api.constrains('page_count')
    def _check_page_count(self):
        if any(book.page_count < 0 for book in self):
            raise ValidationError(self.env._("A book cannot have a negative page count."))

    def action_make_available(self):
        self.write({'state': 'available'})
```

`security/ir.access.csv` (no row = nobody but the superuser can use the model)

```csv
id,name,model_id,group_id/id,operation,domain
access_my_library_book_user,my_library.book user,my_library.book,base.group_user,crud,
```

`views/library_book_views.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="library_book_view_list" model="ir.ui.view">
        <field name="name">my_library.book.list</field>
        <field name="model">my_library.book</field>
        <field name="arch" type="xml">
            <list decoration-muted="state == 'lost'">
                <field name="name"/>
                <field name="isbn" optional="show"/>
                <field name="author_ids" widget="many2many_tags"/>
                <field name="state"/>
                <field name="page_count" optional="hide"/>
            </list>
        </field>
    </record>

    <record id="library_book_view_form" model="ir.ui.view">
        <field name="name">my_library.book.form</field>
        <field name="model">my_library.book</field>
        <field name="arch" type="xml">
            <form>
                <header>
                    <button name="action_make_available" type="object" string="Make Available"
                            class="btn-primary" invisible="state != 'draft'"/>
                    <field name="state" widget="statusbar"/>
                </header>
                <sheet>
                    <div class="oe_title">
                        <h1><field name="name" placeholder="e.g. The Odyssey"/></h1>
                    </div>
                    <group>
                        <group>
                            <field name="isbn"/>
                            <field name="author_ids" widget="many2many_tags"/>
                        </group>
                        <group>
                            <field name="page_count"/>
                            <field name="is_long"/>
                        </group>
                    </group>
                </sheet>
            </form>
        </field>
    </record>

    <record id="library_book_view_search" model="ir.ui.view">
        <field name="name">my_library.book.search</field>
        <field name="model">my_library.book</field>
        <field name="arch" type="xml">
            <search>
                <field name="name"/>
                <field name="isbn"/>
                <filter name="available" string="Available" domain="[('state', '=', 'available')]"/>
                <separator/>
                <filter name="group_state" string="Status" context="{'group_by': 'state'}"/>
            </search>
        </field>
    </record>

    <record id="library_book_action" model="ir.actions.act_window">
        <field name="name">Books</field>
        <field name="res_model">my_library.book</field>
        <field name="path">my-library-books</field>
        <field name="view_mode">list,form</field>
    </record>
</odoo>
```

`views/library_menus.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <menuitem id="library_menu_root" name="Library" sequence="90">
        <menuitem id="library_book_menu" name="Books" action="library_book_action" sequence="10"/>
    </menuitem>
</odoo>
```

`tests/__init__.py`: `from . import test_library_book`; `tests/test_library_book.py`

```python
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestLibraryBook(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.book = cls.env['my_library.book'].create({'name': "The Odyssey", 'page_count': 560})

    def test_compute_and_action(self):
        self.assertTrue(self.book.is_long)
        self.book.action_make_available()
        self.assertEqual(self.book.state, 'available')

    def test_negative_pages(self):
        with self.assertRaises(ValidationError):
            self.book.page_count = -1

    def test_user_access(self):
        user = new_test_user(self.env, login='my_library_reader', groups='base.group_user')
        self.assertTrue(self.env['my_library.book'].with_user(user).has_access('create'))
```

- The action `path` makes the URL `/odoo/my-library-books`; it must match `[a-z][a-z0-9_-]*`, be unique,
  and not start with `m-`/`action-` nor be `new`.
- `ir.access` `operation` is an ordered subset of `crud`; a row with a group is a permission, without
  a group a restriction. Recipes: [ir-access](../../data-security/references/ir-access.md).
- The views validate against `odoo/import_xml.rng`, `base/rng/list_view.rng` and `search_view.rng`
  (form views are checked in Python at install).

Source: odoo/addons/base/models/ir_actions.py:70-100, odoo/orm/table_objects.py, odoo/tests/common.py:268,
odoo/orm/models.py:3464, addons/sale/security/ir.access.csv, odoo/addons/base/rng/list_view.rng,
odoo/addons/base/rng/search_view.rng

## Install and test it

```bash
./odoo-bin -c odoo.conf -d test20 -i my_library --test-tags /my_library --stop-after-init
```

Or with the MCP tools: `odoo_validate` on the folder (legacy rules, RNG, fields/xmlids, access), then
`odoo_test my_library` (throwaway database). `odoo_scaffold` generates this skeleton from the toolkit's
v20 templates; `odoo-bin scaffold` does **not**: its `default` template still writes
`security/ir.model.access.csv` (`id,name,model_id:id,group_id:id,perm_read,...`), which Odoo 20 ignores
as access definition (rules SEC002, MAN002).

Source: odoo/cli/templates/default/security/ir.model.access.csv.template, odoo/cli/templates/default/__manifest__.py.template

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `security/ir.model.access.csv` + `ir.rule` XML | `security/ir.access.csv` (`id,name,model_id,group_id/id,operation,domain`) | odoo/upgrade_code/19.4-00-ir-access.py |
| manifest `demo_xml` / `init_xml` / `update_xml` | `data` / `demo` (MAN001) | odoo/modules/module.py:60-98 |
| `load_manifest(name)` | `Manifest.for_addon(name)` or `get_manifest(name)` (ORM019) | odoo/modules/module.py:338,507 |
| `_sql_constraints = [...]` | `_x = models.Constraint('...', "msg")` (ORM012) | odoo/orm/table_objects.py |
| `<tree>` / `view_mode` `tree` | `<list>` / `list` (XML001) | odoo/addons/base/rng/list_view.rng |
| `version: '19.0.1.0'` | `'1.0'` or `'20.0.1.0'` (other series = not installable) | odoo/modules/module.py:579-610 |
| `odoo-bin scaffold` output used as is | `odoo_scaffold` or the example above | odoo/cli/templates/default/ |
