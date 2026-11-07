# Sessions, file streams and CORS (Odoo 20)

Server-side HTTP plumbing for controllers: the `request.session` object and the session functions of
`odoo.http.session` (methods became functions in 20), file downloads with `odoo.http.stream.Stream` and
`ir.binary`, the built-in `/web/content` and `/web/image` routes, uploads, and CORS.

## Contents
- [The session object](#the-session-object)
- [Session functions](#session-functions)
- [Logging a user in from a controller](#logging-a-user-in-from-a-controller)
- [Stateless requests: bearer and X-Odoo-Database](#stateless-requests-bearer-and-x-odoo-database)
- [Stream](#stream)
- [ir.binary helpers](#irbinary-helpers)
- [Download recipes](#download-recipes)
- [Built-in content routes](#built-in-content-routes)
- [Uploads](#uploads)
- [CORS](#cors)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## The session object

`request.session` is an `odoo.http.session.Session` (a `MutableMapping`) loaded from the `session_id`
cookie and stored as JSON files under `<data_dir>/sessions/` (`session_store()`).

| Member | Meaning |
|---|---|
| `uid`, `db`, `login`, `context`, `debug`, `session_token` | properties backed by keys of the same name |
| `sid` | session id (cookie value) |
| `can_save` | `False` for stateless requests (bearer, `X-Odoo-Database`, `save_session=False` routes) |
| `is_dirty`, `is_new`, `should_rotate` | persistence flags |
| `session['my_key'] = value` | values are JSON round-tripped (`json.loads(json.dumps(value))`): only JSON types |

- Assigning a new value marks the session dirty; mutating a nested value in place does **not**. Call
  `touch(request.session)` after `request.session['cart'].append(x)`.
- New sessions start from `get_default_session()`: `context`, `create_time`, `db`, `debug`, `login`,
  `uid`, `session_token`, `_devices`, `_device_salt`.
- Lifetime: cookie and server-side inactivity `SESSION_LIFETIME` (7 days) unless the ICP
  `sessions.max_inactivity_seconds` is set; authenticated sessions are soft-rotated every 3 hours
  (`SESSION_ROTATION_INTERVAL`); `ir.http._gc_sessions` (autovacuum) deletes stale files.
- `request.session` is saved by the dispatcher after the endpoint (`save_session(request)`); the cookie is
  `httponly`.

Source: odoo/http/session.py:36-215,458-697, odoo/http/router.py:496-532, odoo/addons/base/models/ir_http.py:536-541

## Session functions

All take the session explicitly (rule HTTP002 flags the old method calls).

| Function | Purpose |
|---|---|
| `authenticate(session, env, credential) -> auth_info` | checks `credential` (`{'login', 'password', 'type': 'password'}`) via `res.users.authenticate`; finalizes immediately unless MFA is required; updates `request.env` when the db matches |
| `finalize(session, env)` | turns the pre-login (`pre_login`/`pre_uid`) into a logged-in session (after MFA) |
| `logout(session, *, keep_db=False)` | resets the session (keeps `debug`), marks it for rotation, calls `ir.http._post_logout` |
| `touch(session)` | mark dirty so it is saved |
| `check(session, request_or_env)` | verify expiry + session token (raises `SessionExpiredException`); `ir.http` calls it for you |
| `update_session_token(session, env)` | recompute the token after credential changes |
| `save_session(request, env=None)` | persist / rotate + set cookie (pass `env` only when the db changed) |
| `session_store()` | the `SessionStore` (`get`, `save`, `delete`, `rotate`, `vacuum`) |
| `get_session_max_inactivity(env)` | effective lifetime in seconds |

Exceptions: `SessionExpiredException` (HTTP 403 in json2, redirect to `/web/login` in http routes) and
its subclass `CheckIdentityException` (redirect to `/web/session/identity`).

Source: odoo/http/session.py:84-91,198-456,658-697, odoo/http/dispatcher.py:280-301

## Logging a user in from a controller

Adapted from `/web/session/authenticate`:

```python
from odoo.http import Controller, request, route
from odoo.http.session import authenticate


class MyLogin(Controller):

    @route('/my_module/login', type='jsonrpc', auth='public', methods=['POST'])
    def my_login(self, login, password):
        credential = {'login': login, 'password': password, 'type': 'password'}
        auth_info = authenticate(request.session, request.env, credential)   # raises AccessDenied
        if auth_info['uid'] != request.session.uid:
            return {'mfa_required': True}         # finish through /web/login (2FA)
        return {'uid': request.session.uid}
```

- Prefer redirecting to `/web/login?redirect=...` for interactive logins (captcha, 2FA, rate limit are
  handled there).
- Logout: `logout(request.session, keep_db=True)` then `request.redirect('/web/login')`.

Source: addons/web/controllers/session.py:36-91, addons/web/controllers/home.py:110-140

## Stateless requests: bearer and X-Odoo-Database

- `auth='bearer'` routes default to `save_session=False`, and a valid Bearer key sets
  `session.can_save = False`: no cookie is ever issued, every call must carry the key.
- A request carrying `X-Odoo-Database` (and no session cookie) gets `session.can_save = False` too; a
  session cookie bound to another db plus the header -> 403.
- Without a `Authorization` header, a bearer route only accepts the session for top-level browser
  navigations (checks `Sec-Fetch-Dest/Mode/Site/User`); XHR/fetch from JS must send the key.
- Do not store per-client state in `request.session` on bearer routes; use records.

Source: odoo/http/routing_map.py:204-206, odoo/http/router.py:505-531, odoo/addons/base/models/ir_http.py:319-360

## Stream

`odoo.http.stream.Stream` describes a file to send; `get_response()` builds a cache-aware `Response`
(ETag, `If-None-Match` -> 304, ranges via werkzeug `send_file`).

| Attribute | Meaning |
|---|---|
| `type` | `'data'` (bytes in `data`), `'path'` (file `path`) or `'url'` (redirect to `url`) |
| `mimetype`, `download_name`, `size`, `etag`, `last_modified` | headers |
| `as_attachment`, `immutable`, `max_age`, `public` | defaults for `get_response()` / cache-control |

| Method | Notes |
|---|---|
| `Stream.from_path(path, filter_ext=(), public=False)` | addon resource (`'my_module/static/x.pdf'`, resolved with `file_path`, so only addons paths) |
| `stream.get_response(as_attachment=None, immutable=None, content_security_policy="default-src 'none'", **send_file_kwargs)` | `immutable=True` -> 1 year `max-age`; `max_age=None` disables caching |
| `stream.read()` | bytes (not for `url` streams) |

`content_disposition(filename, disposition_type='attachment')` returns an RFC 6266 header value
(`'inline'` to display in the browser).

With `--x-sendfile`, filestore paths are delegated to the proxy through `X-Accel-Redirect:
/web/filestore/<path>` (nginx must expose that location as `internal`).

Source: odoo/http/stream.py:24-225, addons/web/controllers/binary.py:22-53

## ir.binary helpers

`ir.binary` (AbstractModel in base) is the supported way to stream record files; there is no
`Stream.from_binary_field` / `from_attachment` in 20.

| Method | Notes |
|---|---|
| `_find_record(xmlid=None, res_model='ir.attachment', res_id=None, access_token=None, field=None)` | returns the record (sudo when an access token or `_can_return_content()` allows it, else `check_access('read')`); `MissingError` if absent |
| `_get_stream_from(record, field_name='raw', filename=None, filename_field='name', mimetype=None, default_mimetype='application/octet-stream')` | Stream from a Binary field (attachment-backed or not); fixes mimetype and `download_name` |
| `_get_image_stream_from(record, field_name='raw', ..., placeholder=None, width=0, height=0, crop=False, quality=0)` | same for images, with resize and placeholder fallback |
| `_record_to_stream(record, field_name)` | override hook for custom storage |
| `ir.attachment._to_http_stream()` | Stream of one attachment (path, url or data) |

`BaseModel._can_return_content(field_name, access_token)` (default `False`) is the hook a model
overrides to let unauthorized visitors fetch a file (e.g. `website` for published records,
`ir.attachment` for `public` / token-protected attachments).

Source: odoo/addons/base/models/ir_binary.py:20-298, odoo/addons/base/models/ir_attachment.py:1121-1175,
odoo/orm/models.py:5326

## Download recipes

```python
from odoo.http import Controller, request, route
from odoo.http.stream import content_disposition


class Downloads(Controller):

    # 1. a Binary field of a record the user may read
    @route('/my_module/book/<int:book_id>/cover', type='http', auth='user', readonly=True)
    def cover(self, book_id, download=False):
        book = request.env['my_module.book'].browse(book_id).exists()
        if not book:
            raise request.not_found()
        book.check_access('read')
        stream = request.env['ir.binary']._get_stream_from(book, 'cover_file', filename_field='cover_filename')
        return stream.get_response(as_attachment=bool(download))

    # 2. generated bytes
    @route('/my_module/books.csv', type='http', auth='user', readonly=True)
    def books_csv(self):
        data = request.env['my_module.book']._export_csv_bytes()     # your own helper
        return request.make_response(data, headers=[
            ('Content-Type', 'text/csv; charset=utf-8'),
            ('Content-Length', len(data)),
            ('Content-Disposition', content_disposition('books.csv')),
            ('X-Content-Type-Options', 'nosniff'),
        ])
```

- A file shipped in an addon: `Stream.from_path('my_module/static/doc/manual.pdf').get_response()`.
- Portal pattern (token or rights): `self._document_check_access(model, id, access_token)` then
  `env['ir.binary']._get_stream_from(document_sudo.ir_attachment_id).get_response(as_attachment=True)`
  (`addons/sale/controllers/portal.py`).
- PDF of a report: see `CustomerPortal._show_report()` in
  [portal-controllers.md](portal-controllers.md#reports-and-downloads).

Source: addons/sale/controllers/portal.py:460-475, addons/account/controllers/download_docs.py:11-38,
addons/im_livechat/controllers/main.py:51

## Built-in content routes

| Route (auth public, readonly) | Use |
|---|---|
| `/web/content/<int:id>`, `/web/content/<model>/<int:id>/<field>[/<filename>]`, `/web/content/<xmlid>` | any Binary field / attachment; query `download=1`, `filename`, `filename_field`, `mimetype`, `access_token`, `unique` (immutable 1-year cache), `nocache` |
| `/web/image/<model>/<int:id>/<field>[/<int:width>x<int:height>]`, `/web/image/<int:id>-<unique>` ... | images with resize (`width`, `height`, `crop`), placeholder on missing/forbidden (`save_session=False`) |
| `/web/assets/<unique>/<filename>` | compiled asset bundles |
| `/<module>/static/<path>` | static files (served before any db routing; 1-week cache, `max-age=0` with `?debug=assets`) |
| `/web/binary/upload_attachment` (auth user, POST, CSRF) | multipart `ufile` upload creating `ir.attachment` |
| `/web/binary/company_logo`, `/logo`, `/logo.png` (auth none, `cors='*'`) | company logo |

Access is decided by `ir.binary._find_record` (rights, record `_can_return_content`, or a limited
access token checked with `verify_limited_field_access_token(record, field, token, scope='binary')`).

Source: addons/web/controllers/binary.py:46-260, odoo/http/router.py:327-346, odoo/tools/misc.py:1882-1918

## Uploads

```python
@route('/my_module/import', type='http', auth='user', methods=['POST'])   # CSRF on: post csrf_token
def import_file(self, upload, **kw):
    content = upload.read()                      # werkzeug FileStorage; also request.httprequest.files
    request.env['my_module.book']._import_bytes(content, upload.filename)
    return request.redirect('/odoo/my-library-books')
```

- Max body size: 128 MiB, overridden by ICP `web.max_file_upload_size`, then by the route option
  `max_content_length` (e.g. `/web/database/restore` uses `None`).
- Multiple files with the same field name: `request.httprequest.files.getlist('ufile')`.
- JS uploads post `csrf_token: odoo.csrf_token` with the form data.

Source: odoo/http/_facade.py:10-21, odoo/addons/base/models/ir_http.py:432-447, odoo/http/dispatcher.py:193-197,
addons/web/controllers/binary.py:220-252, addons/web/static/src/core/file_upload/file_upload_service.js:42

## CORS

- `@route(..., cors='*')` (or an origin) adds `Access-Control-Allow-Origin` and
  `Access-Control-Allow-Methods` (`POST` for jsonrpc, otherwise the route `methods` or `GET, POST`).
- `OPTIONS` preflight is answered automatically with 204, `Access-Control-Max-Age: 86400` and
  `Access-Control-Allow-Headers: Origin, X-Requested-With, Content-Type, Accept, Authorization, Range`;
  authentication is skipped for the preflight only.
- CORS does not bypass CSRF: a cross-origin `type='http'` POST still needs a token, so cross-origin APIs
  use `type='json2'` or `jsonrpc` with `auth='bearer'`/`'public'` and explicit validation.
- Core examples: `/websocket` (`cors='*'`), `/logo.png`; JSON-2 (`/json/2`) has no CORS.

Source: odoo/http/dispatcher.py:47,168-197, odoo/http/requestlib.py:114-118, odoo/addons/base/models/ir_http.py:379-382,
addons/bus/controllers/websocket.py:12

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `request.session.authenticate(env, credential)` | `authenticate(request.session, env, credential)` | odoo/http/session.py:225 |
| `request.session.logout(keep_db=True)` | `logout(request.session, keep_db=True)` | odoo/http/session.py:291 |
| `request.session.touch()` | `touch(request.session)` | odoo/http/session.py:303 |
| `root.session_store` | `session_store()` | odoo/http/session.py:658 |
| `from odoo.http import Stream, content_disposition, STATIC_CACHE_LONG` | `from odoo.http.stream import ...` | odoo/http/stream.py |
| `Stream.from_binary_field(record, 'field')` | `request.env['ir.binary']._get_stream_from(record, 'field')` | odoo/addons/base/models/ir_binary.py:116 |
| `attachment.datas` (base64) in a download | `attachment.raw.content` / `_to_http_stream()` | odoo/addons/base/models/ir_attachment.py:1121 |

Find more core download controllers with `odoo_grep "_get_stream_from(" --type py` and check a
controller with `odoo_validate` (HTTP001, HTTP002, ORM014).
