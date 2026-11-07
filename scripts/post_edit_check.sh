#!/usr/bin/env bash
# PostToolUse hook: check an edited file for Odoo 19 -> 20 breaking patterns.
# Silent (exit 0) when the runtime is not installed or the file is not part of an Odoo addon.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib.sh
source "$HERE/scripts/lib.sh"

DATA="$(odoo20_data_dir)"   # reuses an installed runtime when there is one (scripts/lib.sh)
PY="$DATA/venv/bin/python"
[[ -x "$PY" ]] || exit 0
PYTHONPATH="$HERE/mcp" exec "$PY" -m odoo20_mcp.check
