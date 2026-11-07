#!/usr/bin/env bash
# Create (or refresh) a Python virtualenv able to run Odoo 20 from source (odoo-bin).
#
# Skip this script when you already have a working Odoo 20 venv: point the plugin option
# odoo_python at its interpreter instead.
#
# By default the venv reuses the system site-packages and installs only the pins from Odoo's
# requirements.txt that are not already satisfied (fast, and reuses distro packages such as
# python3-psycopg2). Pass --isolated for a clean venv that installs every requirement.
#
# Usage: bash setup_odoo_runtime.sh ODOO_ROOT [VENV_DIR] [--isolated]
#        (ODOO_ROOT defaults to $ODOO20_ROOT, VENV_DIR to $ODOO20_VENV or ~/.venvs/odoo20)
#
# Building some requirements from source needs system headers:
#   Debian/Ubuntu: sudo apt install python3-dev python3-venv libpq-dev libldap2-dev libsasl2-dev \
#                  libxml2-dev libxslt1-dev libjpeg-dev zlib1g-dev
#   macOS (Homebrew): brew install postgresql@16 libpq openldap
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$HERE/lib.sh"

ISOLATED=0
POSITIONAL=()
for arg in "$@"; do
    case "$arg" in
        --isolated) ISOLATED=1 ;;
        -h|--help) sed -n 2,17p "${BASH_SOURCE[0]}"; exit 0 ;;
        *) POSITIONAL+=("$arg") ;;
    esac
done
ODOO_ROOT="${POSITIONAL[0]:-${ODOO20_ROOT:-${CLAUDE_PLUGIN_OPTION_ODOO_ROOT:-}}}"
VENV_DIR="${POSITIONAL[1]:-${ODOO20_VENV:-$HOME/.venvs/odoo20}}"

if [[ -z "$ODOO_ROOT" || ! -f "$ODOO_ROOT/odoo-bin" ]]; then
    echo "error: give the Odoo 20 source tree (the folder containing odoo-bin) as first argument" >&2
    echo "       e.g. git clone --depth 1 --branch 20.0 https://github.com/odoo/odoo.git ~/src/odoo20" >&2
    exit 1
fi
MAJOR="$(sed -n 's/^version_info = (\([0-9]*\),.*/\1/p' "$ODOO_ROOT/odoo/release.py")"
if [[ "$MAJOR" != "20" ]]; then
    echo "error: $ODOO_ROOT is Odoo ${MAJOR:-?}, not Odoo 20" >&2
    exit 1
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    if ! PY="$(odoo20_find_python 3.12)"; then
        echo "error: Odoo 20 needs Python 3.12-3.14; none found (set PYTHON=/path/to/python3.12)" >&2
        exit 1
    fi
    echo "creating venv $VENV_DIR with $PY"
    mkdir -p "$(dirname "$VENV_DIR")"
    if [[ $ISOLATED == 1 ]]; then
        "$PY" -m venv "$VENV_DIR"
    else
        "$PY" -m venv --system-site-packages "$VENV_DIR"
    fi
fi

VPY="$VENV_DIR/bin/python"
"$VPY" -c "import packaging" 2>/dev/null || "$VPY" -m pip install --disable-pip-version-check --quiet packaging

# The requirement lines (for this interpreter and platform) that are not satisfied yet, plus dependencies of
# already-installed requirements that are missing (system packages are not always complete: a distro `zeep`
# without `attrs` breaks `import odoo.addons.base`).
MISSING=()
while IFS= read -r line; do
    [[ -n "$line" ]] && MISSING+=("$line")
done < <("$VPY" - "$ODOO_ROOT/requirements.txt" <<'EOF'
import importlib.metadata as md
import sys
from packaging.requirements import Requirement

def key(name):
    return name.lower().replace("_", "-").replace(".", "-")

wanted, seen = [], set()

def walk(req, top):
    if key(req.name) in seen:
        return
    seen.add(key(req.name))
    try:
        dist = md.distribution(req.name)
    except md.PackageNotFoundError:
        wanted.append(f"{req.name}{req.specifier}" if top else req.name)
        return
    if top and not req.specifier.contains(dist.version, prereleases=True):
        wanted.append(f"{req.name}{req.specifier}")
        return  # pip resolves the dependencies of the version it installs
    for raw in dist.requires or []:
        dep = Requirement(raw)
        if dep.marker and not dep.marker.evaluate({"extra": ""}):
            continue
        walk(dep, False)

for raw in open(sys.argv[1], encoding="utf-8"):
    line = raw.split("#", 1)[0].strip()
    if not line:
        continue
    req = Requirement(line)
    if req.marker and not req.marker.evaluate():
        continue
    walk(req, True)
print("\n".join(wanted))
EOF
)

if ((${#MISSING[@]})); then
    echo "installing ${#MISSING[@]} pinned packages: ${MISSING[*]}"
    "$VPY" -m pip install --disable-pip-version-check --quiet "${MISSING[@]}" || {
        echo "error: pip failed. Install the system headers listed at the top of this script and retry." >&2
        exit 1; }
else
    echo "all requirements already satisfied"
fi

# Test-only dependency: HttpCase browser tests (tours, Hoot suites) are SKIPPED without it.
"$VPY" -m pip install --disable-pip-version-check --quiet websocket-client

echo "checking odoo-bin"
"$VPY" "$ODOO_ROOT/odoo-bin" --version
echo "runtime ready: $VPY"
echo "set the plugin option odoo_python to this path if it is not the default ~/.venvs/odoo20/bin/python"
