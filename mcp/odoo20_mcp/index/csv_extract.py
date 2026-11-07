"""Extract data rows from Odoo CSV data files (model taken from the file name)."""
from __future__ import annotations

import csv
import io
import json
import os

from .xml_extract import full_id


def csv_model(rel: str) -> str:
    return os.path.basename(rel)[:-4].split("-")[0]


def extract(module: str, rel: str, text: str) -> dict[str, list]:
    out: dict[str, list] = {"records": [], "access": [], "refs": [], "errors": []}
    model = csv_model(rel)
    try:
        reader = csv.DictReader(io.StringIO(text))
        header = reader.fieldnames or []
        rows = list(reader)
    except csv.Error as exc:
        out["errors"].append((module, rel, 0, f"csv.Error: {exc}"))
        return out
    # line numbers: header is line 1; assumes no multi-line cells (true for Odoo data CSVs)
    for idx, row in enumerate(rows, start=2):
        xmlid = full_id(module, (row.get("id") or "").strip() or None)
        if model == "ir.access":
            group = (row.get("group_id/id") or row.get("group_id:id") or row.get("group_id") or "").strip()
            out["access"].append((
                module, xmlid, row.get("name"), (row.get("model_id") or "").strip() or None, None,
                full_id(module, group) if group else None, (row.get("operation") or "").strip() or None,
                (row.get("domain") or "").strip() or None,
                0 if (row.get("active") or "").strip() in {"0", "False", "false"} else 1, "csv", rel, idx,
            ))
            if group:
                out["refs"].append((module, full_id(module, group), "csv.group_id", "csv", rel, idx))
        else:
            # keep a small preview: large l10n CSVs would otherwise dominate the index size
            values = {k: (v or "")[:60] for k, v in list(row.items())[:6] if k and k != "id"}
            out["records"].append((module, xmlid, model, "csv", json.dumps(values), 0, rel, idx))
            for col in header:
                if col and (col.endswith("/id") or col.endswith(":id")) and row.get(col):
                    for ref in row[col].split(","):
                        if ref.strip():
                            out["refs"].append((module, full_id(module, ref.strip()), f"csv.{col}", "csv", rel, idx))
    return out
