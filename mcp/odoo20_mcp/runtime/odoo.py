"""Running Odoo 20 (odoo-bin) safely: generated config, database allowlist, helper scripts."""
from __future__ import annotations

import configparser
import json
import os
import shutil
import socket
import subprocess
from pathlib import Path

from ..config import DB_CONF_KEYS, ROOT_HELP, TEMPLATE_DB, Config
from ..util import ToolError

HELPERS = Path(__file__).resolve().parent / "helpers"


class OdooRuntime:
    def __init__(self, config: Config):
        self.cfg = config

    # -- prerequisites -------------------------------------------------------
    def check(self) -> None:
        if self.cfg.odoo_root_source == "unset":
            raise ToolError(ROOT_HELP)
        if not self.cfg.odoo_bin.is_file():
            raise ToolError(f"odoo-bin not found under {self.cfg.odoo_root} (plugin option odoo_root)")
        if not self.cfg.odoo_python.exists():
            raise ToolError(
                f"Odoo runtime interpreter {self.cfg.odoo_python} not found. Create it with: "
                f"bash \"<plugin>/scripts/setup_odoo_runtime.sh\" \"{self.cfg.odoo_root}\"  "
                "(or the /odoo20:setup skill), or point the plugin option odoo_python at an existing Odoo 20 venv")

    def require_db(self, db: str) -> None:
        if not db:
            raise ToolError("a database name is required")
        if not self.cfg.db_allowed(db):
            raise ToolError(
                f"database {db!r} is not in the allowlist {list(self.cfg.db_allow)}; refusing to touch it. "
                "Use a name matching the allowlist (e.g. odoo20_mytest) or change the plugin option db_allow.")

    def require_writes(self, what: str) -> None:
        if not self.cfg.allow_writes:
            raise ToolError(f"{what} needs the plugin option allow_writes=true (currently false).")

    # -- configuration -------------------------------------------------------
    def db_settings(self) -> dict[str, str]:
        """Database connection keys from the user's own odoo.conf (plugin option odoo_config), if any."""
        path = self.cfg.odoo_config
        if not path:
            return {}
        if not path.is_file():
            raise ToolError(f"odoo_config {path} does not exist (plugin option odoo_config)")
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read(path, encoding="utf-8")
        except configparser.Error as exc:
            raise ToolError(f"cannot parse odoo_config {path}: {exc}") from exc
        if not parser.has_section("options"):
            return {}
        return {key: parser.get("options", key) for key in DB_CONF_KEYS
                if parser.has_option("options", key) and parser.get("options", key).strip() not in {"", "False"}}

    def pg_env(self) -> dict[str, str]:
        """Environment for psql matching the generated odoo.conf connection."""
        env = dict(os.environ)
        mapping = {"db_host": "PGHOST", "db_port": "PGPORT", "db_user": "PGUSER", "db_password": "PGPASSWORD",
                   "db_sslmode": "PGSSLMODE"}
        for key, value in self.db_settings().items():
            if key in mapping:
                env[mapping[key]] = value
        return env

    def conf(self) -> Path:
        """Write the toolkit's odoo.conf (deterministic; ~/.odoorc is never used)."""
        paths = ",".join(str(p) for p in self.cfg.addons_paths)
        text = (
            "[options]\n"
            f"addons_path = {paths}\n"
            "http_interface = 127.0.0.1\n"
            "list_db = True\n"
            "log_level = info\n"
        )
        text += "".join(f"{key} = {value}\n" for key, value in self.db_settings().items())
        path = self.cfg.odoo_conf
        if not path.exists() or path.read_text() != text:
            # may hold a database password: private to the user
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as fh:
                fh.write(text)
        os.chmod(path, 0o600)
        return path

    def cmd(self, *args: str) -> list[str]:
        """odoo-bin invocation; ``args[0]`` may be a subcommand (db, module, shell, neutralize...)."""
        self.check()
        conf = str(self.conf())
        args = list(args)
        if args and args[0] in {"db", "module", "shell", "neutralize", "i18n", "upgrade_code", "populate", "duplicate"}:
            return [str(self.cfg.odoo_python), str(self.cfg.odoo_bin), args[0], "-c", conf, *args[1:]]
        return [str(self.cfg.odoo_python), str(self.cfg.odoo_bin), "-c", conf, *args]

    def helper_cmd(self, helper: str, payload: dict) -> list[str]:
        self.check()
        payload = {**payload, "odoo_root": str(self.cfg.odoo_root), "conf": str(self.conf())}
        return [str(self.cfg.odoo_python), str(HELPERS / helper), json.dumps(payload)]

    def run_helper(self, helper: str, payload: dict, timeout: int = 180) -> dict:
        try:
            proc = subprocess.run(self.helper_cmd(helper, payload), capture_output=True, text=True, timeout=timeout,
                                  check=False, cwd=str(self.cfg.odoo_root))
        except subprocess.TimeoutExpired as exc:
            raise ToolError(f"{helper} timed out after {timeout}s") from exc
        lines = [line for line in proc.stdout.splitlines() if line.startswith("@@ODOO20@@")]
        if not lines:
            tail = "\n".join((proc.stderr or proc.stdout).splitlines()[-25:])
            raise ToolError(f"{helper} failed (exit {proc.returncode}):\n{tail}")
        result = json.loads(lines[-1][len("@@ODOO20@@"):])
        if result.get("error"):
            raise ToolError(result["error"])
        return result

    # -- databases -----------------------------------------------------------
    def list_databases(self) -> list[str]:
        psql = shutil.which("psql")
        if psql:
            proc = subprocess.run([psql, "-d", "postgres", "-Atqc",
                                   "SELECT datname FROM pg_database WHERE NOT datistemplate ORDER BY 1"],
                                  capture_output=True, text=True, timeout=20, check=False, env=self.pg_env())
            if proc.returncode == 0:
                return [d for d in proc.stdout.split() if d]
        result = self.run_helper("odoo_query.py", {"op": "list_dbs"})
        return result["databases"]

    def db_exists(self, db: str) -> bool:
        return db in self.list_databases()

    @staticmethod
    def free_port(start: int = 8170) -> int:
        for port in range(start, start + 200):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", port)) != 0:
                    return port
        raise ToolError("no free TCP port found between 8170 and 8370")

    @property
    def template_db(self) -> str:
        return TEMPLATE_DB
