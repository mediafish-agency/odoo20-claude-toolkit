# Python tests (Odoo 20)

How to write server-side tests for an Odoo 20 addon: test classes, tags, `Form`, helpers
(`new_test_user`, `users`, `warmup`, query counts, time freezing, HTTP mocking) and recipes for
access, constraint and onchange tests. House rules (what to test, tagging policy, silent skips)
live in [Odoo test guidelines](../../odoo-guidelines/guidelines/tests.md); this file is the API.

## Contents

- File layout and discovery
- Test classes
- BaseCommon runs as a non-admin user (v20)
- Tags
- Helper reference
- Outgoing HTTP is blocked: MockHTTPClient
- Form (server-side form view)
- Recipes: access, constraints, onchange, query counts, time
- HttpCase essentials
- v19 habit -> Odoo 20

## File layout and discovery

```text
my_module/
  tests/
    __init__.py          # from . import test_book, test_book_access
    common.py            # shared base class (not named test_*, not collected)
    test_book.py         # test classes are DEFINED here
```

- Only submodules of `<addon>.tests` whose name starts with `test_` are scanned, and only if
  `tests/__init__.py` imports them (`inspect.getmembers(tests_mod, inspect.ismodule)`).
- A class is collected only from the module that defines it (`obj.__module__ == module.__name__`);
  only methods named `test*` defined on that class run, unless the class sets
  `allow_inherited_tests_method = True`.
- Upgrade tests are also collected from `<addon>/migrations/tests/test_*.py`,
  `<addon>/upgrades/tests/test_*.py` and `odoo.upgrade.<addon>`.
- Methods run sorted by name; `test_sequence` on a class orders classes in the suite.

Source: odoo/tests/loader.py, odoo/tests/suite.py

## Test classes

Import from `odoo.tests` (re-exports everything public from `odoo.tests.common`, plus `Form`,
`O2MProxy`, `M2MProxy`).

| Class | Module | Use |
|---|---|---|
| `TransactionCase` | `odoo.tests` | Default. One transaction per class, a savepoint per test, rolled back. Put shared data in `setUpClass` (`cls.env` is superuser). `cr.commit()`/`rollback()` raise. |
| `HttpCase` | `odoo.tests` | `TransactionCase` + test HTTP server + headless Chrome (`url_open`, `authenticate`, `browser_js`, `start_tour`, `make_jsonrpc_request`). Keep it `post_install`. |
| `BaseCase` | `odoo.tests` | Abstract base of the two above (assertions, `ref`, `patch`, query helpers). Do not subclass directly. |
| `CrossModule` | `odoo.tests` | Runs once with the list of selected modules (used by `web/tests/test_js.py`). Rarely needed in addons. |
| `BaseCommon` | `odoo.addons.base.tests.common` | Recommended base for business tests: independent company/user hooks, mail side effects disabled, **tests run as a non-admin user** (see below). |
| `TransactionCaseWithUserDemo` / `HttpCaseWithUserDemo` | `odoo.addons.base.tests.common` | Provide `cls.user_demo`/`cls.partner_demo` (created if demo data is absent). |
| `TransactionCaseWithUserPortal` / `HttpCaseWithUserPortal` | `odoo.addons.base.tests.common` | Provide `cls.user_portal`/`cls.partner_portal` (login `portal`, created if absent). |
| `SavepointCaseWithUserDemo` | `odoo.addons.base.tests.common` | Demo user + a set of partners (`_load_partners_set`). |
| `MockSmtplibCase` | `odoo.addons.base.tests.common` | Mixin: `mock_smtplib_connection()`, `assertSMTPEmailsSent(...)`. |

There is no `SingleTransactionCase` any more (TEST001).

Source: odoo/tests/__init__.py, odoo/tests/common.py:580 (BaseCase), :1305 (TransactionCase),
:2603 (HttpCase), :1187 (CrossModule), odoo/addons/base/tests/common.py:17

## BaseCommon runs as a non-admin user (v20)

New in 20.0: `BaseCommon` creates an internal user `test_user` in `setUpClass` and, before each
test, switches `self.env` to it and re-binds every recordset attribute of the test to that env.

