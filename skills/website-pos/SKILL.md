---
name: website-pos
description: >-
  Default for any Odoo work in this Odoo 20.0 tree even when no version is named; takes priority over generic odoo-* skills (17-19 advice such as publicWidget, jQuery is wrong in 20). Website/portal JavaScript, snippet, Point of Sale customisation - Odoo 20 frontend outside the backend web client: website/portal JavaScript with the Interaction framework
  (registry public.interactions, dynamicContent, no publicWidget/jQuery), website snippets and html_builder
  options (builder-options registry + XML option templates), html_editor plugins, and Point of Sale
  (OWL plugins such as PosDataPlugin, PosStore patching, POS models, payment providers registry, receipts).
when_to_use: >-
  Editing website/portal static JS, snippets or builder options, extending the HTML editor, or customising the
  Point of Sale / self-order frontend in Odoo 20.
---

# Odoo 20 website, editor and Point of Sale

## Workflow

1. Find the extension point: `odoo_js(registry="public.interactions")`, `odoo_js(registry="builder-options")`,
   `odoo_js(js_class="PosStore")`, `odoo_js(patches_of="PosStore")`, `odoo_assets("web.assets_frontend")`.
2. Mirror a core implementation of the same kind (cite it), keep classes `o_<module>_` prefixed.
3. `odoo_validate`; then check behaviour in a browser with `odoo_server` (website/POS need the module
   installed on the database) and a tour (`odoo20:testing`).

## Odoo 20 rules

- Public JS = `class X extends Interaction` (`@web/public/interaction`) registered in
  `registry.category("public.interactions")`; declarative `dynamicContent` (`t-on-*`, `t-att-*`, `t-out`);
  the `.withTarget` suffix is gone - read `ev.currentTarget`. jQuery and `publicWidget` do not exist.
- html_builder options: `registry.category("builder-options")` + XML option templates (e.g.
  `website.BuilderOptions` hooks); the editor `Plugin` (`@html_editor/plugin`) is not OWL's `Plugin`;
  dispatch with `trigger`/`delegateTo`/`processThrough` and `*_handlers`/`*_overrides`/`*_processors` names.
- POS services became plugins (PosDataPlugin, PosRouterPlugin, PosTicketPrinterPlugin, ...); `PosStore` is
  still extended with `patch(PosStore.prototype, { async setup() { await super.setup(...arguments); ... } })`;
  payment terminals register in `registry.category("pos_payment_providers")`; receipts are server QWeb.

## References

- [interactions.md](references/interactions.md) - Interaction API, lifecycle, helpers, registries, example
- [website-builder.md](references/website-builder.md) - snippets, builder options, builder plugins
- [html-editor.md](references/html-editor.md) - html_editor plugin system and Html fields
- [pos.md](references/pos.md) - POS architecture, plugins, models, patching, payments, receipts, self-order
