# Running tests (Odoo 20)

How to run Python tests, tours and Hoot suites from the command line or the toolkit: test flags,
the exact `--test-tags` grammar, which tests run in which phase, throwaway test databases, browser
requirements, environment variables, and how to read the log. Never run tests on a database you
care about: tests install modules and write data.

## Contents

- Quick recipes
- Flags
- `--test-tags` grammar
- What runs when (at_install / post_install)
- Throwaway test databases
- Browser tests: Chrome and timeouts
- Reading the log
- Toolkit: `odoo_test`, `odoo_job`
- v19 habit -> Odoo 20

## Quick recipes

```bash
PY=~/.venvs/odoo20/bin/python                 # an interpreter with Odoo 20 requirements
AP=--addons-path=addons,/path/to/custom       # always pass your addons path

# install a module on a scratch DB and run its tests (at_install + post_install)
$PY odoo-bin $AP -d odoo20_t1 -i my_module --test-tags /my_module --http-port 8071

# re-run one class / one method after code changes (update instead of install)
$PY odoo-bin $AP -d odoo20_t1 -u my_module --test-tags /my_module:TestBook
$PY odoo-bin $AP -d odoo20_t1 -u my_module --test-tags /my_module:TestBook.test_rename

# run tests of an already-installed module without updating it (Python + Hoot JS suites)
$PY odoo-bin $AP -d odoo20_t1 --test-tags /my_module

# only the Hoot JS suites of the module (desktop and mobile)
$PY odoo-bin $AP -d odoo20_t1 --test-tags hoot/my_module
```

`--test-tags` (or `--test-enable`) implies `--stop-after-init`; the process exits non-zero when a
test failed or errored.

Source: odoo/tools/config.py:320-352, 821-836; odoo/service/server.py:1524-1551

## Flags

| Flag | Effect |
|---|---|
| `-t SPEC`, `--test-tags=SPEC` | Enable tests and filter them (grammar below). |
| `--test-enable` | Enable tests with the default spec `+standard` (every standard test of the modules in scope). |
| `--test-file=PATH` | Run one Python test file (its absolute path is appended to the tags). |
| `-i MODS` / `-u MODS` | Install / update modules (comma list); with tests, limits post_install collection to the updated modules (see below). |
| `-d DB` | Database. Use a throwaway copy. |
| `--stop-after-init` | Implied by test flags; shown in scripts for clarity. |
| `--http-port=N` | `HttpCase` serves on 127.0.0.1:`http_port`; pick a free port when a dev server runs. |
| `--screenshots=DIR` | Failure screenshots (default `/tmp/odoo_tests/<db>/screenshots`). |
| `--screencasts=DIR` | Record browser tests as video. |
| `--log-level=test` | Quieter log focused on test output; `--log-handler=odoo.tests:DEBUG` for more. |
| `--with-demo` | Load demo data in new databases (demo is off by default in 20.0). |

Source: odoo/tools/config.py:320-352; `odoo-bin server --help` ("Testing Configuration")

## `--test-tags` grammar

Comma-separated specs, each `[-][tag][/module][:Class][.method][[params]]`
(file form: `/path/ending/in/test_x.py`).

