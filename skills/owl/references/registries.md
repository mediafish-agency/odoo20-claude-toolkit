# Registries (Odoo 20)

How the web client registry works in Odoo 20 (`@web/core/registry`), how validation with `t.*`
works, and the value shape of each important category with one core example. Use it whenever
you write `registry.category("...").add(...)`. Verify a category's real entries with
`odoo_js(registry="<name>")` or `odoo_grep 'category("name")'` before relying on a key; the
generated [registry-index.md](registry-index.md) lists every category found in the tree.

## Contents

- [Registry API](#registry-api)
- [Validation](#validation)
- [Callbacks run inside a scope](#callbacks-run-inside-a-scope)
- [Web client categories](#web-client-categories)
- [Public, website, POS categories](#public-website-pos-categories)
- [Plugins are not registries](#plugins-are-not-registries)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## Registry API

`import { registry } from "@web/core/registry";` is Odoo's own `Registry` (an `EventBus`), not the
OWL 3 `Registry` class exported by `@odoo/owl`.

| Method | Behaviour |
|---|---|
| `category(name)` | sub-registry, created on first access (categories can nest: `category("debug").category("form")`) |
| `add(key, value, { sequence, force })` | throws `DuplicatedKeyError` if `key` exists and `force` is not set; default `sequence` 50 (with `force`, the previous sequence is kept unless given); chainable |
| `get(key)` / `get(key, default)` | throws `KeyNotFoundError` without a default |
| `contains(key)` | boolean |
| `getAll()` / `getEntries()` | values / `[key, value]` pairs sorted by sequence |
| `remove(key)` | (OWL's registry uses `delete`; Odoo's uses `remove`) |
| `addValidation(schema)` | once per category, see below |
| `"UPDATE"` event | `detail: { operation: "add" \| "delete", key, value }` |

Reactive read in a component: `useRegistry(registry.category("x"))` from
`@web/core/registry_hook` returns a `proxy({ entries })` kept in sync.

Source: addons/web/static/src/core/registry.js, addons/web/static/src/core/registry_hook.js,
addons/web/static/src/core/main_components_container.js

## Validation

```javascript
import { t } from "@odoo/owl";
registry.category("my_module.widgets").addValidation(
    t.object({ Component: t.component(), sequence: t.number().optional() })
);
```

- Schemas use the same `t.*` builders as `useProps` (see [owl3-core.md](owl3-core.md#props-useprops-and-t-validators)).
- Checks run through `assertType` only when `odoo.debug` is set; existing entries are checked
  when the schema is added. Errors read `Validation error for key "k" in registry "name"`.
- Validated categories in core: `fields`, `views`, `view_widgets`, `main_components`, `services`,
  `web_tour.tours` (strict object).
- For IDE typing of your own category, see [tooling.md](tooling.md).

Source: addons/web/static/src/core/registry.js (validateSchema), addons/web/static/src/views/fields/field.js,
addons/web/static/src/views/view.js, addons/web_tour/static/src/tour_plugin.js

## Callbacks run inside a scope

Odoo 20 invokes registry callbacks with `scope.run(...)`, so they may call `useService(...)` or
`usePlugin(...)` directly (no `env.services` needed): client action functions, `effects`,
`user_menuitems`, systray and cogMenu `isDisplayed`, `command_provider.provide`, `error_handlers`,
`ir.actions.report handlers`, `debug` items. Example: `rainbowMan` in
`addons/web/static/src/core/effects/effect_plugin.js` calls `useService("notification")`.

Source: addons/web/static/src/webclient/actions/action_plugin.js (`scope.run(() => clientAction(env, action, options))`),
addons/web/static/src/core/errors/error_service.js, addons/web/static/src/core/commands/command_palette.js

## Web client categories

| Category | Key -> value shape | Core example |
|---|---|---|
| `fields` | widget name (prefixes `list.`, `form.`, `card.`, `calendar.`, `hierarchy.`, `<js_class>.`) -> `{ component, displayName?, supportedTypes?, supportedOptions?, supportedAttributes?, extractProps?(fieldInfo, dynamicInfo), fieldDependencies?, relatedFields?, isEmpty?, isValid?, additionalClasses?, useSubView?, label?, listViewWidth? }` | `addons/web/static/src/views/fields/char/char_field.js` |
| `views` | view type or `js_class` -> `{ type, Controller, Renderer?, Model?, ArchParser?, Compiler?, SearchModel?, SearchPanel?, buttonTemplate?, searchMenuTypes?, props?(genericProps, view) }`; `type` must exist in `session.view_info` | `addons/web/static/src/views/form/form_view.js` |
| `view_widgets` | `<widget name>` -> `{ component, extractProps?, fieldDependencies?, additionalClasses?, supportedAttributes?, supportedOptions?, listViewWidth? }` | `addons/web/static/src/views/widgets/ribbon/ribbon.js` |
| `actions` | client action tag -> Component (props `standardActionServiceProps`; statics `target`, `path`, `displayName` honoured) or function `(env, action, options)` | `addons/web/static/src/webclient/actions/client_actions.js`, `addons/hr_attendance/static/src/views/badge_scanner/badge_scanner.js` |
| `action_handlers` | custom action `type` -> `({ env, action, options })` | consumer: `addons/web/static/src/webclient/actions/action_plugin.js` |
| `ir.actions.report handlers` | name -> `async (action, options, env) => true` when handled | `addons/printer/static/src/print_action_handler.js` |
| `main_components` | name -> `{ Component, props? }` (capital `Component`; the `.d.ts` says `component`, runtime validation wins) | `addons/web/static/src/webclient/loading_indicator/loading_indicator.js` |
| `systray` | name -> `{ Component, isDisplayed?(env) }`, order with `{ sequence }` | `addons/web/static/src/webclient/user_menu/user_menu.js` |
| `user_menuitems` | name -> `(env) => ({ type: "item" \| "separator", id, description, callback?, href?, sequence?, hide? })` | `addons/web/static/src/webclient/user_menu/user_menu_items.js` |
| `cogMenu` | name -> `{ Component, groupNumber, isDisplayed?(env) }` | `addons/l10n_ro_edi/static/src/components/fetch_invoices.js` |
| `favoriteMenu` | name -> `{ Component, groupNumber, isDisplayed? }` | `addons/web/static/src/search/custom_favorite_item/custom_favorite_item.js` |
| `command_categories` | category -> `{}` or `{ namespace }`, order with `{ sequence }` | `addons/web/static/src/core/commands/command_category.js` |
| `command_provider` | name -> `{ namespace?, provide(options) => [{ name, action, category, Component?, props?, href? }] }` | `addons/web/static/src/webclient/menus/menu_providers.js` |
| `command_setup` | namespace -> `{ name, placeholder, emptyMessage }` | `addons/web/static/src/webclient/menus/menu_providers.js` |
| `formatters` | field type -> `(value, options) => string` | `addons/web/static/src/views/fields/formatters.js` |
| `parsers` | field type -> `(value, options) => value` | `addons/web/static/src/views/fields/parsers.js` |
| `effects` | effect type -> `(params) => ({ Component, props }) \| undefined` | `addons/web/static/src/core/effects/effect_plugin.js` |
| `lazy_components` | name -> Component, rendered by `<LazyComponent bundle="..." Component="'name'"/>` (see [assets.md](assets.md#lazy-loading)) | `addons/website/static/src/builder/website_builder.js` |
| `dialogs` | name -> dialog Component (lookup without importing) | `addons/web/static/src/views/view_dialogs/select_create_dialog.js` |
| `error_handlers` | name -> `(env, error, originalError) => true` when handled; `sequence` matters | `addons/web/static/src/core/errors/error_handlers.js`, `addons/point_of_sale/static/src/app/utils/error_handlers.js` |
| `error_dialogs` | Python exception name -> dialog Component | `addons/base_automation/static/src/base_automation_error_dialog.js` |
| `error_notifications` | Python exception name -> notification options `{ title, message?, type, sticky, buttons? }` | `addons/web/static/src/public/error_notifications.js` |
| `form_compilers` | name -> `{ selector, fn }` (arch node compiler) | `addons/mail/static/src/chatter/web/form_compiler.js` |
| `group_config_items` | name -> `{ label, method, isVisible, class, icon? }` (kanban/list group menu) | `addons/base_automation/static/src/group_config_menu_patch.js` |
| `debug` -> `default`/`view`/`form`/... | name -> `(context) => ({ type: "item", description, callback, sequence, section })` | `addons/web/static/src/views/debug_items.js` |
| `sample_server` | `"model/method"` or `"method"` -> function returning sample data | `addons/calendar/static/src/views/list_view/calendar_list_view.js` |
| `services` | legacy service name -> `{ start(env, deps), dependencies?, async? }` (see [plugins-services.md](plugins-services.md)) | `addons/web/static/src/core/name_service.js` |
| `web_tour.tours` | tour name -> strict `{ steps: () => [...], url? }` | `addons/crm/static/src/js/tours/crm.js` |

Source: the example files above; addons/web/static/src/@types/registries/registries.d.ts (typings,
partly stale: `effetcs` typo, `main_components.component`)

## Public, website, POS categories

| Category | Key -> value shape | Core example | Details |
|---|---|---|---|
| `public.interactions` | name -> `Interaction` subclass | `addons/portal/static/src/interactions/bootstrap_tooltip.js` | [interactions.md](../../website-pos/references/interactions.md) |
| `public.interactions.edit` / `.preview` | name -> `{ Interaction, mixin?, isAbstract? }` | `addons/website/static/src/interactions/text_highlights.preview.js` | same |
| `public_components` (`.edit`) | name -> Component mounted on `<owl-component name="...">` | `addons/web/static/src/core/user_switch/user_switch.js` | same |
| `builder-options`, `website-options` | `Option.id` -> option component class | `addons/html_builder/static/src/plugins/vertical_alignment_option.js` | [website-builder.md](../../website-pos/references/website-builder.md) |
| `builder-plugins`, `website-plugins`, `translation-plugins` | `Plugin.id` -> editor plugin class | `addons/html_builder/static/src/plugins/shadow_option_plugin.js` | same |
| `pos_payment_providers` | `payment_provider` selection value -> class extending `PaymentInterface` | `addons/pos_viva_com/static/src/app/payment_viva_com.js` | [pos.md](../../website-pos/references/pos.md) |
| `pos_pages` | page name -> `{ name, component, route, params }` | `addons/point_of_sale/static/src/app/screens/ticket_screen/ticket_screen.js` | same |
| `pos_available_models` | `Model.pythonModel` -> JS model class | `addons/pos_loyalty/static/src/app/models/loyalty_rule.js` | same |

Source: example files above

## Plugins are not registries

OWL plugins are listed in the `services` **Resource** (`@web/core/services`): `services.add(MyPlugin)`,
no key, no `registry.category`. A Resource has `add(item, { sequence })`, `delete`, `has`, `items()`
(reactive). See [plugins-services.md](plugins-services.md).

Source: addons/web/static/src/core/services.js, addons/web/static/lib/owl/owl.d.ts (Resource)

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `registry.category("fields").add("kanban.many2many_tags", ...)` | `card.many2many_tags` (JS009) | addons/web/static/src/views/card/card_arch_parser.js |
| widgets `selection_badge`, `remaining_days` | `badges_selection`, `relative_date` (XML015) | addons/web/static/src/views/fields |
| effect `(env, params) => ...` | `(params) => ...` | addons/web/static/src/core/effects/effect_plugin.js |
| `provide: (env, options) => [...]` | `provide(options) { ... }` | addons/web/static/src/core/commands/default_providers.js |
| registry validation `{ type: Function, optional: true }` | `t.function().optional()` | addons/web/static/src/core/legacy_service_starter.js |
| tour `{ steps, url, wait_for }` | `{ steps, url }` only | addons/web_tour/static/src/tour_plugin.js |
| new service in `registry.category("services")` | `Plugin` + `services.add(...)` | addons/web/static/src/core/services.js |
| `register_payment_method(...)` (POS) | `registry.category("pos_payment_providers").add(...)` (JS010) | addons/point_of_sale/static/src/app/utils/payment |
| `publicWidget.registry.X = ...` | `registry.category("public.interactions").add(...)` (JS005) | addons/web/static/src/public/interaction.js |
