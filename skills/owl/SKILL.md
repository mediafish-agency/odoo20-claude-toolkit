---
name: owl
description: >-
  Default for any Odoo work in this Odoo 20.0 tree even when no version is named; takes priority over generic odoo-* skills (17-19 advice such as static props, useState, useRef, t-esc, jQuery is wrong in 20). Custom widget, field widget, client action, systray, patch a component - Odoo 20 backend web client JavaScript: OWL 3 (3.0.0-alpha) with Odoo's compatibility layer - components with
  props = useProps({...}) and t.* validators, proxy()/signals/computed, templates with this., t-call-slot,
  signal refs; services as OWL Plugins (usePlugin) and the useService bridge; registries (fields, views,
  actions, systray, ...); custom field widgets and views; patch(); asset bundles; SCSS/dark mode; Material
  Symbols icons; TypeScript typings and ESLint tooling.
when_to_use: >-
  Editing static/src/**/*.js, static/src/**/*.xml (OWL templates) or *.scss for the Odoo 20 backend, adding a
  field widget/client action/systray item, patching an existing component, or porting OWL 2 code.
  Website/portal Interactions, snippets, builder options and Point of Sale: odoo20:website-pos.
---

# Odoo 20 web client (OWL 3)

Most OWL 2 knowledge is wrong in Odoo 20. Check every import against the source.

## Workflow

1. Find the code to extend: `odoo_js(js_class=...)`, `odoo_js(template=...)`, `odoo_js(registry="fields")`,
   `odoo_js(patches_of=...)`; confirm an export before importing it: `odoo_js(module_path="@web/...")`.
2. Copy the shape of a real v20 component of the same kind (field widgets in
   `addons/web/static/src/views/fields/`), follow Odoo's [web guidelines](../odoo-web-guidelines/SKILL.md).
3. Declare files in the right bundle (`web.assets_backend`; tests in `web.assets_unit_tests`).
4. `odoo_validate` (catches OWL 2 APIs, missing exports, Font Awesome); write a Hoot test
   (`odoo20:testing`); check in the browser with `odoo_server` (+ chrome-devtools MCP for console errors).

## Odoo 20 rules

- Props: `props = useProps({ value: t.string(), size: t.number().optional(10) })` - `static props` /
  `static defaultProps` **throw**. Field widgets spread `standardFieldProps`.
- State: `proxy({...})` (not `useState`/`reactive`), `signal()`, `computed()`; refs: `input = signal.ref()` with
  `t-ref="this.input"`, read `this.input()`.
- Templates: component members need `this.` (`t-if="this.props.readonly"`, `t-on-click="this.onClick"`);
  `t-call-slot` (not `t-slot`); `t-out` (not `t-esc`); `t-model.proxy` for proxy state.
- Effects: `useEffect(fn)` auto-tracks signals (no deps array - the arg is ignored); `useLayoutEffect(fn, deps)`
  from `@web/owl2/utils` reproduces the old behaviour; `useListener` replaces `useExternalListener`.
- Services: `usePlugin(ORM)` (`@web/core/orm_plugin`) or the legacy `useService("orm")` bridge;
  `env.debug`/`env.isSmall` throw (use DebugModePlugin / UI service).
- Registries: field widgets for kanban/calendar cards are `card.*` keys; validation uses `t.*` schemas.
- Files under `static/src` and `static/tests` are ES modules automatically (`@odoo-module` comment optional);
  import as `@addon/path`. No jQuery, no `publicWidget`, no QUnit.
- Icons: `<i class="oi" data-icon="name"/>`; check availability in [icons-mapping.md](references/icons-mapping.md).

## References

- [owl3-core.md](references/owl3-core.md) - components, props, signals/proxy, hooks, templates, a full example
- [owl2-to-owl3.md](references/owl2-to-owl3.md) - complete mapping table, compat layer, owl3-migration caveats
- [plugins-services.md](references/plugins-services.md) - Plugins, useService bridge, ORM/action APIs
- [registries.md](references/registries.md) - how registries work + key categories; [registry-index.md](references/registry-index.md) (generated)
- [fields-views-js.md](references/fields-views-js.md) - field widgets, view widgets, js_class, custom views, patch
- [assets.md](references/assets.md) - bundles, directives, module naming, lazy loading, the compat-layer gotcha
- [scss-theming.md](references/scss-theming.md) - variables, dark mode, CSS custom properties
- [icons.md](references/icons.md) - Material Symbols usage; [icons-mapping.md](references/icons-mapping.md) (generated FA -> Material)
- [tooling.md](references/tooling.md) - TypeScript typings, ESLint, debugging the web client
