"""Relax NG validation with Odoo's own schemas.

* Data files: ``odoo/import_xml.rng`` (Odoo asserts it when loading, odoo/tools/convert.py).
* Primary views: ``odoo/addons/base/rng/<type>_view.rng`` (Odoo validates the *combined* arch, so
  inheriting views are only checkable through the database: odoo_views(resolve="db")).
"""
from __future__ import annotations

import copy
from functools import cache
from pathlib import Path

from lxml import etree

from .engine import Finding

RNG_VIEW_TYPES = {"list", "calendar", "graph", "pivot", "search", "activity"}
_PARSER = etree.XMLParser(huge_tree=True, resolve_entities=False)


@cache
def _import_rng(odoo_root: str) -> etree.RelaxNG | None:
    path = Path(odoo_root) / "odoo" / "import_xml.rng"
    try:
        return etree.RelaxNG(etree.parse(str(path)))
    except (OSError, etree.LxmlError):
        return None


@cache
def _view_rng(odoo_root: str, vtype: str) -> etree.RelaxNG | None:
    path = Path(odoo_root) / "odoo" / "addons" / "base" / "rng" / f"{vtype}_view.rng"
    if not path.is_file():
        return None
    try:
        return etree.RelaxNG(etree.parse(str(path)))
    except etree.LxmlError:
        return None


def check_data_file(path: Path, display: str, odoo_root: Path, max_errors: int = 5) -> list[Finding]:
    try:
        doc = etree.parse(str(path), _PARSER)
    except etree.XMLSyntaxError as exc:
        return [Finding("XMLSYNTAX", "error", display, exc.lineno or 0, f"XML syntax error: {exc.msg}")]
    findings: list[Finding] = []
    rng = _import_rng(str(odoo_root))
    if rng is not None and not rng.validate(doc):
        for err in list(rng.error_log)[:max_errors]:
            findings.append(Finding(
                "RNG001", "error", display, err.line,
                f"data file rejected by odoo/import_xml.rng: {err.message}",
                "Odoo refuses to load this file (allowed roots: <odoo>/<data>; tags: record, template, menuitem, "
                "asset, function, delete; see the rng for attributes)", "odoo/import_xml.rng"))
    findings.extend(_check_primary_views(doc, display, odoo_root, max_errors))
    return findings


def _check_primary_views(doc, display: str, odoo_root: Path, max_errors: int) -> list[Finding]:
    findings: list[Finding] = []
    for record in doc.iter("record"):
        if record.get("model") != "ir.ui.view":
            continue
        fields = {f.get("name"): f for f in record.findall("field")}
        if "inherit_id" in fields or "arch" not in fields:
            continue
        arch = next((c for c in fields["arch"] if isinstance(c.tag, str)), None)
        if arch is None or arch.tag not in RNG_VIEW_TYPES:
            continue
        rng = _view_rng(str(odoo_root), arch.tag)
        if rng is None:
            continue
        candidate = copy.deepcopy(arch)
        if candidate.tag == "search":
            for panel in candidate.findall("searchpanel"):
                candidate.remove(panel)  # Odoo validates the search panel separately
        if not rng.validate(candidate):
            for err in list(rng.error_log)[:max_errors]:
                findings.append(Finding(
                    "RNG002", "error", display, err.line or record.sourceline or 0,
                    f"view {record.get('id')}: <{arch.tag}> rejected by base/rng/{arch.tag}_view.rng: {err.message}",
                    "Invalid view definition at install; compare with the rng / a core view of that type",
                    f"odoo/addons/base/rng/{arch.tag}_view.rng"))
    return findings
