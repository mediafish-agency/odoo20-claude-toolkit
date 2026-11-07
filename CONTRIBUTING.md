# Contributing

Thanks for helping improve the toolkit. The most valuable contributions are:

- **Wrong or missing Odoo 20 facts** in a skill. Open an issue or a PR with the Odoo 20 source path that
  shows the correct behaviour.
- **Validator false positives or misses**: the snippet, the rule id, and what Odoo 20 actually does.
- **New breaking changes** between Odoo 19 and 20 that the validator should catch.
- Fixes for installation problems on other systems.

## Ground rules

- Every API claim must be verified in the Odoo 20.0 source and cited (see
  [docs/REFERENCE_STYLE.md](docs/REFERENCE_STYLE.md)).
- Do not edit generated files or Odoo's official skills by hand. See [docs/development.md](docs/development.md).
- Keep the safety model intact: no tool may write into the Odoo tree, touch a database outside the allowlist,
  or print secrets.
- Before opening a PR, run the checks in [docs/development.md](docs/development.md#checks): ruff, the fast and
  slow test suites, `check_skill_refs.py`, and `claude plugin validate --strict .`.

## Pull requests

One topic per PR, with a short description of the problem and how you verified the fix. New rules come
with a planted case in the legacy fixture module. Skill changes that alter behaviour come with an eval run
when possible.

By contributing you agree that your contribution is licensed under the LGPL-3.0, like the rest of the
project.
