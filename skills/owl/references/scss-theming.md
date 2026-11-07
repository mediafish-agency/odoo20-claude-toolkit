# SCSS and theming (Odoo 20)

How Odoo 20 compiles SCSS, which `$o-*` variables and Bootstrap 5.3.3 utilities you can rely on, the
new color palettes, gradient/backdrop-blur hooks, dark mode (`*.dark.scss`) and the `--o-*` CSS custom
properties. Formatting, class prefixes (`o_<module>`) and variable naming are house rules:
[SCSS and CSS guideline](../../odoo-web-guidelines/guidelines/scss.md#scss-and-css). Do not restate them.

## Contents

- [Compilation model](#compilation-model)
- [Overriding variables](#overriding-variables)
- [Key `$o-*` variables](#key-o-variables)
- [Color palettes](#color-palettes)
- [Gradients and backdrop blur (opt-in)](#gradients-and-backdrop-blur-opt-in)
- [Bootstrap and Odoo utilities](#bootstrap-and-odoo-utilities)
- [Dark mode](#dark-mode)
- [Print styles](#print-styles)
- [CSS custom properties](#css-custom-properties)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## Compilation model

All `.scss` files of one bundle are concatenated in bundle order and compiled in **one** libsass pass.
A variable is visible to every file after its definition, in that bundle only. Backend order
(`web.assets_backend`):

1. `web._assets_helpers`: Bootstrap `_functions`/`_mixins`, Odoo `functions.scss`,
   `mixins_forwardport.scss`, `bs_mixins_overrides.scss`, `utils.scss`, then
   `web._assets_primary_variables` (`primary_variables.scss` + `web/static/src/**/*.variables.scss`
   + what addons append) and `web._assets_secondary_variables` (`secondary_variables.scss` + addons).
2. `web._assets_backend_helpers`: `bootstrap_overridden.scss`, `bs_mixins_overrides_backend.scss`.
3. `pre_variables.scss`, Bootstrap `_variables.scss`, `_variables-dark.scss`, `_maps.scss`.
4. `web._assets_bootstrap_backend`: `import_bootstrap.scss`, `utilities_custom.scss`,
   `utilities_custom_backend.scss`, Bootstrap `utilities/_api.scss`, `bootstrap_review.scss`,
   `bootstrap_review_backend.scss`.
5. `web._assets_core` and every component's `.scss` (yours included).

Frontend swaps step 2 for `web._assets_frontend_helpers` (`bootstrap_overridden_frontend.scss`) and step
4 for `web._assets_bootstrap_frontend`.

Helpers you can call anywhere after step 1: `o-to-rem($-px-value)`, `@include o-print-color($-color, $-rule,
$-css-opacity-var)`, `@include o-position-absolute($top, $right, $bottom, $left)`,
`@include o-hover-text-color(...)`, Bootstrap `media-breakpoint-up/down(...)`, and
`@include material-icon-base` from `webclient/icons.scss` (see [icons.md](icons.md)).

Source: addons/web/__manifest__.py:46-60, addons/web/__manifest__.py:350-406, odoo/addons/base/models/assetsbundle.py:611-649, addons/web/static/src/scss/functions.scss:30-48, addons/web/static/src/scss/utils.scss:20

## Overriding variables

Almost every variable is declared `!default`: the **first** `!default` assignment wins, a plain
assignment (no `!default`) always overrides what came before.

| Goal | Put the file in | Write |
|---|---|---|
| New variables for your addon | `web._assets_primary_variables` | `$o-my-addon-x: 4px !default;` |
| Change an existing `$o-*` value | `('before', 'web/static/src/scss/primary_variables.scss', 'my/...variables.scss')` in `web._assets_primary_variables` | `$o-brand-primary: #0d6efd !default;` |
| Change a Bootstrap variable (backend) | `web._assets_backend_helpers` | plain `$border-radius-lg: 4px;` (it runs after `bootstrap_overridden.scss`) |
| Change a Bootstrap variable (frontend) | `('prepend', ...)` in `web._assets_frontend_helpers` | `!default` form (core: html_editor) |
| Contextual tweak of one component | your component `.scss` | override its CSS variable on a scoped selector |

Changing `$o-*` values globally affects every addon; prefer CSS variables on your own selectors.

Source: addons/account/__manifest__.py:99, addons/html_editor/__manifest__.py:18-20, addons/html_editor/__manifest__.py:108-117, addons/web/static/src/scss/bootstrap_overridden.scss

## Key `$o-*` variables

| Variable | Default (community) |
|---|---|
| `$o-brand-primary`, `$o-brand-odoo` | `$o-community-color` = `#71639e` (`$o-enterprise-color: #714B67`) |
| `$o-action` | `$o-brand-primary` |
| `$o-success`, `$o-info`, `$o-warning`, `$o-danger` | `#28a745`, `#17a2b8`, `#ffac00`, `#dc3545` |
| `$o-gray-100` .. `$o-gray-900`, `$o-white`, `$o-black` | Bootstrap grays |
| `$o-font-size-base` / `-touch` / `-small` / `-smaller` | `o-to-rem(14px)` / 16 / 13 / 12 px |
| `$o-border-color` (new) | `$o-gray-300`; feeds Bootstrap `$border-color` |
| `$o-border-radius-sm/-lg/-xl` (`-xl` new) | 3px / 6px / 12px |
| `$o-view-background-color` | `#FFFFFF` |
| `$o-modal-sm` (new) / `$o-modal-md` | 460px / 620px (was 650px) |
| `$o-modal-animation-duration` (new) | `.4s` |
| `$o-form-check-input-border-color` (new) | `$o-gray-500` |
| `$o-breadcrumb-item-padding-x` | `.25rem` (was `.5rem`) |
| `$o-opacities` | `0 25 50 75 100 disabled muted` (feeds `.opacity-*`) |
| `$o-webclient-color-scheme` | `bright` (also exposed as `--o-webclient-color-scheme`) |

Button maps `$o-btns-bs-override` / `$o-btns-bs-outline-override`: each entry is passed as-is to the
Bootstrap mixin and "all states must be defined". v20 added `disabled-background`, `disabled-border`,
`disabled-color` to every entry: a custom entry without them breaks compilation.

Removed (validator SCSS002): `$o-touch-btn-padding`, `$o-touch-btn-with-icon-padding`.

Source: addons/web/static/src/scss/primary_variables.scss, addons/web/static/src/scss/bootstrap_overridden.scss:33-125, addons/web/static/src/webclient/webclient.scss:2

## Color palettes

| Variable | Use |
|---|---|
| `$o-colors` (12 colors, now in `primary_variables.scss`) | base palette, index 0..11 = record `color` field |
| `$o-colors-border`, `$o-colors-bg-subtle`, `$o-colors-text-emphasis` (new, OKLCH-generated) | tag and badge colors |
| `$o-colors-ui` (new) | map `color-1`..`color-12` built from `$o-colors`, merged into Bootstrap `$theme-colors` in the backend |
| `$o-colors-secondary`, `$o-colors-complete` | extended picker palette (`secondary_variables.scss`) |

Classes driven by the palettes: `.o_tag.o_tag_color_N`, `.badge.o_badge_color_N`,
`.o_colorlist_item_color_N` (N = 0..11). Because `$theme-colors` gains `color-1..12`, backend loops
over `$theme-colors` (buttons, `bg-*`) also emit those names. Reuse the palette with
`nth($o-colors-bg-subtle, $index)` rather than hard-coding hex values.

Source: addons/web/static/src/scss/primary_variables.scss:75-101, addons/web/static/src/scss/secondary_variables.scss, addons/web/static/src/scss/bootstrap_overridden.scss:41-50, addons/web/static/src/core/badge/badge.scss, addons/web/static/src/core/tags_list/tags_list.scss, addons/web/static/src/scss/bootstrap_review_backend.scss:82-160

## Gradients and backdrop blur (opt-in)

Both are hooks that are **off** in community.

```scss
// my_theme.variables.scss, inserted 'before' web/static/src/scss/primary_variables.scss
// in web._assets_primary_variables (the $o-* defaults are all `null !default`)
$o-gradient: linear-gradient(180deg, rgba(255, 255, 255, .15), rgba(255, 255, 255, 0)) !default;
$o-gradient-sm: $o-gradient !default;
$o-gradient-lg: $o-gradient !default;
$o-gradient-btn: $o-gradient !default;   // printed as --gradient on .btn

// bootstrap_overridden.scss of your addon, in web._assets_backend_helpers
$enable-gradients: true;                 // Bootstrap switch, false by default
```

- With `$enable-gradients`, the backend defines `:root { --o-gradient, --o-gradient-sm, --o-gradient-lg }`
  and the utilities `.bg-gradient`, `.bg-gradient-sm`, `.bg-gradient-lg`. `$o-gradient-btn` feeds the
  `--gradient` custom property of `.btn` (backend).
- `$o-enable-backdrop-blur: true` defines `--o-backdrop-blur(-sm|-lg)` and the classes
  `.backdrop-blur`, `.backdrop-blur-sm`, `.backdrop-blur-lg`, **but** `$o-backdrop-blur`,
  `$o-backdrop-blur-sm`, `$o-backdrop-blur-lg` are not defined anywhere in community: define all
  three (e.g. `blur(8px)`) in a primary-variables file or compilation fails.
- Core already reads `var(--o-backdrop-blur-sm)` (list sticky header, activity view): undefined
  variable = no blur, so it is safe when the feature is off.

Source: addons/web/static/src/scss/primary_variables.scss:15-16, addons/web/static/src/scss/primary_variables.scss:130-135, addons/web/static/src/scss/utilities_custom_backend.scss:34-81, addons/web/static/src/scss/bootstrap_review_backend.scss:11-19, addons/web/static/lib/bootstrap/scss/_variables.scss:373, addons/web/static/src/views/list/list_renderer.scss:100

## Bootstrap and Odoo utilities

Bootstrap is **5.3.3**. In the backend the CSS variable prefix is empty (`$variable-prefix: ''` in
`bootstrap_overridden.scss`): write `var(--primary)`, `var(--border-color)`, `var(--body-bg)`, not
`var(--bs-primary)`. Check the frontend bundle before assuming either prefix there.

Odoo additions (`utilities_custom.scss`, backend extras in `utilities_custom_backend.scss`):

| Class | Effect |
|---|---|
| `.cursor-default`, `.cursor-pointer` | cursor |
| `.bg-opacity-{0,25,50,75,100,disabled,muted}` | sets the `--bg-opacity` used by `bg-*` |
| `.opacity-{key}-hover` + `.opacity-trigger-hover` on a parent | opacity on hover/focus-visible |
| `.flex-basis-{0,25,50,75,100,auto}` (responsive) | flex-basis |
| `.transition-none`, `.transition-base`, `.transition-fade` | transition presets |
| `.min-w-0` | `min-width: 0` |
| `.text-prewrap`, `.d-contents`, `.border-transparent`, responsive `.position-*` | Bootstrap maps extended |
| `.d-empty-none` | hide when `:empty` |
| `.smaller` | `$o-font-size-base-smaller` |
| `.o_line_clamp` (+ `.o_line_clamp_{1,3,5,7,10}` or `--lines-clamp`) | multi-line truncation |

Backend specifics: `text-*` utilities are limited to `text-body`, `text-muted`, `text-reset` plus the
theme text colors from `bootstrap_review_backend.scss`; the generic `bg-*` utility is disabled and
regenerated there with `o-print-color` (so `--bg-opacity` works).

Source: addons/web/static/lib/bootstrap/js/dist/base-component.js:24, addons/web/static/src/scss/bootstrap_overridden.scss:63, addons/web/static/src/scss/utilities_custom.scss, addons/web/static/src/scss/utilities_custom_backend.scss:5-32, addons/web/static/src/scss/bootstrap_review_backend.scss

## Dark mode

Dark mode is a **bundle swap**, not a CSS media query or `data-bs-theme`: when
`ir.http.color_scheme()` returns `'dark'`, the page loads `web.assets_web_dark` (= `web.assets_web` +
every `*.dark.scss`) instead of `web.assets_web` for CSS. Community's `color_scheme()` returns
`'light'`; the toggle comes from an override outside community (unverified: web_enterprise).

Per addon, the pattern every core module follows:

```python
'web.assets_backend': [
    'my_addon/static/src/**/*',
    ('remove', 'my_addon/static/src/**/*.dark.scss'),   # never in light mode
],
'web.assets_web_dark': [
    'my_addon/static/src/**/*.dark.scss',
],
```

- `.dark.scss` files are appended at the **end** of the dark bundle: they can use every SCSS variable
  but cannot change values already compiled. Override CSS variables or write rules:

```scss
// my_widget.dark.scss (core: core/datetime/datetime_picker.dark.scss)
.o_my_widget {
    --MyWidget-bg: #{$gray-300};
}
```

- To change an SCSS **variable** for dark, insert a `*.variables.dark.scss` *before* the light
  variables file in the dark bundle and remove it from the light one (core: `web_hierarchy` with
  `('before', 'web_hierarchy/static/src/hierarchy.variables.scss',
  'web_hierarchy/static/src/hierarchy.variables.dark.scss')` in `web.assets_backend_lazy_dark`).
- `onboarding` targets a `web.dark_mode_variables` bundle that is not defined in community
  (unverified: provided by enterprise); avoid relying on it.
- Lazy views have their own dark twin: `web.assets_backend_lazy_dark`.

Source: addons/web/views/webclient_templates.xml:299-305, addons/web/models/ir_http.py:72-79, addons/web/__manifest__.py:334-337, addons/hr_holidays/__manifest__.py:104-117, addons/web_hierarchy/__manifest__.py:14-22, addons/onboarding/__manifest__.py:20-29, addons/web/static/src/core/datetime/datetime_picker.dark.scss

## Print styles

`web.assets_web_print` (loaded with `media="print"`) prepends `primary_variables_print.scss` and
`web/static/src/**/*.print_variables.scss` to `web.assets_backend`; ship `*.print_variables.scss`
files only if your addon adds them to that bundle. Reports use `web.report_assets_common` instead.

Source: addons/web/__manifest__.py:323-329, addons/web/views/webclient_templates.xml:298

## CSS custom properties

New `--o-*` properties defined by web in 20.0 (useful hooks for contextual overrides):

| Property | Defined in |
|---|---|
| `--o-gradient`, `--o-gradient-sm`, `--o-gradient-lg` | `scss/utilities_custom_backend.scss` (opt-in) |
| `--o-backdrop-blur`, `--o-backdrop-blur-sm`, `--o-backdrop-blur-lg` | same (opt-in) |
| `--o-statusbar-padding`, `--o-statusbar-button-padding-x/-y`, `--o-statusbar-caret-gap`, `--o-statusbar-border-color` | `views/fields/statusbar/statusbar_field.scss` |
| `--o-field-box-spacing`, `--o-field-box-border-color` | `views/form/form_controller_m3.scss` (boxed fields on small screens) |
| `--o-control-panel-breadcrumbs-display` | `core/dialog/dialog.scss` |
| `--o-btn-circle-height`, `--o-btn-circle-radius` | `views/fields/image/image_field.scss` |
| `--o-translate-bg-color`, `--o-translate-dir`, `--o-translate--to-translate-bg-color`, `--o-translate--translated-bg-color` | `views/fields/translation/translation_components.scss` |
| `--o-subtotal-footer-label-padding` | `views/form/form_controller.scss` |
| `--o-calendar-disabled-bg` | `views/calendar/calendar_renderer.dark.scss` |

Removed: `--o-statusbar-background-active/-hover`, `--o-statusbar-border(-active)`,
`--o-statusbar-padding-x/-y`, `--o-statusbar-point-inner-*`, `--o-color-picker-grid-columns`.
Icon properties `--icon-font-family` and `--oi-font-size` are in [icons.md](icons.md).

Find a property's definition with `odoo_grep(pattern="--o-statusbar-padding", glob="*.scss")`.

Source: addons/web/static/src/scss/utilities_custom_backend.scss, addons/web/static/src/views/fields/statusbar/statusbar_field.scss, addons/web/static/src/views/form/form_controller_m3.scss, addons/web/static/src/core/dialog/dialog.scss

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `$o-touch-btn-padding`, `$o-touch-btn-with-icon-padding` | removed (SCSS002) | addons/web/static/src/scss/primary_variables.scss |
| `$o-colors` only in secondary variables | defined in primary variables (usable in `*.variables.scss`) | addons/web/static/src/scss/primary_variables.scss:75 |
| tag colors via `adjust-color(nth($o-colors, N), ...)` | `$o-colors-bg-subtle` / `$o-colors-text-emphasis` | addons/web/static/src/core/tags_list/tags_list.scss |
| `$o-btns-bs-override` entry with 9 keys | add `disabled-background/-border/-color` | addons/web/static/src/scss/primary_variables.scss:268-345 |
| `.fa`, `.fa-*` selectors, `fontawesome_overridden.scss` | `.oi[data-icon='name']` (SCSS001) | addons/web/static/src/webclient/icons.scss |
| `--o-statusbar-padding-x/-y`, `--o-statusbar-background-*` | `--o-statusbar-padding`, `--o-statusbar-button-padding-x/-y` | addons/web/static/src/views/fields/statusbar/statusbar_field.scss |
| `.user-select-none` defined by Odoo | Bootstrap's own `.user-select-none` | addons/web/static/src/scss/bootstrap_overridden.scss |
| `$modal-content-border-radius: $border-radius` | `$border-radius-lg`; popovers too | addons/web/static/src/scss/bootstrap_overridden.scss |
