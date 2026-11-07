"""Extract records, views, templates, menus, access rows and references from XML."""
from __future__ import annotations

import json
import re

from lxml import etree

_PARSER = etree.XMLParser(remove_blank_text=False, resolve_entities=False, huge_tree=True, recover=False)
_REF_EVAL = re.compile(r"\bref\(\s*['\"]([\w.]+)['\"]")
_PCT_REF = re.compile(r"%\(([\w.]+)\)d")
SUBVIEW_TAGS = {"list", "form", "kanban", "graph", "pivot", "calendar", "search", "activity", "card", "hierarchy"}
RECORD_FIELDS_KEEP = 25


def full_id(module: str, xmlid: str | None) -> str | None:
    if not xmlid:
        return None
    return xmlid if "." in xmlid else f"{module}.{xmlid}"


def _ancestor_attr(el, tag_names: set[str], attr: str):
    node = el.getparent()
    while node is not None:
        if node.tag in tag_names and node.get(attr) is not None:
            return node.get(attr)
        node = node.getparent()
    return None


LONG_TEXT_FIELDS = {"domain", "domain_force", "code", "operation", "context", "arch"}


def _field_value(field_el, module: str):
    if field_el.get("ref"):
        return {"ref": full_id(module, field_el.get("ref"))}
    limit = 4000 if field_el.get("name") in LONG_TEXT_FIELDS else 300
    if field_el.get("eval") is not None:
        return {"eval": field_el.get("eval")[:limit]}
    if field_el.get("search") is not None:
        return {"search": field_el.get("search")[:300]}
    if field_el.get("file"):
        return {"file": field_el.get("file"), "type": field_el.get("type")}
    if field_el.get("type") in {"xml", "html"} or len(field_el):
        return {"type": field_el.get("type") or "xml"}
    return (field_el.text or "").strip()[:limit]


def _arch_root(record_el):
    for f in record_el.findall("field"):
        if f.get("name") == "arch":
            for child in f:
                if isinstance(child.tag, str):
                    return child
    return None


# any further path step after field[@name=...] (e.g. "/list/field", "//field") goes into the field's sub-view
_SUBVIEW_EXPR = re.compile(r"field\[@name=['\"][\w.]+['\"]\]\s*/(?!\.\.)")
_LAST_FIELD = re.compile(r"field\[@name=['\"]([\w.]+)['\"]\]")


def _own_elements(container, foreign_roots=frozenset()):
    """Fields and object buttons of ``container`` that act on the container's model.

    Skips x2many sub-views (children of a real <field>), list <groupby> blocks (they act on the
    grouped-by model) and any element under ``foreign_roots``.
    """
    fields, buttons = [], []
    for el in container.iter():
        if not isinstance(el.tag, str):
            continue
        node, foreign = (None if el is container else el.getparent()), el in foreign_roots
        while node is not None and not foreign:
            if node in foreign_roots:
                foreign = True
                break
            if node.tag in {"field", "groupby"} and node.get("position") is None:
                foreign = True
                break
            if node is container:
                break
            node = node.getparent()
        if foreign or el.tag == "groupby":
            continue
        if el.tag == "field" and el.get("name") and el.get("position") is None:
            fields.append(el.get("name"))
        elif el.tag == "button" and el.get("type") == "object" and el.get("name"):
            buttons.append(el.get("name"))
    return fields, buttons


