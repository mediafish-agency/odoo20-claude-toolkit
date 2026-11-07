# How to write odoo20 skill reference files

These files are loaded by Claude while it writes Odoo 20 code. They must be **correct for Odoo 20.0**
(the public `20.0` branch of https://github.com/odoo/odoo), dense, and quick to scan.

## Hard rules

1. **Verify every API claim in the v20 source** before writing it (grep/read the file). Never write an
   import, method, field parameter, attribute, registry name, template name, CLI flag or XML syntax from
   memory. If you cannot verify something, leave it out or mark it `(unverified)`.
2. **Cite evidence.** Each section ends with a `Source:` line listing v20 paths relative to the Odoo root
   (e.g. `odoo/orm/models.py`, `addons/sale/security/ir.access.csv:12`). Prefer real core examples over
   invented ones; when you show a snippet copied/adapted from core, cite its path.
3. **Odoo 20 only.** Show the v20 way. When a v19 habit is wrong in 20, add it to a short
   "v19 habit → Odoo 20" table (old → new → source). Do not teach removed APIs except in those tables.
4. **No duplication of Odoo's own house rules.** The plugin ships Odoo's official skills next to ours
   (`skills/odoo-guidelines`, `odoo-web-guidelines`, `odoo-security`, `odoo-review`, `odoo-git`). For
   style/convention topics link to them with a relative path from your file, e.g.
   `[ORM guidelines](../../odoo-guidelines/guidelines/orm.md#recordsets-domains-and-context)`. Our files
   teach *how to build things in v20* (APIs, syntax, recipes, pitfalls), not naming conventions.
5. **Plain ASCII punctuation** in prose (no em dashes, curly quotes). Markdown only; fenced code blocks
   with a language tag (`python`, `xml`, `javascript`, `csv`, `scss`, `bash`).
6. **Size**: 120–400 lines per file. Start with a 2–4 line summary and a table of contents when > 150
   lines. Prefer tables and short bullets over paragraphs.
7. **Mention the MCP tools** where they help verify things at work time (names below), e.g.
   "check the merged fields with `odoo_model`".

## MCP tools available to the reader (plugin `odoo20`)

`odoo_status`, `odoo_search`, `odoo_grep`, `odoo_module`, `odoo_model`, `odoo_method`, `odoo_xmlid`,
`odoo_views`, `odoo_access`, `odoo_js`, `odoo_assets`, `odoo_validate` (legacy-pattern rules with ids like
ORM001/JS002, Odoo RNG, cross-module checks, ruff), `odoo_upgrade_code` (sandboxed diff of Odoo's
upgrade_code scripts), `odoo_scaffold`, `odoo_db`, `odoo_test` (install + run tests on a throwaway DB),
`odoo_job`, `odoo_server`, `odoo_shell`, `odoo_live_call` (JSON-2).

## File skeleton

```markdown
# <Topic> (Odoo 20)

<2-4 line summary: what this covers and when to read it>

## Contents  (only if long)

## <Section>
<rules / table / minimal correct example>

Source: odoo/orm/models.py, addons/sale/models/sale_order.py:120

## v19 habit -> Odoo 20   (when relevant)
| v19 / older | Odoo 20 | Source |
|---|---|---|
```
