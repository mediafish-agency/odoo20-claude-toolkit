# Populate: synthetic data blueprints (Odoo 20)

Odoo 20 replaces the v19 `odoo-bin populate` duplication tool with the `populate` addon: declarative
`populate.blueprint` records (XML or JSON) executed by `odoo-bin populate -d DB -b <blueprint>`.
The old duplication tool survives as `odoo-bin duplicate`. Read this to write a blueprint for your
module, run it, or pick between the two tools. The addon's own `addons/populate/README.md` is the
long-form manual; this page is the verified quick reference.

## Contents
- [populate vs duplicate](#populate-vs-duplicate)
- [Running a blueprint](#running-a-blueprint)
- [Where blueprints live and how they load](#where-blueprints-live-and-how-they-load)
- [Blueprint record and operation blocks](#blueprint-record-and-operation-blocks)
- [field / value / arg attributes](#field--value--arg-attributes)
- [Generators](#generators)
- [Distributions and dynamic dates](#distributions-and-dynamic-dates)
- [Relations, references, imports, inheritance](#relations-references-imports-inheritance)
- [Custom generators](#custom-generators)
- [Sessions, parallelism, retries](#sessions-parallelism-retries)
- [Pitfalls](#pitfalls)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## populate vs duplicate

| Need | Tool | Source |
|---|---|---|
| Realistic, controlled data for a module (counts, distributions, relations, workflows) | `odoo-bin populate -d DB -b xmlid` (addon `populate`, must be installed) | addons/populate/cli/populate.py |
| Blow up existing data volume by copying rows (SQL-level duplication) | `odoo-bin duplicate -d DB --models a.b,c.d --factors 10,3 [--sep _]` | odoo/cli/duplicate.py, odoo/tools/duplicate.py |

`duplicate` defaults: `--factors 10000`, `--models res.partner,product.template,account.move,
sale.order,crm.lead,stock.picking,project.task`, `--sep _`; it skips transient/abstract models.

Source: odoo/cli/duplicate.py:13-70

## Running a blueprint

Prerequisites:
1. The `populate` addon is installed in the DB (the CLI exits otherwise) and Python `faker` is
   installed (`addons/populate/requirements.txt`); without faker the `fake.*` generators are not
   registered and blueprints using them fail.
2. After installing a module that ships blueprints, **upgrade `populate`** (`-u populate` or
   `odoo-bin module upgrade -d DB populate`): blueprints are only scanned when `populate` itself is
   installed or upgraded.

```bash
./odoo-bin populate -d mydb -b project.fake_project_demo --scale 10 -j 4
./odoo-bin populate -d mydb --resume          # last unfinished session
./odoo-bin populate -d mydb --resume 42       # a given session id
./odoo-bin --addons-path=addons,../custom populate -c odoo.conf -d mydb -b my_module.my_blueprint
```

| Flag | Meaning |
|---|---|
| `-b`, `--blueprint` | full xmlid, or the blueprint `name` (must be unique) |
| `--seed INT` | RNG seed (random when omitted) |
| `--scale FLOAT` | multiplies every `count` (default `1`; blocks with `scale="False"` are not scaled) |
| `-j`, `--jobs N\|auto` | worker processes (default `1`; `auto` = `os.cpu_count()`) |
| `--resume [ID]` | resume the last (no value) or a given interrupted session |
| `--profile` | one `ir.profile` row per executed job |

All normal server options (`-c`, `-d`, `--db_host`...) are accepted: the command calls
`config.parse_config(['--no-http'] + cmdargs)`. Exactly one database is required. To find an addon
CLI command, `odoo-bin` scans `*/cli/<command>.py` on the addons path; `--addons-path=` must then
be the **first** argument, written with `=`.

Source: addons/populate/cli/populate.py:25-150, addons/populate/README.md, addons/populate/generators/__init__.py:54-70, odoo/cli/command.py:67-140

## Where blueprints live and how they load

- Files: `<module>/populate/*.xml`, ordinary `<odoo><record model="populate.blueprint">` data files.
  **Not** listed in the manifest (the model only exists when `populate` is installed) and the module
  does **not** depend on `populate` (`addons/project/__manifest__.py` has no such dependency).
- Loader: `populate.blueprint._register_hook()` runs `load_populate(env)` when `populate` is in
  `registry.updated_modules`. It walks installed modules in dependency order, imports
  `odoo.addons.<module>.populate` if `populate/__init__.py` exists (custom generators), then loads the
  folder's `*.xml` files sorted by name with `convert_file(..., mode='init', noupdate=False)`.
- xmlids are `<module>.<id>` as in any data file. Core examples: `odoo/addons/base/populate/common.xml`
  (`base.fake_partners`, `base.fake_internal_users`), `addons/product/populate/common.xml`
  (`product.fake_products`), `addons/{project,sale,product,account,stock}/populate/populate_demo.xml`
  and `benchmarks.xml`.

Source: addons/populate/models/blueprint.py:309-313, addons/populate/utils/loading.py:15-72, odoo/addons/base/populate/common.xml

## Blueprint record and operation blocks

```xml
<odoo>
    <record id="my_blueprint" model="populate.blueprint">
        <field name="name">Library - Populate Demo</field>
        <field name="definition_xml" type="xml">
            <import ref="base.fake_partners" as="customers"/>
            <create model="library.book" count="500" id="books">
                <field name="name" generator="fake.catch_phrase"/>
                <field name="isbn" generator="misc.counter" start="1000" unique="True"/>
                <field name="author_id" ref="customers/partners" null_ratio="0.1"/>
                <field name="state" values="{'draft': 3, 'available': 6, 'lost': 1}"/>
                <field name="date_published" start="today -20y" end="today"/>
            </create>
            <function model="library.book" name="action_archive" ref="books" domain="[('state', '=', 'lost')]" batched="True"/>
        </field>
    </record>
</odoo>
```

`populate.blueprint` fields: `name` (required), `inherit_id`, `definition_xml` (Char, write it with
`type="xml"`), `definition_json` (Json), computed `definition`. One of XML/JSON is required
(`_has_definition`); XML wins when both are set. `@api.constrains` `_check_definition` validates
models, field names, method names and duplicate names at load.

| Block | Purpose | Allowed attributes |
|---|---|---|
| `<create>` | create `count` records | `model` (req), `count` (req), `id`, `scale`, `parallel`, `context` |
| `<write>` | write generated values | `model`, `ref`, `domain`, `batched`, `parallel`, `context` |
| `<function>` | call a method on targets | `model`, `name` (method), `ref`, `domain`, `batched`, `parallel`, `context`; children `<arg>` |
| `<import>` | inline another blueprint's blocks (XML only) | `ref` (req, xmlid), `as` (namespace); children are xpath specs |

- `<create>` rejects `ref` and `domain`; `<write>`/`<function>` reject `id`.
- Targets of write/function: `ref` only, `domain` only, both (intersection), neither (all records).
- `batched="True"`: one value set and one `write`/call per job instead of per record.
- `context` is a Python dict literal (`literal_eval`), e.g. `{'mail_auto_subscribe_no_notify': True}`
  or `{'tracking_disable': True}` as in core blueprints.

Source: addons/populate/models/blueprint.py:18-60, addons/populate/utils/xml.py:41-170, addons/populate/README.md, addons/project/populate/populate_demo.xml

## field / value / arg attributes

- `<field name>` = persisted ORM value; `<value name>` = local variable usable by later
  fields/values/args (not written); `<arg>` = method argument (named -> kwarg, unnamed -> positional).

| Attribute | Meaning |
|---|---|
| `generator` | generator name (see below); omitted -> `misc.eval` if `eval` given, else the default for the field type |
| `eval` | Python expression; other targets of the block are referenced by name; context has `env`, `model`, `Command` only. Must not start with `lambda`. |
| `values` | list (equal weights) or weighted dict literal: `"{'draft': 4, 'sale': 6}"` |
| `null_ratio` | probability of `False` (0-1); **raises** on a required field or together with weighted `values` |
| `unique` | `True` to force unique values |
| `distribution` | e.g. `normal(mean=50, std=10)`; cannot be combined with `values` |
| `domain` | relational pick filter; may reference sibling targets (dynamic) |
| `ref` | restrict picks to records of a populate reference (`id`), namespaced or dot-path |
| generator params | `start`, `end`, `step`, `length`, `count`, `std`, `groupby`, `partition`, `comodel_name`, faker kwargs, `locale` |

Source: addons/populate/generators/generator.py:113-230, addons/populate/generators/misc.py:106-181, addons/populate/models/job.py:403-416

## Generators

Default generator by field type (`DEFAULT_GENERATORS`): boolean `scalar.boolean`, integer
`scalar.integer`, float `scalar.float`, monetary `scalar.monetary`, char `textual.char`,
text/html `textual.text`, date `temporal.date`, datetime `temporal.datetime`, selection
`choice.selection`, binary `binary.binary`, many2one `relation.one`, one2many/many2many
`relation.many`, many2one_reference `reference.one`, reference `reference.raw`, properties
`properties.value`, properties_definition `properties.definition`. Other types need `generator`/`eval`.

| Family | Names | Key params |
|---|---|---|
| scalar | `scalar.boolean`, `scalar.integer`, `scalar.float`, `scalar.monetary` | `start`, `end`; monetary needs its currency field generated too |
| textual | `textual.char`, `textual.text` | `length`, `char_set` |
| temporal | `temporal.date`, `temporal.datetime` | `start`, `end` (`"today -6m"`, `"now +90d"`) |
| choice | `choice.selection`, `choice.sample` | `values` |
| binary | `binary.binary`, `binary.image` | `size` / `width`, `height` |
| relation | `relation.one`, `relation.many` | `domain`, `ref`, `comodel_name` (for `<value>`), `partition`; many: `count` (req), `std`, `groupby` |
| reference | `reference.one`, `reference.raw` | `partition`; raw: `res_model`, `res_id`, `ref` |
| misc | `misc.counter`, `misc.cycle`, `misc.eval` | counter `start`, `step`, `end`; cycle `values` |
| properties | `properties.definition`, `properties.prop`, `properties.value` | |
| faker | `fake.<method>` (e.g. `fake.company`, `fake.email`, `fake.paragraph`) | method kwargs (`nb_words="5"`), `locale` |

Faker methods are limited to an allow-list of providers (address, company, internet, lorem,
person, phone_number, ...): see the README list.

Source: addons/populate/generators/generator.py:31-51, addons/populate/generators/*.py, addons/populate/generators/relation.py:21-149, addons/populate/README.md

## Distributions and dynamic dates

`distribution="..."` accepts `normal(mean, std)`, `uniform(min, max)`, `exponential(rate)`,
`beta(alpha, beta)` (mapped onto `start`/`end`), `poisson(lam)`, `triangular(min, max, mode)`.
Without it values are uniform. Temporal `start`/`end` go through `odoo.tools.date_utils.parse_date`,
the same relative-date grammar as domains (`today -1y`, `today -6m +1d`, `now -20d`), see
[domain.md](../../orm/references/domain.md).

```xml
<field name="date_order" start="now -2y" end="now" distribution="exponential(rate=0.003)"/>
<value name="qty_delivered_ratio" generator="scalar.float" start="0" end="1" distribution="beta(alpha=2, beta=2)"/>
```

Source: addons/populate/utils/distributions.py:229-500, addons/populate/generators/temporal.py:19-31, addons/sale/populate/populate_demo.xml

## Relations, references, imports, inheritance

- `ref="orders"` picks among records created by the block with `id="orders"`; `ref="customers/partners"`
  reads the `partners` reference of an `<import ... as="customers"/>`; `ref="my_projects.task_ids"`
  follows a field path from the referenced records.
- Dynamic domain: `<field name="task_id" domain="[('project_id', '=', project_id)]"/>` evaluates
  `project_id` from the current record's generated values.
- `partition="True"` gives each parallel worker a distinct slice of comodel ids.
- `<import ref="product.fake_product_demo" as="catalog">` with `<xpath expr="//create[@id='products']"
  position="attributes"><attribute name="count">500</attribute></xpath>` children customises the
  import. The caller's module must depend on the imported blueprint's module.
- `inherit_id` + `definition_xml` with `position="attributes|inside|before|after|replace"` or
  `<xpath>` specs extends another blueprint (cycles rejected).

Source: addons/populate/README.md, addons/populate/models/blueprint.py:220-307, addons/sale/populate/populate_demo.xml, addons/project/populate/populate_demo.xml

## Custom generators

Put them in `<module>/populate/__init__.py` (imported by the loader). A concrete subclass of
`Generator` registers itself under its `name` (`__init_subclass__`):

```python
# my_module/populate/__init__.py  (pattern from addons/populate/generators/misc.py)
from odoo.addons.populate.generators import Generator


class LibraryCode(Generator):
    name = 'library.code'            # use in XML: generator="library.code"
    allowed_on = ('char', 'value')

    def __init__(self, prefix='LIB', **kwargs):
        super().__init__(**kwargs)
        self.prefix = prefix

    def _next(self, known_vals):
        return f"{self.prefix}-{self.random.randrange(10**6):06d}"

    @classmethod
    def convert_to_kwargs(cls, attrs):
        kwargs = super().convert_to_kwargs(attrs)
        if 'prefix' in attrs:
            kwargs['prefix'] = attrs['prefix']
        return kwargs
```

Use `self.random` (seeded per job) for reproducibility; `known_vals` holds already generated targets.
No core module ships a custom generator yet (no `populate/__init__.py` in core addons).

Source: addons/populate/generators/generator.py:72-100, addons/populate/generators/generator.py:144-152, addons/populate/generators/generator.py:331-360, addons/populate/generators/misc.py:10-80, addons/populate/utils/loading.py:46-55

## Sessions, parallelism, retries

- Each run creates a `populate.session` with `populate.job` rows; created records are tracked in
  `populate.model.data`. Access is read-only for `base.group_system` (`addons/populate/security/ir.access.csv`).
- Jobs above `MAX_RECORD_COMMIT_SIZE` (1000) are split into sub-jobs; with `-j > 1` they run in
  worker processes (disable per block with `parallel="False"`, or globally with env var
  `ODOO_POPULATE_MULTIPROCESS_ENABLE=False`).
- Unique/not-null/check/exclusion violations re-roll the job seed and retry; only persistent failures
  surface.

Source: addons/populate/models/session.py:60-100, addons/populate/models/job.py:32-46, addons/populate/models/job.py:165-175, addons/populate/README.md

## Pitfalls

- Blueprint not found -> `populate` was not upgraded after installing your module, or the name is
  ambiguous (use the full xmlid).
- Listing `populate/*.xml` in the manifest `data` breaks install on DBs without `populate`.
- `null_ratio` on a required field, or with weighted `values`, raises instead of being ignored.
- Mail-heavy models: pass `context="{'mail_auto_subscribe_no_notify': True}"` (or
  `tracking_disable`) like core blueprints, or populate spends its time in notifications.
- Business states: create in draft and reach the final state through a `<function>` block
  (e.g. `account.move` `_post`, README), not by writing `state` directly when the model has logic.
- Never run populate or duplicate on production: use a throwaway DB (`odoo_db`, `odoo-bin db duplicate -n`).

Source: addons/populate/cli/populate.py:110-135, addons/populate/generators/generator.py:190-215, odoo/addons/base/populate/common.xml

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `odoo-bin populate --models x --factors 10` (row duplication) | `odoo-bin duplicate --models x --factors 10` | odoo/cli/duplicate.py |
| `odoo.tools.populate.populate_models` | `odoo.tools.duplicate.duplicate_models` | odoo/tools/duplicate.py |
| hand-written scripts / demo XML to create volume | `<module>/populate/*.xml` blueprints + `odoo-bin populate -b` | addons/populate/README.md |
| `populate/` folder absent from module layout | canonical optional dir (see [module structure](../../odoo-guidelines/guidelines/module_structure.md)) | skills/odoo-guidelines/guidelines/module_structure.md |