| Attribute / hook | Meaning |
|---|---|
| `_test_user_groups = ('base.group_user',)` | Groups (xmlids) of `test_user`. Missing groups (module not installed) are ignored. Set `None` or `()` to keep running as the class env user (core uses `None  # FIXME` in ~650 classes). |
| `_test_user_name = 'Test User'` | Display name of the test user. |
| `cls._test_user` | The user the tests run as (or `cls.env.user` when groups are empty). |
| `default_env_context()` | Returns `DISABLED_MAIL_CREATE_CONTEXT` (`mail_create_nolog`, `mail_create_nosubscribe`, `no_reset_password`); override to re-enable tracking. |
| `setup_independent_company(**kw)` / `setup_independent_user()` | Return a company/user to isolate from demo data (default `None`). |
| `setup_main_company(currency_code='USD')`, `setup_other_currency(code, rates=[...])` | Currency setup. |
| `_create_partner`, `_create_company`, `_create_new_internal_user`, `_create_new_portal_user`, `quick_ref(xmlid)` | Factories. |
| `cls.company`, `cls.currency`, `cls.partner`, `cls.group_user/portal/public/system` | Ready-made records. |

Data created in `setUpClass` is created with `cls.env` (superuser or the independent user);
only the test methods run as `test_user`. A test that needs more rights must list the groups:

```python
from odoo.addons.base.tests.common import BaseCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestBook(BaseCommon):
    _test_user_groups = ('base.group_user', 'my_module.group_library_manager')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.book = cls.env['library.book'].create({'name': 'Dune'})

    def test_rename(self):
        self.assertEqual(self.env.user, self._test_user)   # not admin
        self.book.name = 'Dune Messiah'                     # runs with test_user's rights
```

Source: odoo/addons/base/tests/common.py:17-200, addons/delivery/tests/test_delivery_cost.py:14

## Tags

`@tagged(*tags)` (class decorator). Every `BaseCase` subclass in an addon starts with
`{'standard', 'post_install'}`; `-tag` removes a tag; tags are inherited by subclasses.

| Want | Decorator |
|---|---|
| Default (after all modules are loaded) | nothing, or `@tagged('post_install', '-at_install')` |
| Run right after this module installs, before others load | `@tagged('at_install', '-post_install')` (justify it; never for `HttpCase`) |
| Extra selectable tag | `@tagged('post_install', '-at_install', 'my_slow')` -> run with `--test-tags my_slow` |
| Opt-in only (not in normal runs) | `@tagged('-standard', 'my_bench')` -> runs only when `my_bench` is selected |

A class with both or neither of `at_install`/`post_install` only logs a warning (both = runs
twice, neither = never runs). The module name also matches as a tag (deprecated retro-compat).
Selection syntax: [running-tests.md](running-tests.md).

Source: odoo/tests/common.py:3141 (tagged), :597 (`__init_subclass__` defaults),
odoo/tests/tag_selector.py

## Helper reference

| Helper | Import | Notes |
|---|---|---|
| `new_test_user(env, login, groups='base.group_user', context=None, **vals)` | `odoo.tests` | `groups` = comma-separated xmlids (or pass `group_ids=` ids). Password defaults to `login` padded with `x` to 8 chars; email generated if missing. |
| `@users('login1', 'login2')` | `odoo.tests` | Runs the method once per login (subTest), switching `self.uid`, invalidating cache between runs. Users must exist (create them in `setUpClass`). |
| `@warmup` | `odoo.tests` | Runs the method once to warm caches (assertions on queries ignored), then for real. Pair with `@users` and `assertQueryCount`. |
| `with self.assertQueryCount(N)` / `assertQueryCount(admin=3, demo=5)` | method | Flushes before/after; only *more* queries fails, fewer only logs. |
| `with self.assertQueries([...])` | method | Exact query list, compared with `QueryLike` (case/space-insensitive, `...` wildcard). |
| `QueryLike(sql)`, `Like(pattern)`, `WhitespaceInsensitive(s)`, `Approx(value, rounding, decorate=...)` | `odoo.tests` | Fuzzy comparison wrappers for `assertEqual`/`assertIn`. |
| `self.assertRecordValues(records, [dict, ...], field_names=None)` | method | Ordered comparison; m2o by id, x2many by id list. |
| `RecordCapturer(model, domain)` | `odoo.tests` | `with RecordCapturer(self.env['x'], []) as cap: ...; cap.records` = records created inside. |
| `freeze_time(...)` | `odoo.tests` (also patches `freezegun.freeze_time`) | Decorator on method or **class** (`cls.freeze_time`, started in `setUpClass`) or context manager. |
| `self.mock_datetime_and_now(dt)` | `TransactionCase` classmethod (new in 20.0 core) | `freeze_time` **and** patches `env.cr.now()`; sets `cls.frozen_datetime_mock`. |
| `MockHTTPClient(url=..., method=..., matcher=..., return_json=..., return_body=..., return_status=..., return_headers=..., side_effect=...)` | `odoo.tests` | New in 20.0. See next section. |
| `self.registry_test_mode()` | classmethod context manager (new) | New cursors from the registry wrap the test cursor (`TestCursor`). `HttpCase` enters it for the whole class. Replaces `registry_enter_test_mode`/`registry_leave_test_mode`. |
| `self.allow_pdf_render()` | context manager | Lets wkhtmltopdf call back the test server (not needed in `HttpCase`). |
| `self.file_read(path)` | classmethod (new) | Reads an addon file via `file_open`, returns `BinaryBytes`. |
| `with self.with_user('login'):`, `with self.debug_mode():` | `BaseCase` | Temporarily switch user / enable debug-mode groups. |
| `self.patch(obj, key, val)`, `self.startPatcher(p)`, `self.enterContext(cm)` (+ `classPatch`, `startClassPatcher`, `enterClassContext`) | `BaseCase` | Auto-undone at cleanup. Leftover patchers are stopped with a warning. |
| `standalone(*tags)` | `odoo.tests` | Registers a function test that may install/uninstall modules; run by the `odoo/tests/test_module_operations.py` script, not by `--test-tags`. |
| `no_retry`, `can_import(module)`, `loaded_demo_data(env)` | `odoo.tests` | Disable auto-retry; skip if optional lib missing; demo present? |
| `try_report(cr, uid, rname, ids, data=None, ...)`, `try_report_action(cr, uid, action_id, ...)` | `odoo.tests.reports` (new location) | Render a report / follow an action until a report is produced. |
| `mute_logger('odoo.sql_db')` | `odoo.tools` | Silence expected error logs. |

