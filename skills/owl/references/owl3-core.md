# OWL 3 components in Odoo 20

Odoo 20 ships OWL 3.0.0-alpha.50 plus an Odoo compatibility layer. Components declare props with
`useProps` + `t.*` validators, hold state in `proxy()` objects or signals, and their templates must
prefix every component member with `this.`. Read this before writing any `static/src/**/*.js|xml`
component. Migrating OWL 2 code: see [owl2-to-owl3.md](owl2-to-owl3.md). Look up a core template or
module with `odoo_js(template="web.CheckBox")` / `odoo_js(module_path="@web/core/utils/hooks")`.

## Contents

- [What you import from where](#what-you-import-from-where)
- [Component skeleton](#component-skeleton)
- [Props: useProps and t validators](#props-useprops-and-t-validators)
- [Reactivity: proxy, signal, computed, effect](#reactivity-proxy-signal-computed-effect)
- [Lifecycle and effect hooks](#lifecycle-and-effect-hooks)
- [Templates](#templates)
- [Env, plugins, services](#env-plugins-services)
- [Complete example](#complete-example)
- [Pitfalls](#pitfalls)

## What you import from where

| Need | Import |
|---|---|
| `Component`, `xml`, `useProps`, `t`, `proxy`, `signal`, `computed`, `effect`, `untrack`, `markup`, `markRaw`, `toRaw`, `useEffect`, `useOnChange`, `useListener`, `onWillStart`, `onMounted`, `onWillUpdateProps`, `onWillPatch`, `onPatched`, `onWillUnmount`, `onWillDestroy`, `onError`, `useScope`, `usePlugin`, `providePlugins`, `Plugin`, `Portal`, `ErrorBoundary`, `EventBus`, `assertType`, `shallowEqual`, `batched`, `STATUS` | `"@odoo/owl"` (native OWL 3) |
| `useLayoutEffect`, `useEnv`, `useSubEnv`, `onWillRender`, `render` | `"@web/owl2/utils"` (compat layer) |
| `useService`, `useBus`, `useAutofocus`, `useOwnedDialogs` | `"@web/core/utils/hooks"` |
| `registry` | `"@web/core/registry"` |
| `_t` | `"@web/core/l10n/translation"` |

`@odoo/owl` is the OWL global after Odoo's compat layer patched it: `Component` there throws on
`static props` and sets `this.env`. Also patched onto it (but prefer the right-hand side):
`status` -> `useScope().status`, `useComponent` -> `useScope().component`,
`useEnv`/`useSubEnv`/`onWillRender`/`useLayoutEffect` -> import from `@web/owl2/utils` (validator JS003).
Not exported at all: `useState`, `reactive`, `useRef`, `useExternalListener`, `useChildSubEnv`,
`onRendered`, `validate`, `loadFile` (validator JS002).

Source: addons/web/static/lib/owl/owl.js (export map), addons/web/static/lib/owl/odoo_module.js,
addons/web/static/src/owl2/owl3_compatibility_layer.js, addons/web/static/src/owl2/utils.js

## Component skeleton

```javascript
import { Component, signal, t, useProps } from "@odoo/owl";

export class CheckBox extends Component {
    static template = "web.CheckBox";      // still static
    static components = {};                // still static
    props = useProps({                     // NOT static props / static defaultProps (JS001: throws)
        value: t.boolean().optional(),
        onChange: t.function().optional(() => () => {}),
    });
    rootRef = signal.ref();                // used as t-ref="this.rootRef"

    setup() {
        // hooks here or in class field initializers
    }
}
```

- The constructor runs inside the component scope, so hooks may be called in class field
  initializers (`orm = usePlugin(ORM)`, `scope = useScope()`, `props = useProps(...)`) as well as
  in `setup()`. Fields initialize in declaration order, before `setup()`.
- A component has no `this.render()` and no `this.el`. Force a render with
  `render(this, deep)` from `@web/owl2/utils` (deprecated) or `useScope().render(deep)`; normally
  rely on reactivity.
- Subclassing: when the child redeclares `props = useProps(...)`, spread the parent's exported
  shape (`...charFieldProps`). See `addons/web_tour/static/src/widgets/tour_start.js`.

Source: addons/web/static/src/core/checkbox/checkbox.js, addons/web/static/src/webclient/navbar/navbar.js,
addons/web/static/lib/owl/owl.js (ComponentNode constructor)

## Props: useProps and t validators

`useProps(shape)` returns an object whose keys are getters backed by signals: reading
`this.props.x` inside a render, `computed` or `useEffect` subscribes to it. **Only declared keys
exist on the returned object**; an undeclared prop reads `undefined` even if the parent passed it.

| Call | Effect |
|---|---|
| `useProps({ a: t.string(), b: t.number().optional(0) })` | Declares, validates (dev mode only), applies defaults |
| `useProps(["a", "b"])` | Declares keys without types; dev mode still requires every listed key |
| `useProps()` | Exposes every prop passed by the parent, no validation (used by `Field`, `Widget`, hooks) |
| `useProps.static("key", type)` | Returns the plain value once (not a signal getter); in dev mode throws if the parent later passes a different value. Pattern for parent-owned refs: `modalRef = useProps.static("modalRef", t.signal(t.ref()).optional(() => signal.ref()))` |

Calling `useProps` again (from a hook or a `patch`) is allowed: it returns another view on the same
props, e.g. `this.extraProps = useProps({ reviewChatter: t.any().optional() })` in
`addons/portal_rating/static/src/chatter/portal/portal_chatter_patch.js`.

Validation (and `useConfig`/`static` checks) runs only when the app is in dev mode:
`odoo.debug || session.test_mode` (`addons/web/static/src/env.js`). Shapes are loose objects:
extra props pass.

### `t` builders (`import { t } from "@odoo/owl"`, alias `types`)

| Builder | Accepts |
|---|---|
| `t.any()` | anything |
| `t.boolean()`, `t.number()`, `t.string()` | typeof check |
| `t.array()`, `t.array(elemType)` | arrays (elements validated) |
| `t.object()` | any non-null, non-array object |
| `t.object({ k: type })` / `t.object(["k1", "k2"])` | object with those keys (loose: extra keys allowed); `.toShape()` returns the shape |
| `t.strictObject({...})` | same, unknown keys rejected |
| `t.record(valueType)` | object whose every value matches |
| `t.tuple([t1, t2])` | array of exact length |
| `t.or([t1, t2])` / `t.and([s1, s2])` | union / intersection (`and` merges shapes) |
| `t.literal(v)` / `t.selection(["a", "b"])` | exact value(s) |
| `t.function()` / `t.function([params], result)` | `typeof === "function"` (params are typing only) |
| `t.instanceOf(Cls)` | `instanceof` |
| `t.constructor(Cls)` | `Cls` or a subclass of it |
| `t.component()` | a `Component` subclass |
| `t.promise()` | a `Promise` |
| `t.signal()` / `t.signal(type)` | a signal or computed (reactive value) |
| `t.ref()` / `t.ref(HTMLInputElement)` | `null` or an element |
| `t.customValidator(type, (v) => bool, "msg")` | type plus predicate |

Every type has `.optional()` (`undefined` allowed, key may be omitted) and `.optional(default)`:
the default is used when the prop is `undefined`. **A function given as default is called as a
factory**: write `.optional(() => [])` for fresh arrays and `.optional(() => () => {})` for a
callback default; `.optional(myCallback)` would call `myCallback` to get the default.

Source: addons/web/static/lib/owl/owl.d.ts:150-305, addons/web/static/lib/owl/owl.js (makeProps,
staticProp, makeOptional), addons/web/static/src/core/dialog/dialog.js,
addons/web/static/src/search/search_bar/search_bar.js

## Reactivity: proxy, signal, computed, effect

| API | Use |
|---|---|
| `proxy(obj)` | Deep reactive object (`this.state = proxy({ items: [] })`); property reads inside a render/effect subscribe, writes notify. Replaces `useState`/`reactive`. |
| `signal(v)` | `s()` reads, `s.set(v)` writes (notifies if `!Object.is`; option `{ equals }`). Mutating the inner object does NOT notify: call `s.set(...)` or `signal.trigger(s)`. |
| `signal.Array([])`, `signal.Object({})`, `signal.Map()`, `signal.Set()` | Signal whose value is proxified one level: `s().push(x)` notifies. |
| `signal.ref()` | `Signal<HTMLElement \| null>` for `t-ref` (replaces `useRef`). Read with `this.inputRef()`. |
| `computed(() => expr, { set?, equals? })` | Cached derived value, recomputed lazily when a dependency changes. Prefer it over getters ([Avoid getters](../../odoo-web-guidelines/guidelines/javascript.md#avoid-getters)). |
| `effect(fn)` | Runs `fn` now and again (batched in a microtask) when what it read changes; returns a dispose function. Outside components only; in a component use `useEffect`. |
| `untrack(fn)` | Read without subscribing. |
| `markRaw(obj)` / `toRaw(p)` | Exclude an object from reactivity / get the raw target. |
| `asyncComputed(fetcher)` | Experimental, avoid in addons. |

A component re-renders when anything it read during its last render changes; there is no
`useState` subscription step.

Source: addons/web/static/lib/owl/owl.d.ts:460-600, addons/web/static/src/core/ui/ui_plugin.js,
addons/web/static/src/core/browser/title_plugin.js

## Lifecycle and effect hooks

| Hook | Notes |
|---|---|
| `onWillStart(async fn)` | Before first render; awaited. |
| `onWillUpdateProps(async (nextProps) => ...)` | Before props change; awaited. Often replaceable by `useOnChange`. |
| `onMounted`, `onWillPatch`, `onPatched`, `onWillUnmount` | DOM lifecycle, unchanged. |
| `onWillDestroy(fn)` | Also available in plugins. |
| `onError(fn)` | Catch errors of the subtree (or use `<ErrorBoundary>`). |
| `useEffect(fn)` (`@odoo/owl`) | Auto-tracking effect bound to the scope. Runs **immediately during setup** (refs are still `null`), then whenever a signal/proxy/prop it read changes. Return a cleanup. **No dependency argument** (JS004; ESLint rejects a second argument or callback parameters). |
| `useOnChange(() => [deps], (...deps) => cleanup?, { initialRun })` | Only the deps function is tracked (compared with `shallowEqual`); the callback is untracked. Use it when the callback reads or writes other reactive state. |
| `useListener(target, "event", handler, options)` | `target` is an `EventTarget` or a ref signal (re-attaches when the element changes). Handler is NOT bound: use an arrow. Replaces `useExternalListener`. |
| `useLayoutEffect(fn, () => [deps])` (`@web/owl2/utils`) | Compat: OWL 2 semantics, runs on mount and on patch when deps changed. Use when the DOM must be patched first. |
| `onWillRender(fn)` (`@web/owl2/utils`) | Compat only. |

An effect fires when its signals change, not after the patch they cause. When code must look at
the patched DOM, use `onMounted`/`onPatched` (see the comment in
`addons/web/static/src/views/form/form_controller.js`) or `useLayoutEffect`.

Source: addons/web/static/lib/owl/owl.d.ts:640-720, addons/web/static/src/owl2/owl3_compatibility_layer.js,
addons/web/tooling/_eslintrc.json, addons/web/static/src/core/pager/pager.js

## Templates

Template expressions are compiled against a context `{ this: component }`: a bare `props.x` is
`undefined`. **Write `this.` for every component member** (`this.props.x`, `this.state.y`,
`this.onClick`, `this.env.x`). Bare names are only template locals: `t-set`, `t-foreach`/`t-as`
(`item`, `item_index`, `item_first`...), slot scope variables, parametric `t-call` attributes.
Templates rendered with `renderToString`/`renderToElement` (`@web/core/utils/render`) accept both
`x` and `this.x`. Validator OWL005 flags `props.`/`state.`/`env.` without `this.`.

| Directive | v20 form |
|---|---|
| Output | `t-out="expr"` (escaped unless the value is `markup(...)`); `t-esc` warns (OWL001); `t-raw` does not exist (OWL002) |
| Events | `t-on-click="this.onClick"` (called with `this` = component) or `t-on-click="() => this.select(item)"`; modifiers `.stop .prevent .self .capture .synthetic .passive` |
| Refs | `t-ref="this.rootRef"` where `rootRef = signal.ref()` (a string name no longer works) |
| Two-way binding | `t-model="this.query"` on a signal; `t-model.proxy="this.state.name"` on a proxy property; modifiers `.trim .lazy .number` (input, textarea, select only) |
| Slots | `<t t-call-slot="default"/>` (was `t-slot`, OWL003); pass scope as attributes `<t t-call-slot="item" record="r"/>`; callers use `<t t-set-slot="item" t-slot-scope="s">` |
| Sub-templates | `<t t-call="mod.tmpl" title="this.title" label.translate="Save"/>`: a `t-set` inside the `t-call` body is not visible to the callee |
| Portal | `<Portal target="'body'">...</Portal>` with `Portal` in `static components` (OWL004); target is an expression: selector string, element or ref signal |
| Child props | `<Child value="this.x" onPick.bind="this.pick" label.translate="Name" sig.signal="this.state.x"/>` (`.signal` passes a read-only signal) |
| Markup | tagged form ``markup`<b>${userText}</b>` `` escapes the interpolated values; `markup(str)` trusts the whole string |

Compat-only custom directive: `t-custom-portal="'body'"` (value is an expression, as with the
old `t-portal`; still used by `web.NavBar`). `t-custom-click`
(click plus middle-click) is provided by `addons/web/static/src/env.js`.

Source: addons/web/static/lib/owl/owl.js (parser: t-model, t-call, t-call-slot, formatProp),
addons/web/static/src/core/user_switch/user_switch.xml, addons/web/static/src/core/utils/render.js

## Env, plugins, services

- `this.env` is set by the compat `Component` (`useEnv()`); it holds `services`, `bus`, and
  contextual keys (`config`, `searchModel`, `dialogData`...). `env.debug` and `env.isSmall`
  **throw** (JS008): use `usePlugin(DebugModePlugin).isActive()` / `odoo.debug`, and
  `useService("ui").isSmall` (getter) or `usePlugin(UIPlugin).isSmall()` (signal).
- Add keys for children with `useSubEnv({...})` from `@web/owl2/utils` (also changes `this.env` of
  the caller). For shared state of a subtree prefer `providePlugins([MyPlugin])` + `usePlugin`.
- Services: `useService("orm")` still works; native form `usePlugin(ORM)`. See
  [plugins-services.md](plugins-services.md).

Source: addons/web/static/src/env.js, addons/web/static/src/core/debug_mode_plugin.js,
addons/web/static/src/core/ui/ui_plugin.js, addons/hr_holidays/static/src/views/kanban/kanban_controller.js

## Complete example

```javascript
/** my_module/static/src/partner_list/partner_list.js */
import { Component, computed, onWillStart, proxy, signal, t, useOnChange, useProps, usePlugin } from "@odoo/owl";
import { ORM } from "@web/core/orm_plugin";
import { useAutofocus } from "@web/core/utils/hooks";

export class PartnerList extends Component {
    static template = "my_module.PartnerList";

    props = useProps({
        domain: t.array().optional(() => []),
        title: t.string().optional("Partners"),
        onSelect: t.function().optional(() => () => {}),
    });
    orm = usePlugin(ORM);
    inputRef = signal.ref();
    query = signal("");
    state = proxy({ partners: [], onlyCompanies: false });
    visible = computed(() => {
        const q = this.query().toLowerCase();
        return this.state.partners.filter(
            (p) => (!this.state.onlyCompanies || p.is_company) && p.display_name.toLowerCase().includes(q)
        );
    });

    setup() {
        useAutofocus({ ref: this.inputRef });
        onWillStart(() => this.load(this.props.domain));
        // a domain literal in the parent template is a new array on each parent render:
        // compare its JSON so only real changes reload
        useOnChange(
            () => [JSON.stringify(this.props.domain)],
            () => this.load(this.props.domain),
            { initialRun: false }
        );
    }

    async load(domain) {
        this.state.partners = await this.orm.searchRead(
            "res.partner", domain, ["display_name", "is_company"], { limit: 80 }
        );
    }
}
```

```xml
<!-- my_module/static/src/partner_list/partner_list.xml -->
<templates xml:space="preserve">
    <t t-name="my_module.PartnerList">
        <div class="o_my_module_partner_list">
            <h5 t-out="this.props.title"/>
            <input class="form-control" placeholder="Search..." t-ref="this.inputRef" t-model="this.query"/>
            <label class="form-check my-2">
                <input type="checkbox" class="form-check-input" t-model.proxy="this.state.onlyCompanies"/>
                Companies only
            </label>
            <ul class="list-unstyled">
                <li t-foreach="this.visible()" t-as="partner" t-key="partner.id">
                    <a href="#" t-on-click.prevent="() => this.props.onSelect(partner.id)">
                        <i t-if="partner.is_company" class="oi oi-fw" data-icon="business"/>
                        <t t-out="partner.display_name"/>
                    </a>
                </li>
            </ul>
            <t t-call-slot="footer"/>
        </div>
    </t>
</templates>
```

Parent usage: `<PartnerList domain="[['customer_rank', '>', 0]]" onSelect.bind="this.openPartner"/>`
with `static components = { PartnerList }`. Add both files to `web.assets_backend` (see
[assets.md](assets.md)); check the result with `odoo_validate` and the icon name with
[icons.md](icons.md).

Source: patterns from addons/web/static/src/core/checkbox/checkbox.js,
addons/web/static/src/core/pager/pager.js, addons/web/static/src/core/orm_plugin.js,
addons/web/static/src/core/utils/hooks.js (useAutofocus)

## Pitfalls

- `this.props.foo` is `undefined` although the parent passes `foo`: `foo` is not declared in
  `useProps`.
- Wrong prop types pass silently outside dev mode: test with `?debug=1` or in tours/Hoot.
- `useEffect(() => {...}, () => [deps])`: the second argument is ignored (JS004).
- `useEffect` reading `this.ref()` runs first with `null`: guard with `if (!el) return;`.
- `t-ref="input"` (string) or `t-model="state.x"` without `.proxy`: template compile errors
  ("Ref should implement either a 'set' function..." / "Invalid t-model expression").
- Default given as a bare function in `.optional(fn)` is invoked as a factory.
- A plain `signal({...})` does not notify on `s().x = 1`; use `signal.Object`, `proxy`, or `s.set`.
- `usePlugin(X)` in a component throws `Unknown plugin "X"` when X was never started: add it to the
  `services` resource or `providePlugins([X])` above.

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `static props = {...}`, `static defaultProps` | `props = useProps({ x: t.string().optional("d") })` | addons/web/static/src/owl2/owl3_compatibility_layer.js |
| `useState(obj)` / `reactive(obj)` | `proxy(obj)` | addons/web/static/lib/owl/owl.d.ts |
| `useRef("name")` + `t-ref="name"` | `name = signal.ref()` + `t-ref="this.name"` | addons/web/static/src/core/checkbox/checkbox.xml |
| `useEffect(fn, () => [deps])` | `useEffect(fn)` (auto-track) / `useOnChange` / `useLayoutEffect` | addons/web/tooling/_eslintrc.json |
| `useExternalListener(window, "click", fn)` | `useListener(window, "click", fn)` | addons/web/static/src/core/pager/pager.js |
| `t-esc`, `t-slot`, `t-portal` | `t-out`, `t-call-slot`, `<Portal target="...">` | addons/web/static/lib/owl/owl.js |
| `props.x` in templates | `this.props.x` | odoo/upgrade_code/owl3-migration.py |
| `this.render(true)` | reactivity, or `render(this, true)` from `@web/owl2/utils` | addons/web/static/src/owl2/utils.js |
| `env.isSmall`, `env.debug` | `useService("ui").isSmall`, `usePlugin(DebugModePlugin).isActive()` | addons/web/static/src/env.js |
