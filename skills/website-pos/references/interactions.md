# Public / website JavaScript: Interactions (Odoo 20)

Every piece of JS that runs on public pages (website, portal, shop, login) is an **Interaction**: a small
class bound to the DOM elements matching a CSS selector, started by the `public.interactions` service.
publicWidget, `web/static/src/legacy/` and jQuery do not exist in Odoo 20. Read this before writing any
`static/src/interactions/*.js` or snippet JS.

## Contents
- [Minimal interaction](#minimal-interaction)
- [Class API](#class-api)
- [dynamicContent directives](#dynamiccontent-directives)
- [Lifecycle](#lifecycle)
- [Helpers](#helpers)
- [Services, plugins and RPC](#services-plugins-and-rpc)
- [Owl components on public pages](#owl-components-on-public-pages)
- [Edit and preview mode](#edit-and-preview-mode)
- [Assets and tests](#assets-and-tests)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## Minimal interaction

```javascript
import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class ShowMore extends Interaction {
    static selector = ".o_my_show_more";        // static, never on the instance
    dynamicContent = {                           // instance field, never static
        ".o_my_toggle": { "t-on-click.prevent": this.onToggle },
        ".o_my_body": { "t-att-class": () => ({ "d-none": !this.open }) },
        ".o_my_label": { "t-out": () => (this.open ? "Less" : "More") },
    };

    setup() {
        this.open = this.el.dataset.open === "1";
    }

    onToggle(ev) {
        // `this` is the interaction; read the clicked node from ev.currentTarget
        this.open = !this.open;                  // dynamic content re-applied after the handler
    }
}

registry.category("public.interactions").add("my_module.show_more", ShowMore);
```

- Key convention: `"<module>.<name>"`. Handlers in `dynamicContent` are called with `this` bound to the
  interaction, so pass `this.onToggle` directly (no `.bind`).
- After every `t-on-*` handler (sync or async) the framework calls `updateContent()`: just mutate
  instance fields; there is no `proxy()`/render loop here.
- The service throws if `selector` is empty or if `dynamicContent` is declared `static`.

Source: addons/web/static/src/public/interaction.js, addons/web/static/src/public/interaction_service.js,
addons/website/static/src/interactions/full_screen_height.js

## Class API

| Member | Kind | Meaning |
|---|---|---|
| `static selector` | string | Required. One instance per matching element (the root itself if it matches). |
| `static selectorHas` | string or string[] | Keep only targets containing a match (array = all must match). Use instead of `:has()`. |
| `static selectorNotHas` | string or string[] | Drop targets containing a match (`:not(:has())` equivalent). |
| `static INITIAL_VALUE` | symbol | Return it from a `t-att-*`/`t-out` getter to restore the original value. |
| `dynamicSelectors` | object of `() => el/els/null` | Named selectors usable as `dynamicContent` keys. Defaults: `_root`, `_body`, `_window`, `_document`. Extend with `{ ...this.dynamicSelectors, _x: () => ... }`. A falsy return disables the entry. |
| `dynamicContent` | object | `{ selector: { directive: value } }` (see next section). |
| `el`, `env`, `services` | fields | Root element, env, `env.services` (legacy services bridge). |
| `isReady`, `isDestroyed` | getters | Lifecycle flags. |

Never define `constructor`: use `setup()`.

```javascript
// addons/website/static/src/interactions/post_link.js
dynamicSelectors = {
    ...this.dynamicSelectors,
    _select: () => this.el.matches("select") && this.el,
    _nonSelect: () => !this.el.matches("select") && this.el,
};
dynamicContent = {
    _root: { "t-att-class": () => ({ o_post_link_js_loaded: true }) },
    _nonSelect: { "t-on-click.prevent": this.onClickPost },
    _select: { "t-on-change.prevent": this.onClickPost },
};
```

Source: addons/web/static/src/public/interaction.js, addons/web/static/src/public/interaction_service.js,
addons/website/static/src/interactions/post_link.js

## dynamicContent directives

This is not Owl: values are JS functions, not template expressions.

| Directive | Value | Notes |
|---|---|---|
| `t-on-<event>[.suffix...]` | handler `(ev) => ...` or method | Suffixes, combinable: `.prevent`, `.stop`, `.capture`, `.once`, `.noUpdate` (skip the implicit `updateContent()`). Event names may contain dots (`t-on-shown.bs.modal`). |
| `t-att-class` | `() => ({ "cls other": bool })` | Falsy removes the class. Must return an object. |
| `t-att-style` | `() => ({ prop: value })` | `undefined` removes; `"10px !important"` sets priority. Must return an object. |
| `t-att-<attr>` | `(el) => value` | `false`/`undefined`/`null` remove the attribute, `true` sets `attr="attr"`, `""`/`0` are applied as is. |
| `t-out` | `(el) => value` | Text content; a `markup()` value sets innerHTML and (re)starts interactions inside it. |
| `t-component` | `Component` or `(el) => [Component, props]` | Mounts an Owl component in each matched node (cleaned on destroy). |

- Getters receive the matched node as argument, so one entry can serve several nodes.
- `.withTarget` no longer exists (validator JS014): use `ev.currentTarget`.
- Throttled/debounced handlers: `"t-on-scroll": this.throttled(this.onScroll)`,
  `"t-on-resize.noUpdate": this.debounced(this.updateContent, 250)`.

```javascript
// addons/website_links/static/src/interactions/website_links.js
"#campaign-select-wrapper": {
    "t-component": () => [WebsiteLinksTagsWrapper, { placeholder: _t("e.g. June Sale"), model: "utm.campaign" }],
},
```

Source: addons/web/static/src/public/colibri.js, addons/website_links/static/src/interactions/website_links.js,
addons/website/static/src/snippets/s_floating_blocks/floating_blocks.js

## Lifecycle

| Step | Method | Notes |
|---|---|---|
| 1 | `setup()` | Sync. Element, env and services ready. Runs inside an Owl `Scope`, so `usePlugin(...)` works here. Do not attach listeners with `addListener` yet. |
| 2 | `async willStart()` | Awaited (with any scope `willStart`) before dynamic content is applied. Wrap promises in `this.waitFor(...)`. |
| 3 | dynamic content applied | `t-on-*` listeners attached, `t-att-*`/`t-out` evaluated. |
| 4 | `start()` | Like Owl `mounted`. `addListener`, `insert`, `renderAt` are safe. |
| 5 | `destroy()` | Called when the element leaves the page or the website enters edit mode. Cleanups registered with `registerCleanup` run first (reverse order); `t-att-*`/`t-out` are restored to initial values. No need to call `super.destroy()` unless extending a concrete class. |

Interactions are destroyed and restarted when the builder switches to edit mode: every side effect must
be undone (use the helpers below, which auto-clean).

Source: addons/web/static/src/public/interaction.js, addons/web/static/src/public/colibri.js

## Helpers

| Helper | Use |
|---|---|
| `waitFor(promise)` | Resolves only if not destroyed, then calls `updateContent()`. Use around every `await` in handlers/willStart. |
| `protectSyncAfterAsync(fn)` | Wrap DOM-mutating code that runs after an `await` (edit mode history protection). |
| `waitForTimeout(fn, delay)` | Safe `setTimeout` (skipped if destroyed). |
| `waitForAnimationFrame(fn)` | Safe `requestAnimationFrame`. |
| `setSafeInterval(fn, delay)` | `setInterval` cleared on destroy. New in v20. |
| `debounced(fn, delay, options)` | Debounced fn, cancelled on destroy; result has `.cancel()`. |
| `throttled(fn)` | Animation-frame throttle, cancelled on destroy. |
| `locked(fn, useLoadingAnimation = false)` | Prevents re-entry until the promise settles; `true` adds a button spinner after 400ms. |
| `addListener(target(s), event, fn, options)` | Listener auto-removed on destroy, triggers `updateContent`; accepts the same suffixes; returns a remover. Only after start. |
| `insert(el, locationEl = this.el, position = "beforeend", removeOnClean = true)` | Inserts, starts interactions inside, removes on destroy. |
| `removeChildren(el, insertBackOnClean = true)` | Stops interactions in children and removes them (restored on destroy). |
| `renderAt(template, context, locationEl, position, callback, removeOnClean)` | Renders a QWeb template (`renderToFragment`), inserts each root, returns the elements. |
| `registerCleanup(fn)` | Run `fn` on destroy. |
| `mountComponent(el, Component, props = null, position = "beforeend")` | Mounts an Owl component; returns a destroy function. |
| `updateContent()` | Re-apply dynamic content manually (rarely needed). |

```javascript
// addons/website_sale/static/src/interactions/add_to_cart.js
_root: { "t-on-click.prevent": this.locked(this.addToCart, true) },

// addons/website/static/src/snippets/s_countdown/countdown.js
this.waitForTimeout(() => {
    this.render();
    this.setInterval = this.setSafeInterval(this.render, 1000);
}, 1000 - (Date.now() % 1000));
```

Templates rendered by `renderAt`/`renderToString` get the context both as plain variables and as
`this` (`ctx.this = context` in `render.js`), so `t-out="this.agentName"` and `t-out="agentName"` both
work there; `website.s_whatsapp.chatbox` uses the `this.` form.

Source: addons/web/static/src/public/interaction.js, addons/web/static/src/core/utils/render.js,
addons/website/static/src/snippets/s_whatsapp/whatsapp.js, addons/website/static/src/snippets/s_whatsapp/whatsapp_chatbox.xml

## Services, plugins and RPC

- `this.services.<name>` is `env.services`: legacy services (`orm`, `dialog`, `notification`, `ui`,
  `website`, `website_cookies`, `public.interactions`, ...). In core interactions `this.services.orm` is
  the most used (`call`, `searchRead`, `read`, `write`, `create`, `unlink`); `orm` is still registered as
  a legacy service in `orm_plugin.js`. Details: [plugins-services.md](../../owl/references/plugins-services.md).
- Plain HTTP JSON-RPC: `import { rpc } from "@web/core/network/rpc"`; `await this.waitFor(rpc("/my/route", params))`.
- Lazy libraries: `import { loadBundle } from "@web/core/assets"`; `await loadBundle("web.chartjs_lib")` in
  `willStart` (addons/website/static/src/snippets/s_chart/chart.js).
- Owl plugins work in `setup()` because colibri runs it in an interaction scope:

```javascript
// addons/website/static/src/interactions/image_popup.js
import { usePlugin } from "@odoo/owl";
import { BootstrapInstance } from "@web/core/utils/bootstrap_plugin";

setup() {
    this.bootstrap = usePlugin(BootstrapInstance);
}
onClickImg(ev) {
    const modal = this.bootstrap.getOrCreateInstance(Modal, this.modalEl, { keyboard: true });
    this.registerCleanup(() => this.bootstrap.disposeBootstrapInstance(modal));
    modal.show();
}
```

Use `BootstrapInstance` (ref-counted, auto-disposed with the scope) instead of calling
`window.Modal.getOrCreateInstance(...)` directly, which was the v19 pattern.

Source: addons/web/static/src/public/interaction.js, addons/web/static/src/core/orm_plugin.js:413,
addons/web/static/src/core/utils/bootstrap_plugin.js, addons/web/static/src/core/network/rpc.js:93,
addons/website/static/src/interactions/image_popup.js

## Owl components on public pages

Three ways, from simplest:

1. `t-component` in `dynamicContent` or `this.mountComponent(el, C, props)` from an interaction.
2. Server markup `<owl-component name="key" t-att-props="json.dumps(props)"/>` + register the component in
   `registry.category("public_components")`. The built-in `PublicComponentInteraction`
   (selector `owl-component[name]`) mounts it with the JSON props.
3. Register a `Component` subclass with a `static selector` directly in `public.interactions`: the service
   mounts it in each match (see `Counter` in addons/website/static/src/interactions/_example.js).

```javascript
// addons/portal/static/src/signature_form/signature_form.js
export class SignatureForm extends Component {
    static template = "portal.SignatureForm";
    props = useProps({ callUrl: t.string(), defaultName: t.string().optional() });
    rootRef = signal.ref();
}
registry.category("public_components").add("portal.signature_form", SignatureForm);
```

```xml
<!-- addons/portal/views/portal_templates.xml -->
<owl-component name="portal.signature_form" t-att-props="json.dumps(signature_form_props)"/>
```

Components follow OWL 3 rules (`useProps`, `proxy`, `this.` in templates): see
[owl3-core.md](../../owl/references/owl3-core.md). In edit mode `<owl-component>` is rendered inert
(`pointer-events: none`) unless also registered in `public_components.edit`.

Source: addons/web/static/src/public/public_component_interaction.js,
addons/website/static/src/core/component_interaction_edit.js, addons/portal/static/src/signature_form/signature_form.js

## Edit and preview mode

When the website builder opens, interactions are stopped and restarted from two other registries. Only
interactions registered there run in edit/preview mode; entries are `{ Interaction, mixin?, isAbstract? }`
where `mixin` is `(I) => class extends I {...}`.

| Registry | When | Example |
|---|---|---|
| `public.interactions` | normal page | addons/website/static/src/interactions/full_screen_height.js |
| `public.interactions.edit` | builder edit mode | addons/website/static/src/interactions/full_screen_height.edit.js |
| `public.interactions.preview` | snippet previews in the builder | addons/website/static/src/interactions/text_highlights.preview.js |
| `public_components` / `public_components.edit` | `<owl-component>` | addons/website/static/src/components/user_switch.js |

```javascript
// addons/website/static/src/interactions/full_screen_height.edit.js
const FullScreenHeightEdit = (I) =>
    class extends I {
        shouldStop() {
            return true; // force restart on refresh
        }
    };
registry.category("public.interactions.edit").add("website.full_screen_height", {
    Interaction: FullScreenHeight,
    mixin: FullScreenHeightEdit,
});
```

- Mixins registered for parent classes are applied too, from the top-most class down
  (`buildEditableInteractions`); a parent without an entry only logs `No mixin defined for: X`. An entry
  with `isAbstract: true` contributes its mixin without being started itself.
- In edit mode `this.services.website_edit` exposes `callShared(pluginId, method, ...args)` to reach
  builder plugins (addons/website/static/src/interactions/dropdown/mega_menu_dropdown.edit.js).
- Listeners are "stealth" in edit mode (not recorded in undo history); add `.keepInHistory` to an event
  name to record it.

Source: addons/website/static/src/core/website_edit_service.js, addons/website/static/src/core/component_interaction_edit.js

## Assets and tests

```python
'assets': {
    'web.assets_frontend': [
        'my_module/static/src/interactions/**/*',
        ('remove', 'my_module/static/src/interactions/**/*.edit.js'),
    ],
    'website.assets_inside_builder_iframe': [
        'my_module/static/src/interactions/**/*.edit.js',
    ],
    'web.assets_unit_tests': ['my_module/static/tests/interactions/**/*'],
    'web.assets_unit_tests_setup': ['my_module/static/src/interactions/**/*'],
},
```

That split is how `website`, `website_sale` and `website_event` ship theirs. Check the final bundle content
with `odoo_assets`; see [assets.md](../../owl/references/assets.md).

Hoot test helpers (`@web/../tests/public/helpers`): `startInteraction(I, html, options)`,
`startInteractions(html, { waitForStart, editMode, translateMode })`,
`setupInteractionWhiteList("my_module.show_more")`; website edit mode: `switchToEditMode(core)` from
`@website/../tests/helpers`.

Source: addons/website/__manifest__.py:286, addons/website_sale/__manifest__.py, addons/website_event/__manifest__.py,
addons/web/static/tests/public/helpers.js, addons/website/static/tests/helpers.js

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `publicWidget.registry.X = publicWidget.Widget.extend({...})` | `class X extends Interaction` + `registry.category("public.interactions").add(...)` (JS005) | addons/web/static/src/public/interaction.js |
| `@web/legacy/js/public/...` imports | removed directory (JS005) | addons/web/static/src |
| `$(...)`, `$.ajax`, `.modal("show")` | DOM APIs, `rpc()`, `BootstrapInstance` plugin (JS006, JS017) | addons/web/__manifest__.py |
| `"t-on-click.withTarget": (ev, currentTarget) => ...` | `.withTarget` removed; use `ev.currentTarget` (JS014) | addons/web/static/src/public/colibri.js |
| `setInterval` + manual `registerCleanup` | `this.setSafeInterval(fn, delay)` | addons/web/static/src/public/interaction.js |
| `window.Modal.getOrCreateInstance(el)` in interactions | `usePlugin(BootstrapInstance).getOrCreateInstance(Modal, el)` | addons/web/static/src/core/utils/bootstrap_plugin.js |
| Component props `static props = {...}` in `public_components` | `props = useProps({...})` (JS001) | addons/portal/static/src/signature_form/signature_form.js |
| `useState` in public components | `proxy()` (JS002) | addons/website/static/src/interactions/_example.js |

Run `odoo_validate` on the addon to flag the patterns above; `odoo_grep "extends Interaction"` finds
more core examples (about 240 in v20).
