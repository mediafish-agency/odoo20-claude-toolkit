# Development

## Repository layout

```
.claude-plugin/plugin.json        plugin manifest and user options (userConfig)
.claude-plugin/marketplace.json   marketplace "mediafish-odoo" listing this plugin
.mcp.json                         registers the MCP server; maps options to ODOO20_* variables
hooks/hooks.json                  SessionStart bootstrap, PostToolUse edit check
skills/<name>/SKILL.md            our 15 skills (+ references/*.md) and Odoo's 5 official skills
mcp/odoo20_mcp/
  config.py                       options, Odoo root detection, data folder
  index/                          source scanner and extractors (Python ast, lxml, CSV, JS) -> SQLite + FTS5
  query/core.py                   module graph, load order, merged models, method chains, view trees
  validate/rules.py               the rule catalogue: single source of truth for the validator, the hook and docs
  validate/{engine,semantic,rng,lint}.py   pattern engine, cross-module checks, Odoo RNG schemas, ruff/eslint
  runtime/                        odoo-bin driver, job manager, helpers run under the Odoo interpreter
  tools/                          MCP tool implementations
  server.py                       MCP server and tool registration
  check.py                        PostToolUse hook / CLI checker
mcp/tests/                        pytest suite; fixtures/addons has a clean v20 module and a planted v19 module
scripts/                          bootstrap, runtime setup, doc generators, reference checker, official-skill sync
evals/                            `claude plugin eval` cases
docs/                             this documentation
```

## Development setup

```bash
git clone https://github.com/mediafish-agency/odoo20-claude-toolkit.git
cd odoo20-claude-toolkit
export ODOO20_ROOT=~/src/odoo20                     # an Odoo 20.0 checkout
export ODOO20_DATA_DIR=~/.local/share/odoo20-dev    # keep dev data apart from an installed plugin
bash scripts/bootstrap.sh                            # venv with mcp, lxml, ruff, pytest + index
PY=$ODOO20_DATA_DIR/venv/bin/python

claude --plugin-dir .                                # run Claude Code with this working copy as the plugin
```

## Checks

```bash
$PY -m ruff check mcp scripts                        # lint (ruff.toml)
(cd mcp && $PY -m pytest)                            # fast suite (about 10 s on a warm index)
(cd mcp && $PY -m pytest -m slow)                    # calibration: validator over all of Odoo core (about 1 min)
$PY scripts/check_skill_refs.py                      # every cited path / import in the skills exists in Odoo 20
claude plugin validate --strict .                    # plugin and marketplace manifests
```

CI runs all of these against the current head of Odoo's public `20.0` branch, and once a week, to catch
upstream changes.

The calibration test is the main guard against false positives. Running the validator over every Odoo 20 core
module must report no errors, apart from a short whitelist of real upstream issues in
`mcp/tests/test_calibration.py`, each with an explanation.

## Adding a validator rule

1. Add a rule with `R(...)` in `mcp/odoo20_mcp/validate/rules.py`. It needs an id, severity, file kinds,
   title, fix, `source` (the Odoo 20 path that proves the change; the tests check it exists), the regex
   `pattern` or a `check` function, and `fixed_by` when an `upgrade_code` script fixes it. Add the literal
   strings that must be present for the rule to match to `NEEDLES` in the same file: these prefilters keep
   validation of the whole core tree fast.
2. Plant a violation in `mcp/tests/fixtures/addons/odoo19_legacy_demo`. The tests check that every rule fires
   exactly where expected.
3. Run the calibration test to make sure Odoo core does not trigger it.
4. Regenerate the docs: `$PY scripts/gen_docs.py` updates
   `skills/develop/references/version-traps.md`.

## Changing skills

- Follow [REFERENCE_STYLE.md](REFERENCE_STYLE.md). Verify every API claim in the Odoo 20 source, cite the
  path, and keep `SKILL.md` short with details in `references/`.
- Skill `description` + `when_to_use` must stay under 1,536 characters together. They decide when the skill
  loads.
- Run `scripts/check_skill_refs.py` and, for behaviour changes, the evals.
- Generated files (`version-traps.md`, `widget-index.md`, `registry-index.md`, `icons-mapping.md`,
  `docs/mcp-tools.md`) are produced by `scripts/gen_docs.py` and `scripts/gen_tool_docs.py`. Do not edit
  them by hand.
- Odoo's official skills are synced with `python3 scripts/sync_official_skills.py $ODOO20_ROOT`, never edited.

## Changing MCP tools

Tool names, descriptions and parameters live in `mcp/odoo20_mcp/server.py` and
`tools/register_runtime.py`. After a change, regenerate `docs/mcp-tools.md` with
`$PY scripts/gen_tool_docs.py`. Mark tools that only read with `readOnlyHint`, and anything that can change
state with `destructiveHint`. Keep the safety rules in [safety.md](safety.md) true.

## Evals

`evals/<case>/prompt.md` plus `graders/*.md`, run with `claude plugin eval`:

```bash
claude plugin eval . --case access-rules        # one case, with and without the plugin
```

Cases: `access-rules` (ir.access CSV semantics), `owl3-field-widget` (OWL 3 component), `port-v19-view`,
`qweb-report` (t-out, t-call parameters), `mcp-method-chain` (uses the tools as evidence). On the 0.1.0
release, with one run per case, the plugin scored 1.00 on all five cases. Without the plugin, Claude scored
0.00 on `access-rules`, 0.00 on `owl3-field-widget` and 0.67 on `qweb-report`.

## Releasing

Claude Code updates installed plugins by version number: a change pushed without a version bump does not
reach users who already installed the plugin.

1. Bump the version in `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` (plugin entry and
   metadata), `mcp/pyproject.toml` and `mcp/odoo20_mcp/server.py`.
2. Update `CHANGELOG.md`.
3. Run all checks above, then tag: `git tag v0.x.y && git push --tags`.

Users get the update with `claude plugin marketplace update mediafish-odoo` and
`claude plugin update odoo20@mediafish-odoo`. When `mcp/pyproject.toml` changed, the bootstrap hook reinstalls
the MCP dependencies on their next session.
