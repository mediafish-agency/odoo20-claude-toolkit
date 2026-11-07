# OWL 2 (Odoo 19) to OWL 3 (Odoo 20)

Mapping of every OWL 2 / Odoo 19 frontend habit to its Odoo 20 replacement, what the compatibility
layer really provides, what Odoo's `owl3-migration` upgrade_code script does (and where it is stale),
and a checklist for porting an addon. Writing new code: read [owl3-core.md](owl3-core.md) instead.

## Contents

- [Mapping table](#mapping-table)
- [Removed or moved web modules](#removed-or-moved-web-modules)
- [What the compatibility layer provides](#what-the-compatibility-layer-provides)
- [The owl3-migration script](#the-owl3-migration-script)
- [Migration checklist](#migration-checklist)

## Mapping table

| OWL 2 / Odoo 19 | Odoo 20 | Notes / source (short paths are under `addons/web/static/src/`) |
|---|---|---|
| `static props = { a: String }` | `props = useProps({ a: t.string() })` | static props throw (JS001); `owl3_compatibility_layer.js` |
| `static defaultProps = { a: 1 }` | `a: t.number().optional(1)` | function defaults are factories: `.optional(() => [])` |
| `{ type: String, optional: true }` | `t.string().optional()` | `owl.d.ts` |
| `{ type: Array, element: Number }` | `t.array(t.number())` | |
| `{ type: Object, shape: {...} }` | `t.object({...})` (loose) / `t.strictObject({...})` | |
| `[String, Boolean]` | `t.or([t.string(), t.boolean()])` | |
| `{ validate: fn }` | `t.customValidator(type, fn, "msg")` | |
| `"*"` / `{ "*": true }` | `t.any()` or `useProps()` without schema | `views/fields/field.js` uses `useProps()` |
| `{ value: "x" }` / enum | `t.literal("x")` / `t.selection([...])` | |
| `Component` constructor class as prop | `t.component()` or `t.constructor(Cls)` | |
| `useState(obj)` | `proxy(obj)` | JS002 |
| `reactive(obj)` | `proxy(obj)` | |
| `reactive(obj, callback)` | `proxy(obj)` + `effect(() => ...)` (or `useEffect` in a component) | script leaves 2-arg calls untouched |
| `useRef("x")` + `t-ref="x"` | `x = signal.ref()` + `t-ref="this.x"`, read `this.x()` | `core/checkbox/checkbox.js` |
| `ref.el` | `ref()` | |
| `useExternalListener(t, ev, fn, opts)` | `useListener(t, ev, fn, opts)` (handler not bound) | |
| `useEffect(fn, () => [deps])` | `useEffect(fn)` auto-tracks; or `useOnChange(() => [deps], cb)`; or `useLayoutEffect(fn, () => [deps])` from `@web/owl2/utils` | JS004; ESLint rule in `addons/web/tooling/_eslintrc.json` |
| `useEffect` callback parameters `(a, b) =>` | read signals inside: callback gets no arguments | ESLint rule |
| `onRendered(fn)` | no equivalent: `onMounted`/`onPatched`, or update where the data changes | `views/form/form_controller.js` |
| `onWillRender(fn)` | `onWillRender` from `@web/owl2/utils` (compat), better a `computed` | |
| `useEnv()` | `this.env`, or `useEnv` from `@web/owl2/utils` | |
| `useSubEnv(ext)` | `useSubEnv` from `@web/owl2/utils` | also replaces the caller's `this.env` |
| `useChildSubEnv(ext)` | `useSubEnv` from `@web/owl2/utils`, or `providePlugins([P])` | `core/dropdown/_behaviours/dropdown_nesting.js` |
| `useComponent()` | `useScope().component` | compat keeps `useComponent` on `@odoo/owl` "for spreadsheet" |
| `status(this) === "destroyed"` | `this.scope = useScope()` then `this.scope.isDestroyed()` / `this.scope.status === STATUS.DESTROYED` | compat `status()` is `@deprecated` |
| `this.render(deep)` | reactivity; else `render(this, deep)` from `@web/owl2/utils` or `useScope().render(deep)` | Component has no `render` method |
| `validate(obj, schema)` | `assertType(value, t...)` / `validateType` | `@odoo/owl` exports |
| `loadFile` | removed; templates come from asset bundles | |
| `t-esc` | `t-out` | warns (OWL001) |
| `t-raw` | `t-out` + `markup(...)` | OWL002 |
| `t-slot="name"` | `t-call-slot="name"` | OWL003 |
| `t-portal="'body'"` | `<Portal target="'body'">` (`static components = { Portal }`) or `t-custom-portal="'body'"` | OWL004 |
| `t-model="state.x"` | `t-model.proxy="this.state.x"` (proxy) or `t-model="this.sig"` (signal) | owl.js parser |
| `props.x`, `state.y`, `onClick` in templates | `this.props.x`, `this.state.y`, `this.onClick` | OWL005 |
| `<t t-call="tmpl"><t t-set="a" t-value="1"/></t>` | `<t t-call="tmpl" a="1"/>` (`a.translate="Text"` for strings) | body `t-set` is invisible to the callee |
| `useChildRef()` / `useForwardRefToParent("x")` | parent passes a signal: child `x = useProps.static("x", t.signal(t.ref()).optional(() => signal.ref()))` + `t-ref="this.x"` | JS013; `core/dialog/dialog.js` |
| `useRefListener(ref, ...)` | `useListener(refSignal, "event", fn)` | JS013 |
| `useAutofocus({ refName })` | `useAutofocus({ ref: this.inputRef })` | `core/utils/hooks.js` |
| `useSpellCheck({ refName })` | `useSpellCheck({ ref })` | |
| `env.debug` | `usePlugin(DebugModePlugin).isActive()` / `odoo.debug` | throws (JS008) |
| `env.isSmall` | `useService("ui").isSmall` (boolean) / `usePlugin(UIPlugin).isSmall()` (signal) | throws (JS008) |
| `useService("x")` | still works through the legacy bridge; native: `usePlugin(XPlugin)` | see [plugins-services.md](plugins-services.md) |
| `class X extends Reactive` (`@web/core/utils/reactive`) | `proxy(...)` directly (`Reactive` is `@deprecated`) | `core/utils/reactive.js` |
| effects registry fn `(env, params)` | `(params)`, runs in a scope (use `useService` inside) | `core/effects/effect_plugin.js` |
| `command_provider` `provide(env, options)` | `provide(options)` | `core/commands/default_providers.js` |
| `web_tour.tours` `wait_for` key | removed: schema is strict `{ steps, url }` | `addons/web_tour/static/src/tour_plugin.js` |
| field keys `kanban.*` | `card.*` | JS009 |

Source: addons/web/static/lib/owl/owl.js, addons/web/static/lib/owl/owl.d.ts,
addons/web/static/src/owl2/*.js, addons/web/static/src/core/utils/hooks.js, odoo/upgrade_code/owl3-migration.py

## Removed or moved web modules

v19 `*_service.js` modules became `*_plugin.js`; importing an old path stops the bundle with "The
following modules are needed by other modules but have not been defined". Check any path and its exports with `odoo_js(module_path="@web/core/orm_plugin")` before writing it.

| v19 import | v20 import (exports) |
|---|---|
| `@web/core/orm_service` | `@web/core/orm_plugin` (`ORM`, `x2ManyCommands`, `UPDATE_METHODS`) |
| `@web/webclient/actions/action_service` | `@web/webclient/actions/action_plugin` (`ActionPlugin`, `actionService`, `standardActionServiceProps`) |
| `@web/core/ui/ui_service` | `@web/core/ui/ui_plugin` (`UIPlugin`, `uiService`, `useActiveElement`) |
| `@web/core/dialog/dialog_service` | `@web/core/dialog/dialog_plugin` (`DialogPlugin`, `dialogService`) |
| `@web/core/notifications/notification_service` | `@web/core/notifications/notification_plugin` (`NotificationPlugin`) |
| `@web/core/effects/effect_service` | `@web/core/effects/effect_plugin` (`EffectPlugin`) |
| `@web/core/popover/popover_service` | `@web/core/popover/popover_plugin` (`PopoverPlugin`) |
| `@web/core/overlay/overlay_service` | `@web/core/overlay/overlay_plugin` (`OverlayPlugin`) |
| `@web/core/hotkeys/hotkey_service` | `@web/core/hotkeys/hotkey_plugin` (`HotkeyPlugin`) |
| `@web/core/l10n/localization_service` | `@web/core/l10n/localization_plugin` (`LocalizationPlugin`) |
| `@web/core/browser/title_service` | `@web/core/browser/title_plugin` (`TitlePlugin`) |
| `@web/webclient/currency_service` | `@web/webclient/currency_plugin` (`CurrencyPlugin`) |
| `@web/core/utils/sortable_service` | `@web/core/utils/sortable_plugin` (`SortablePlugin`) |
| `@web/core/bottom_sheet/bottom_sheet_service` | `@web/core/bottom_sheet/bottom_sheet_plugin` (`BottomSheetPlugin`) |
| `@web/core/emoji_picker/frequent_emoji_service` | `@web/core/emoji_picker/frequent_emoji_plugin` (`FrequentEmojiPlugin`) |
| `@web/legacy/*`, `publicWidget`, jQuery | removed: Interactions (JS005, JS006) |
| `@web_tour/js/*` | `@web_tour/*` (JS011) |

Source: `ls addons/web/static/src/core` in both trees (an Odoo 19.0 checkout vs v20)

## What the compatibility layer provides

Bundles load `web/static/lib/owl/owl.js`, then `web/static/src/owl2/owl3_compatibility_layer.js`,
then `web/static/src/owl2/utils.js`, then `lib/owl/odoo_module.js` (defines `@odoo/owl`). A custom
bundle that ships owl.js without the two owl2 files breaks (MAN003, see
[assets.md](assets.md#custom-bundles-and-the-owl-3-compatibility-layer)).

Patched onto the `@odoo/owl` object:

| Name | Behaviour |
|---|---|
| `Component` | subclass: throws if `static props`/`static defaultProps` exist; sets `this.env = useEnv()` |
| `App`, `mount` | add the internal `EnvPlugin`, the `portal` custom directive and the `Portal` global; `createRoot(C, { env })` |
| `useEnv`, `useSubEnv` | env stored in the `EnvPlugin` (`static id = "__ENV__"`) |
| `useLayoutEffect(fn, deps)` | OWL 2 `useEffect` semantics (mounted/patched, deps compared) |
| `onWillRender(cb)` | wraps the render function |
| `status(component)` | `"new" \| "mounted" \| "destroyed"`, `@deprecated` |
| `useComponent()` | `useScope().component` |
| `config`, `plugin`, `props` | aliases of `useConfig`, `usePlugin`, `useProps` |
| `t-custom-portal` directive | OWL 2 style portal |

`@web/owl2/utils` exports exactly: `render`, `onWillRender`, `useLayoutEffect`, `useEnv`,
`useSubEnv`. Nothing else (no `useRef`, `useState`, `useExternalListener`, `useChildSubEnv`,
`useComponent`, `onRendered`). The layer's header comment mentions `t-custom-model`, but no such
directive is registered.

Source: addons/web/static/src/owl2/owl3_compatibility_layer.js, addons/web/static/src/owl2/utils.js,
addons/web/static/lib/owl/odoo_module.js, addons/web/__manifest__.py

## The owl3-migration script

`odoo/upgrade_code/owl3-migration.py` is not version-prefixed, so `--from 19.0` does not run it:
call it by name. It rewrites every `.js`/`.xml` under `static/` of every addon on the addons path
(core included), so restrict it with `--glob` and prefer a dry run:

```bash
./odoo-bin upgrade_code --script owl3-migration --addons-path /path/to/custom --glob 'my_module/**/*' --dry-run
```

At work time prefer the MCP tool: `odoo_upgrade_code(path="/path/to/my_module", script="owl3-migration")`
runs it on a sandbox copy of your addon only and returns a diff (`apply=true` writes; without
`script`, it runs the 19.x -> 20.0 scripts plus owl3-migration).

| # | Step | Result | Status |
|---|---|---|---|
| 1 | `useEffect` -> `useLayoutEffect` from `@web/owl2/utils` (all of them) | OK, but keeps OWL 2 semantics; convert back to native `useEffect` later | valid |
| 2 | `onWillRender` -> `@web/owl2/utils` | OK | valid |
| 3 | `onRendered` -> `@web/owl2/utils` | utils does not export it: the import is `undefined` (TypeError when called) | **stale** |
| 4 | `useComponent` -> `@web/owl2/utils` | not exported there (only on `@odoo/owl`) | **stale** |
| 5-6 | `useEnv`, `useSubEnv` -> `@web/owl2/utils` | OK | valid |
| 7 | `useChildSubEnv` -> `@web/owl2/utils` | not exported: rename to `useSubEnv` | **stale** |
| 8 | `useRef` -> `@web/owl2/utils` | not exported: convert to `signal.ref()` | **stale** |
| 9-10 | `useState` -> `proxy` | OK | valid |
| 11-12 | `reactive(x)` -> `proxy(x)` (one-argument calls only) | 2-argument calls stay and break | partial |
| 13 | `useExternalListener` -> `@web/owl2/utils` | not exported: convert to `useListener` | **stale** |
| 14 | `t-portal` -> `t-custom-portal` | works (compat) | valid |
| 15 | `t-esc` -> `t-out` (also `<attribute name="t-esc">`) | OK | valid |
| 16 | `t-ref` -> `t-custom-ref` | no such directive: `Custom directive "ref" is not defined` | **stale** |
| 17 | `t-model` -> `t-custom-model` | no such directive | **stale** |
| 18 | add `this.` in XML templates of components (skips templates listed in `EXCLUDED_TEMPLATES`, uses whitelists for dynamic `t-call`) | heuristic: review dynamic `t-call` / `t-set` | valid, review |
| 19 | add `this.` inside ``xml`...` `` literals in JS (skips literals containing `${`) | | valid, review |
| 20 | `t-slot` -> `t-call-slot` | OK | valid |
| 21 | parametric `t-call` (body `t-set` -> attributes) | OK | valid |
| 22 | `useService("x")` -> `usePlugin(XPlugin)` per `SERVICES_MAPPING` | see below | partly stale |

`SERVICES_MAPPING` problems:

- `action` maps to `ActionManagerPlugin`; the class is `ActionPlugin` (`@web/webclient/actions/action_plugin`).
- `sortable` maps to `@web/core/util/sortable_plugin`; the path is `@web/core/utils/sortable_plugin`.
- `color_scheme`, `mobile`, `signInfo` point to enterprise addons (not in this tree, unverified).
- Plugin APIs differ from the service wrappers: `useService("ui").isSmall` is a boolean getter but
  `usePlugin(UIPlugin).isSmall` is a signal (always truthy unless called); same for `activeElement`,
  `isBlocked`, `size`. `useService("title").current`/`setCounters`/`getParts` do not exist on
  `TitlePlugin`. Review every converted call site.
- Not handled at all: `static props`/`defaultProps`, `env.debug`/`env.isSmall`, `useChildRef`,
  removed module paths, effects/command provider signatures.

Source: odoo/upgrade_code/owl3-migration.py (upgrade(), SERVICES_MAPPING), odoo/cli/upgrade_code.py,
addons/web/static/src/core/ui/ui_plugin.js, addons/web/static/src/core/browser/title_plugin.js

## Migration checklist

1. Inventory: `odoo_grep` for `static props`, `defaultProps`, `useState`, `useRef`, `useEffect(`,
   `t-esc`, `t-slot`, `t-portal`, `t-ref=`, `t-model`, `env.debug`, `env.isSmall`, `_service"`.
2. Run `odoo_upgrade_code(path=..., script="owl3-migration")`, review the diff, apply.
3. Fix the stale outputs: imports of `onRendered`/`useComponent`/`useChildSubEnv`/`useRef`/
   `useExternalListener` from `@web/owl2/utils`; `t-custom-ref`/`t-custom-model`;
   `ActionManagerPlugin`; `util/sortable_plugin`; plugin vs service API (`isSmall()`).
4. Convert every `static props`/`defaultProps` to `props = useProps({...})` with `t.*` (JS001).
5. Fix module paths (table above) and registry signatures (effects, command providers).
6. Replace `env.debug`/`env.isSmall`, `useChildRef`/`useForwardRefToParent`.
7. Optional cleanup: `useLayoutEffect` -> native `useEffect`/`useOnChange`, `t-custom-portal` ->
   `<Portal>`, `useSubEnv` -> plugins.
8. `odoo_validate` the addon (OWL001-006, JS001-017, MAN003).
9. Install and run Hoot tests and tours with `odoo_test` (test mode turns on prop validation), and
   open the UI with `?debug=assets` to catch "Invalid component props" errors.
