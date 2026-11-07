# Shared helpers for the odoo20 shell entry points. Sourced, never executed.
# Portable to Linux and macOS (bash >= 3.2, no GNU-only tools required).

# Home directory of the real user: HOME may be overridden (eval sandboxes, sudo, containers).
odoo20_real_home() {
    local h=""
    if command -v getent >/dev/null 2>&1; then
        h="$(getent passwd "$(id -u)" 2>/dev/null | cut -d: -f6)"
    fi
    if [[ -z "$h" ]] && command -v python3 >/dev/null 2>&1; then
        h="$(python3 -c 'import os, pwd; print(pwd.getpwuid(os.getuid()).pw_dir)' 2>/dev/null || true)"
    fi
    echo "${h:-$HOME}"
}

# First odoo20 plugin data dir (under HOME, then the real home) that already holds an installed runtime.
odoo20_existing_runtime_dir() {
    local home d
    for home in "$HOME" "$(odoo20_real_home)"; do
        for d in "$home"/.claude/plugins/data/odoo20-*; do
            if [[ -x "$d/venv/bin/python" ]]; then
                echo "$d"
                return 0
            fi
        done
    done
    return 1
}

# Where the MCP venv, source index, generated odoo.conf and job logs live:
#   1. ODOO20_DATA_DIR                          (explicit; standalone use)
#   2. CLAUDE_PLUGIN_DATA when it is ours and already holds a runtime
#      (ours = basename odoo20-*; another plugin's value may leak into hook environments)
#   3. any odoo20 plugin data dir that already holds a runtime (reinstall under another marketplace
#      name, /odoo20:setup run from a shell, eval sandbox with another HOME): reuse it, no duplicate index
#   4. CLAUDE_PLUGIN_DATA when it is ours       (fresh install)
#   5. ~/.claude/plugins/data/odoo20-standalone
# Keep in sync with default_data_dir() in mcp/odoo20_mcp/config.py.
odoo20_data_dir() {
    if [[ -n "${ODOO20_DATA_DIR:-}" ]]; then
        echo "$ODOO20_DATA_DIR"
        return
    fi
    local ours=""
    case "$(basename "${CLAUDE_PLUGIN_DATA:-}")" in
        odoo20-*) ours="$CLAUDE_PLUGIN_DATA" ;;
    esac
    if [[ -n "$ours" && -x "$ours/venv/bin/python" ]]; then
        echo "$ours"
        return
    fi
    odoo20_existing_runtime_dir && return
    echo "${ours:-$HOME/.claude/plugins/data/odoo20-standalone}"
}

# A Python >= $1 (default 3.12) interpreter: $PYTHON first, then python3.14 .. python3.
odoo20_find_python() {
    local min="${1:-3.12}" c
    for c in "${PYTHON:-}" python3.14 python3.13 python3.12 python3; do
        [[ -n "$c" ]] || continue
        command -v "$c" >/dev/null 2>&1 || continue
        if "$c" -c "import sys; sys.exit(0 if sys.version_info >= tuple(map(int, '$min'.split('.'))) else 1)" 2>/dev/null; then
            command -v "$c"
            return 0
        fi
    done
    return 1
}

odoo20_sha256() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | cut -d' ' -f1
    else
        shasum -a 256 "$1" | cut -d' ' -f1
    fi
}

# Non-blocking exclusive lock: flock when available (Linux), else an atomic mkdir (macOS).
# Returns 1 when another holder is active. Released automatically when the shell exits.
odoo20_try_lock() {
    local lock="$1"
    if command -v flock >/dev/null 2>&1; then
        exec 9>"$lock"
        flock -n 9
        return
    fi
    local dir="$lock.d"
    if ! mkdir "$dir" 2>/dev/null; then
        # a lock older than 30 minutes is stale (killed bootstrap)
        if [[ -n "$(find "$dir" -maxdepth 0 -mmin +30 2>/dev/null)" ]]; then
            rm -rf "$dir"
            mkdir "$dir" 2>/dev/null || return 1
        else
            return 1
        fi
    fi
    # shellcheck disable=SC2064
    trap "rm -rf '$dir'" EXIT
}
