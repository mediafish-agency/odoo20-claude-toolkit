# odoo.conf and server options (Odoo 20)

The Odoo 20 configuration system (`odoo/tools/config.py`): where options come from, the options that
matter for development and deployment, their defaults, and what changed since 19 (HTTP interface now
`127.0.0.1`, `--unsafe-policy`, `--db-system`, `--gevent-workers`). Flags of each subcommand are in
[cli.md](cli.md).

## Contents
- [Sources and precedence](#sources-and-precedence)
- [A development odoo.conf](#a-development-odooconf)
- [Paths and modules](#paths-and-modules)
- [Database](#database)
- [HTTP](#http)
- [Workers and limits](#workers-and-limits)
- [Logging](#logging)
- [Developer mode (--dev)](#developer-mode---dev)
- [Tests and demo data](#tests-and-demo-data)
- [Security and file-only options](#security-and-file-only-options)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## Sources and precedence

`config.options` is a `ChainMap`: **runtime** (post-processing) > **command line** > **environment** >
**config file** > defaults.

- Config file: `-c PATH` / `--config` (env `ODOO_RC`); otherwise `~/.config/Odoo/odoo.conf` if it exists,
  else `~/.odoorc`. Format: INI section `[options]`, keys = option `dest` names (`http_port`, not
  `http-port`), plus an optional `[colors]` section.
- Environment: every file-loadable option has an `ODOO_<DEST>` variable (`ODOO_HTTP_PORT`,
  `ODOO_WORKERS`, `ODOO_ADDONS_PATH`, `ODOO_DEV`); database options use libpq names (`PGDATABASE`,
  `PGUSER`, `PGPASSWORD`, `PGHOST`, `PGPORT`, `PGSSLMODE`, `PGAPPNAME`, `PGHOST_REPLICA`,
  `PGPORT_REPLICA`, `PGDATABASE_TEMPLATE`, `PGDATABASE_SYSTEM`, `PGPATH`). Environment beats the file.
- `--save` writes the current options to the config file. CLI-only options (`-i`, `-u`, `--test-*`,
  `--stop-after-init`, `--dev`) are not saved.
- In code: `from odoo.tools import config`; `config['http_port']`, `config.get('x')`.
- Unknown keys in the file are kept as raw strings with a warning; `False`/`false` for a non-boolean
  option is ignored with a warning.

Source: odoo/tools/config.py:100-140,192-215,560-576,640-700,1001-1075

## A development odoo.conf

```ini
[options]
addons_path = /src/odoo20/addons,/src/custom
data_dir = /home/me/.local/share/Odoo
db_host = localhost
db_port = 5432
db_user = odoo
db_password = odoo
dbfilter = ^dev20$|^test20$
http_port = 8069
; http_interface defaults to 127.0.0.1 in 20 (use 0.0.0.0 inside containers)
workers = 0
log_level = info
log_handler = :INFO,odoo.addons.my_module:DEBUG
dev_mode = reload,xml,qweb
admin_passwd = change-me
```

`db_user` must not be `postgres` (the server exits). Prefer `dbfilter` / `-d` so that a single database
is visible (JSON-2 clients then do not need `X-Odoo-Database`).

Source: odoo/cli/server.py:36-45, odoo/http/router.py:87-122

## Paths and modules

| Option (CLI / file key) | Default | Notes |
|---|---|---|
| `--addons-path` / `addons_path` | `[]` | comma list; globs allowed; dirs without any `__init__.py`+`__manifest__.py` module are skipped with a warning. Core `odoo/addons` and `<root>/addons` are always added |
| `-D`, `--data-dir` / `data_dir` | `~/.local/share/Odoo` | filestore (`filestore/<db>`), sessions (`sessions/`), `addons/20.0` |
| `--upgrade-path` / `upgrade_path` | `[]` | dirs with `<module>/<version>/{pre,post,end}-*.py` (the `odoo.upgrade` package) |
| `--pre-upgrade-scripts` | `[]` | scripts run before loading modules when `-u` is given |
| `--load` / `server_wide_modules` | `base,rpc,web` | `base` and `web` are re-added if missing; their routes exist on every database |

Source: odoo/tools/config.py:31-33,270-276,548-560,752-776,892-920,1110-1124, odoo/modules/module.py:143-160

## Database

| Option | Default | Notes |
|---|---|---|
| `-d`, `--database` / `db_name` | `[]` | comma list; one db required with `-i/-u`; also restricts the db list when no `dbfilter` |
| `-r` `db_user`, `-w` `db_password`, `db_host`, `db_port` | libpq defaults | `db_sslmode` default `prefer` |
| `db_replica_host`, `db_replica_port` | `None` | read-only routes/methods use the replica |
| `db_maxconn` | 64 | pool size per process; `db_maxconn_gevent` for the gevent worker |
| `db_template` | `template0` | template for new databases |
| `--db-system` / `db_system` | `postgres` | **new**: database used for shared system work (bus `LISTEN/NOTIFY`, cron wake-up notifications, `/web/health?db_server_status=1`) |
| `--db-filter` / `dbfilter` | `''` | regex; `%h` = host, `%d` = first label of the host (`www.` stripped) |
| `--no-database-list` / `list_db` | `True` | hide the database manager/selector |
| `--unaccent` | `False` | create new dbs with `unaccent` |
| `--pg_path` | `''` | where `pg_dump`/`pg_restore` live |

Source: odoo/tools/config.py:405-440, odoo/http/router.py:87-122, addons/bus/bus_dispatcher.py:317,
odoo/addons/base/models/ir_cron.py:825, addons/web/controllers/home.py:200-210

## HTTP

| Option | Default | Notes |
|---|---|---|
| `--http-interface` / `http_interface` | `127.0.0.1` | **changed** (was `0.0.0.0`): bind explicitly to `0.0.0.0` in Docker/VMs |
| `-p`, `--http-port` / `http_port` | 8069 | |
| `--gevent-port` / `gevent_port` | 8072 | websocket/evented worker (prefork mode) |
| `--no-http` / `http_enable` | `True` | |
| `--proxy-mode` / `proxy_mode` | `False` | trusts `X-Forwarded-For/-Proto/-Host` (one hop) **only when `X-Forwarded-Host` is sent** |
| `--x-sendfile` / `x_sendfile` | `False` | filestore downloads via `X-Accel-Redirect: /web/filestore/...` |
| env `ODOO_MAX_HTTP_THREADS` | `2 * cpu + 1` | threaded server pool size |
| env `LISTEN_FDS`/`LISTEN_PID` | - | systemd socket activation |

Source: odoo/tools/config.py:292-310,1155-1172, odoo/http/server.py:185-189, odoo/http/router.py:256-265,
odoo/http/stream.py:196-209

## Workers and limits

| Option | Default | Notes |
|---|---|---|
| `--workers` | 0 | 0 = threaded server; > 0 = prefork (POSIX) |
| `--gevent-workers` | 1 | **new**: number of gevent (websocket) processes in prefork mode, needs `SO_REUSEPORT` for > 1 |
| `--max-cron-threads` | 2 | cron threads/workers |
| `--limit-memory-soft` / `-hard` | 2048 MiB / 2560 MiB | per worker; `*-gevent` variants default to these |
| `--limit-time-cpu` / `--limit-time-real` | 60 / 120 s | per request (workers mode) |
| `--limit-time-real-cron` | -1 | -1 = use `limit_time_real`, 0 = unlimited |
| `--limit-time-worker-cron` | 0 | recycle a cron worker after N seconds (0 = never) |
| `--limit-request` | 65536 | requests per worker before recycling |
| `--transient-age-limit` | 1.0 h | `TransientModel` vacuum age |
| `--osv-memory-count-limit` | 0 | max transient records (0 = no limit) |

- With `workers > 0`, the browser websocket (`/websocket`) must reach `gevent_port` (reverse proxy rule);
  otherwise the bus logs "Couldn't bind the websocket. Is the connection opened on the evented port
  (8072)?".
- wkhtmltopdf reports need `workers != 1` (an HTTP worker would deadlock on its own request).

Source: odoo/tools/config.py:442-545, odoo/service/server.py:920-935,1560-1575, addons/bus/websocket.py:866,
addons/base_report_wkhtmltox/models/ir_actions_report.py:88-90

## Logging

| Option | Notes |
|---|---|
| `--log-handler=LOGGER:LEVEL` (repeatable) / `log_handler` | default `:INFO`; e.g. `odoo.sql_db:DEBUG`, `odoo.addons.my_module:DEBUG`, `odoo.http:DEBUG` |
| `--log-sql`, `--log-web` | shortcuts for `odoo.sql_db:DEBUG`, `odoo.http:DEBUG` |
| `--log-level` | `info` (default), `debug` (= `odoo:DEBUG`), `debug_sql` (= `odoo.sql_db:DEBUG`), `warn`, `error`, `critical`, `runbot`, `test`, `notset`; `debug_rpc`/`debug_rpc_answer` are still accepted but map to nothing in 20 |
| `--logfile PATH` | instead of stderr |
| `--log-config PATH` | JSON `logging.config.dictConfig` file |
| `--log-db DB`, `--log-db-level` | store logs in `ir.logging` |
| `--syslog` | deprecated since 20 (use `--log-config` with a syslog handler) |

HTTP access lines come from the logger `odoo.http.server` (Odoo's own HTTP server, not werkzeug) and
end with `query_count query_time remaining_time cursor_mode`. Colors: env `NO_COLOR`, `FORCE_COLOR`,
`ODOO_PY_COLORS=always|never|auto`.

Source: odoo/tools/config.py:349-386,700-737, odoo/netsvc.py:30-195, odoo/http/server_log.py:36-50,276

## Developer mode (--dev)

`--dev=FEATURE,...` (env `ODOO_DEV`, file key `dev_mode`); values are not validated, unknown ones do nothing.

| Feature | Effect |
|---|---|
| `access` | log the traceback of `AccessError`s raised while serving HTTP requests |
| `qweb` | log the compiled template and source line on QWeb errors |
| `reload` | restart the server when Python files change (needs the `inotify` or `watchdog` Python package; not in evented mode) |
| `replica` | open read-only cursors without a real replica: catches writes in `readonly` routes/methods |
| `xml` | read view archs and templates from the XML files instead of the database (no `-u` needed for arch changes of existing views); also disables the compiled-template and asset-bundle caches, so JS/SCSS/XML asset edits show on reload |
| `all` | `access,qweb,reload,xml` |

There is no `werkzeug`, `assets` or `pdb` dev feature in 20: non-minified assets are a URL debug mode
(`?debug=assets`), see [debugging-profiling.md](debugging-profiling.md#debug-mode-in-the-browser).

Source: odoo/tools/config.py:31,462-470,818-819, odoo/service/server.py:1600-1612, odoo/http/router.py:307,
odoo/addons/base/models/ir_qweb.py:1040-1043,1397,2948-2952, odoo/addons/base/models/ir_asset.py:115-118,
odoo/addons/base/models/ir_ui_view.py:239, odoo/orm/registry.py:321

## Tests and demo data

| Option | Notes |
|---|---|
| `-t`, `--test-tags SPEC` | enables tests and `--stop-after-init`; spec `[-][tag][/module][:class][.method][[params]]` |
| `--test-enable` | same as `--test-tags +standard` |
| `--test-file PATH` | converted into a test-tag for that file |
| `--screenshots DIR` (default `/tmp/odoo_tests`), `--screencasts DIR` | browser test artefacts |
| `--with-demo` | install demo data in **new** databases (default off) |
| `--without-demo=BOOL` | inverse; stored as `with_demo`; a config file may contain either key |

Tests are CLI-only (not read from the config file). Demo data for an existing database:
`odoo-bin module force-demo`.

Source: odoo/tools/config.py:261-265,312-345,820-840,960-1015

## Security and file-only options

| Key | Default | Notes |
|---|---|---|
| `admin_passwd` | `admin` | database-manager master password: always set it; stored hashed once changed from the UI |
| `--unsafe-policy` / `unsafe_policy` | `log` | **new**: `disable`, `log`, `raise`, `terminate` when `safe_eval` meets an unsafe object |
| `list_db` | `True` | see Database |
| `csv_internal_sep`, `reportgz`, `import_file_maxbytes` (10 MiB), `import_file_timeout` (3), `import_url_regex`, `websocket_keep_alive_timeout` (3600), `websocket_rate_limit_burst` (10), `websocket_rate_limit_delay` (0.2), `proxy_access_token` | - | config-file only |

SMTP (`--smtp`, `--smtp-port`, `--smtp-ssl`, `--smtp-user`, `--smtp-password`, `--email-from`,
`--from-filter`, certificate files) and GeoIP (`--geoip-city-db`, `--geoip-country-db`) are unchanged.

Source: odoo/tools/config.py:234-246,280-290,388-410,452-458,1140-1155, odoo/tools/safe_eval/runtime.py:64-135

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| server reachable on all interfaces by default | `http_interface` defaults to `127.0.0.1` | odoo/tools/config.py:294 |
| `-s` | `--save` | odoo/tools/config.py:253 |
| `--log-level=debug_rpc` to trace RPC | no effect; use `--log-handler=odoo.http:DEBUG` / `--log-web` | odoo/netsvc.py:181-189 |
| `--syslog` | `--log-config` with a syslog handler | odoo/netsvc.py:167-175 |
| `--log-handler=werkzeug:...` for access logs | logger `odoo.http.server` | odoo/http/server_log.py:276 |
| `--dev=werkzeug` / `--dev=assets` | not features; use `?debug=assets` | odoo/tools/config.py:462-470 |
| bus/cron using the `postgres` db implicitly | configurable `db_system` | odoo/tools/config.py:436 |
| one gevent process | `--gevent-workers N` | odoo/tools/config.py:503-506 |
| running with `python -O` | refused at startup | odoo/init.py:11-14 |