def _arch_summary(arch):
    """Return (fields, buttons, specs).

    Primary views: fields/buttons on the view's model. Inheriting views: ``specs`` is a list of
    {spec, anchor, fields, buttons, subview}: ``anchor`` is the field the spec is positioned on, so a
    checker can tell (anchor not on the model => the spec edits an x2many sub-view of another model).
    """
    inheriting = arch.tag == "data" or arch.get("position") is not None or any(
        isinstance(c.tag, str) and c.get("position") for c in arch)
    if not inheriting:
        fields, buttons = _own_elements(arch)
        return sorted(set(fields)), sorted(set(buttons)), []
    specs = []
    all_fields, all_buttons = set(), set()
    for spec in ([arch] if arch.get("position") is not None else list(arch)):
        if not isinstance(spec.tag, str):
            continue
        expr = spec.get("expr") or ""
        if spec.tag == "field":
            anchor = spec.get("name")
        else:
            names = _LAST_FIELD.findall(expr)
            anchor = names[-1] if names else None
        position = spec.get("position", "inside")
        subview = bool(_SUBVIEW_EXPR.search(expr)) or (position == "inside" and anchor is not None) or \
            bool(re.search(r"(?:^|/)(?:list|kanban)\b", expr) and spec.tag == "xpath" and anchor is not None)
        if spec.tag == "field":
            # children of a <field position=...> spec are inserted content, not a sub-view
            fields, buttons = [], []
            for child in spec:
                if isinstance(child.tag, str):
                    f, b = _own_elements(child)
                    if child.tag == "field" and child.get("name") and child.get("position") is None:
                        f = [child.get("name")]
                    elif child.tag == "button" and child.get("type") == "object" and child.get("name"):
                        b = [child.get("name")]
                    fields += f
                    buttons += b
        else:
            fields, buttons = _own_elements(spec)
        specs.append({
            "spec": f"{spec.tag}[{expr or spec.get('name') or ''}] {position}",
            "anchor": anchor, "subview": subview,
            "fields": sorted(set(fields)), "buttons": sorted(set(buttons)),
        })
        all_fields |= set(fields)
        all_buttons |= set(buttons)
    return sorted(all_fields), sorted(all_buttons), specs[:60]


def _collect_refs(module: str, rel: str, root, out_refs: list) -> None:
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        line = el.sourceline or 0
        attrs = ("ref", "inherit_id", "parent", "action") if el.tag == "menuitem" else ("ref", "inherit_id")
        for attr in attrs:
            val = el.get(attr)
            if val and not val.startswith("%") and re.fullmatch(r"[\w.]+", val):
                out_refs.append((module, full_id(module, val), f"xml.{attr}", "xml", rel, line))
        groups = el.get("groups")
        if groups:
            for grp in groups.split(","):
                grp = grp.strip().lstrip("!-")
                if grp:
                    out_refs.append((module, full_id(module, grp), "xml.groups", "xml", rel, line))
        tcall = el.get("t-call")
        if tcall and re.fullmatch(r"[\w.]+", tcall):
            out_refs.append((module, tcall, "xml.t-call", "xml", rel, line))
        texts = [v for v in el.attrib.values()]
        if el.text:
            texts.append(el.text)
        for text in texts:
            if "ref(" in text:
                for m in _REF_EVAL.finditer(text):
                    out_refs.append((module, full_id(module, m.group(1)), "xml.eval", "xml", rel, line))
            if "%(" in text:
                for m in _PCT_REF.finditer(text):
                    out_refs.append((module, full_id(module, m.group(1)), "xml.%d", "xml", rel, line))


