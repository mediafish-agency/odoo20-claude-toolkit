---
name: run-tests
description: >-
  Install Odoo 20 modules on a throwaway database copied from odoo20_tmpl and run their Python tests (and their
  Hoot JS tests with js_tests=true), then report failures with tracebacks and propose fixes.
argument-hint: "<module[,module]> [test-tags, e.g. /my_module:TestX.test_y]"
disable-model-invocation: true
---

# Run Odoo 20 tests

Arguments: `$ARGUMENTS` - first word: comma-separated modules; optional second: a `--test-tags` spec.

1. `odoo_test(modules=<modules>, test_tags=<tags or omit>, js_tests=<true when the modules have static/tests>)`.
   The module must be in an indexed addons path. Skipped browser tests are reported separately: not a pass.
2. If a job id comes back, poll `odoo_job(job_id)` until it finishes (do not start a second run on the same
   database).
3. On failure: read the tracebacks in the result; for more context `odoo_job(job_id, action="log",
   grep="FAIL|ERROR|Traceback")`. Install errors (ParseError, Invalid view definition, access errors) come
   before tests: fix them first, guided by `odoo_validate`.
4. Report passed/failed counts, each failure with its cause, and the fix applied or proposed. Use
   `keep_db=true` when the failing state must be inspected (then `odoo_shell` on that database).