- Include spec without a tag means tag `standard`; exclude spec without a tag means any tag (`*`).
- `*` as tag = every tag (also tests tagged `-standard`).
- If only exclusions are given, `standard` is included implicitly.
- A test runs if it matches at least one include and no exclude. Commas inside `[...]` are kept;
  escape `[`, `]`, `\` with a backslash.
- In the post_install phase, module includes for modules not in scope are ignored (debug log).

| Spec | Selects |
|---|---|
| `/my_module` | standard tests of `my_module` |
| `/my_module:TestBook` / `/my_module:TestBook.test_rename` | one class / one method |
| `:TestBook.test_rename`, `.test_rename` | by class/method name in any module in scope |
| `my_slow` / `my_slow/my_module` | tests tagged `my_slow` (in `my_module`) |
| `*/my_module` | all tests of the module, including `-standard` ones |
| `/my_module,-/my_module:TestSlow` | module minus one class |
| `-external` | all standard tests except those tagged `external` |
| `post_install` / `at_install` | by phase tag (phases are also filtered automatically) |
| `/my_module/tests/test_book.py` | one file (same as `--test-file`) |
| `hoot/my_module`, `hoot/my_module:WebSuite` | Hoot suites for the module (both / desktop only) |
| `is_tour`, `is_query_count` | dynamic tags: methods calling `self.start_tour` / `self.assertQueryCount` |

`:post_install` is **not** a phase filter: it means "class named post_install". Write `post_install`.

Source: odoo/tests/tag_selector.py:9-171, odoo/tests/common.py:1176-1185, 3022-3031

## What runs when (at_install / post_install)

| Phase | When | Modules scanned |
|---|---|---|
| at_install | right after each module is loaded, while loading the registry | with `-i/-u`: each installed/updated module; without: every module (tests filtered by tags) |
| post_install | after all modules are loaded | with `-i/-u`: `registry.updated_modules` only; without: all installed modules |

Consequences:
- Tests are discovered only from modules in scope. With `-i my_module` on a database where `web`
  is already installed, `web/tests/test_js.py` (the Hoot launcher, `WebSuite`/`MobileWebSuite`,
  tag `hoot`) is not collected: run Hoot suites without `-i/-u`, or add `web` to `-u`.
- `--test-enable` without `-i/-u` on a big database runs the tests of every installed module.
- `HttpCase` must be `post_install` (registry fully loaded, assets generated:
  `_pregenerate_assets_bundles()` runs before a post_install suite containing an `HttpCase`).

Source: odoo/modules/loading.py:142-280, odoo/service/server.py:1526-1550 (assets pregeneration :1541), odoo/tests/loader.py:91-108,
addons/web/tests/test_js.py:191-217

## Throwaway test databases

```bash
$PY odoo-bin $AP db init odoo20_tmpl                       # base + auto-install modules (web, ...); --with-demo, --country, --language
$PY odoo-bin $AP db duplicate odoo20_tmpl odoo20_t1        # copies DB + filestore (-f overwrite, -n neutralize)
$PY odoo-bin $AP -d odoo20_t1 -i my_module --test-tags /my_module --http-port 8071
$PY odoo-bin $AP db drop odoo20_t1
```

Keep a template with the heavy dependencies already installed (e.g. `sale`, `stock`) and
duplicate it for each run: installs are the slow part. `db` subcommands: `init`, `load`, `dump`,
`duplicate`, `rename`, `drop` (all filestore-aware).

Source: odoo/cli/db.py:35-240, `odoo-bin db --help`, odoo/modules/db.py:399-470

## Browser tests: Chrome and timeouts

- `HttpCase.browser_js`/`start_tour` and Hoot suites need Chrome or Chromium: found as
  `google-chrome`, `chromium`, `chromium-browser`, `google-chrome-stable` in `PATH`, or the path in
  `ODOO_BROWSER_BIN`. The Python package `websocket-client` is also required.
- If either is missing the test is **skipped** (`skipped Class.test : Chrome executable not found`),
  so a green run can hide untested tours: check the log for `skipped`.

| Environment variable | Effect |
|---|---|
| `ODOO_TEST_DISABLE_TIMEOUT=1` | No browser / request timeouts, test cursor lock timeout 3600 s (debugging) |
| `ODOO_TEST_MAX_FAILED_TESTS=N` | Stop the run after N failures |
| `ODOO_BROWSER_BIN=/path/chrome` | Browser binary |
| `ODOO_BROWSER_CPU_THROTTLING=N` | Slow the browser CPU N times (reproduce races) |

Source: odoo/tests/common.py:86-93, 116, 2483-2516, 2961; odoo/tests/result.py:24, 163-166

## Reading the log

| Line | Meaning |
|---|---|
| `INFO db odoo.addons.my_module.tests.test_book: Starting TestBook.test_rename ...` | test start |
| `ERROR ... FAIL: TestBook.test_rename` + traceback | assertion failed |
| `ERROR ... ERROR: TestBook.test_rename` + traceback | unexpected exception |
| `ERROR ... FAIL: Subtest TestBook.test_x (login='demo')` | failure inside `subTest` / `@users` |
| `INFO ... skipped TestUi.test_tour : Chrome executable not found` | skipped test |
| `... odoo.tests.stats: my_module: 12 tests 3.20s 1520 queries` | per-module summary |
| `N post-tests in Xs, Y queries` | post_install phase done |
| `ERROR ... At least one test failed when loading the modules.` | at_install failures |
| `[HOOT] Test "@my_module/..." failed:` | Hoot unit test failure (inside `WebSuite.test_unit_desktop`) |
| `[i/n] Tour my_tour -> Step ...` then an error | tour step that failed or timed out |

Search with `grep -E "FAIL:|ERROR:|Traceback|skipped|\[HOOT\]"`. The first traceback is
usually the real cause; later ones can be consequences.

Source: odoo/tests/result.py:118-166, 251-307; odoo/modules/loading.py:584-586; odoo/service/server.py:1544

## Toolkit: `odoo_test`, `odoo_job`

| Tool | What it does |
|---|---|
| `odoo_test(modules, test_tags=None, db=None, keep_db=False, install=False, timeout=1800, wait=300, js_tests=False)` | Without `db`: duplicates the template `odoo20_tmpl` (creating it with `db init` if missing) to `odoo20_test_<module>_<time>`, runs `-i <modules> --test-tags <tags or /module,...> --stop-after-init --log-level test` on a free port, drops the DB (unless `keep_db`). With `db`: `-u` (or `-i` with `install=True`) on that allowlisted DB. Returns pass/fail counts and tracebacks, or a job id. |
| `odoo_job(job_id, action="status"\|"log"\|"cancel", lines=120, grep=None)` | Poll a long run, tail its log (`grep="FAIL|ERROR|HOOT"`), or kill it (whole process group, including Chrome). |
| `odoo_db(action=...)` | `list`, `create_template`, `create`, `install`, `upgrade`, `neutralize`, `drop` on allowlisted DBs. |
| `odoo_server(action="start", db=..., port=8070)` | Dev server on 127.0.0.1 for `/web/tests` in a browser or tour debugging. |

Toolkit notes:
- Pass tags in the grammar above (`post_install`, not `:post_install`).
- Hoot suites live in `web` (`WebSuite`/`MobileWebSuite`, CrossModule tests) and post-install tests are only
  collected from modules updated in the run: pass `js_tests=True` and the toolkit adds `-u web`, so the default
  `/my_module` tag also runs the module's Hoot tests in headless Chrome (verified: `[HOOT] Passed 1 tests`).
  Or open `/web/tests` on a dev server (`odoo_server`).
- Browser tests are SKIPPED (not failed) without Chrome or the `websocket-client` package; the toolkit reports
  skipped tests explicitly - never read a skip as a pass.
- Only databases matching the allowlist (default `odoo20_*`) are touched.

Source: odoo20-toolkit/mcp/odoo20_mcp/tools/register_runtime.py, odoo20-toolkit/mcp/odoo20_mcp/tools/runtime.py:194-247

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `WebSuite.test_qunit_desktop` / QUnit suites in test runs | removed; Hoot only (`test_unit_desktop`, `test_unit_mobile`) | addons/web/tests/test_js.py |
| Hoot suites filtered from config inside a normal `HttpCase` | `WebSuite`/`MobileWebSuite` are `CrossModule` tests tagged `hoot`: `--test-tags hoot/my_module` | addons/web/tests/test_js.py:191-217 |
| Python 3.10+, PostgreSQL 13+ | Python 3.12 to 3.14, PostgreSQL 16+ | odoo/release.py:39-41 |
| `--http-interface` default `0.0.0.0` | `127.0.0.1` | odoo/tools/config.py:294 |
| `odoo-bin populate` (old generator) for test data | `odoo-bin duplicate` (old behaviour) or `populate` blueprints from the `populate` addon | odoo/cli/duplicate.py, addons/populate |
