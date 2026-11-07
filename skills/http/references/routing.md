# HTTP routing and controllers (Odoo 20)

How to write `controllers/*.py` in Odoo 20: the `odoo.http` package (no compat shims), every `@route()`
option, auth methods incl. `bearer`, URL converters, controller overriding, the `request` API and error
handling per route type. House rules (auth choice, POST/CSRF) live in
[controllers guidelines](../../odoo-guidelines/guidelines/controllers.md) and
[odoo-security: Routes](../../odoo-security/SKILL.md#routes-auth-post-csrf); this file is the API reference.

## Contents
- [Package layout and imports](#package-layout-and-imports)
- [Minimal controller](#minimal-controller)
- [route() options](#route-options)
- [Route types: http, jsonrpc, json2](#route-types-http-jsonrpc-json2)
- [Auth methods](#auth-methods)
- [URL converters](#url-converters)
- [Overriding a controller](#overriding-a-controller)
- [The request object](#the-request-object)
- [Responses](#responses)
- [Errors per route type](#errors-per-route-type)
- [Read-only routes](#read-only-routes)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## Package layout and imports

`odoo/http/__init__.py` only defines `request` (a `LocalProxy`), `request_var`, `Response`,
`Controller`, `route`, then imports the submodules. Everything else must be imported from its submodule.

| Submodule | What lives there (import from here) |
|---|---|
| `odoo.http` | `request`, `Response`, `Controller`, `route`, `request_var` |
| `odoo.http.requestlib` | `Request` class, `fragment_to_query_string`, `is_cors_preflight`, `CSRF_TOKEN_SALT` |
| `odoo.http.routing_map` | `Controller`, `route`, `ROUTING_KEYS` |
| `odoo.http.dispatcher` | `HttpDispatcher`, `JsonRPCDispatcher`, `Json2Dispatcher`, `serialize_exception`, `conceal_debug_traceback`, `SAFE_HTTP_METHODS` |
| `odoo.http.router` | `root` (WSGI `Application`), `db_list`, `db_filter`, `dispatch_rpc`, `serve_db` |
| `odoo.http.session` | `Session`, `SessionExpiredException`, `authenticate`, `finalize`, `logout`, `touch`, `check`, `session_store`, `get_default_session` |
| `odoo.http.stream` | `Stream`, `content_disposition`, `STATIC_CACHE`, `STATIC_CACHE_LONG` |
| `odoo.http.response` | `Response` (unsafe base), `FutureResponse` |
| `odoo.http.retrying` | `retrying()` (serialization-failure retry loop) |

- `from odoo import http` then `http.Controller` / `http.route` / `http.request` is what most core code
  does; `from odoo.http import Controller, request, route` is equally valid.
- Pitfall: `from odoo.http import session` imports the **module** `odoo.http.session`, not the current
  session. The current session is `request.session`.
- `odoo.http.Response` is the "safe" facade (`_facade.SafeResponse`) around werkzeug's Response.

Source: odoo/http/__init__.py, odoo/http/router.py, odoo/http/dispatcher.py, odoo/http/session.py,
odoo/http/stream.py, odoo/http/_facade.py

## Minimal controller

```python
# my_module/controllers/main.py   (controllers/__init__.py: from . import main)
from odoo import http
from odoo.http import request


class MyController(http.Controller):

    @http.route('/my_module/books', type='http', auth='user', methods=['GET'], readonly=True)
    def books(self, **kw):
        books = request.env['my_module.book'].search([], limit=80)
        return request.render('my_module.books_page', {'books': books})

    @http.route('/my_module/book/<int:book_id>/toggle', type='jsonrpc', auth='user', methods=['POST'])
    def toggle(self, book_id):
        book = request.env['my_module.book'].browse(book_id).exists()
        if not book:
            raise request.not_found()
        book.action_toggle()
        return {'state': book.state}
```

- The module's root `__init__.py` must import `controllers`. Controllers are only routed when their
  addon is installed (or is a server-wide module).
- `self.env` works in controllers (`Controller.env` returns `request.env`); core v20 code uses both.

Source: odoo/http/routing_map.py:73, addons/sale/controllers/portal.py

## route() options

`route(route=None, **routing)`; `route` is a path or a list of paths (werkzeug rule syntax).

| Option | Default | Meaning |
|---|---|---|
| `type` | `'http'` | `'http'`, `'jsonrpc'` or `'json2'`. `'json'` still works but warns (deprecated alias of `jsonrpc`). Asserted against registered dispatchers. |
| `auth` | `'user'` | `'user'`, `'public'`, `'none'`, `'bearer'` (or a custom `_auth_method_<x>`). |
| `bearer_scope` | - | Required with `auth='bearer'` (assert), meaningless otherwise. Core uses `'rpc'`. |
| `methods` | all | e.g. `['POST']`. `OPTIONS` is appended automatically to the werkzeug rule. `method=` (singular) is accepted with a warning. |
| `csrf` | `True` | Only checked by the `http` dispatcher, for non-safe methods (not GET/HEAD/OPTIONS/TRACE). No effect on `jsonrpc`/`json2`. |
| `cors` | - | Value of `Access-Control-Allow-Origin`; also answers `OPTIONS` preflight with 204 (auth forced to `none` for the preflight). |
| `readonly` | `False` (`True` for `auth='none'`) | Use a read-only cursor; may be a callable `(controller, rule, args) -> bool`. See [Read-only routes](#read-only-routes). |
| `save_session` | `True` (`False` for `auth='bearer'`) | Set the `session_id` cookie / persist a dirty session. |
| `captcha` | - | Action name; `ir.http._verify_request_recaptcha_token(action)` runs for non-safe methods (e.g. `captcha='signup'`). |
| `handle_params_access_error` | - | `callable(exc, **args)` called when a `model(...)` converter record is missing/unreadable; may return a Response or status code to abort with. |
| `max_content_length` | 128 MiB (ICP `web.max_file_upload_size`) | Per-route upload limit (int, `None`, or callable taking the controller). |
| `check_identity` | `True` | `False` skips the "confirm your identity" check for `auth='user'` routes. |
| werkzeug keys | - | `alias`, `build_only`, `defaults`, `host`, `redirect_to`, `strict_slashes`, `subdomain`, `websocket` are passed to the werkzeug `Rule`. |
| `website` | `False` | (`http_routing`/`website`) frontend route: language prefix, `request.is_frontend`, website context. |
| `multilang` | `type == 'http'` | (`http_routing`) whether the URL accepts a `/<lang>/` prefix when `website=True`. |
| `sitemap` | - | (`website`) `False` to exclude, `True`, or a generator `sitemap(env, rule, qs)` yielding `{'loc': url}`. |
| `list_as_website_content` | - | (`website`) translatable label to list the route as a technical page. |

Source: odoo/http/routing_map.py:30-227, odoo/http/dispatcher.py:168-197, odoo/addons/base/models/ir_http.py:380-486,
addons/http_routing/models/ir_http.py:389, addons/website/models/website.py:1710-1830,
addons/auth_signup/controllers/main.py:40, addons/web/controllers/database.py:268

## Route types: http, jsonrpc, json2

| | `http` | `jsonrpc` | `json2` |
|---|---|---|---|
| Accepted request Content-Type | anything | `application/json`, `application/json-rpc` | `application/json` or empty body |
| Endpoint kwargs | query string + form + files + path args | `params` object of the JSON-RPC body + path args | top-level JSON object of the body + path args |
| Return value | `Response`, `str`, `bytes`, `None` (anything else: `TypeError`) | any JSON-serializable value, wrapped as `{"jsonrpc": "2.0", "id", "result"}` | any JSON-serializable value (recordsets: return `.ids`), or a `Response` returned as-is |
| CSRF | token required on unsafe methods | none (JSON content type is the protection) | none |
| Client | browser forms/links, QWeb pages | web client `rpc()` (`@web/core/network/rpc`), Interactions | external API (`/json/2`), see [json2-api.md](json2-api.md) |

- A Content-Type that does not match the route type is rejected with **415** ("Request inferred type is
  compatible with ... Please verify the Content-Type request header").
- Unknown kwargs are dropped with a warning (`... called ignoring args {...}`); declare `**kw` to accept
  extra parameters.
- JSON values are serialized with `odoo.tools.json_default` (dates -> strings, `Domain` -> list,
  `BinaryValue` -> decoded string, anything else `str()`).

Source: odoo/http/dispatcher.py:226-472, odoo/http/routing_map.py:211-222, odoo/http/response.py:47-78,
odoo/tools/json.py:61

## Auth methods

| `auth` | Behaviour |
|---|---|
| `user` | Session user required; public/no user raises `SessionExpiredException` (http: redirect to `/web/login?redirect=...`; jsonrpc: error code 100). |
| `public` | Session user if logged in, else `base.public_user` (website: the website's user). |
| `none` | `request.env` has no user (`uid=None`); only `auth='none'` routes are served when there is no database. Read-only by default. |
| `bearer` | `Authorization: Bearer <api key>` checked with `res.users.apikeys._check_credentials(scope=bearer_scope, key=...)`; invalid -> 401 `Invalid apikey`. Without header, falls back to the session **only** for top-level browser navigations (`Sec-Fetch-*` headers), otherwise 401. Session never saved. |

Authentication runs **before** the dispatcher parses the body, so `request.params` is not set yet inside
an auth method (use `request.get_http_params()` / `request.get_json_data()`).

Custom method on `ir.http` (v20 signature receives the routing dict, rule HTTP005):

```python
from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _auth_method_my_token(cls, routing: dict):
        cls._auth_method_public(routing)
        token = request.httprequest.headers.get('X-My-Token')
        ...  # raise werkzeug.exceptions.Unauthorized / AccessDenied when invalid
```

Then `@http.route('/x', auth='my_token', type='json2', save_session=False)`.

Source: odoo/addons/base/models/ir_http.py:318-421, addons/im_livechat/models/ir_http.py:12-50

## URL converters

| Converter | Example | Value passed |
|---|---|---|
| `int` (signed in Odoo) | `/order/<int:order_id>` | `int` |
| `string`, `path` | `/doc/<string:name>`, `/json/<path:subpath>` | `str` |
| `model("x")` | `/event/<model("event.event"):event>/ics` | one record; read access checked before the endpoint: MissingError -> 404, AccessError -> 404 for public users, 403 otherwise |
| `models("x")` | `/download/<models("ir.attachment"):attachments>` | recordset from `1,2,3` |

`http_routing`/`website` extend `model(...)` to accept slugs (`name-42`) and to build sitemaps. Use
`env['ir.http']._slug(record)` / `_unslug(value)` to build or parse them.

Source: odoo/addons/base/models/ir_http.py:112-145,248-250,453-475, addons/event/controllers/main.py:16,
addons/account/controllers/download_docs.py:30

## Overriding a controller

```python
from odoo.http import request, route
from odoo.addons.portal.controllers.portal import CustomerPortal


class MyPortal(CustomerPortal):

    @route()                      # mandatory re-decoration; empty = keep parent routing
    def home(self, **kw):
        response = super().home(**kw)
        response.qcontext['my_extra'] = 42   # lazy Response: qcontext still editable
        return response

    @route(sitemap=False)          # any argument overrides the parent's value, the rest is kept
    def account(self, **kw):
        return super().account(**kw)
```

- Routing of all classes in the MRO is merged (ancestors first). `type` can never change (warning,
  parent type kept). Changing `readonly` in an override always ends read/write (warning logged): a child
  can relax a read-only route but cannot make a read/write route read-only.
- An override without `@route()` still works but logs "is not decorated by @route(), decorating it
  myself".
- Only classes defined in **installed** addons take part: Odoo rebuilds one class per top controller
  from the installed leaf subclasses, so do not instantiate controllers yourself.
- All installed leaf subclasses of a controller are combined, so subclassing portal's `CustomerPortal`
  is enough to extend portal methods; subclass `odoo.addons.sale.controllers.portal.CustomerPortal`
  only when you call sale's own helpers (it extends `payment.PaymentPortal`).

Source: odoo/http/routing_map.py:73-365, addons/sale/controllers/portal.py:15

## The request object

`request` is only bound inside an HTTP request (`unbound_message="request not bound"`); check `if request:`
in model code that may run from cron/shell.

| Attribute / method | Notes |
|---|---|
| `env`, `registry`, `db`, `session` | `env` is None for `auth='none'` without db; `db` is the database name |
| `params` | dict of endpoint kwargs (set by the dispatcher) |
| `httprequest` | werkzeug request facade: `method`, `path`, `args`, `form`, `files`, `headers`, `cookies`, `host_url`, `get_data()`, `remote_addr`, `user_agent` ... |
| `update_env(user=None, context=None, su=None)` | replace the request env (keeps the cursor) |
| `update_context(**overrides)` | merge into `request.env.context` |
| `get_http_params()` / `get_json_data()` | parse query+form+files / JSON body yourself |
| `make_response(data, headers=None, cookies=None, status=200)` | raw `Response` |
| `make_json_response(data, headers=None, cookies=None, status=200)` | JSON body + `Content-Type: application/json; charset=utf-8` |
| `render(template, qcontext=None, lazy=True, **kw)` | lazy QWeb `Response`; `lazy=False` returns the rendered markup; `**kw` go to `Response` (`headers=`, `status=`) |
| `redirect(location, code=303, local=True)` | `local=True` strips scheme/host (open-redirect safe); pass `local=False` for external URLs |
| `redirect_query(location, query=None, code=303, local=True)` | redirect with an url-encoded query |
| `not_found(description=None)` | returns a `NotFound` exception: **raise** it |
| `csrf_token(time_limit=None)` / `validate_csrf(token)` | form tokens (see [portal-controllers.md](portal-controllers.md#forms-and-csrf)) |
| `reroute(path, query_string=None)` | internal rewrite without a 3xx |
| `future_response` | headers/cookies to add to whatever response is returned (`request.future_response.set_cookie(...)`) |
| `best_lang`, `default_lang()`, `cookies`, `geoip` | browser language, sanitized cookies, GeoIP lookup |
| `lang`, `is_frontend`, `is_frontend_multilang` | set by `http_routing` (frontend routes) |

Deprecated since 19 (warn): `request.context`, `request.uid`, `request.cr` -> use `request.env.context`,
`request.env.uid`, `request.env.cr`. `request.website` does not exist in 20: use `request.env.website`
(property on `Environment`, model `website` is defined in `base`).

Source: odoo/http/requestlib.py:121-416, odoo/http/__init__.py:13, odoo/orm/environments.py:306,
odoo/addons/base/models/website.py, addons/http_routing/models/ir_http.py:389-493

## Responses

- `type='http'` endpoints go through `Response.load()`: a `Response` is kept, `str`/`bytes`/`None`
  become a `text/html` Response, a werkzeug Response is converted, an `HTTPException` returned (instead
  of raised) is raised with a warning.
- `request.render(...)` responses stay lazy until `ir.http._dispatch` flattens them, which is why an
  override can still edit `response.qcontext`.
- Files: use `odoo.http.stream` / `ir.binary`, see [sessions-streams.md](sessions-streams.md).
- `Response.set_cookie(..., cookie_type='required')`: non-required cookies get `max_age=0` when the
  visitor refused optional cookies (`ir.http._is_allowed_cookie`).

```python
return request.make_json_response({'ok': True}, status=201)
return request.redirect('/my/home')
return request.make_response(csv_bytes, headers=[
    ('Content-Type', 'text/csv'),
    ('Content-Disposition', content_disposition('export.csv')),  # from odoo.http.stream
])
```

Source: odoo/http/response.py:17-146, odoo/addons/base/models/ir_http.py:477-486, addons/event/controllers/main.py:30

## Errors per route type

| Raised | `http` | `jsonrpc` | `json2` |
|---|---|---|---|
| `werkzeug.exceptions.HTTPException` (`NotFound`, `Forbidden`, `BadRequest`...) | that status | `error` object (`code` 404 for NotFound) | that status, JSON body |
| `UserError` | 422 | `error` object, HTTP 200 | 422 |
| `AccessError` / `AccessDenied` | 403 | `error` object | 403 |
| `MissingError` | 404 | `error` object | 404 |
| `LockError` | 409 | `error` object | 409 |
| `SessionExpiredException` | redirect to `/web/login` (or `/web/session/identity`) | `error.code = 100` | 403 |
| other exceptions | 500 | `error` object ("Odoo Server Error") | 500 |

- The error payload is `serialize_exception(exc)`: keys `name`, `message`, `arguments`, `timestamp`,
  `context`, `debug` (traceback).
- Hide the traceback of sensitive code with `@conceal_debug_traceback()` (decorator or context manager,
  from `odoo.http.dispatcher`).
- The `website` module turns `http` errors into rendered error pages via `ir.http._handle_error`.
- Serialization/concurrency errors are retried by `retrying()` (5 tries, random backoff); an
  `IntegrityError` is not retried, it surfaces as a `ValidationError` ("The operation cannot be completed: ...").

Source: odoo/http/dispatcher.py:78-136,269-472, odoo/exceptions.py, odoo/http/retrying.py

## Read-only routes

- `readonly=True` opens a read-only cursor (on the replica when `db_replica_host` is set). If the code
  writes anyway, `ReadOnlySqlTransaction` is caught and the request is retried on a read/write cursor
  with a warning. The HTTP log line ends with the cursor mode `ro`, `rw` or `ro->rw`.
- Read-only cursors are only used with a replica, with `--test-enable`, or with `--dev=replica`: use
  `--dev=replica` locally to detect accidental writes in routes declared read-only.
- `readonly` may be a callable, e.g. the JSON-2 route decides per model method via `@api.readonly`.
- Routes that call `_portal_ensure_token()` or create records must stay read/write (see the comment in
  `addons/sale/controllers/portal.py`).

Source: odoo/http/router.py:377-459, odoo/orm/registry.py:321,1163, addons/rpc/controllers/json2.py:22-56

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `from odoo.http import content_disposition, Stream` (HTTP001) | `from odoo.http.stream import content_disposition, Stream` | odoo/http/stream.py |
| `from odoo.http import serialize_exception` (HTTP001) | `from odoo.http.dispatcher import serialize_exception` | odoo/http/dispatcher.py:78 |
| `from odoo.http import root, dispatch_rpc, db_list, db_filter` (HTTP001) | `from odoo.http.router import ...` | odoo/http/router.py |
| `from odoo.http import SessionExpiredException, Session` (HTTP001) | `from odoo.http.session import ...` | odoo/http/session.py |
| `request.session.authenticate(env, cred)`, `.finalize()`, `.logout()`, `.touch()` (HTTP002) | `authenticate(request.session, env, cred)`, `finalize(session, env)`, `logout(session, keep_db=...)`, `touch(session)` from `odoo.http.session` | odoo/http/session.py:225-305 |
| `odoo.service.db` / `odoo.service.security` (HTTP003) | `odoo.modules.db`; session check `odoo.http.session.check` | odoo/modules/db.py |
| `@route(type='json')` (HTTP004) | `type='jsonrpc'` (internal) or `type='json2'` + `auth='bearer'` (API) | odoo/http/routing_map.py:189, odoo/upgrade_code/18.1-02-route-jsonrpc.py |
| `def _auth_method_x(cls)` (HTTP005) | `def _auth_method_x(cls, routing)` | odoo/addons/base/models/ir_http.py:319 |
| `root.session_store` | `session_store()` function | odoo/http/session.py:658 |
| `request.website` | `request.env.website` | odoo/orm/environments.py:306 |
| `Stream.from_binary_field(record, field)` | `request.env['ir.binary']._get_stream_from(record, field)` | odoo/addons/base/models/ir_binary.py:116 |
| `request.uid` / `request.cr` / `request.context` | `request.env.uid` / `.cr` / `.context` | odoo/http/requestlib.py:163-196 |

Check a controller file with `odoo_validate` (rules HTTP001-HTTP005) and find core examples of an
option with `odoo_grep "readonly=_" --module rpc` or `odoo_search route`.
