"""Copy Odoo's official skills (odoo/skills/*) verbatim into this plugin's skills/ folder.

They must sit side by side (they link to each other with ../), and our own skills link to them for house
rules. Re-run after updating the Odoo checkout:  python3 scripts/sync_official_skills.py ODOO_ROOT
(ODOO_ROOT defaults to $ODOO20_ROOT).
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ODOO = Path(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("ODOO20_ROOT", "")).expanduser()
OFFICIAL = ["odoo-git", "odoo-guidelines", "odoo-review", "odoo-security", "odoo-web-guidelines"]


def main() -> None:
    src_root = ODOO / "skills"
    if not str(ODOO) or str(ODOO) == "." or not src_root.is_dir():
        sys.exit(f"{src_root} not found (is this an Odoo 20 checkout?)")
    head = subprocess.run(["git", "-C", str(ODOO), "rev-parse", "HEAD"], capture_output=True,
                          text=True, check=False).stdout.strip() or "unknown"
    for name in OFFICIAL:
        src, dst = src_root / name, ROOT / "skills" / name
        if not src.is_dir():
            print(f"skip {name}: not in {src_root}")
            continue
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        print(f"synced {name}")
    (ROOT / "skills" / "OFFICIAL_SKILLS_SOURCE.txt").write_text(
        "Copied verbatim from the skills/ folder of Odoo 20.0 (https://github.com/odoo/odoo, branch 20.0)\n"
        f"at commit {head}. Do not edit; re-run scripts/sync_official_skills.py.\n"
        "Copyright Odoo S.A., licensed under the GNU LGPL v3 like Odoo Community (see NOTICE.md).\n")


if __name__ == "__main__":
    main()
