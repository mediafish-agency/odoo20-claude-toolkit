#!/usr/bin/env bash
# Start the odoo20 MCP server (stdio). Never installs anything: installation is
# done by scripts/bootstrap.sh (run by the SessionStart hook, the /odoo20:setup
# skill or by hand), so the server start stays well inside the MCP connection timeout.
#
# Standalone use (any MCP client): set ODOO20_ROOT (and optionally the other ODOO20_*
# variables, see docs/configuration.md) and run:  bash mcp/run.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../scripts/lib.sh
source "$HERE/../scripts/lib.sh"

DATA="$(odoo20_data_dir)"   # reuses an installed runtime when there is one (scripts/lib.sh)
PY="$DATA/venv/bin/python"

if [[ ! -x "$PY" ]] || ! "$PY" -c "import mcp, lxml" 2>/dev/null; then
    echo "odoo20 MCP: runtime not installed yet in $DATA. Run: bash \"$HERE/../scripts/bootstrap.sh\"" \
         "(or the /odoo20:setup skill), then reconnect the server with /mcp." >&2
    exit 1
fi

export PYTHONPATH="$HERE${PYTHONPATH:+:$PYTHONPATH}"
export CLAUDE_PLUGIN_DATA="$DATA"
exec "$PY" -m odoo20_mcp "$@"
