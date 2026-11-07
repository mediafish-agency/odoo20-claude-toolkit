# Field widgets, view widgets, views and client actions (Odoo 20)

Recipes for the backend view layer in Odoo 20: custom field widgets (`fields` registry), `<widget>`
view widgets, extending a view with `js_class`, adding a new view type, client actions, and
`patch()`. All components follow [owl3-core.md](owl3-core.md) (`props = useProps(...)`, `this.` in
templates). Check existing widgets/keys with `odoo_js(registry="fields", key="char")`, a view's
subclasses with `odoo_js(js_class="ListController")` and existing patches with
`odoo_js(patches_of="FormController")`.

## Contents

- [Custom field widget](#custom-field-widget)
- [Field registry entry](#field-registry-entry)
- [Record API used by fields](#record-api-used-by-fields)
- [Field hooks](#field-hooks)
- [View widgets](#view-widgets)
- [Extending a view with js_class](#extending-a-view-with-js_class)
- [New view type](#new-view-type)
- [Client actions](#client-actions)
- [Patch](#patch)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## Custom field widget

```javascript
/** my_module/static/src/views/fields/toggle_icon/toggle_icon_field.js */
import { Component, t, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class ToggleIconField extends Component {
    static template = "my_module.ToggleIconField";
    props = useProps({
        ...standardFieldProps,                       // id?, name, readonly?, record
        icon: t.string().optional("check_box"),
        label: t.string().optional(),
    });

    toggle() {
        const { name, record } = this.props;
        record.update({ [name]: !record.data[name] });
    }
}

export const toggleIconField = {
    component: ToggleIconField,
    displayName: _t("Toggle Icon"),
    supportedTypes: ["boolean"],
    supportedOptions: [{ label: _t("Icon"), name: "icon", type: "string" }],
    extractProps: ({ options, string }) => ({ icon: options.icon, label: string }),
};

registry.category("fields").add("my_module_toggle_icon", toggleIconField);
```

```xml
<t t-name="my_module.ToggleIconField">
    <button class="btn btn-link p-0" t-att-disabled="this.props.readonly"
            t-att-data-tooltip="this.props.label" t-on-click.prevent.stop="this.toggle">
        <i class="oi" t-att-class="{'oi-filled': this.props.record.data[this.props.name]}"
           t-att-data-icon="this.props.icon"/>
    </button>
</t>
```

Use it in an arch: `<field name="is_vip" widget="my_module_toggle_icon" options="{'icon': 'star'}"/>`.
Subclassing a core field: export and spread its props shape (`charFieldProps`) and its registry
object (`...charField`), as in `addons/web_tour/static/src/widgets/tour_start.js`.

Source: adapted from addons/web/static/src/views/fields/boolean_icon/boolean_icon_field.js(.xml),
addons/web/static/src/views/fields/standard_field_props.js

## Field registry entry

| Key | Meaning |
|---|---|
| `component` | the OWL component (required) |
| `displayName` | label in Studio / widget pickers |
| `supportedTypes` | field types; must be valid types (`char`, `many2one`, `json`, ...) |
| `supportedOptions` / `supportedAttributes` | `[{ label, name, type: "boolean"\|"string"\|"number"\|"selection"\|"field", default?, help?, choices?, availableTypes? }]` |
| `extractProps(fieldInfo, dynamicInfo)` | maps arch to props. `fieldInfo`: `{ name, type, viewType, widget, options, attrs, string, context, domain, decorations, placeholder, field, ... }`; `dynamicInfo`: `{ context (getter), domain(), required, readonly }` |
| `fieldDependencies` | `[{ name, type }]` or `(fieldInfo) => [...]`: extra fields loaded on the record (e.g. `write_date`) |
| `relatedFields` | fields loaded on the relation of an x2many/many2one (`[{ name, type, readonly?, selection? }]` or function) |
| `isEmpty(record, fieldName)`, `isValid(record, fieldName, fieldInfo)` | visual feedback overrides |
| `additionalClasses`, `useSubView`, `label`, `listViewWidth` | layout tweaks |

Key resolution: `<js_class>.<widget>`, then `<viewType>.<widget>`, then `<widget>`; view types are
`list`, `form`, `card` (kanban cards and calendar popovers; JS009), `calendar`, `hierarchy`. Props
received: the `extractProps` result plus `name`, `record`, `readonly` (and `id`).

Source: addons/web/static/src/views/fields/field.js (validation, getFieldFromRegistry,
fieldComponentProps), addons/web/static/src/views/fields/badge/badge_field.js (fieldDependencies function)

## Record API used by fields

`this.props.record` is a `Record` from `@web/model/relational_model/record` (reactive).

| Member | Use |
|---|---|
| `data[fieldName]` | current value; many2one is `{ id, display_name }` or `false`; x2many is a list datapoint (`.records`, `.resIds`) |
| `fields[fieldName]` | field definition (`type`, `string`, `relation`, `selection`, `size`, `trim`, ...) |
| `update({ field: value })` | write the change (triggers onchanges); saves immediately when the record is not in edition |
| `save()`, `discard()`, `urgentSave()`, `isDirty()` | persistence |
| `resId`, `resModel`, `isNew`, `isInEdition`, `dirty` | state |
| `evalContext`, `evalContextWithVirtualIds` | context for evaluating arch expressions |
| `setInvalidField(name)`, `resetFieldValidity(name)`, `isFieldInvalid(name)` | validity feedback |
| `isFieldTranslatable(name)`, `model` (`model.orm`, `model.root`) | misc |

Source: addons/web/static/src/model/relational_model/record.js,
addons/web/static/src/model/relational_model/datapoint.js, addons/web/static/src/model/relational_model/utils.js

## Field hooks

| Hook | Import | Use |
|---|---|---|
| `useInputField({ ref, getValue, parse?, preventLineBreaks?, fieldName?, shouldSave? })` | `@web/views/fields/input_field_hook` | for `<input>`/`<textarea>` fields: commits on change, keeps the typed value during onchanges, handles urgent save. `ref` is a `signal.ref()` |
| `useRecordObserver((record) => {...})` | `@web/model/relational_model/utils` | runs now (awaited in `onWillStart` if async) and again whenever what it read on the record changes (implemented with `useEffect`) |
| `useSpecialData(loadFn)` | `@web/views/fields/relational_utils` | cached extra load for a field (read the source for the `loadFn` contract) |
| `useDynamicPlaceholder(inputRef)` | `@web/views/fields/dynamic_placeholder_hook` | `{{object.x}}` placeholder popover (see `CharField`) |

```javascript
input = signal.ref();
setup() {
    useInputField({ ref: this.input, getValue: () => this.props.record.data[this.props.name] || "" });
}
// template: <input class="o_input" t-ref="this.input" t-att-readonly="this.props.readonly"/>
```

Source: addons/web/static/src/views/fields/input_field_hook.js,
addons/web/static/src/views/fields/char/char_field.js, addons/web/static/src/model/relational_model/utils.js:761

## View widgets

`<widget name="web_ribbon" title="Archived" bg_color="text-bg-danger" invisible="active"/>` renders
an entry of `view_widgets`. Props: `record`, `readonly`, plus `extractProps(widgetInfo, { readonly })`
where `widgetInfo` has `name`, `options`, `attrs`.

```javascript
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

export class RibbonWidget extends Component {
    static template = "web.Ribbon";
    props = useProps({ ...standardWidgetProps, text: t.string(), bgClass: t.string().optional("text-bg-success") });
}
registry.category("view_widgets").add("web_ribbon", {
    component: RibbonWidget,
    extractProps: ({ attrs }) => ({ text: attrs.title || attrs.text, bgClass: attrs.bg_color }),
});
```

Source: addons/web/static/src/views/widgets/ribbon/ribbon.js, addons/web/static/src/views/widgets/widget.js,
addons/web/static/src/views/widgets/standard_widget_props.js

## Extending a view with js_class

Arch: `<list js_class="hr_expense_tree">` (same for `form`, `kanban`, ...). JS: spread the core view
definition and replace pieces.

```javascript
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";

export class ExpenseListController extends ListController {
    static template = "hr_expense.ListView";
    setup() {
        super.setup();
        this.actionService = useService("action");
    }
}
registry.category("views").add("hr_expense_tree", {
    ...listView,
    Controller: ExpenseListController,
    buttonTemplate: "hr_expense.ListButtons",   // t-inherit="web.ListView.Buttons" t-inherit-mode="primary"
});
```

| Replace | Core classes (import path) |
|---|---|
| `Controller` | `FormController` (`@web/views/form/form_controller`), `ListController` (`@web/views/list/list_controller`), `KanbanController` (`@web/views/kanban/kanban_controller`) |
| `Renderer` | `FormRenderer`, `ListRenderer` (+ `listRendererProps`), `KanbanRenderer` |
| `Model` | `RelationalModel` (`@web/model/relational_model/relational_model`) or a subclass |
| `SearchModel`, `SearchPanel`, `ArchParser`, `Compiler`, `buttonTemplate` | as needed |

- The registry key is the `js_class` value; `type` stays the base view type.
- Graph and pivot live in `web.assets_backend_lazy`: a `js_class` extending them must be declared
  in that bundle (see [assets.md](assets.md#lazy-loading)).
- Shared state for the controller subtree: `providePlugins([MyPlugin])` in the controller `setup`
  (`addons/hr_holidays/static/src/views/kanban/kanban_controller.js`).

Source: simplified from addons/hr_expense/static/src/views/list.js (+ list.xml),
addons/hr_holidays/static/src/views/kanban/kanban_view.js, addons/web/static/src/views/form/form_view.js

## New view type

Python side (the JS `views` registry rejects a `type` missing from `session.view_info`):

```python
class IrUiView(models.Model):
    _inherit = 'ir.ui.view'
    type = fields.Selection(selection_add=[('hierarchy', "Hierarchy")])

    def _get_view_info(self):
        return {'hierarchy': {'icon': 'family_history'}} | super()._get_view_info()   # Material icon name

class IrActionsAct_WindowView(models.Model):
    _inherit = 'ir.actions.act_window.view'
    view_mode = fields.Selection(selection_add=[('hierarchy', 'Hierarchy')], ondelete={'hierarchy': 'cascade'})
```

Add arch validation with `_validate_tag_<type>` (see the hierarchy module). JS side:

```javascript
export const hierarchyView = {
    type: "hierarchy",
    ArchParser: HierarchyArchParser,      // class with parse(arch, relatedModels, resModel)
    Controller: HierarchyController,      // props: ...standardViewProps (@web/views/standard_view_props)
    Model: HierarchyModel,                // extends Model (@web/model/model), used via useModel()
    Renderer: HierarchyRenderer,
    buttonTemplate: "web_hierarchy.HierarchyButtons",
    searchMenuTypes: ["filter"],
    props: (genericProps, view) => ({
        ...genericProps,
        archInfo: new view.ArchParser().parse(genericProps.arch, genericProps.relatedModels, genericProps.resModel),
        buttonTemplate: genericProps.buttonTemplate || view.buttonTemplate,
        Model: view.Model,
        Renderer: view.Renderer,
    }),
};
registry.category("views").add("hierarchy", hierarchyView);
```

- Controller: `this.model = useModel(this.props.Model, {...})` (`@web/model/model`), wrap in
  `<Layout>` (`@web/search/layout`), `useSetupAction({ rootRef, getLocalState })`
  (`@web/search/action_hook`).
- Model: `class M extends Model { static services = []; setup(params, services) {...}; async load(searchParams) {...} }`;
  `this.orm` is provided; call `this.notify()` to re-render.

Source: addons/web_hierarchy/models/ir_ui_view.py, addons/web_hierarchy/models/ir_actions.py,
addons/web_hierarchy/static/src/hierarchy_view.js, addons/web_hierarchy/static/src/hierarchy_controller.js,
addons/web/static/src/model/model.js, addons/web/models/ir_ui_view.py

## Client actions

```xml
<record id="action_reset_linked_printers" model="ir.actions.client">
    <field name="name">reset.linked.printers</field>
    <field name="path">reset-printers</field>
    <field name="tag">reset_linked_printers</field>
</record>
```

```javascript
import { Component, onWillStart, proxy, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_plugin";

class ReportPrintersLocalStorage extends Component {
    static template = "printer.ReportPrintersLocalStorage";
    props = useProps(standardActionServiceProps);   // action, actionId?, className?, state?, ...
    setup() {
        this.orm = useService("orm");
        this.state = proxy({ reports: [] });
        onWillStart(async () => {
            this.state.reports = await this.orm.searchRead("ir.actions.report", [], ["name"]);
        });
    }
}
registry.category("actions").add("reset_linked_printers", ReportPrintersLocalStorage);
```

- Read params with `this.props.action.params` / `this.props.action.context`; navigate back with
  `this.env.config.historyBack()`; set the breadcrumb title with `this.env.config.setDisplayName(...)`.
- A function action `(env, action, options) => next` is allowed (runs in a scope, `useService` works):
  `addons/web/static/src/webclient/actions/client_actions.js`.

Source: adapted from addons/printer/static/src/client_actions/reset_cached_printers.js, addons/printer/views/printer_views.xml,
addons/hr_attendance/static/src/views/badge_scanner/badge_scanner.js

## Patch

`patch(target, extension)` from `@web/core/utils/patch` returns an `unpatch` function. Patch
`Class.prototype` for methods/getters, `Class` itself for statics; use `super.method(...arguments)`.

```javascript
import { patch } from "@web/core/utils/patch";
import { providePlugins, t, usePlugin, useProps } from "@odoo/owl";

patch(PortalChatter.prototype, {
    setup() {
        super.setup(...arguments);
        providePlugins([PortalRatingPlugin]);
        this.portalChatterProps = useProps({ reviewChatter: t.any().optional() }); // extra prop
        usePlugin(PortalRatingPlugin).reviewChatter.set(this.portalChatterProps.reviewChatter ?? false);
    },
});
patch(AttachmentList, { components: { ...AttachmentList.components, VoicePlayer } });
```

- Class fields (`props = useProps(...)`, `rootRef = signal.ref()`, `orm = usePlugin(ORM)`) are
  instance properties: a prototype patch cannot replace them; add what you need in `setup()`.
- An added prop is not on `this.props` (only declared keys are): call `useProps({...})` again as above.
- Patching is discouraged inside Odoo itself and acceptable in custom addons, but prefer an
  extension point first (`js_class`, registry entry, subclass + `force: true`):
  [Avoid patching JavaScript code](../../odoo-web-guidelines/guidelines/javascript.md#avoid-patching-javascript-code).

Source: addons/web/static/src/core/utils/patch.js, addons/portal_rating/static/src/chatter/portal/portal_chatter_patch.js,
addons/mail/static/src/discuss/voice_message/common/attachment_list_patch.js

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `static props = { ...standardFieldProps }` | `props = useProps({ ...standardFieldProps })` (JS001) | addons/web/static/src/views/fields/standard_field_props.js |
| `useRef("input")` + `useInputField({ refName: "input" })` | `input = signal.ref()` + `useInputField({ ref: this.input })` | addons/web/static/src/views/fields/char/char_field.js |
| `kanban.many2many_tags` keys | `card.many2many_tags` (JS009) | addons/web/static/src/views/card/card_arch_parser.js |
| widgets `selection_badge`, `remaining_days` | `badges_selection`, `relative_date` (XML015) | addons/web/static/src/views/fields |
| `standardActionServiceProps` from `action_service` | from `@web/webclient/actions/action_plugin` | addons/web/static/src/webclient/actions/action_plugin.js |
| `_get_view_info` icon `fa-sitemap` | Material Symbols name (`family_history`) | addons/web_hierarchy/models/ir_ui_view.py |
| graph/pivot `js_class` in `web.assets_backend` | `web.assets_backend_lazy` | addons/web/__manifest__.py |
