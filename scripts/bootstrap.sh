#!/usr/bin/env bash
# Install / refresh the odoo20 MCP server runtime in the plugin data directory and pre-build the
# Odoo source index. Idempotent and quick when nothing changed. Safe to run by hand, from the
# /odoo20:setup skill, or from the SessionStart hook.
#
#   bash scripts/bootstrap.sh                # install if needed, refresh the index
#   bash scripts/bootstrap.sh --quiet        # no output unless something fails
#   bash scripts/bootstrap.sh --if-missing   # only act when the venv is missing/outdated (hook mode)
#
# Needs Python >= 3.12 with the venv module (Debian/Ubuntu: apt install python3-venv).
# Override the interpreter with PYTHON=/path/to/python3.12.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib.sh
source "$HERE/scripts/lib.sh"

DATA="$(odoo20_data_dir)"
VENV="$DATA/venv"
STAMP="$VENV/.pyproject.sha"
QUIET=0
IF_MISSING=0
for arg in "$@"; do
    case "$arg" in
        --quiet) QUIET=1 ;;
        --if-missing) IF_MISSING=1 ;;
        -h|--help) sed -n 2,11p "${BASH_SOURCE[0]}"; exit 0 ;;
    esac
done
say() { [[ $QUIET == 1 ]] || echo "odoo20 bootstrap: $*"; }

mkdir -p "$DATA"
if ! odoo20_try_lock "$DATA/.bootstrap.lock"; then
    say "another bootstrap is running; skipping"
    exit 0
fi

WANT="$(odoo20_sha256 "$HERE/mcp/pyproject.toml")"
HAVE="$(cat "$STAMP" 2>/dev/null || true)"

if [[ ! -x "$VENV/bin/python" || "$WANT" != "$HAVE" ]]; then
    if ! PY="$(odoo20_find_python 3.12)"; then
        echo "odoo20 bootstrap: Python >= 3.12 not found (tried \$PYTHON, python3.14 .. python3)." \
             "Install it, or run with PYTHON=/path/to/python3.12." >&2
        exit 1
    fi
    say "installing the MCP runtime into $VENV (with $PY)"
    if [[ ! -x "$VENV/bin/python" ]]; then
        "$PY" -m venv "$VENV" || {
            echo "odoo20 bootstrap: '$PY -m venv' failed (Debian/Ubuntu: sudo apt install python3-venv)." >&2
            rm -rf "$VENV"; exit 1; }
    fi
    "$VENV/bin/python" -m pip install --disable-pip-version-check --quiet --upgrade pip >/dev/null
    "$VENV/bin/python" -m pip install --disable-pip-version-check --quiet "mcp>=2.3,<3" "lxml>=5.2" "ruff>=0.6" "pytest>=8"
    echo "$WANT" > "$STAMP"
elif [[ $IF_MISSING == 1 ]]; then
    exit 0
fi

say "refreshing the Odoo source index"
PYTHONPATH="$HERE/mcp" CLAUDE_PLUGIN_DATA="$DATA" "$VENV/bin/python" - <<'EOF'
from odoo20_mcp.config import ROOT_HELP
from odoo20_mcp.context import config, index

cfg = config()
if not cfg.has_odoo_root:
    print("odoo20 bootstrap: runtime installed; index skipped.", ROOT_HELP)
else:
    print(f"odoo20 bootstrap: indexing {cfg.odoo_root} ({cfg.odoo_root_source})"
          + (f" + {len(cfg.extra_addons)} extra path(s)" if cfg.extra_addons else ""))
    print("odoo20 bootstrap: index", index().build())
EOF
say "done (data dir: $DATA)"
