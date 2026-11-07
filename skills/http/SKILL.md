---
name: http
description: >-
  Default for any Odoo work in this Odoo 20.0 tree even when no version is named; takes priority over generic odoo-* skills (17-19 advice such as type='json', XML-RPC clients, from odoo.http import content_disposition is wrong in 20). Controller, REST/JSON endpoint, integration or API client, file download - Odoo 20 HTTP layer and external API: controllers (odoo.http package, route() types http/jsonrpc/json2,
  auth user/public/none/bearer with bearer_scope, CSRF, readonly), request/response helpers, file streams,
  sessions, portal and website routes, and the JSON-2 API (/json/2/<model>/<method> with Bearer API keys,
  X-Odoo-Database) that replaces deprecated XML-RPC/JSON-RPC. Includes Python/JS/curl client examples.
when_to_use: >-
  Editing controllers/*.py, exposing data to a frontend or another system, writing an integration that calls
  Odoo 20, downloading files, or porting controllers from Odoo <= 19.
---

# Odoo 20 HTTP and JSON-2

## Workflow

1. Find existing routes to extend: `odoo_grep("@http.route\\('/my/", regex=true)` or `odoo_search` on the
   controller class; inherit the controller class and call `super()`.
2. Apply Odoo's [controllers guidelines](../odoo-guidelines/guidelines/controllers.md) and the security
   rules in [odoo-security](../odoo-security/SKILL.md) (auth, POST + CSRF for writes, never `sudo().write(post)`).
3. `odoo_validate` (catches removed imports such as `from odoo.http import content_disposition`), then test
   with an `HttpCase` (`odoo20:testing`) or `odoo_server` + `odoo_live_call`.

## Odoo 20 rules

- `from odoo.http import Controller, request, route, Response`; streams from `odoo.http.stream`
  (`Stream`, `content_disposition`), session helpers from `odoo.http.session`.
- `route(type=...)`: `http` (pages, forms), `jsonrpc` (web client JSON-RPC; `json` is a deprecated alias),
  `json2` (REST-like JSON, used with `auth='bearer'`).
- `auth='bearer'` requires `bearer_scope=...`; API keys are matched by exact scope (`rpc` for JSON-2).
- External integrations use **JSON-2**: `POST /json/2/<model>/<method>`, `Authorization: Bearer <key>`,
  `X-Odoo-Database: <db>`, JSON body `{ids, context, **kwargs}`; XML-RPC/JSON-RPC log a deprecation (removal
  planned in Odoo 22) and the `db` RPC service is gone.
- `http_interface` now defaults to `127.0.0.1`.

## References

- [routing.md](references/routing.md) - route options, request API, controller inheritance, v19 import changes
- [json2-api.md](references/json2-api.md) - JSON-2 server behaviour, API keys, client examples (Python, JS, curl)
- [sessions-streams.md](references/sessions-streams.md) - sessions, Stream, downloads, binary routes, CORS
- [portal-controllers.md](references/portal-controllers.md) - CustomerPortal, website routes, forms, rendering QWeb
