# Website snippets and builder options (Odoo 20)

How to ship a website snippet (QWeb template + panel entry + public JS) and its options in the Odoo 20
website builder (`html_builder` + `website`). In v20 options are **declared in an XML template**
(`website.BuilderOptions`), not in a plugin `builder_options` resource as in v19.

## Contents
- [Pieces of a snippet](#pieces-of-a-snippet)
- [Snippet template and panel entry](#snippet-template-and-panel-entry)
- [Declaring options: website.BuilderOptions](#declaring-options-websitebuilderoptions)
- [Option templates and building blocks](#option-templates-and-building-blocks)
- [Option components (BaseOptionComponent)](#option-components-baseoptioncomponent)
- [Builder plugins and actions](#builder-plugins-and-actions)
- [Registries and bundles](#registries-and-bundles)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## Pieces of a snippet

| Piece | File (convention) | Registered via |
|---|---|---|
| HTML of the block | `views/snippets/s_my_block.xml` (`<template id="s_my_block">`) | manifest `data` |
| Entry in the snippet panel | `<template inherit_id="website.snippets">` + `t-snippet` | manifest `data` |
| Public behaviour | `static/src/snippets/s_my_block/my_block.js` (Interaction) | `public.interactions`, see [interactions.md](interactions.md) |
| Edit-mode behaviour | `static/src/snippets/s_my_block/my_block.edit.js` | `public.interactions.edit` |
| Option panel | `static/src/website_builder/my_block_option.xml` (+ `.js`) | `website.BuilderOptions` extension, `builder-options` / `website-options` |
| Custom actions | `static/src/website_builder/my_block_option_plugin.js` | `website-plugins` (or `builder-plugins`) |
| Styles | `static/src/snippets/s_my_block/000.scss` | `web.assets_frontend` (or `<asset>` records) |

Source: addons/website/views/snippets/s_alert.xml, addons/website/static/src/snippets/s_countdown,
addons/website_sale/__manifest__.py

## Snippet template and panel entry

```xml
<!-- addons/website/views/snippets/s_alert.xml (shape) -->
<template id="s_my_block" name="My Block">
    <section class="s_my_block o_cc o_cc1 pt48 pb48">
        <div class="container">
            <h2>Title</h2>
            <i class="oi" data-icon="info"/>
        </div>
    </section>
</template>

<!-- panel entry; same pattern as addons/test_website/views/templates.xml -->
<template id="snippets" inherit_id="website.snippets">
    <xpath expr="//snippets[@id='snippet_structure']" position="inside">
        <t t-snippet="my_module.s_my_block" string="My Block" group="content">
            <keywords>banner, promo</keywords>
        </t>
    </xpath>
</template>
```

- Containers in `website.snippets`: `snippet_groups` (category tiles), `snippet_structure` (blocks, need
  `group="intro|columns|content|images|people|text|contact_and_forms|social|ecommerce|..."`),
  `snippet_content` (inner content, takes `t-thumbnail`), `snippet_custom`.
- Useful `t-snippet` attributes seen in core: `string`, `group`, `label`, `t-thumbnail`,
  `t-image-preview`, `t-drag-image-preview`, `t-forbid-sanitize`, `t-grid-column-span`; `t-install="module"`
  shows an "install" placeholder.
- Hooks for third-party modules: `//t[@id='installed_snippets_hook']` (new category), plus many
  `*_hook` placeholders replaced by the owning module (e.g. `snippet_add_to_cart_hook`).
- Icons are Material Symbols (`<i class="oi" data-icon="name"/>`), not Font Awesome (XML004).
- Versioned snippet SCSS is shipped as `<asset>` records (`website.s_alert_001_scss` in s_alert.xml).

Source: addons/website/views/snippets/snippets.xml, addons/website/views/snippets/s_alert.xml,
addons/website_event/views/snippets/snippets.xml, addons/test_website/views/templates.xml:95

## Declaring options: website.BuilderOptions

The options panel is computed by rendering the OWL template `website.BuilderOptions`
(`website.TranslationBuilderOptions` in translation mode). Each child element is one option: the
**tag name is the option id** (snake_case) and attributes configure it.

| Attribute | Meaning |
|---|---|
| `selector` | Required. Elements the option applies to. |
| `exclude` | Elements to skip. |
| `applyTo` | Sub-element (relative selector, e.g. `:scope > .row`) actually edited. |
| `template` | Option template name, only when no JS class is registered for this tag. |
| `title` | Panel section title (page-level options). |
| `editableOnly="false"` | Option also works outside editable zones (header/footer/page options). |
| `groups='["website.group_website_designer"]'` | JSON list of required groups. |
| `reloadTarget="true"` | Reloading actions re-render this option's `selector` (default region: header/main/footer). |
| `props='{ "level": 0 }'` | JSON props passed to the option component. |
| `t-att-*`, `t-attf-*` | Dynamic values from the render context (`builder_options_render_context` resources). |

Anchors: `context_hook` (extra `t-set` values for the template), then placement anchors in display
order: `page_options_hook`, `top_options_hook`,
`background_options`, `image_options`, `key_snippet_specific_options`, `snippet_specific_options`
(default), then animation/visibility, then `bottom_options_hook`.

```xml
<!-- my_module/static/src/website_builder/my_block_option.xml -->
<templates xml:space="preserve">
<t t-name="my_module.MyBlockOption">
    <BuilderRow label.translate="Style">
        <BuilderSelect>
            <BuilderSelectItem classAction="'text-bg-primary'">Primary</BuilderSelectItem>
            <BuilderSelectItem classAction="'text-bg-dark'">Dark</BuilderSelectItem>
        </BuilderSelect>
    </BuilderRow>
    <BuilderRow label.translate="Radius">
        <BuilderNumberInput styleAction="'border-radius'" unit="'px'" min="0"/>
    </BuilderRow>
</t>

<t t-inherit="website.BuilderOptions" t-inherit-mode="extension">
    <xpath expr="//t[@id='snippet_specific_options']" position="after">
        <my_block_option template="my_module.MyBlockOption" selector=".s_my_block"/>
    </xpath>
</t>
</templates>
```

Validation (`validateOptionDeclaration`): `selector` is mandatory; without a JS class `template` is
mandatory; with a JS class the template must be on the class and `selector/exclude/applyTo/title/
groups` must stay in the XML (an error is thrown otherwise).

Source: addons/website/static/src/builder/website_options.xml,
addons/html_builder/static/src/core/builder_options_plugin.js (computeBuilderOptionsFromTemplate,
validateOptionDeclaration, getOptionAttributes), addons/html_builder/static/src/plugins/badge_option.xml,
addons/website_sale/static/src/website_builder/website_sale_options.xml

## Option templates and building blocks

Option templates are OWL 3 templates: component members need `this.` (OWL005), slots/props follow
[owl3-core.md](../../owl/references/owl3-core.md). The building blocks are injected automatically
(`builderComponents` plugin): `BuilderRow`, `BuilderSelect`, `BuilderSelectItem`, `BuilderButtonGroup`,
`BuilderButton`, `BuilderCheckbox`, `BuilderNumberInput`, `BuilderTextInput`, `BuilderRange`,
`BuilderColorPicker`, `BuilderUrlPicker`, `BuilderDateTimePicker`, `BuilderFontFamilyPicker`,
`BuilderMany2One`, `BuilderMany2Many`, `ModelMany2Many`, `BuilderList`, `BuilderContext`,
`BuilderOptionsSection`, `BuilderSlidingPanel`, `BuilderSearchSelect`, `Dropdown`, `DropdownItem`.

Common action props (all are JS expressions, so quote strings: `classAction="'w-50'"`):

| Prop | Effect |
|---|---|
| `classAction` (+ `classActionValue`) | Toggle CSS class(es) |
| `styleAction` (+ `unit`, `styleActionValue`) | Set an inline style |
| `attributeAction` + `attributeActionValue` | Set an attribute |
| `dataAttributeAction` + `dataAttributeActionValue` | Set a `data-*` attribute |
| `action` + `actionParam` / `actionValue` | Run a custom `BuilderAction` by id |
| `applyTo`, `id`, `preview`, `inheritedActions`, `inverseAction` | Target sub-element, name the item for `this.isActiveItem(id)`, disable preview, ... |

`label.translate="..."` / `title.translate="..."` mark translatable literal props.

```xml
<!-- addons/website/static/src/builder/plugins/options/clickable_card_option.xml -->
<BuilderRow label.translate="Make it clickable">
    <BuilderCheckbox id="'is_clickable_opt'" action="'setCardClickable'" preview="false"/>
</BuilderRow>
<t t-if="this.isActiveItem('is_clickable_opt')">
    <BuilderRow label.translate="Your URL" level="1">
        <BuilderUrlPicker action="'setCardAnchorUrl'" preview="false"/>
    </BuilderRow>
</t>
```

Source: addons/html_builder/static/src/core/builder_component_plugin.js,
addons/html_builder/static/src/core/utils.js:1453 (basicContainerBuilderComponentProps,
clickableBuilderComponentProps), addons/html_builder/static/src/plugins/separator_option.xml

## Option components (BaseOptionComponent)

Add a JS class only when the option needs state or logic. The class gives the template, the XML still
gives the selector.

```javascript
// addons/website/static/src/builder/plugins/options/clickable_card_option.js
import { useDomState } from "@html_builder/core/utils";
import { registry } from "@web/core/registry";
import { BaseOptionComponent } from "@html_builder/core/base_option_component";

export class ClickableCardOption extends BaseOptionComponent {
    static id = "clickable_card_option";          // = XML tag name
    static template = "website.ClickableCardOption";

    setup() {
        super.setup();
        this.state = useDomState((editingElement) => ({
            hasHref: editingElement.querySelector(":scope > a.stretched-link")?.hasAttribute("href"),
        }));
    }
}
registry.category("builder-options").add(ClickableCardOption.id, ClickableCardOption);
```

- `BaseOptionComponent` exposes `this.document`, `this.window`, `this.editable`, `this.config`,
  `this.services`, `this.dependencies` (plugin shared methods, list them in `static dependencies`),
  `this.getResource`, `this.trigger`, `this.delegateTo`, `this.processThrough`, `this.checkPredicates`,
  `this.isActiveItem(id)`, `this.isActiveItems(ids)`.
- `useDomState(getState)` (from `@html_builder/core/utils`) recomputes from the editing element after
  each DOM change; async getters are allowed (`website_sale` ProductTemplateOption).
- `static editableOnly = true` by default; set `editableOnly="false"` in XML, never on the class.

Source: addons/html_builder/static/src/core/base_option_component.js,
addons/html_builder/static/src/core/utils.js:51, addons/website_sale/static/src/website_builder/product_template_option.js

## Builder plugins and actions

Builder plugins are **html_editor plugins** (`Plugin` from `@html_editor/plugin`, see
[html-editor.md](html-editor.md)), not OWL plugins. They contribute `resources`:

```javascript
// addons/website/static/src/builder/plugins/options/clickable_card_option_plugin.js
import { BuilderAction } from "@html_builder/core/builder_action";
import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";

export class ClickableCardOptionPlugin extends Plugin {
    static id = "clickableCardOptionPlugin";
    resources = {
        builder_actions: { SetCardClickableAction },
        is_empty_link_legit_predicates: (linkEl) => linkEl.matches("a.stretched-link[href]") || undefined,
    };
}

class SetCardClickableAction extends BuilderAction {
    static id = "setCardClickable";                 // used as action="'setCardClickable'"
    apply({ editingElement }) {
        const anchorEl = document.createElement("a");
        anchorEl.classList.add("stretched-link");
        editingElement.prepend(anchorEl);
    }
    clean({ editingElement }) {
        editingElement.querySelector(":scope > a.stretched-link")?.remove();
    }
    isApplied({ editingElement }) {
        return !!editingElement.querySelector(":scope > a.stretched-link");
    }
}
registry.category("website-plugins").add(ClickableCardOptionPlugin.id, ClickableCardOptionPlugin);
```

`BuilderAction` methods: `setup()`, `async prepare(ctx)`, `getPriority(ctx)`, `async load(ctx)` (no
side effects; result passed as `loadResult`), `async apply({ editingElement, value, params, loadResult,
isPreviewing })`, `async clean(ctx)`, `isApplied(ctx)` (buttons/selects), `getValue(ctx)` (inputs).
`params.mainParam` holds a non-object `actionParam`. Instance flags: `preview`, `reload`,
`withLoadingEffect`, `loadOnClean`. Action ids must be unique ("Duplicate builder action id").

Frequently used builder resources (v20 names, plural):

| Resource | Value |
|---|---|
| `builder_actions` | `{ ActionClass, ... }` |
| `builder_options_render_context` | `{ name: value }` exposed to `website.BuilderOptions` (`t-att-selector="this.name"`) |
| `so_snippet_addition_selectors` / `so_content_addition_selectors` | where snippets / inner content can be dropped |
| `dropzone_selectors` | `{ selector, dropIn, dropNear, ... }` |
| `is_unremovable_selectors`, `system_node_selectors` | protect nodes |
| `clone_disabled_reason_providers`, `remove_disabled_reason_providers` | disable clone/remove with a reason |

Source: addons/html_builder/static/src/core/builder_action.js, addons/html_builder/static/src/core/builder_actions_plugin.js,
addons/html_builder/static/src/core/dropzone_selector_plugin.js, addons/html_builder/static/src/plugins/alert_option_plugin.js,
addons/website_sale/static/src/website_builder/product_template_option_plugin.js

## Registries and bundles

| Registry | Content | Loaded by |
|---|---|---|
| `builder-plugins` | generic builder plugins (html_builder) | website builder + other builders |
| `website-plugins` | website-only builder plugins | `WebsiteBuilder.builderProps` |
| `translation-plugins` | plugins active in translation mode | `WebsiteBuilder.builderProps` |
| `builder-options` | generic option classes, key = `static id` | `computeBuilderOptionsFromTemplate` |
| `website-options` | website-only option classes (merged over `builder-options`) | `config.builderOptionsRegistry` |

```python
'assets': {
    'website.website_builder_assets': [
        'my_module/static/src/website_builder/**/*',
        ('remove', 'my_module/static/src/**/*.edit.*'),
    ],
    'website.assets_inside_builder_iframe': [
        'my_module/static/src/**/*.edit.*',
    ],
    'web.assets_frontend': ['my_module/static/src/snippets/**/*.js'],
},
```

`website.website_builder_assets` is lazy-loaded with the editor (includes `html_builder.assets`); the
option XML must live there so it can extend `website.BuilderOptions`. Verify with `odoo_assets` and
search core examples with `odoo_grep "website.BuilderOptions"`. Builder Hoot helpers:
`setupWebsiteBuilder`, `setupWebsiteBuilderWithSnippet` in `website/static/tests/builder/website_helpers.js`.

Source: addons/website/static/src/builder/website_builder.js:197, addons/website/__manifest__.py:518,
addons/website_sale/__manifest__.py, addons/html_builder/__manifest__.py

## v19 habit -> Odoo 20

| v19 | Odoo 20 | Source |
|---|---|---|
| `resources.builder_options: [withSequence(before(WIDTH), MyOption)]` | `<my_option .../>` in a `website.BuilderOptions` extension; class in `builder-options`/`website-options` | addons/website/static/src/builder/website_options.xml |
| `static selector = ".s_x"` / `static name` on the option class | `selector=` in XML; class has `static id` + `static template` | addons/html_builder/static/src/core/builder_options_plugin.js |
| `@html_builder/utils/option_sequence`, `website/static/src/builder/option_sequence.js` | removed; place options with XML anchors | addons/website/static/src/builder |
| `import { BaseOptionComponent } from "@html_builder/core/utils"` | `@html_builder/core/base_option_component` | addons/html_builder/static/src/core/base_option_component.js |
| `so_content_addition_selector`, `so_snippet_addition_selector`, `dropzone_selector`, `is_unremovable_selector` | plural: `..._selectors` | addons/html_builder/static/src/core/dropzone_selector_plugin.js |
| `patch_builder_options` resource | removed (extend the XML template) | addons/html_builder/static/src/core/builder_options_plugin.js |
| `this.dispatchTo("x_handlers")` in plugins/options | `this.trigger(...)` (see html-editor.md) | addons/html_editor/static/src/editor.js |
| Font Awesome in snippets / `fa-` in actions | `<i class="oi" data-icon="..."/>`, `icon="'name'"` (XML004, JS015) | addons/html_builder/static/src/plugins/separator_option.xml |
