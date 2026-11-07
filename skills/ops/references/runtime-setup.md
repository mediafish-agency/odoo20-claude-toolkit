# Runtime setup (Odoo 20)

What an Odoo 20 source checkout needs to run: supported Python and PostgreSQL versions, Python
dependencies (and the toolkit's fast system-site-packages venv), PostgreSQL role and extensions, PDF
engines (wkhtmltopdf or Paper Muncher), Chrome for JS tests and tours, and running behind a reverse proxy.

## Contents
- [Supported versions](#supported-versions)
- [Python dependencies](#python-dependencies)
- [The toolkit runtime script](#the-toolkit-runtime-script)
- [PostgreSQL](#postgresql)
- [PDF engines](#pdf-engines)
- [Chrome for JS tests and tours](#chrome-for-js-tests-and-tours)
- [Behind a reverse proxy](#behind-a-reverse-proxy)
- [Embedding Odoo in a script](#embedding-odoo-in-a-script)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## Supported versions

| Component | Rule in 20.0 | Enforcement |
|---|---|---|
| Python | >= 3.12 (`MIN_PY_VERSION = (3, 12)`), officially up to 3.14 (`MAX_PY_VERSION`) | older: assertion at import; newer than 3.14: warning "Python X is not officially supported" |
| Python flags | no `-O`, `-OO`, `PYTHONOPTIMIZE` | `RuntimeError` at import (Odoo relies on `assert`) |
| PostgreSQL | >= 16 (`MIN_PG_VERSION = 16`) | `warnings.warn("Postgres version is ..., lower than minimum required 160000")` on connect |
| OS packages | Debian/Ubuntu: `postgresql-client`, fonts (`fonts-dejavu-core` or noto, `fonts-inconsolata`, `fonts-roboto-unhinted`, `gsfonts`) | `debian/control` |
| Pins | `requirements.txt` targets Ubuntu 24.04 (Noble) / Debian 12-13 package versions | comments in `requirements.txt` |

`setup.py` declares `python_requires='>=3.12'`. Check an interpreter with
`<python> odoo-bin --version` (prints `Odoo Server 20.0`).

Source: odoo/release.py:39-41, odoo/init.py:8-16, odoo/cli/server.py:69-73, odoo/sql_db.py:721-722,
setup.py:69, debian/control:14-66, requirements.txt:1-2

## Python dependencies

- `pip install -r requirements.txt` in a venv works but compiles several packages (psycopg2,
  python-ldap, lxml for some Pythons): you need `libpq-dev`, `libldap2-dev`, `libsasl2-dev`,
  `libxml2-dev`/`libxslt1-dev`, a compiler. Pins are per Python version through environment markers
  (e.g. `Pillow==10.2.0` on 3.12, `11.1.0` on 3.13, `12.1.1` on 3.14).
- Notable pins: `Werkzeug==3.0.1` (older Werkzeug fails at `import odoo.http` with a `TypeError` on
  `LocalProxy(..., unbound_message=...)`), `psycopg2`, `lxml` + `lxml-html-clean`, `gevent`/`greenlet`,
  `h11==0.16.0` (used by Odoo's own HTTP server), `libsass`, `cryptography`.
- Removed vs 19: `pytz` and `xlwt` (code uses `zoneinfo`, `xlsxwriter`/`openpyxl`); new: `h11`,
  `tzdata` (Windows only).
- Not in `requirements.txt` but needed for some features: `websocket-client` (browser tests: tours and
  Hoot suites are **skipped** without it), `inotify` or `watchdog` (`--dev=reload`), `ipython`/
  `ptpython`/`bpython` (shell), the `ffmpeg` binary (screencasts).
- Modules declare their own extras in `external_dependencies` (`{'python': [...], 'bin': [...]}`);
  a missing one blocks the install with `MissingDependency`.

Source: requirements.txt, odoo/http/__init__.py:13-14, odoo/http/server.py, odoo/service/server.py:1600-1612,
setup.py:70-72, odoo/modules/module.py:298-320,611-643

## The toolkit runtime script

`scripts/setup_odoo_runtime.sh [ODOO_ROOT] [VENV_DIR]` (in the plugin; env `ODOO20_ROOT`, `ODOO20_VENV`,
`PYTHON`) builds a usable interpreter fast:

1. `python3 -m venv --system-site-packages $VENV_DIR` (default `~/.venvs/odoo20`): reuses the distro's
   `python3-*` packages listed in `debian/control`.
2. Reads `requirements.txt` with `packaging`, evaluates markers, and `pip install`s **only** the pins the
   system does not satisfy (on Ubuntu 24.04 typically Werkzeug, Pillow, gevent, libsass, h11, idna,
   chardet, docutils).
3. Runs `odoo-bin --version`.

The MCP runtime tools (`odoo_db`, `odoo_test`, `odoo_server`, `odoo_shell`) use this interpreter
(`odoo_python` user setting); `odoo_status` reports whether it works.

```bash
bash scripts/setup_odoo_runtime.sh "/src/odoo20" "$HOME/.venvs/odoo20"
~/.venvs/odoo20/bin/python /src/odoo20/odoo-bin --version
```

Source: (toolkit) scripts/setup_odoo_runtime.sh, requirements.txt

## PostgreSQL

```bash
sudo -u postgres createuser --createdb --no-superuser --no-createrole "$USER"   # role used as db_user
```

- Never run Odoo as db user `postgres`: the server exits ("Using the database user 'postgres' is a
  security risk, aborting.").
- `CREATEDB` is needed for `odoo-bin db init`, `-d <new db>` auto-creation and test databases.
- New databases are created from `db_template` (`template0`, `LC_COLLATE 'C'`), then Odoo runs
  `CREATE EXTENSION IF NOT EXISTS pg_trgm` (trigram indexes, `index='trigram'`) and, with `--unaccent`,
  `unaccent`; failures are only warnings. `GRANT CREATE ON SCHEMA public TO PUBLIC` is applied for PG15+.
- `db_system` (default `postgres`) must be connectable: bus notifications, cron wake-up and the health
  check use it (`--db-system` / `PGDATABASE_SYSTEM`).
- Read replica: `db_replica_host`/`db_replica_port`; simulate it with `--dev=replica`.

Source: odoo/cli/server.py:36-45, odoo/modules/db.py:238-251,341-398, odoo/tools/config.py:405-440,
odoo/addons/base/models/ir_model.py:711-740

## PDF engines

PDF rendering is pluggable in 20; base has no wkhtmltopdf code any more.

| | wkhtmltopdf | Paper Muncher |
|---|---|---|
| Module | `base_report_wkhtmltox` (`auto_install`, sets ICP `report.pdf_engine_default = wkhtmltopdf` in its post-init hook) | `base_report_paper_muncher` (depends `base_setup`, install it explicitly) |
| Binary | `wkhtmltopdf` (+ `wkhtmltoimage`) on `PATH`; >= 0.12.0, "with patched qt" build recommended | `paper-muncher` on `PATH` or `/opt/paper-muncher/bin/paper-muncher`; >= 0.6 |
| `report_type` | `qweb-pdf-wkhtmltopdf` | `qweb-pdf-paper-muncher` |
| Constraint | does not work with `--workers=1` (state `workers`) | - |

- Engine choice: the report's `report_type`, otherwise ICP `report.pdf_engine_default`.
- State check: `env['ir.actions.report'].get_pdf_engine_state('wkhtmltopdf')` returns `ok`, `install`,
  `upgrade`, `workers` or `broken` (logged at startup: "Will use the Wkhtmltopdf binary at ...").
- Report templates/layouts: see the `odoo20:qweb-reports` skill.

Source: addons/base_report_wkhtmltox/__manifest__.py, addons/base_report_wkhtmltox/__init__.py:7,
addons/base_report_wkhtmltox/models/ir_actions_report.py:58-132, addons/base_report_paper_muncher/__manifest__.py,
addons/base_report_paper_muncher/paper_muncher.py:34-39,382-407, odoo/addons/base/models/ir_actions_report.py:170,788-800

## Chrome for JS tests and tours

- `HttpCase.browser_js()` / `start_tour()` (and the Hoot suites run through them) start a headless
  Chrome. Lookup: env `ODOO_BROWSER_BIN`, else on Linux the first of `google-chrome`, `chromium`,
  `chromium-browser`, `google-chrome-stable` on `PATH` (macOS: the `/Applications/...` bundles).
- Missing Chrome or missing `websocket-client` raise `unittest.SkipTest` ("Chrome executable not
  found", "websocket-client module is not installed"): a green run may just mean skipped browser
  tests, so grep the log for these messages.
- Tests start the HTTP server automatically when `--test-enable`/`--test-tags` is set; keep
  `--workers=0` (prefork warns "Unit testing in workers mode could fail").
- Useful env: `ODOO_TEST_DISABLE_TIMEOUT=1` (debugging), `ODOO_BROWSER_LOG_VERBOSITY`; `ffmpeg` on
  `PATH` for `--screencasts`; screenshots of failures go to `--screenshots` (default `/tmp/odoo_tests`).
- `browser_js(..., watch=True)` opens a visible browser; `debug=True` runs with `?debug=assets` and stops
  on the error.

Source: odoo/tests/common.py:86-92,116,1585-1593,1715-1724,2481-2515,2881-2920,2985, odoo/service/server.py:1567-1572,
odoo/service/server.py:529-531

## Behind a reverse proxy

- Start Odoo with `--proxy-mode`; the proxy must send `X-Forwarded-Host` (the trigger), `X-Forwarded-For`
  and `X-Forwarded-Proto`. One proxy hop is trusted (`ProxyFix(x_for=1, x_proto=1, x_host=1)`).
- Keep the default `--http-interface=127.0.0.1` when the proxy runs on the same host.
- With `--workers > 0`, route `/websocket` (upgrade headers) to `gevent_port` (8072), everything else
  to `http_port` (8069).
- With `--x-sendfile`, expose an `internal` location `/web/filestore` aliased to `<data_dir>/filestore`.

```nginx
upstream odoo      { server 127.0.0.1:8069; }
upstream odoo_evt  { server 127.0.0.1:8072; }
server {
    listen 443 ssl;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    location /websocket {
        proxy_pass http://odoo_evt;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    location / { proxy_pass http://odoo; }
}
```

The nginx block is a minimal sketch (TLS, timeouts and `client_max_body_size` omitted); only the header
names, ports and paths above are taken from Odoo.

Source: odoo/http/router.py:26-31,256-265, odoo/http/server.py:185-189, odoo/tools/config.py:292-310,
addons/bus/controllers/websocket.py:12, addons/bus/websocket.py:866, addons/web/controllers/binary.py:22-36

## Embedding Odoo in a script

```python
import odoo.init                      # first: version checks, monkeypatches
from odoo.tools import config
from odoo.modules.registry import Registry
from odoo.api import Environment, SUPERUSER_ID

config.parse_config(['-c', '/etc/odoo20.conf'], setup_logging=True)   # say True or False explicitly
with Registry('dev20').cursor() as cr:
    env = Environment(cr, SUPERUSER_ID, {})
    print(env['res.partner'].search_count([]))
```

- `parse_config()` without `setup_logging=` warns in 20 ("it is strongly recommended to specify whether
  you want Odoo to setup its own logging").
- `odoo` is a namespace package (no `odoo/__init__.py`): run with the Odoo source root on `sys.path` or
  use `python -m odoo <command>` / `odoo-bin shell` instead.

Source: odoo/tools/config.py:600-635, odoo/init.py, odoo/__main__.py, odoo/cli/shell.py:130-150

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| Python 3.10/3.11, PostgreSQL 12-15 | Python >= 3.12 (<= 3.14 supported), PostgreSQL >= 16 | odoo/release.py:39-41 |
| `import pytz` / `xlwt` available | not dependencies: `zoneinfo`, `xlsxwriter`/`openpyxl` (rule ORM015) | requirements.txt |
| wkhtmltopdf handled by `base` (`_run_wkhtmltopdf`, `get_wkhtmltopdf_state`) | engine modules + `get_pdf_engine_state(engine)` (rule REP001) | odoo/addons/base/models/ir_actions_report.py:170 |
| werkzeug dev server / werkzeug access logs | Odoo HTTP server on h11, logger `odoo.http.server` | odoo/http/server.py, odoo/http/server_log.py:276 |
| bus/cron/health on the hard-coded `postgres` db | `db_system` option | odoo/tools/config.py:436 |
| `python -O odoo-bin` in production images | refused at startup | odoo/init.py:11-14 |
