# Notices

## License

This toolkit is licensed under the GNU Lesser General Public License v3.0 (see [LICENSE](LICENSE)), the same
license as Odoo Community. The LGPL v3 is a set of additional permissions on top of the GNU General Public
License v3: <https://www.gnu.org/licenses/gpl-3.0.txt>.

## Third-party content

| Content | Origin | License |
|---|---|---|
| `skills/odoo-guidelines`, `skills/odoo-web-guidelines`, `skills/odoo-review`, `skills/odoo-security`, `skills/odoo-git` | Copied unchanged from the `skills/` folder of [Odoo 20.0](https://github.com/odoo/odoo/tree/20.0/skills) (commit recorded in `skills/OFFICIAL_SKILLS_SOURCE.txt`) | LGPL-3.0, Copyright Odoo S.A. |
| `skills/owl/references/icons-mapping.md` | Generated from `odoo/upgrade_code/material_symbols_icons_mapping.py` and the shipped icon list of Odoo 20.0 | LGPL-3.0, Copyright Odoo S.A. |
| `skills/views/references/widget-index.md`, `skills/owl/references/registry-index.md` | Generated from the JavaScript registries of Odoo 20.0 | LGPL-3.0, Copyright Odoo S.A. |
| Short code excerpts and file/line citations in `skills/**/references/*.md` | Odoo 20.0 source, quoted to document its APIs | LGPL-3.0, Copyright Odoo S.A. |

At runtime the MCP server reads (but does not redistribute) your own Odoo checkout, including Odoo's RelaxNG
schemas, `ruff.toml` and `upgrade_code` scripts.

The Python packages installed by `scripts/bootstrap.sh` (`mcp`, `lxml`, `ruff`, `pytest`) come from PyPI under
their own licenses and are not part of this repository.

## Trademarks

Odoo is a trademark of Odoo S.A. Claude and Claude Code are trademarks of Anthropic, PBC. This project is
an independent community toolkit by mediafish; it is not affiliated with, sponsored or endorsed by Odoo S.A.
or Anthropic.
