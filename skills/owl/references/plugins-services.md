# Plugins and services (Odoo 20)

Odoo 20 replaces most web "services" with OWL 3 Plugins registered in the `services` Resource of
`@web/core/services`. `useService("name")` keeps working through a legacy bridge, but the native
form is `usePlugin(PluginClass)`, and the two APIs differ in places. Covers: plugin anatomy, the
main web plugins, the legacy bridge, writing your own plugin or service, ORM calls and `doAction`.

## Contents

- [Plugin anatomy](#plugin-anatomy)
- [Main web plugins](#main-web-plugins)
- [The legacy service bridge](#the-legacy-service-bridge)
- [Writing your own plugin](#writing-your-own-plugin)
- [Writing your own legacy service](#writing-your-own-legacy-service)
- [ORM calls](#orm-calls)
- [doAction](#doaction)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## Plugin anatomy

```javascript
import { Plugin, usePlugin, useListener } from "@odoo/owl";
import { ORM, UPDATE_METHODS } from "@web/core/orm_plugin";
import { rpcBus } from "@web/core/network/rpc";
import { services } from "@web/core/services";

export class CurrencyPlugin extends Plugin {
    orm = usePlugin(ORM);                  // dependency: starts ORM first if needed

    setup() {
        useListener(rpcBus, "RPC:RESPONSE", (ev) => { /* ... */ });
    }

    async reloadCurrencies() {
        const result = await this.orm.call("res.currency", "get_all_currencies");
        // ...
    }
}
services.add(CurrencyPlugin);              // started by the web client app
```

| Concept | Rule |
|---|---|
| Base class | `Plugin` from `@odoo/owl` (not `@html_editor/plugin`, which is the editor's own class) |
| Identity | `static id` if set, else the class name: two plugins with the same class name collide ("Trying to start a plugin with the same id as an other plugin") |
| `static sequence` | default 50; global plugins start in batches of equal sequence, lowest first, each batch's `onWillStart` settling before the next (`EnvBusBridgePlugin` 1, `LocalizationPlugin` 10, `LegacyServiceStarterPlugin` 100) |
| Hooks allowed in a plugin | class fields / `setup()`: `usePlugin`, `useConfig`, `useScope`, `onWillStart`, `onWillDestroy`, `useListener`, `useEffect`, `useEnv`/`useService`; no `onMounted`/`useProps` (component-only) |
| `static scoped(plugin, scope)` | optional factory returning a per-consumer view; `ORM` uses it so RPCs are guarded by the caller's lifetime |
| App-level registration | `services.add(MyPlugin)` (`services` is an OWL `Resource` validated with `t.constructor(Plugin)`) |
| Subtree registration | in a component `setup()`: `providePlugins([MyPlugin], config)`; descendants get the same instance through `usePlugin` |
| Config | inside a plugin: `useConfig("key", t.instanceOf(EventBus).optional(() => new EventBus()))`; the value comes from `providePlugins(..., { key })` or the app config |
| Lookup failure | `usePlugin(X)` in a component throws `Unknown plugin "X"` if X was never started (in a plugin scope it starts X on demand) |

Source: addons/web/static/src/core/services.js, addons/web/static/src/webclient/currency_plugin.js,
addons/web/static/src/core/global_bus_plugin.js, addons/web/static/lib/owl/owl.js (Plugin, PluginManager,
usePlugin, useConfig, providePlugins), addons/hr_holidays/static/src/views/kanban/kanban_controller.js

## Main web plugins

| Plugin (import) | Legacy service | Main API |
|---|---|---|
| `ORM` (`@web/core/orm_plugin`) | `orm` | see [ORM calls](#orm-calls) |
| `ActionPlugin` (`@web/webclient/actions/action_plugin`) | `action` | `doAction`, `doActionButton`, `switchView`, `restore`, `loadState`, `loadAction`, `currentController`, `currentAction` |
| `UIPlugin` (`@web/core/ui/ui_plugin`) | `ui` | signals `isSmall()`, `size()`; computed `activeElement()`, `isBlocked()`; `block()`, `unblock()`, `activateElement(el)`, `bus` |
| `DialogPlugin` (`@web/core/dialog/dialog_plugin`) | `dialog` | `add(DialogComponent, props, { onClose, rootRef, scope })` returns `close`; `closeAll()` |
| `NotificationPlugin` (`@web/core/notifications/notification_plugin`) | `notification` | `add(message, { type, title, className, buttons, sticky, autocloseDelay, onClose })` returns `close` |
| `EffectPlugin` (`@web/core/effects/effect_plugin`) | `effect` | `add({ type: "rainbow_man", message, fadeout, img_url })` |
| `PopoverPlugin` (`@web/core/popover/popover_plugin`) | `popover` | `add(target, Component, props, options)` returns `close` (hook: `usePopover` in `@web/core/popover/popover_hook`) |
| `OverlayPlugin` (`@web/core/overlay/overlay_plugin`) | `overlay` | `add(Component, props, { onRemove, sequence, rootId, scope })` |
| `HotkeyPlugin` (`@web/core/hotkeys/hotkey_plugin`) | `hotkey` | `add(hotkey, callback, options)` (hook: `useHotkey` in `@web/core/hotkeys/hotkey_hook`) |
| `TitlePlugin` (`@web/core/browser/title_plugin`) | `title` | `setParts({ key: value })`, computed `title()` |
| `LocalizationPlugin` (`@web/core/l10n/localization_plugin`) | `localization` | loads translations; data in `localization` (`@web/core/l10n/localization`) |
| `CurrencyPlugin` (`@web/webclient/currency_plugin`) | `currency` | `reloadCurrencies()` |
| `DebugModePlugin` (`@web/core/debug_mode_plugin`) | none | `isActive(mode?)`, `toList()` (replaces `env.debug`) |
| `GlobalBusPlugin` (`@web/core/global_bus_plugin`) | none | `bus` (the same `EventBus` as `env.bus`) |
| `OfflinePlugin` (`@web/core/offline/offline_plugin`) | `offline` | signal `isOffline()` |
| `SortablePlugin` (`@web/core/utils/sortable_plugin`) | `sortable` | |
| `BootstrapInstance` (`@web/core/utils/bootstrap_plugin`) | none | `getOrCreateInstance(window.Tooltip, el)` |
| `BusPlugin` (`@bus/services/bus_plugin`) | `bus_service` | `subscribe(type, cb)`, `unsubscribe`, `addChannel`, `deleteChannel`, `send` |
| `TourPlugin` (`@web_tour/tour_plugin`) | none | `startTour(name, options)` |

Still plain legacy services (no plugin, use `useService`): `command`, `datetime_picker`, `error`,
`field`, `file_upload`, `fileViewer`, `http`, `menu`, `name`, `profiling`, `pwa`, `tooltip`,
`tree_processor`, `view`, `public.interactions`, ... (grep `category("services").add` with
`odoo_grep`). Not services at all, import the module: `rpc` (`@web/core/network/rpc`), `user`
(`@web/core/user`), `session` (`@web/session`), `router` (`@web/core/browser/router`), `browser`
(`@web/core/browser/browser`).

Source: `rg "services.add\(" addons/*/static/src`, addons/web/static/src/core/**/*_plugin.js,
addons/bus/static/src/services/bus_plugin.js, addons/web_tour/static/src/tour_plugin.js

## The legacy service bridge

`LegacyServiceStarterPlugin` (sequence 100) starts every entry of `registry.category("services")`
inside its plugin scope and stores the result in `env.services`. Most plugin files also register a
thin wrapper (`start() { return usePlugin(XPlugin); }`), so `useService("x")` returns the plugin or
an adapter around it.

| Aspect | `useService("x")` | `usePlugin(XPlugin)` |
|---|---|---|
| Works in | components and plugins (reads `env.services`) | components and plugins |
| `ui.isSmall` | boolean getter | signal: call `isSmall()` |
| `ui.activeElement`, `isBlocked`, `size` | getters | computed/signals: call them |
| `title.current`, `setCounters`, `getParts` | exist (adapter) | absent; use `title()`, `setParts`, `prefix.set` |
| `orm` methods after the component died | listed `async` methods reject with "Component is destroyed"; in-flight ones never resolve | in-flight calls reject with `AbortError` (silently ignored by the error service); calling after destroy throws |
| Escape the component lifetime | `env.services.orm` | `this.orm.unscoped` |

The services registry is validated (debug mode) against
`{ start: t.function(), dependencies: t.array(t.string()).optional(), async: t.or([t.literal(true), t.array(t.string())]).optional() }`.

Source: addons/web/static/src/core/legacy_service_starter.js, addons/web/static/src/core/utils/hooks.js
(useService, protectMethod), addons/web/static/src/core/ui/ui_plugin.js, addons/web/static/src/core/orm_plugin.js

## Writing your own plugin

```javascript
/** my_module/static/src/counter/counter_plugin.js */
import { Plugin, computed, signal, usePlugin } from "@odoo/owl";
import { ORM } from "@web/core/orm_plugin";
import { services } from "@web/core/services";

export class MyModuleCounterPlugin extends Plugin {   // unique class name = plugin id
    orm = usePlugin(ORM);
    count = signal(0);
    isHigh = computed(() => this.count() > 10);

    async refresh() {
        this.count.set(await this.orm.searchCount("res.partner", [["is_company", "=", true]]));
    }
}
services.add(MyModuleCounterPlugin);   // omit to start it per subtree with providePlugins
```

```javascript
// in a component
counter = usePlugin(MyModuleCounterPlugin);
// template: <span t-out="this.counter.count()"/>
```

- Expose state as signals/computed or `proxy` objects so components re-render.
- Keep the file in the feature folder ([organize by feature](../../odoo-web-guidelines/guidelines/javascript.md#organize-files-by-feature-not-by-type)).
- Only add a `registry.category("services")` wrapper if non-OWL code needs `env.services.x`.
- Patch a plugin with `patch(MyPlugin.prototype, {...})` like any class (see [fields-views-js.md](fields-views-js.md#patch)).

Source: addons/web/static/src/core/browser/title_plugin.js, addons/hr_holidays/static/src/views/time_off_plugin.js

## Writing your own legacy service

Use only when the consumer is not a component/plugin (or for code shared with older patterns).
`start()` runs inside a scope, so it may call `usePlugin(...)`.

```javascript
import { registry } from "@web/core/registry";
import { rpcBus } from "@web/core/network/rpc";

registry.category("services").add("reloadCompany", {
    dependencies: ["action"],
    start(env, { action }) {
        rpcBus.addEventListener("RPC:RESPONSE", (ev) => { /* ... action.doAction("reload_context") */ });
    },
});
```

`async: ["loadDisplayNames"]` (list of method names, or `true` for a function service) makes
`useService` guard those methods against destroyed components (`addons/web/static/src/core/name_service.js`).

Source: addons/web/static/src/webclient/reload_company_service.js, addons/web/static/src/core/name_service.js

## ORM calls

`this.orm = useService("orm")` (most core code) or `orm = usePlugin(ORM)`. All return promises and
add `user.context` to `kwargs.context`.

| Method | Server method |
|---|---|
| `call(model, method, args = [], kwargs = {})` | any public method |
| `create(model, [vals, ...], kwargs)` | `create` (returns ids) |
| `read(model, ids, fields, kwargs)` | `read` (empty `ids` resolves `[]`) |
| `search(model, domain, kwargs)` / `searchCount(model, domain, kwargs)` | `search` / `search_count` |
| `searchRead(model, domain, fields, kwargs)` | `search_read` (`kwargs`: `limit`, `offset`, `order`, `context`) |
| `write(model, ids, vals, kwargs)` | `write` |
| `unlink(model, ids, kwargs)` / `webUnlink(...)` | `unlink` / `web_unlink` (only from the confirmed delete flow) |
| `webRead(model, ids, { specification, context })` | `web_read` |
| `webSearchRead(model, domain, { specification, limit, offset, order, count_limit, context })` | `web_search_read` |
| `webSave(model, ids, vals, { specification })` / `webSaveMulti(model, ids, [vals])` | `web_save` / `web_save_multi` |
| `formattedReadGroup(model, domain, groupby, aggregates, kwargs)` | `formatted_read_group` (adds `__domain` per group) |
| `formattedReadGroupingSets(model, domain, grouping_sets, aggregates, kwargs)` | `formatted_read_grouping_sets` |
| `webReadGroup(model, domain, groupby, aggregates, kwargs)` | `web_read_group` |
| `webResequence(model, ids, kwargs)` | `web_resequence` |
| `orm.silent.<method>(...)` | no loading indicator |
| `orm.cache({ type: "disk" }).read(...)` | cached RPC |

Many2one values come back as `{ id, display_name }` in `web_*` methods. x2many commands:
`x2ManyCommands.create/update/link/unlink/delete/clear/set` from `@web/core/orm_plugin`. Check
server signatures with `odoo_method` before calling `call(...)`.

Source: addons/web/static/src/core/orm_plugin.js, addons/web/static/src/core/network/rpc.js,
addons/web/static/src/model/relational_model/utils.js

## doAction

```javascript
this.action = useService("action");      // or: action = usePlugin(ActionPlugin)
await this.action.doAction("my_module.action_my_model", {
    additionalContext: { default_partner_id: id },
    onClose: (infos) => this.reload(),
});
await this.action.doAction({
    type: "ir.actions.act_window", res_model: "res.partner", res_id: id,
    views: [[false, "form"]], target: "new",
});
```

| Option | Effect |
|---|---|
| `additionalContext` | merged into the action context |
| `clearBreadcrumbs` | start a new breadcrumb (forced for `target: "main"`) |
| `stackPosition` | `"replaceCurrentAction"` / `"replacePreviousAction"` |
| `index` | cut the breadcrumb stack at this index |
| `onClose(infos)` | called when a `target: "new"` dialog closes |
| `props` | extra props for the controller (e.g. `{ resId }`) |
| `viewType` | first view to open |
| `newWindow` | open in a new tab (act_window) |
| `forceLeave` | leave even if the current record cannot be saved |
| `keepDialogs`, `onActionReady(action)`, `noEmptyTransition` | advanced |

`actionRequest` may be an id, an xmlid, a client-action tag or an action dict; unknown `type`s are
dispatched to `registry.category("action_handlers")`. `doActionButton({ type: "object", resModel,
name, resId, context })` runs a button.

Source: addons/web/static/src/webclient/actions/action_plugin.js (ActionOptions typedef, doAction,
doActionButton), addons/l10n_ro_edi/static/src/components/fetch_invoices.js

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `import { ORM } from "@web/core/orm_service"` | `@web/core/orm_plugin` | addons/web/static/src/core/orm_plugin.js |
| `@web/webclient/actions/action_service` | `@web/webclient/actions/action_plugin` | action_plugin.js |
| `env.isSmall` | `useService("ui").isSmall` or `usePlugin(UIPlugin).isSmall()` | addons/web/static/src/env.js |
| `env.debug` | `usePlugin(DebugModePlugin).isActive()` | addons/web/static/src/core/debug_mode_plugin.js |
| `usePlugin(ActionManagerPlugin)` (from owl3-migration) | `usePlugin(ActionPlugin)` | odoo/upgrade_code/owl3-migration.py |
| new service via `registry.category("services")` | new code: a `Plugin` + `services.add(...)` | addons/web/static/src/core/services.js |
| service `start(env, deps)` returning an object with getters | plugin fields as signals/computed | addons/web/static/src/core/ui/ui_plugin.js |
