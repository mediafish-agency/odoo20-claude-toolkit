---
name: testing
description: >-
  Default for any Odoo work in this Odoo 20.0 tree even when no version is named; takes priority over generic odoo-* skills (17-19 advice such as SavepointCase, QUnit, asyncStep is wrong in 20). A test fails, write a test or a tour, reproduce a bug - testing Odoo 20 addons: Python tests (TransactionCase, HttpCase, tagged at_install/post_install, Form,
  new_test_user, assertQueryCount, MockHTTPClient, QueryLike), Hoot JavaScript unit tests (@odoo/hoot,
  web_test_helpers with makeTestApp/mountView/onRpc; no QUnit), tours (web_tour.tours registry,
  @web_tour/tour_utils), and running them with --test-tags on throwaway databases (odoo_test).
when_to_use: >-
  Writing tests/*.py or static/tests/**/*.test.js or tours for an Odoo 20 module, reproducing a bug with a
  test, or running and reading test results.
---

# Testing Odoo 20 addons

## Workflow

1. Look at tests of the module you extend: `odoo_module(name)` lists them; reuse their common classes.
2. Write tests following Odoo's [tests guideline](../odoo-guidelines/guidelines/tests.md) (one of
   at_install/post_install, files `tests/test_*.py` imported in `tests/__init__.py`).
3. Run: `odoo_test("my_module")` (throwaway copy of `odoo20_tmpl`, dropped afterwards); add `js_tests=true`
   to also run the module's Hoot tests in headless Chrome; one test:
   `odoo_test("my_module", test_tags="/my_module:TestX.test_y")`; long runs return a job id -> `odoo_job`.
   A **skipped** browser test (no Chrome / websocket-client) is reported as such - it is not a pass.
4. Read failures from the returned tracebacks; full log: `odoo_job(job_id, action="log", grep="FAIL|ERROR")`.

## Odoo 20 rules

- `SingleTransactionCase`, `assertQueriesContain`, `registry_enter_test_mode` are gone; use
  `TransactionCase`, `with self.registry_test_mode():`.
- Constraint violations: `with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'),
  self.env.cr.savepoint(): ...; self.env.flush_all()`.
- Outbound HTTP in tests: `MockHTTPClient`; SQL assertions: `QueryLike`.
- JS: Hoot only (`@odoo/hoot`); helpers from `@web/../tests/web_test_helpers` (`makeTestApp` replaces
  `makeMockEnv`; `expect.step` + `expect.verifySteps` / `await expect.waitForSteps([...])`).
- Tours: `registry.category("web_tour.tours").add(name, { steps: () => [...] })`, helpers from
  `@web_tour/tour_utils` (no `/js/`); icon triggers use `[data-icon='close']`.
- HttpCase/JS/tours need Chrome (installed here).

## References

- [python-tests.md](references/python-tests.md) - test classes, decorators, helpers, patterns
- [hoot.md](references/hoot.md) - Hoot API and web_test_helpers with a complete widget test
- [tours.md](references/tours.md) - writing, running and debugging tours
- [running-tests.md](references/running-tests.md) - --test-tags syntax, databases, reading logs, odoo_test
