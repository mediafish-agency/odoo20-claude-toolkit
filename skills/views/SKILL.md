---
name: views
description: >-
  Default for any Odoo work in this Odoo 20.0 tree even when no version is named; takes priority over generic odoo-* skills (17-19 advice such as <tree>, attrs=, fa icons, kanban-box is wrong in 20). Hide a field or make it readonly, add a button/tab/filter/menu/settings option - Odoo 20 backend XML views: list (<column>, dialog_size), form (<chatter/>, buttons with
  Material icons), kanban card templates and the new card view (card_id), search views (date filters with
  end_date/default_period, parent filters, searchpanel), calendar/graph/pivot/activity/hierarchy, xpath
  inheritance, python-expression modifiers, field widgets, window/server/client actions with path, and menus.
when_to_use: >-
  Editing views/*.xml or any ir.ui.view/ir.actions/menuitem record in an Odoo 20 addon, choosing a widget,
  extending another module's view, Settings pages (res.config.settings), or fixing "Invalid view definition" errors.
  Server QWeb <template> pages and PDF reports: odoo20:qweb-reports.
---

# Odoo 20 views, actions and menus

## Workflow

1. Inspect the target: `odoo_views(model=..., view_type=...)` for primary views,
   `odoo_views(xmlid=...)` for the inheritance tree; exact final arch with `resolve="db"`.
2. Check fields exist: `odoo_model(model, scope_module=<your module>)`; widgets: `odoo_js(registry="fields",
   key=...)` or [widget-index.md](references/widget-index.md); icons: [buttons-icons.md](references/buttons-icons.md).
3. Write the XML following Odoo's [XML guidelines](../odoo-guidelines/guidelines/xml.md) (anchor xpaths on
   names, never positions).
4. `odoo_validate(<module>)` runs Odoo's RNG schemas and checks fields/buttons against the merged model.

## Odoo 20 rules

- `<list>` only (no `<tree>`); `attrs`/`states` are rejected: use `invisible="state != 'draft'"`,
  `readonly=`, `required=`, `column_invisible=` python expressions.
- Forms end with `<chatter/>`; kanban uses `<templates><t t-name="card">` (+ optional `menu`); the
  reusable `card` view is referenced by `<kanban card_id="%(xmlid)d">` and calendar `<popover card_id>`.
- Icons are Material Symbols: `<i class="oi" data-icon="person"/>`; buttons `icon="check"
  icon_class="oi-filled"`; Font Awesome classes no longer render.
- Search date filters: `start_month/end_month/start_year/end_year` are removed; use `date=`, `end_date=`,
  `default_period=` (e.g. `this_month`, `year-1`) and child option filters.
- Calendar has no `date_delay` (use `date_stop`); list `<column name>` groups fields and gives xpath anchors.
- Actions get a URL slug with `<field name="path">my-records</field>`; `get_formview_action` is now
  `get_record_default_action`.

## References

- [list-form.md](references/list-form.md) - list and form structure, modifiers, x2many sub-views, buttons
- [kanban-card.md](references/kanban-card.md) - kanban card templates and the card view
- [search.md](references/search.md) - search views, date filters, searchpanel, dynamic dates
- [other-views.md](references/other-views.md) - calendar, graph, pivot, activity, hierarchy, which have RNG
- [inheritance.md](references/inheritance.md) - xpath, positions, attributes, primary vs extension, QWeb inheritance
- [actions-menus.md](references/actions-menus.md) - window/server/client/URL actions, path, menus
- [widgets.md](references/widgets.md) - field widgets by type with options; [widget-index.md](references/widget-index.md) (generated list)
- [buttons-icons.md](references/buttons-icons.md) - buttons, Material icons in views, shipped subset
- [settings.md](references/settings.md) - Settings pages: res.config.settings fields and <app>/<block>/<setting>
