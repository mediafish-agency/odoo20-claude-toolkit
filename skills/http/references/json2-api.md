# JSON-2 external API (Odoo 20)

The supported way for external programs to call Odoo 20 models: `POST /json/2/<model>/<method>` with an
API key as Bearer token. Covers request/response format, status codes, API keys (UI and programmatic),
client code in Python, JavaScript and curl, and the deprecated XML-RPC / JSON-RPC endpoints.

## Contents
- [Endpoint and headers](#endpoint-and-headers)
- [Request body binding](#request-body-binding)
- [Return values](#return-values)
- [Errors and status codes](#errors-and-status-codes)
- [Read-only methods](#read-only-methods)
- [API keys](#api-keys)
- [Python client (requests)](#python-client-requests)
- [JavaScript client (fetch)](#javascript-client-fetch)
- [curl](#curl)
- [XML-RPC / JSON-RPC (deprecated)](#xml-rpc--json-rpc-deprecated)
- [Other bearer routes: /json/1, /doc](#other-bearer-routes-json1-doc)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## Endpoint and headers

| Item | Value |
|---|---|
| URL | `POST {base_url}/json/2/{model}/{method}` (any other method or path under `/json/2` -> 404 "Did you mean POST /json/2/<model>/<method>?") |
| `Authorization` | `Bearer <api key>` (scope `rpc`); required, session cookies are not a substitute for scripts |
| `Content-Type` | `application/json` (another type -> 415) |
| `X-Odoo-Database` | database name; needed when the server exposes several databases (no `--db-filter`/`-d` narrowing it to one). Without it in multi-db: 404 HTML page "the requested URL is not server-wide" |
| Body | JSON object (may be empty `{}` or absent) |

- Route: `@http.route('/json/2/<__model__>/<__method__>', methods=['POST'], auth='bearer',
  bearer_scope='rpc', type='json2', readonly=<per method>, save_session=False)` in the `rpc` addon
  (auto_install, server-wide by default via `--load=base,rpc,web`).
- Sending both a `session_id` cookie and `X-Odoo-Database` for a different db -> 403.
- No `cors=` on this route: browsers on another origin are blocked; call it from a backend/server.

Source: addons/rpc/controllers/json2.py:21-90, addons/rpc/__manifest__.py, odoo/http/router.py:496-532,
odoo/tools/config.py:32, odoo/addons/test_http/tests/test_webjson2.py:41-80

## Request body binding

```text
{"ids": [..], "context": {..}, <every other key = keyword argument of the method>}
```

- `ids` (list or a single int) -> `records = Model.browse(ids)`; omit for `@api.model` methods
  (`create`, `search`, `search_read`, `fields_get`, `name_search`...). Sending `ids` to an `@api.model`
  method -> 422 "cannot call <model>.<method> with ids".
- `context` **replaces** the context (`Model.with_context(context)`, default `{}`): when omitted the call
  runs without `lang`/`tz` (`allowed_company_ids` is only kept if the request already had it). Pass e.g.
  `{"lang": "fr_FR", "tz": "Europe/Brussels", "allowed_company_ids": [1]}` explicitly.
- Other keys are bound by name with `inspect.signature(func).bind(records, **kwargs)`: a missing or
  unexpected argument -> 422 with Python's message ("missing a required argument: 'domain'"). There is
  no positional `args` list: always use the parameter names.
- Only public methods: names starting with `_` or decorated `@api.private` -> 403 ("Private methods ...
  cannot be called remotely"); unknown method/model -> 404.
- Path parameters win over body keys (`__model__`/`__method__` in the body are ignored).

| ORM method | Body example |
|---|---|
| `search_read` | `{"domain": [["is_company", "=", true]], "fields": ["name"], "limit": 10, "order": "name"}` |
| `search` / `search_count` | `{"domain": [], "limit": 10}` |
| `read` | `{"ids": [7], "fields": ["name", "email"]}` |
| `create` | `{"vals_list": [{"name": "ACME"}]}` (a single dict is accepted too) |
| `write` | `{"ids": [7], "vals": {"email": "a@b.c"}}` |
| `unlink` / `action_archive` | `{"ids": [7]}` |
| `name_search` | `{"name": "acm", "limit": 5}` |
| `fields_get` | `{"attributes": ["string", "type", "required"]}` |
| custom method `def action_x(self, reason)` | `{"ids": [7], "reason": "late"}` |

Source: addons/rpc/controllers/json2.py:57-90, odoo/orm/models.py:199-225,1432,1593,2798,3805,4088,5241,5505-5535,
odoo/orm/decorators.py:274-315

## Return values

- A recordset result is converted to its `ids` list (`create` returns `[id, ...]`).
- Anything else is JSON-encoded with `json_default` (date/datetime -> `"YYYY-MM-DD[ HH:MM:SS]"`,
  `Domain` -> list, other unknown objects -> `str()`); `None` -> `null`.
- Binary/Image fields are read as `{"filename": ..., "content": "<base64>", "size": n}` (filename
  omitted when empty) and accept a base64 string or `{"filename", "content"}` on write.
- Response header `Content-Type: application/json; charset=utf-8`; a method may also return an
  `odoo.http.Response` (passed through untouched).

Source: odoo/http/dispatcher.py:414-448, odoo/tools/json.py:61, odoo/orm/fields_binary.py:85-142,
odoo/addons/test_http/tests/test_webjson2.py:229-266

## Errors and status codes

Error body (JSON): `{"name", "message", "arguments", "timestamp", "context", "debug"}` where `name` is the
dotted exception class (`odoo.exceptions.AccessError`) and `debug` the server traceback.

| Status | Typical cause |
|---|---|
| 400 | body is not valid JSON ("could not parse the body as json: ...") |
| 401 | missing header ("User not authenticated, use an API Key with a Bearer Authorization header."), wrong/expired/revoked key ("Invalid apikey"); header `WWW-Authenticate: bearer` |
| 403 | `AccessError`/`AccessDenied` (ir.access denial, private method), session/header db conflict |
| 404 | unknown model or method, `MissingError`, wrong URL, multi-db without `X-Odoo-Database` (HTML body) |
| 409 | `LockError` |
| 415 | wrong `Content-Type` (HTML body) |
| 422 | `UserError`/`ValidationError`, argument binding error, `ids` sent to an `@api.model` method |
| 500 | any other exception (e.g. invalid domain field -> `builtins.ValueError`) |

Client rule: check the status first, then parse JSON only when the response `Content-Type` is JSON.

Source: odoo/http/dispatcher.py:450-472, odoo/exceptions.py, odoo/addons/base/models/ir_http.py:342-360,
odoo/addons/test_http/tests/test_webjson2.py:81-185

## Read-only methods

The route's `readonly` callable walks the model MRO for `_readonly` (set by `@api.readonly`): such calls
run on a read-only cursor (replica if configured) and retry on read/write if they write. In core:
`search`, `search_count`, `search_fetch`, `search_read`, `read`, `name_search` and web helpers
(`web_read`, `web_search_read`, `web_read_group`, `formatted_read_group`, `read_progress_bar`...).
Decorate your own pure-read public methods with `@api.readonly` to get the same behaviour.

Source: addons/rpc/controllers/json2.py:22-34, odoo/orm/decorators.py:306, odoo/orm/models.py:1415-1452,
addons/web/models/models.py

## API keys

**UI**: user form or *My Preferences* -> *Security* tab -> *Create API Key* (`api_key_wizard`, needs an
identity check). Fields: description, scope (`rpc`, the only scope offered), duration.

| Rule | Detail |
|---|---|
| Scope | Strict match: a key works only on routes whose `bearer_scope` equals its scope. JSON-2 and XML-RPC/JSON-RPC use `rpc`. |
| Durations | UI choices 1 day / 1 month / 1 year, capped by `max(group.api_key_duration)` of the user's groups (`base.group_user_regular` = 90 days); "Never" only for system users. |
| Who | only internal users (`check_access_make_key`); the key acts with that user's rights (ir.access applies). |
| Storage | only a hash is stored; the key is shown once. Expired keys are garbage-collected (`@api.autovacuum`). |

**Programmatic (server side)**, e.g. in `odoo-bin shell` (the shell env is superuser uid 1, which is
inactive, so pick the real user):

```python
from datetime import datetime, timedelta
user = env.ref('base.user_admin')
key = env['res.users.apikeys'].with_user(user)._generate(
    'rpc', 'CI integration', datetime.now() + timedelta(days=30))   # scope, name, expiration_date
env.cr.commit()      # the shell rolls back otherwise
print(key)
```

`_generate()` checks the expiration against the user's maximum unless the env is system/sudo
(`.sudo()` + `None` expiration = persistent key).

**Programmatic (client side)**: `res.users.apikeys.generate(key, scope, name, expiration_date)` and
`revoke(key)` are callable over JSON-2 with an existing key, but only for administrators or when the ICP
`base.enable_programmatic_api_keys` is true, limited by `base.programmatic_api_keys_limit` (default 10):

```json
POST /json/2/res.users.apikeys/generate
{"key": "<current key>", "scope": "rpc", "name": "rotated", "expiration_date": "2027-01-31 00:00:00"}
```

Source: odoo/addons/base/models/res_users.py:1142-1150,1610-1963, odoo/addons/base/models/res_groups.py:40,
odoo/addons/base/security/base_groups.xml:31, odoo/addons/test_http/tests/test_webjson2.py:26-30,303-370

## Python client (requests)

```python
import os
import requests

BASE_URL = "https://odoo.example.com"
SESSION = requests.Session()
SESSION.headers.update({
    "Authorization": f"Bearer {os.environ['ODOO_API_KEY']}",   # never hard-code keys
    "X-Odoo-Database": os.environ.get("ODOO_DB", ""),           # needed in multi-db setups
})
CTX = {"lang": "en_US", "tz": "UTC"}


def call(model, method, **body):
    resp = SESSION.post(f"{BASE_URL}/json/2/{model}/{method}", json=body, timeout=60)
    if resp.ok:
        return resp.json()
    if resp.headers.get("Content-Type", "").startswith("application/json"):
        err = resp.json()
        raise RuntimeError(f"{resp.status_code} {err['name']}: {err['message']}")
    resp.raise_for_status()


companies = call("res.partner", "search_read",
                 domain=[["is_company", "=", True]], fields=["name", "email"], limit=5, context=CTX)
[partner_id] = call("res.partner", "create", vals_list=[{"name": "ACME"}], context=CTX)
call("res.partner", "write", ids=[partner_id], vals={"email": "info@acme.test"}, context=CTX)
call("sale.order", "action_confirm", ids=[42], context=CTX)      # custom public method
```

Source: addons/api_doc/static/src/utils/doc_code_gen.js:72-95

## JavaScript client (fetch)

Server-side JS (Node 18+ has `fetch`); from a browser on another origin the request is blocked (no CORS).

```javascript
const BASE_URL = "https://odoo.example.com";
const headers = {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${process.env.ODOO_API_KEY}`,
    "X-Odoo-Database": process.env.ODOO_DB,
};

async function call(model, method, body = {}) {
    const res = await fetch(`${BASE_URL}/json/2/${model}/${method}`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
    });
    const isJson = (res.headers.get("Content-Type") || "").startsWith("application/json");
    const data = isJson ? await res.json() : await res.text();
    if (!res.ok) {
        throw new Error(`${res.status} ${isJson ? `${data.name}: ${data.message}` : data}`);
    }
    return data;
}

const rows = await call("res.partner", "search_read", {
    domain: [["is_company", "=", true]], fields: ["name"], limit: 5, context: { lang: "en_US" },
});
const [id] = await call("res.partner", "create", { vals_list: [{ name: "ACME" }] });
await call("res.partner", "write", { ids: [id], vals: { email: "info@acme.test" } });
await call("sale.order", "action_confirm", { ids: [42] });
```

Source: addons/api_doc/static/src/utils/doc_code_gen.js:31-58

## curl

```bash
curl -sS "$ODOO_URL/json/2/res.partner/search_read" \
  -H "Authorization: Bearer $ODOO_API_KEY" \
  -H "X-Odoo-Database: $ODOO_DB" \
  -H "Content-Type: application/json" \
  -d '{"domain": [["is_company", "=", true]], "fields": ["name"], "limit": 5}'

curl -sS "$ODOO_URL/json/2/res.partner/write" --oauth2-bearer "$ODOO_API_KEY" \
  -H "Content-Type: application/json" -d '{"ids": [7], "vals": {"phone": "+32 2 000 00 00"}}'

curl -sS "$ODOO_URL/json/version"     # {"version_info": [...], "version": "20.0"}, auth none
```

Source: addons/api_doc/static/src/utils/doc_code_gen.js:59-70, addons/rpc/controllers/__init__.py:22-29

## XML-RPC / JSON-RPC (deprecated)

- `/xmlrpc/<service>`, `/xmlrpc/2/<service>` and `/jsonrpc` still exist in the `rpc` addon but each call
  logs a warning: "deprecated in Odoo 19 and scheduled for removal in Odoo 22"; mute it with
  `--log-handler odoo.addons.rpc.controllers.jsonrpc:ERROR` (or `.xmlrpc`).
- Only two services remain: `common` (`version`, `login`, `authenticate`) and `object` (`execute`,
  `execute_kw`). The `db` service is gone (`dispatch_rpc` raises "Invalid service name"): manage
  databases with `odoo-bin db ...` or `odoo.modules.db`.
- An API key (scope `rpc`) can still be used as the password.

| XML-RPC habit | JSON-2 |
|---|---|
| `common.authenticate(db, login, pwd, {})` then pass uid/pwd every call | no login step: `Authorization: Bearer <key>` (+ `X-Odoo-Database`) |
| `execute_kw(db, uid, pwd, 'res.partner', 'search_read', [domain], {'fields': [...]})` | `POST /json/2/res.partner/search_read` `{"domain": [...], "fields": [...]}` |
| positional `args` `[[ids], vals]` for `write` | `{"ids": [...], "vals": {...}}` |
| `{'context': {...}}` in kwargs | top-level `"context"` key |
| Fault codes / string faults | HTTP status + JSON error body |

Source: addons/rpc/controllers/__init__.py:6-11, addons/rpc/controllers/jsonrpc.py, addons/rpc/controllers/xmlrpc.py:139-158,
odoo/http/router.py:125-150, odoo/service/common.py, odoo/service/model.py:71-92, odoo/addons/base/models/res_users.py:389

## Other bearer routes: /json/1, /doc

| Route | Module | Notes |
|---|---|---|
| `GET /json/1/<subpath>` (auth bearer, scope rpc, type http) | `web` | JSON of an action/view like the web client at `/odoo/<subpath>` (`view_type`, `domain`, `limit`, `offset`, `groupby`...). Experimental: enabled only on demo databases or with ICP `web.json.enabled`; needs group `base.group_allow_export`. `/json/<subpath>` (session) redirects to it. |
| `/doc`, `/doc/<model>` (auth user) | `api_doc` (auto_install) | interactive API browser with request generators; group `api_doc.group_allow_doc` |
| `/doc-bearer/index.json`, `/doc-bearer/<model>.json` (json2, bearer rpc) | `api_doc` | machine-readable model/method/field listing for API clients |

Source: addons/web/controllers/json.py:30-70,201-205, addons/api_doc/controllers/api_doc.py:39-175,
addons/api_doc/__manifest__.py

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| API key with empty scope used everywhere | keys are strictly scoped; create them with scope `rpc` | odoo/addons/base/models/res_users.py:1816-1843 |
| `db` RPC service (`create_database`, `list`, `drop`) | removed: `odoo-bin db init/dump/load/...`, `odoo.modules.db` | odoo/http/router.py:125-150 |
| New integrations on XML-RPC/JSON-RPC | JSON-2 (`/json/2`); RPC endpoints removed in 22 | addons/rpc/controllers/__init__.py:6 |
| `@route(type='json', auth='user')` for an API | `type='json2', auth='bearer', bearer_scope='rpc'` | odoo/http/routing_map.py:204-206 |

Use `odoo_live_call` (MCP) to try a JSON-2 call against the configured test database; read methods are
allowed by default, writes need `allow_writes`.