def extract_server(module: str, rel: str, data: bytes) -> dict[str, list]:
    out: dict[str, list] = {"records": [], "views": [], "refs": [], "access": [], "errors": []}
    try:
        root = etree.fromstring(data, _PARSER)
    except etree.XMLSyntaxError as exc:
        out["errors"].append((module, rel, exc.lineno or 0, f"XMLSyntaxError: {exc.msg}"))
        return out
    _collect_refs(module, rel, root, out["refs"])

    for el in root.iter("record", "template", "menuitem", "asset"):
        line = el.sourceline or 0
        noupdate = el.get("noupdate") or _ancestor_attr(el, {"odoo", "openerp", "data"}, "noupdate") or "0"
        noupdate = int(str(noupdate).strip().lower() in {"1", "true"})
        xmlid = full_id(module, el.get("id"))
        if el.tag == "record":
            model = el.get("model")
            values = {}
            for f in el.findall("field"):
                if f.get("name") and len(values) < RECORD_FIELDS_KEEP:
                    values[f.get("name")] = _field_value(f, module)
            out["records"].append((module, xmlid, model, "record", json.dumps(values, default=str), noupdate, rel, line))
            if model == "ir.ui.view":
                arch = _arch_root(el)
                inherit = values.get("inherit_id")
                inherit = inherit.get("ref") if isinstance(inherit, dict) else None
                vtype = arch.tag if arch is not None else (values.get("type") if isinstance(values.get("type"), str) else None)
                kind = "qweb" if vtype in {"t", "templates"} or values.get("type") == "qweb" else "view"
                fields, buttons, specs = _arch_summary(arch) if arch is not None else ([], [], [])
                mode = values.get("mode") if isinstance(values.get("mode"), str) else None
                priority = values.get("priority") if isinstance(values.get("priority"), str) else None
                vmodel = values.get("model") if isinstance(values.get("model"), str) else None
                out["views"].append((
                    module, xmlid, kind, vmodel, vtype, inherit, mode or ("extension" if inherit else "primary"),
                    priority, values.get("name") if isinstance(values.get("name"), str) else None,
                    json.dumps(fields), json.dumps(specs), json.dumps(buttons), el.get("groups"), rel, line,
                ))
            elif model == "ir.access":
                def _txt(key, values=values):
                    v = values.get(key)
                    return v if isinstance(v, str) else (json.dumps(v) if v else None)
                model_ref = values.get("model_id")
                group_ref = values.get("group_id")
                active = values.get("active")
                out["access"].append((
                    module, xmlid, _txt("name"),
                    model_ref if isinstance(model_ref, str) else None,
                    model_ref.get("ref") if isinstance(model_ref, dict) else None,
                    group_ref.get("ref") if isinstance(group_ref, dict) else (group_ref or None),
                    _txt("operation"), _txt("domain"),
                    0 if isinstance(active, dict) and active.get("eval", "").strip() in {"False", "0"} else 1,
                    "xml", rel, line,
                ))
        elif el.tag == "template":
            inherit = full_id(module, el.get("inherit_id"))
            mode = "primary" if el.get("primary") in {"True", "1", "true"} or not inherit else "extension"
            fields, buttons, specs = _arch_summary(el) if inherit else ([], [], [])
            out["views"].append((
                module, xmlid, "qweb", None, "qweb", inherit, mode, el.get("priority"), el.get("name"),
                json.dumps([]), json.dumps(specs), json.dumps([]), el.get("groups"), rel, line,
            ))
            out["records"].append((module, xmlid, "ir.ui.view", "template", json.dumps({"inherit_id": inherit}), noupdate, rel, line))
        elif el.tag == "menuitem":
            parent = el.get("parent")
            if not parent:
                anc = el.getparent()
                parent = anc.get("id") if anc is not None and anc.tag == "menuitem" else None
            values = {
                "name": el.get("name"), "parent": full_id(module, parent), "action": full_id(module, el.get("action")),
                "sequence": el.get("sequence"), "groups": el.get("groups"), "web_icon": el.get("web_icon"),
            }
            out["records"].append((module, xmlid, "ir.ui.menu", "menuitem", json.dumps(values), noupdate, rel, line))
        elif el.tag == "asset":
            values = {"name": el.get("name"), "active": el.get("active")}
            out["records"].append((module, xmlid, "theme.ir.asset", "asset", json.dumps(values), noupdate, rel, line))
    return out


def extract_static(module: str, rel: str, data: bytes) -> dict[str, list]:
    """OWL / client-side QWeb templates under static/."""
    out: dict[str, list] = {"templates": [], "refs": [], "errors": []}
    try:
        root = etree.fromstring(data, _PARSER)
    except etree.XMLSyntaxError as exc:
        out["errors"].append((module, rel, exc.lineno or 0, f"XMLSyntaxError: {exc.msg}"))
        return out
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        name = el.get("t-name")
        if name:
            out["templates"].append((
                module, name, el.get("t-inherit"), el.get("t-inherit-mode"), rel, el.sourceline or 0,
            ))
        tcall = el.get("t-call")
        if tcall and re.fullmatch(r"[\w.]+", tcall):
            out["refs"].append((module, tcall, "owl.t-call", "xml", rel, el.sourceline or 0))
    return out
