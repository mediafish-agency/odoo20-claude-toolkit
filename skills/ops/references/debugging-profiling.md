# Debugging and profiling (Odoo 20)

Tools to understand a misbehaving Odoo 20 instance or module: logging recipes, `--dev` features, browser
debug modes, `odoo-bin shell`, process signals, the built-in profiler (speedscope), query counting in
tests, and the error messages you will meet most often with what they mean in 20.

## Contents
- [Logging recipes](#logging-recipes)
- [Reading the HTTP log line](#reading-the-http-log-line)
- [--dev features](#--dev-features)
- [Debug mode in the browser](#debug-mode-in-the-browser)
- [odoo-bin shell](#odoo-bin-shell)
- [Signals](#signals)
- [Profiler](#profiler)
- [Query counting](#query-counting)
- [Common errors in Odoo 20](#common-errors-in-odoo-20)

## Logging recipes

| Goal | Flags |
|---|---|
| your module only | `--log-handler=odoo.addons.my_module:DEBUG` (module code: `_logger = logging.getLogger(__name__)`) |
| every SQL query | `--log-sql` = `--log-handler=odoo.sql_db:DEBUG` (or `--log-level=debug_sql`) |
| request dispatch details | `--log-web` = `--log-handler=odoo.http:DEBUG` |
| everything from Odoo | `--log-level=debug` (= `odoo:DEBUG`, `odoo.sql_db:INFO`) |
| quieter tests | `--log-level=warn` (`odoo:WARNING`) |
| mute a noisy logger | `--log-handler=odoo.addons.rpc.controllers.jsonrpc:ERROR` |
| full control | `--log-config logging.json` (dictConfig) |

`--log-handler` is repeatable and comma separated in the config file (`log_handler = :INFO,odoo.sql_db:DEBUG`).
`debug_rpc` / `debug_rpc_answer` are accepted but do nothing in 20.

Source: odoo/tools/config.py:349-378, odoo/netsvc.py:150-190

## Reading the HTTP log line

Logger `odoo.http.server` (Odoo's own h11 server, not werkzeug):

```text
<remote_addr> <ident> <http_auth> [<date>] "<request line>" <status> <body size> <query_count> <query_time> <remaining_time> <cursor_mode>
```

- `ident` is `S/<8 chars of session id>` or `B/<8 chars of the API key>`.
- `query_count`/`query_time` = SQL work of the request, `remaining_time` = Python time; `cursor_mode` is
  `ro`, `rw` or `ro->rw` (a read-only route that wrote and was retried).
- Accessing a missing route prints the 404 in this line; exceptions are logged by `odoo.http` with the
  traceback (`AccessError`/`UserError` as warnings, tracebacks only with `--dev=access`).

Source: odoo/http/server_log.py:36-140,276, odoo/http/router.py:298-311

## --dev features

| Feature | Use it when |
|---|---|
| `reload` | editing Python: auto-restart (install `inotify` or `watchdog`) |
| `xml` | editing view/template XML of an installed module: archs read from disk, no `-u` (new records still need `-u`) |
| `qweb` | QWeb rendering errors: logs the compiled code and source line |
| `access` | `AccessError` in HTTP requests: logs the traceback |
| `replica` | checking that `readonly=True` routes / `@api.readonly` methods do not write |

Combine: `--dev=reload,xml,qweb` or `--dev=all` (`access,qweb,reload,xml`). See [config.md](config.md#developer-mode---dev).

Source: odoo/tools/config.py:31,462-470, odoo/service/server.py:1600-1612

## Debug mode in the browser

| URL | Effect |
|---|---|
| `/odoo?debug=1` | technical features (debug menu, field tooltips, full tracebacks in frontend errors) |
| `/odoo?debug=assets` | load assets non-minified with source maps (also serves `/<module>/static` without cache) |
| `/odoo?debug=tests` | also load the test assets (tours) |
| `?debug=assets,tests` | several modes, comma separated |
| `?debug=0` (any falsy value) | leave debug mode |

The mode is stored in the session. In JS read it with `odoo.debug` or `usePlugin(DebugModePlugin)`;
`env.debug` throws in 20 (rule JS008).

Source: addons/web/models/ir_http.py:34-65, odoo/http/router.py:335-341

## odoo-bin shell

```bash
./odoo-bin shell -c odoo.conf -d dev20 --log-level=warn
```

```python
env['my_library.book']._fields['state']                 # field object (selection, compute...)
env['ir.ui.view'].browse(42).get_combined_arch()         # final arch of a view
book = env['my_library.book'].create({'name': 'Test'})   # superuser: no ir.access checks
reader = env.ref('base.user_demo')                       # exists only with demo data
env['my_library.book'].with_user(reader).search([])      # reproduce an AccessError
env.cr.commit()                                          # otherwise everything is rolled back on exit
from odoo.tests.shell import run_tests; run_tests(env, '/my_library')   # threaded mode only
```

Pipe a script for one-shot checks (`... shell -d dev20 < check.py`). The MCP `odoo_shell` tool runs code
the same way on an allowlisted db and refuses commits unless writes are allowed.

Source: odoo/cli/shell.py:79-150, odoo/tests/shell.py:19-55, odoo/addons/base/models/ir_ui_view.py:1059

## Signals

| Signal to the server process | Effect |
|---|---|
| `kill -QUIT <pid>` | dump the stack of every thread to the log (`dumpstacks`) |
| `kill -USR1 <pid>` / `-USR2` | log ormcache statistics (`log_ormcache_stats`) |
| `kill -HUP <pid>` | restart (re-exec) the server, same as a `--dev=reload` restart |
| first `SIGINT`/`SIGTERM` | graceful stop; a second one forces the exit |

Source: odoo/service/server.py:276-310,513-531,1000-1015, odoo/tools/misc.py:826, odoo/orm/cache.py:184

## Profiler

`odoo.tools.profiler.Profiler` records collector entries for a block of code and stores them in
`ir.profile` (or keeps them in memory with `db=None`).

```python
from odoo.tools.profiler import Profiler

with Profiler(db=None, collectors=['sql', 'traces_async'], log=True) as prof:   # log=True: summary in the log
    env['sale.order'].search([])._compute_amounts()
print(prof.json()[:500])          # or prof.summary()
```

| Parameter | Meaning |
|---|---|
| `collectors` | names `sql`, `traces_async` (periodic stack sampling, default with `sql`), `qweb`, or `Collector` instances such as `PeriodicCollector(interval=0.01)` |
| `db` | database where `ir_profile` rows are saved; default = current thread's db; `None` = do not save |
| `description`, `profile_session` | labels to group profiles (`make_session(name)`) |
| `params` | collector parameters, e.g. `{'entry_count_limit': ..., 'time_limit': ...}` |
| `disable_gc` | avoid GC pauses in the measurement |

- Saved profiles: model `ir.profile` (form view, SQL query list with *Explain Analyze*), flame graphs at
  `/web/speedscope/<id>[,<id>...]`.
- Profile live requests: an admin enables profiling for a period (wizard `base.enable.profiling.wizard`,
  ICP `base.profiling_enabled_until`), then in debug mode use the debug menu's profiling item or
  `/web/set_profiling?profile=1&collectors=sql,traces_async`; every request of that session is profiled
  until disabled (`profile=0`) or expiry.
- In tests: `with self.profile(): ...` (`BaseCase.profile`; on `HttpCase` it also profiles each HTTP
  request made by the test).
- `ExecutionContext(**ctx)` adds labelled frames to the samples.

Source: odoo/tools/profiler.py:64-110,162-350,441-676, odoo/addons/base/models/ir_profile.py:162-279,
addons/web/controllers/profiling.py:14-60, odoo/http/router.py:462-493, odoo/tests/common.py:1060-1069,3010-3020

## Query counting

```python
from odoo.tests import TransactionCase, users, warmup


class TestPerf(TransactionCase):

    @users('admin')
    @warmup
    def test_search_cost(self):
        with self.assertQueryCount(admin=3):          # or assertQueryCount(3)
            self.env['my_library.book'].search([]).mapped('name')

    @warmup
    def test_exact_sql(self):
        with self.assertQueries(["SELECT ... FROM \"my_library_book\" ..."]):
            self.env['my_library.book'].search([])
```

- `@warmup` runs the test once to fill caches (assertions ignored, changes rolled back), then for
  real; without it the assertions run on cold caches and the counts are unstable.
- `assertQueries` compares with `QueryLike`: case and whitespace insensitive, `...` matches anything.
- Outside tests: `env.cr.sql_log_count` before/after, or `--log-sql`, or the HTTP log `query_count`.
- More test patterns: the `odoo20:testing` skill.

Source: odoo/tests/common.py:589,851-925,1243-1262,3097-3120

## Common errors in Odoo 20

| Message (start) | Meaning / fix |
|---|---|
| `You are not allowed to access '<Model>' (<model>) records.` + "This operation is allowed for the following groups" / "No group currently allows this operation." | no `ir.access` **permission** row for the user's groups and operation: add a row to `security/ir.access.csv` |
| `Uh-oh! Looks like you have stumbled upon some top-secret records.` | record-level failure: a permission/restriction **domain** excludes these records (debug mode lists the failing accesses; often multi-company) |
| `Field "x" does not exist in model "y"` (inside "Error while validating view near: ...") | view uses a field of a module not in `depends`, a typo, or a field removed in 20 (`acc_number`, `company_type`...) |
| `Element '<xpath ...>' cannot be located in parent view` | the xpath does not match the combined parent arch: inspect it with `odoo_views ... resolve="db"` |
| `Invalid view <name> definition in <file>` | the arch fails the RNG (`<tree>`, unknown attributes) |
| `Since 17.0, the "attrs" and "states" attributes are no longer used.` | convert to `invisible="..."`/`readonly="..."` expressions (rule XML002) |
| `ParseError: while parsing <file>:<line>` | a data file failed; the nested error says why (missing xmlid, bad field, access) |
| `External ID not found in the system: <xmlid>` | wrong module prefix or missing `depends` / load order in `data` |
| `You try to install module "a" that depends on module "b". But the latter module is not available` | `b` missing from `addons_path` (or removed in 20, e.g. `base_iban`, `base_vat`) |
| `module x: not installable, skipped` / `has an incompatible version, setting installable=False` | `installable: False` or a manifest `version` like `19.0.1.0` (use `1.0` or `20.0.x.y`) |
| `Unable to install module "x" because an external dependency is not met: y` | a manifest `external_dependencies` python package or binary is missing in the runtime |
| `Session expired (invalid CSRF token)` | POST to a `type='http'` route without `csrf_token` |
| `Request inferred type is compatible with [...] but '/x' is type='...'` (415) | client sent the wrong `Content-Type` for the route type |
| `Private methods (such as 'm._x') cannot be called remotely.` | RPC/JSON-2 call to a `_method` or `@api.private` method |
| `Missing "Authorization" or Sec-headers for interactive usage.` | bearer route called from JS/script without an API key |
| `Couldn't bind the websocket. Is the connection opened on the evented port (8072)?` | proxy sends `/websocket` to 8069 in workers mode |
| `...: use BinaryValue instead of bytes` | raw `bytes` written to a Binary field (only `raw` accepts bytes); pass base64 str or `BinaryValue` |
| `DeprecationWarning: Since 20.0 import ormcache from odoo.api` | `from odoo.tools import ormcache` -> `from odoo.api import ormcache` (rule ORM003) |

Most of these are caught before runtime by `odoo_validate` (legacy rules, RNG, field/xmlid checks).

Source: odoo/addons/base/models/ir_access.py:48-53,325-470, odoo/addons/base/models/ir_ui_view.py:505-550,2029,
odoo/tools/template_inheritance.py:146,343, odoo/tools/convert.py:634-645, odoo/addons/base/models/ir_model.py:2368,
odoo/addons/base/models/ir_module.py:349-360,390, odoo/modules/module_graph.py:242, odoo/modules/module.py:497-502,617-643,
odoo/http/dispatcher.py:260, odoo/http/router.py:546-553, odoo/orm/models.py:207, odoo/addons/base/models/ir_http.py:356-359,
addons/bus/websocket.py:866, odoo/orm/fields_binary.py:110, odoo/tools/cache/__init__.py:2