Source: odoo/tests/common.py:268, 317, 851, 880, 929, 1079, 1243, 1478, 1490, 3063, 3097,
3166; odoo/tests/reports.py:18,64

## Outgoing HTTP is blocked: MockHTTPClient

For classes tagged `standard`, `requests.Session.send` is patched: requests to anything other
than `127.0.0.1`/`localhost`/`file:` raise `BlockedRequest` ("External requests verboten").
Mock them:

```python
import requests
from odoo.tests import MockHTTPClient, TransactionCase


class TestCarrierApi(TransactionCase):
    def test_rate(self):
        with MockHTTPClient(
            url='https://api.example.com/v1/rates',      # scheme/host/port/path/query compared if given
            method='POST',
            return_json={'price': 12.5},                 # or return_body=..., not both
        ) as mock:
            rate = self.env['my.carrier']._fetch_rate()  # code under test calls requests.post(...)
        mock.assert_called_once()                        # also assert_called(n_times), assert_not_called()
        self.assertEqual(rate, 12.5)
        self.assertIn(b'"weight"', mock.calls[0].body)   # calls = list of PreparedRequest
```

Non-matching requests fall through to the outer mock or the real (blocked) sender, so mocks nest.
`return_*` and `side_effect` accept callables taking the `PreparedRequest`.

Source: odoo/tests/common.py:373-563 (MockHTTPClient), :616 (BaseCase._request_handler)

## Form (server-side form view)

`Form(record_or_empty_model, view=None)` replays the form view: defaults + onchanges on creation,
onchange on each assignment, view modifiers enforced. `view` = id, xmlid or `ir.ui.view` record.

```python
from odoo.tests import Form

with Form(self.env['sale.order']) as so_form:          # empty recordset -> creation mode
    so_form.partner_id = self.partner                  # triggers onchanges
    with so_form.order_line.new() as line:             # One2many: O2MProxy.new()/edit(i)/remove(index=i)
        line.product_id = self.product
        line.product_uom_qty = 3
so = so_form.record                                    # saved on context exit

form = Form(so)                                        # singleton -> edit mode
form.tag_ids.add(self.tag)                             # Many2many: add/remove(id=|index=)/set/clear
self.assertEqual(form.amount_total, 30.0)              # read computed/onchange values
so = form.save()                                       # returns the record
```

- Assigning a field that is not in the view, `readonly` or `invisible` raises `AssertionError`;
  a missing required field fails at `save()`. One2many fields cannot be assigned directly.
- Many2one values must be recordsets of the right model.
- `Form.from_action(env, action_dict)` opens the form an `ir.actions.act_window` would open
  (first view must be `form`; `context` and `res_id` are applied).
- `form.record` is only readable when there are no pending changes.

Source: odoo/tests/form.py:27-480

## Recipes

### Access (ir.access)

```python
from odoo.exceptions import AccessError
from odoo.tests import new_test_user, users
from odoo.addons.base.tests.common import BaseCommon


class TestBookAccess(BaseCommon):
    _test_user_groups = None            # tests switch users explicitly

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        new_test_user(cls.env, login='librarian', groups='base.group_user,my_module.group_library_manager')
        new_test_user(cls.env, login='reader', groups='base.group_user')
        cls.book = cls.env['library.book'].create({'name': 'Dune'})

    @users('reader')
    def test_reader_cannot_write(self):
        book = self.book.with_user(self.env.user)
        self.assertTrue(book.has_access('read'))
        self.assertFalse(book.has_access('write'))
        with self.assertRaises(AccessError):
            book.name = 'x'             # write() calls check_access('write') immediately
```

