# html_editor plugins and the Html field (Odoo 20)

The rich-text editor (`html_editor`) and the website builder (`html_builder`) are made of **editor
plugins**: classes extending `Plugin` from `@html_editor/plugin` that share methods and contribute
named resources. They are not OWL `Plugin`s (`@odoo/owl`), although editor plugins can call
`usePlugin(...)` in `setup()`. Read this to add a command/toolbar button/behaviour to the editor or to
customize the `html` field.

## Contents
- [Editor plugin anatomy](#editor-plugin-anatomy)
- [Dispatching resources](#dispatching-resources)
- [Resource naming and common resources](#resource-naming-and-common-resources)
- [Using the editor: the html field and Wysiwyg](#using-the-editor-the-html-field-and-wysiwyg)
- [Adding your plugin to an Html field](#adding-your-plugin-to-an-html-field)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## Editor plugin anatomy

```javascript
// adapted from addons/html_editor/static/src/main/star_plugin.js
import { Plugin } from "@html_editor/plugin";
import { parseHTML } from "@html_editor/utils/html";
import { isHtmlContentSupported } from "@html_editor/core/selection_plugin";
import { _t } from "@web/core/l10n/translation";

export class StarPlugin extends Plugin {
    static id = "star";                          // unique, required
    static dependencies = ["dom", "history"];    // ids of plugins whose shared methods you use
    static shared = [];                          // method names other plugins may call
    resources = {
        user_commands: [{
            id: "addStars",
            title: _t("Stars"),
            description: _t("Insert a rating"),
            icon: "star",                         // Material Symbols name
            run: this.addStars.bind(this),
            isAvailable: isHtmlContentSupported,
        }],
        powerbox_items: [{
            title: _t("5 Stars"),
            description: _t("Insert a rating over 5 stars"),
            categoryId: "widget",
            icon: "star",
            commandId: "addStars",
            commandParams: { length: 5 },
        }],
    };

    setup() {
        this.addDomListener(this.editable, "pointerdown", this.onMouseDown);
    }

    addStars({ length }) {
        const stars = Array(length).fill('<i class="oi" data-icon="star"></i>').join("");
        this.dependencies.dom.insert(parseHTML(this.document, `<span class="o_stars">${stars}</span>`));
        this.dependencies.history.commit();      // create an undo step
    }
}
```

| Member | Notes |
|---|---|
| `static id`, `static dependencies`, `static shared`, `static defaultConfig` | Plugins are topologically sorted by `dependencies`; missing or circular ones throw. `defaultConfig` is merged under `editor.config`. |
| `resources` | Instance field (can use `this`); values may be arrays or single items; wrap with `withSequence(n, item)` (`@html_editor/utils/resource`, default 10) to order. |
| `this.document`, `this.window`, `this.editable`, `this.config`, `this.services` | Context; `services` = `env.services` (legacy services: `orm`, `dialog`, `notification`, ...). |
| `this.dependencies.<id>.<method>` | Shared methods of declared dependencies only. |
| `this.getResource(id)` | Sorted array of every contribution. |
| `this.trigger / triggerAsync / delegateTo / processThrough / checkPredicates` | See next section. |
| `setup()`, `destroy()` | `setup` runs inside the editor's Owl scope (`useEditor`), so `usePlugin(BootstrapInstance)` works (addons/html_builder/static/src/core/remove_plugin.js). |
| `addDomListener(target, event, fn, capture, isGlobal)`, `addGlobalDomListener(event, fn)` | Auto-removed on destroy; filtered on protected nodes unless global. |

Core plugin ids you will depend on: `dom` (`insert`, `setBlock`, `setTagName`, ...), `selection`
(`getEditableSelection`, `setSelection`, `setCursorStart`, `preserveSelection`, ...), `history`
(`commit`, `undo`, `redo`, `makeSavePoint`, `makePreviewableOperation`, ...), `domObserver` (`ignore`, ...),
`format`, `split`, `delete`, `clipboard`, `userCommand`, `sanitize`, `baseContainer`.

Source: addons/html_editor/static/src/plugin.js, addons/html_editor/static/src/editor.js (sortPlugins,
preparePlugins, useEditor), addons/html_editor/static/src/main/star_plugin.js,
addons/html_editor/static/src/core/history_plugin.js:71, addons/html_editor/static/src/core/dom_plugin.js:107

## Dispatching resources

| Call | Resource suffix | Semantics |
|---|---|---|
| `this.trigger(id, ...args)` | `_handlers` | Call every handler, return their results (array). |
| `await this.triggerAsync(id, ...args)` | `_handlers` | Call handlers sequentially, awaiting each. |
| `this.delegateTo(id, ...args)` | `_overrides` | Stop at the first function returning truthy; returns `true` if handled. |
| `this.processThrough(id, item, ...args)` | `_processors` | Pipe `item` through each processor (each must return the item). |
| `this.checkPredicates(id, ...args) ?? default` | `_predicates` | `undefined` = no opinion; any `false` wins; `undefined` overall if nobody answered. |
| `this.getResource(id)` | anything else (`_providers`, `_selectors`, `_items`, ...) | Raw list. |

A wrong suffix only logs a console warning (`warnOfNamingConvention`), it does not throw. Handler
resources are mostly named `on_<event>_handlers` / `on_will_<event>_handlers` (e.g.
`on_editor_started_handlers`, `on_content_updated_handlers`, `on_will_delete_handlers`,
`on_pasted_handlers`); a few older names such as `before_format_handlers` remain.

```javascript
// addons/html_editor/static/src/main/banner_plugin.js
isAvailable: (selection) =>
    this.checkPredicates("is_banner_command_available_predicates", selection, "info") ?? true,
```

Source: addons/html_editor/static/src/editor.js (trigger, triggerAsync, delegateTo, processThrough,
checkPredicates), addons/html_editor/static/src/utils/resource.js

## Resource naming and common resources

Every resource id is typed in `addons/html_editor/static/src/@types/plugins.d.ts` (imports show which
plugin consumes it). Check there or with `odoo_grep "getResource(\"<id>\")"` before contributing.

| Resource | Item shape | Consumer |
|---|---|---|
| `user_commands` | `{ id, title, description, icon, run(params), isAvailable(selection) }` | core/user_command_plugin.js |
| `powerbox_items` | `{ title, description, categoryId, icon, iconClass?, commandId, commandParams? }` | main/powerbox/powerbox_plugin.js |
| `powerbox_categories` | `{ id, name }` (core ids include `structure`, `format`, `banner`, `widget`, `media`, `navigation`) | main/powerbox/powerbox_plugin.js |
| `toolbar_groups` / `toolbar_items` | `withSequence(n, { id })` / `{ id, groupId, commandId }` | main/toolbar/toolbar_plugin.js |
| `shortcuts` | `{ hotkey: "control+shift+q", commandId }` | core/shortcut_plugin.js |
| `clean_for_save_processors` | `(root) => root` | editor.js `getElContent` |
| `html_compatibility_processors` | `(root) => root` | editor.js `startPlugins` |
| `normalize_processors` | node processor | core/dom_plugin.js |
| `on_editor_started_handlers` | `() => void` | editor.js |
| `selectors_for_feff_providers` | `() => "css selector"` | main/feff_plugin.js |

Source: addons/html_editor/static/src/@types/plugins.d.ts, addons/html_editor/static/src/fields/html_field.js
(codeview toolbar entry), addons/html_editor/static/src/core/shortcut_plugin.js

## Using the editor: the html field and Wysiwyg

In views use the `html` widget (default for `fields.Html`). Options read by `htmlField.extractProps`:

```xml
<field name="description" options="{'collaborative': true, 'height': 300, 'allowVideo': false,
    'codeview': true, 'embedded_components': false, 'dynamic_placeholder': true}"/>
```

Recognized keys: `height`, `allowImage`, `allowMediaDocuments`, `allowVideo`, `allowFile`,
`allowChecklist`, `allowScrollableTables`, `saveScrollableTables`, `allowAttachmentCreation`,
`baseContainers`, `cleanEmptyStructuralContainers`, `debouncePowerbuttons`, `debounceHints`,
`allowWhiteboard`, `collaborative`, `collaborative_trigger`, `migrateHTML` (default true),
`dynamic_placeholder`, `dynamic_placeholder_model_reference_field`, `embedded_components` (default true),
`sandboxedPreview`, `cssReadonly`, `codeview` (debug only); `placeholder` attribute is honoured.

Outside a view, mount `Wysiwyg` (`@html_editor/wysiwyg`) with props `config` (EditorConfig: `content`,
`Plugins`, `resources`, `onChange`, `baseContainers`, `placeholder`, ...), `onLoad(editor)`, `onBlur`,
`iframe`, `copyCss`, `class`, `contentClass`, `style`. Plugin lists come from
`@html_editor/plugin_sets`: `CORE_PLUGINS`, `MAIN_PLUGINS` (default), `COLLABORATION_PLUGINS`,
`EMBEDDED_COMPONENT_PLUGINS`, `EXTRA_PLUGINS`. Read the content with `editor.getContent()` (runs
`clean_for_save_processors`). Low level: `useEditor(config)` from `@html_editor/editor` returns an
`Editor`; call `editor.attachTo(el)`.

Source: addons/html_editor/static/src/fields/html_field.js:418 (htmlField.extractProps),
addons/html_editor/static/src/wysiwyg.js (wysiwygProps), addons/html_editor/static/src/plugin_sets.js,
addons/html_editor/static/src/editor.js

## Adding your plugin to an Html field

Prefer a dedicated widget that subclasses `HtmlField` and edits `getConfig()`:

```javascript
// pattern from addons/calendar/static/src/views/fields/calendar_notes_html_field.js
// and addons/mail/static/src/views/web/fields/html_mail_field/html_mail_field.js
import { registry } from "@web/core/registry";
import { htmlField, HtmlField, htmlFieldProps } from "@html_editor/fields/html_field";
import { t, useProps } from "@odoo/owl";
import { StarPlugin } from "@html_editor/main/star_plugin";
import { MyPlugin } from "./my_plugin";

class MyHtmlField extends HtmlField {
    props = useProps({ ...htmlFieldProps, withMyPlugin: t.boolean().optional(true) });

    getConfig() {
        const config = super.getConfig();
        config.Plugins = config.Plugins.filter((P) => P !== StarPlugin);
        if (this.props.withMyPlugin) {
            config.Plugins = [...config.Plugins, MyPlugin];
        }
        return config;
    }
}

registry.category("fields").add("my_html", { ...htmlField, component: MyHtmlField });
```

```xml
<field name="body" widget="my_html"/>
```

- Extra resources without a plugin: `getConfig()` result has `resources` (also fed by
  `props.editorConfig`), e.g. `config.resources.user_commands = [...]`.
- `MAIN_PLUGINS.push(X)` mutates the shared list for every editor in the bundle; core only does it in an
  isolated bundle (addons/project/static/src/project_sharing/editor/project_sharing_media_plugin.js).
  Avoid it in backend addons.
- Patching `HtmlField.prototype.getConfig` affects every html field: see
  [Avoid patching](../../odoo-web-guidelines/guidelines/javascript.md#avoid-patching-javascript-code)
  and [fields-views-js.md](../../owl/references/fields-views-js.md).
- Ship plugin files in `web.assets_backend` (the html field bundle) and check with `odoo_assets`.

Source: addons/html_editor/static/src/fields/html_field.js:309 (getConfig), addons/calendar/static/src/views/fields/calendar_notes_html_field.js,
addons/mail/static/src/views/web/fields/html_mail_field/html_mail_field.js, addons/html_editor/__manifest__.py

## v19 habit -> Odoo 20

| v19 | Odoo 20 | Source |
|---|---|---|
| `this.dispatchTo("x_handlers", ...)` | `this.trigger("on_x_handlers", ...)` (`triggerAsync` for sequential async) | addons/html_editor/static/src/editor.js |
| context had `dispatchTo` | context has `trigger`, `triggerAsync`, `delegateTo`, `processThrough`, `checkPredicates` | addons/html_editor/static/src/plugin.js |
| `this.dependencies.history.addStep()` | `this.dependencies.history.commit()` | addons/html_editor/static/src/core/history_plugin.js:71 |
| `clean_for_save_handlers: ({ root }) => {...}` | `clean_for_save_processors: (root) => root` | addons/html_editor/static/src/editor.js |
| `normalize_handlers`, `content_updated_handlers`, `before_delete_handlers`, `after_paste_handlers`, `added_image_handlers` | `normalize_processors`, `on_content_updated_handlers`, `on_will_delete_handlers`, `on_pasted_handlers`, `on_image_added_handlers` | addons/html_editor/static/src/@types/plugins.d.ts |
| `new Editor(config, services)` | `new Editor(scope, config, services)`; use `useEditor(config)` inside a component | addons/html_editor/static/src/editor.js |
| `static props` on HtmlField subclasses | `props = useProps({ ...htmlFieldProps, ... })` (JS001) | addons/mail/static/src/views/web/fields/html_mail_field/html_mail_field.js |
| Font Awesome `icon: "fa-star"` in commands | Material Symbols name `icon: "star"` (JS015) | addons/html_editor/static/src/main/star_plugin.js |