`check_access(op)` raises, `has_access(op)` returns a bool, `_filtered_access(op)` filters.
`self.assertRaises` opens a savepoint for you and clears the cache when expecting `AccessError`.
Check the effective rows with `odoo_access` before writing expectations.

Source: odoo/orm/models.py:3443, 3464, 3506; odoo/tests/common.py:790 (`_raisesContext`);
addons/project/tests/test_access_rights.py

### Constraints

```python
from psycopg2 import IntegrityError
from odoo.exceptions import ValidationError
from odoo.tools import mute_logger

def test_unique_isbn(self):                      # models.Constraint('UNIQUE(isbn)', ...)
    self.env['library.book'].create({'name': 'A', 'isbn': '1'})
    with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
        self.env['library.book'].create({'name': 'B', 'isbn': '1'})

def test_pages_positive(self):                   # @api.constrains python check
    with self.assertRaises(ValidationError):
        self.book.pages = -1                     # write() runs _validate_fields
```

No manual savepoint needed: `BaseCase.assertRaises` wraps the block in `cr.savepoint()`, so the
transaction stays usable. Specific errors exist too (`psycopg2.errors.UniqueViolation`,
`CheckViolation`, `NotNullViolation`). Odoo 20 pins psycopg2.

Source: addons/fleet/tests/test_unique_license_plate.py, addons/hr/tests/test_hr_version.py:46,
requirements.txt:36

### Onchange

Use `Form`: it calls the same `onchange()` as the web client and respects the view.

```python
form = Form(self.env['library.loan'])
form.book_id = self.book
self.assertEqual(form.due_date, fields.Date.today() + timedelta(days=14))
```

### Query counts

```python
from odoo.tests import users, warmup

@users('admin', 'reader')
@warmup
def test_list_books_perf(self):
    with self.assertQueryCount(admin=3, reader=4):
        self.env['library.book'].search([]).mapped('name')
```

Only in dedicated performance classes; see the guidelines link at the top.

### Time

```python
from odoo.tests import freeze_time

@freeze_time('2025-01-31 10:00:00')
def test_overdue(self): ...

def test_sync(self):
    with self.mock_datetime_and_now('2025-01-31 10:00:00'):   # also fixes env.cr.now()
        ...
```

## HttpCase essentials

- `self.url_open(url, data=None, json=None, method=None, ...)`: relative URLs are prefixed with
  `base_url()`; `data`/`json`/`files` imply POST.
- `self.authenticate(login, password)` logs the opener (and browser) session in.
- `self.make_jsonrpc_request(route, params)` posts JSON-RPC and returns `result` or raises
  `JsonRpcException`.
- `self.start_tour(url, tour_name, login='admin')`: see [tours.md](tours.md).
- Chrome missing or `websocket-client` missing -> browser tests are **skipped**, not failed.

Source: odoo/tests/common.py:2733, 2787, 2985, 3033, 2483

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `SingleTransactionCase` | `TransactionCase` (or `BaseCommon`) | odoo/tests/common.py (TEST001) |
| `self.registry_enter_test_mode()` / `registry_leave_test_mode()` / `registry_enter_test_mode_cls()` | `with self.registry_test_mode():` (`enter_registry_test_mode()` remains a deprecated alias) | odoo/tests/common.py:1079, 1497 (TEST002) |
| `self.assertQueriesContain(...)` | `assertQueries([...])` with `...` wildcards, or `QueryLike` | odoo/tests/common.py:851 (TEST002) |
| `from odoo.tools import test_reports` / `odoo.tools.test_reports` | `from odoo.tests.reports import try_report, try_report_action` | odoo/tests/reports.py (TEST003) |
| Per-addon `mock_datetime_and_now` copies (mail, sms, event tests) | `TransactionCase.mock_datetime_and_now` | odoo/tests/common.py:1478 |
| `unittest.mock.patch('requests...')` for external calls | `MockHTTPClient(...)` | odoo/tests/common.py:380 |
| `BaseCommon` tests run as superuser | run as `test_user`; set `_test_user_groups` (or `None`) | odoo/addons/base/tests/common.py:87 |
| `ir.model.access` rows created in test setup | `ir.access` records (`operation`, `domain`) | odoo/addons/base/models/ir_access.py |

Run the legacy checks with `odoo_validate` (rules TEST001-TEST003) and execute tests with
`odoo_test` (see [running-tests.md](running-tests.md)).
