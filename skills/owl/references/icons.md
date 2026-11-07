# Icons: Material Symbols (Odoo 20)

Odoo 20 dropped Font Awesome. Every icon is an `<i class="oi" data-icon="NAME"/>` whose name is a
Material Symbols ligature (`close`, `star`, `delete`) or an Odoo/brand glyph prefixed `oi_`
(`oi_odoo`, `oi_view-kanban`, `oi_linkedin`). Only a **subset** of names is shipped: check a name
before using it. Read this for any icon in XML views, OWL templates, JS or SCSS.

## Contents

- [Markup](#markup)
- [Modifier classes](#modifier-classes)
- [Brand and Odoo glyphs (`oi_*`)](#brand-and-odoo-glyphs-oi_)
- [Icons from JS](#icons-from-js)
- [Icons in SCSS](#icons-in-scss)
- [The shipped subset](#the-shipped-subset)
- [Adding an icon to the subset](#adding-an-icon-to-the-subset)
- [Reports, emails, website](#reports-emails-website)
- [Tests](#tests)
- [Migrating from Font Awesome](#migrating-from-font-awesome)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## Markup

```xml
<!-- decorative -->
<i class="oi oi-fw me-1" data-icon="print" aria-hidden="true"/>
<!-- meaningful on its own -->
<i class="oi" role="img" data-icon="warning" aria-label="Warning" title="Warning"/>
<!-- dynamic (OWL 3 template: component members need this.) -->
<i class="oi" t-att-class="this.props.iconClass" t-att-data-icon="this.props.icon"/>
<!-- icon-only button -->
<button class="btn oi oi-lg" data-icon="arrow_back" aria-label="Close"/>
```

- The class is always `oi`; the glyph comes from `data-icon` through `content: attr(data-icon)` on
  `::before`. Never put the name in the class (`oi-close`) or as text content.
- Server views (form/list buttons, stat buttons) take the bare name in `icon` and modifiers in
  `icon_class`: `<button name="..." type="object" icon="star" icon_class="oi-filled"/>`
  (validator XML005). The `boolean_icon` field widget takes `options="{'icon': 'redo',
  'icon_class': 'oi-filled'}"`.

Source: addons/web/static/src/webclient/icons.scss:31-77, addons/web/static/src/core/dialog/dialog.xml:33, addons/web/static/src/core/notifications/notification.xml:18, addons/web/static/src/search/cog_menu/cog_menu.xml:9, addons/web/static/src/views/view_button/view_button.js:24-61, addons/base_geolocalize/views/res_partner_views.xml:18, addons/web/static/src/views/fields/boolean_icon/boolean_icon_field.js

## Modifier classes

| Class | Effect |
|---|---|
| `oi-filled` | filled variant (`font-variation-settings: 'FILL' 1`); no effect if the icon has no fill (`has_fill: False`) |
| `oi-fw` | fixed width (`1.28571429` x font size) |
| `oi-sm`, `oi-lg` | `0.8em`, `1.25em` (+ `vertical-align: middle`) |
| `oi-2x` .. `oi-10x` | `2em` .. `10em` |
| `oi-spin`, `oi-pulse` | continuous / stepped rotation |
| `oi-rotate-90/180/270`, `oi-flip-horizontal`, `oi-flip-vertical` | transforms |
| `oi-stack` + `oi-stack-1x` / `oi-stack-2x` | stacked icons |

- Size can also be driven by the `--oi-font-size` CSS variable (default `1em`).
- Under `.o_rtl`, directional icons (`arrow_back`, `arrow_forward`, `keyboard_arrow_left`, ...,
  listed in `$ms-rtl-icons`, plus `oi_view-pivot`, `oi_view-cohort`) are mirrored automatically.

Source: addons/web/static/src/webclient/icons.scss:9-178, addons/web/static/src/webclient/icons_mappings/rtl_icons.scss

## Brand and Odoo glyphs (`oi_*`)

Names starting with `oi_` switch the element to the `odoo_ui_icons` font (via the
`--icon-font-family` variable). The set (203 names) covers what Material Symbols lacks: Odoo glyphs
(`oi_odoo`, `oi_studio`, `oi_view-kanban`, `oi_view-pivot`, `oi_view-cohort`, `oi_app_documents`),
brands (`oi_facebook`, `oi_facebook-square`, `oi_x`, `oi_x-square`, `oi_linkedin`, `oi_github`,
`oi_instagram`, `oi_youtube`, `oi_whatsapp`, `oi_telegram`, `oi_tiktok`, `oi_threads`,
`oi_bluesky`, `oi_discord`, `oi_google`, `oi_apple`, `oi_android`, `oi_paypal`, `oi_cc-visa`, ...)
and a few Font Awesome 4.7 leftovers (`oi_birthday-cake`, `oi_bomb`, `oi_user-secret`).
`oi_twitter` / `oi_twitter-square` render as `oi_x` / `oi_x-square`.

```xml
<i class="oi oi-fw" data-icon="oi_linkedin"/>
```

Source: addons/web/tooling/icons/odoo_ui_icons_config.json, addons/web/icons.py, addons/web/static/src/webclient/icons.scss:68-77, addons/website_slides/static/src/js/public/components/slide_share_dialog/slide_share_dialog.xml:23-31, addons/web/models/ir_ui_view.py:27-28

## Icons from JS

Core components accept a bare icon name and render `data-icon` themselves:

```javascript
// web/static/src/views/list/list_controller.js (static action menu items)
duplicate: {
    isAvailable: () => this.activeActions.duplicate,
    sequence: 30,
    icon: "content_copy",
    description: _t("Duplicate"),
    callback: () => this.model.root.duplicateRecords(),
},
```

When you build DOM by hand: `el.classList.add("oi"); el.dataset.icon = "close";`. Font Awesome names
in JS strings (`"fa-trash"`, `"fa fa-check"`) are flagged by validator JS015 and render nothing.

Source: addons/web/static/src/views/list/list_controller.js:452-490, addons/web/static/src/views/form/form_controller.js:614-651, addons/web/static/src/search/cog_menu/cog_menu.xml:54

## Icons in SCSS

```scss
// target an icon
.o_my_widget .oi[data-icon='close'] {
    color: $o-danger;
}

// draw an icon in a pseudo-element (core: webclient.scss, colorlist.scss)
.o_my_item.active::before {
    font: 1em/1 "Material Symbols Outlined";
    content: "check";
}

// or reuse the full .oi base on your own class (core: mail core.scss)
.o_my_round_button {
    @include material-icon-base;   // then set data-icon on the element
}
```

- Filled glyph in a `content:` declaration: append `_f` to the name (`content: "home_f"`), or use
  `font-variation-settings: 'FILL' 1`.
- `$ms-font-family` (`'Material Symbols Outlined'`) and `$oi-font-family` (`'odoo_ui_icons'`) are
  defined in `webclient/icons.scss`, which is in `web.icons_fonts` and `web.assets_backend`.
- `.fa` / `.fa-*` selectors and `FontAwesome` font names match nothing (validator SCSS001).

Source: addons/web/static/src/webclient/icons.scss:8-9, addons/web/static/src/webclient/webclient.scss:104-111, addons/web/static/src/core/colorlist/colorlist.scss:35-43, addons/mail/static/src/core/common/core.scss:121-122, addons/web/tooling/icons/generate_icons.py:15-23

## The shipped subset

- `addons/web/tooling/icons/icons_wishlist.txt`: the 484 Material Symbols names in the fonts (one
  per line, `#` comments allowed).
- `addons/web/icons.py`: generated `ICONS` frozendict, name -> `{'has_fill', 'codepoint', 'tags'}`,
  687 entries (484 Material Symbols + 203 `oi_*`). Used by the html_editor icon picker
  (`/html_editor/icons_search`) and mail's icon-to-PNG renderer.
- A name outside the subset has no ligature in the font, so no icon is drawn. Verify first:
  `odoo_grep(pattern="'content_copy':", module="web", glob="icons.py")` or read the wishlist.
- Common names that **are** shipped: `close add edit delete check search settings star person group
  mail phone info warning help refresh open_in_new arrow_back arrow_forward expand_more
  keyboard_arrow_down keyboard_arrow_right chevron_left chevron_right more_vert menu home
  calendar_today schedule download upload attach_file lock visibility visibility_off filter_alt
  content_copy save print favorite notifications forum label sell location_on link
  progress_activity autorenew drag_indicator`.

Source: addons/web/tooling/icons/icons_wishlist.txt, addons/web/icons.py, addons/web/tests/test_icons.py, addons/html_editor/controllers/main.py:823-832

## Adding an icon to the subset

The fonts are owned by `web`; a custom addon cannot extend them without changing `web`. Prefer a
shipped name; otherwise use an SVG/image. Inside the Odoo tree the procedure is:

```bash
# 1. add the Material Symbols name to addons/web/tooling/icons/icons_wishlist.txt
#    (oi_* glyphs: edit odoo_ui_icons_config.json, a Fontello project file)
pip install 'fonttools[pathops]' brotli
npm install fontext            # the script runs `npx --no-install fontext`
python3 addons/web/tooling/icons/generate_icons.py   # downloads from the Google Fonts API
```

It regenerates `static/src/libs/materialsymbols/material_symbols_{outlined,rounded,sharp}_subset.woff2`
and `.css`, `material_symbols_backend.woff` (wkhtmltopdf and Pillow), `static/lib/odoo_ui_icons/fonts/
odoo_ui_icons.woff2` / `odoo_ui_icons_backend.woff`, and `web/icons.py`. `test_icons.py` asserts
`ICONS` equals wishlist + Odoo UI glyphs, so commit everything together.

Source: addons/web/tooling/icons/generate_icons.py:1-70, addons/web/tooling/icons/generate_icons.py:189-212, addons/web/tooling/icons/generate_icons.py:1244-1287, addons/web/tests/test_icons.py

## Reports, emails, website

- Bundles: `web.material_symbols_outlined`, `web.material_symbols_rounded`,
  `web.material_symbols_sharp`, `web.odoo_ui_icons`, all included by `web.icons_fonts`. Custom bundles
  `('include', 'web.icons_fonts')`; layouts preload the font with
  `<t t-call-assets="web.material_symbols_outlined" t-binary="True"/>`.
- QWeb reports: `web.report_assets_common` includes `web.icons_fonts` + `icons_report.scss`
  (wkhtmltopdf reads the WOFF fallback, ignores `var()`/`FILL`, so filled icons use the `_f` names).
  Same markup works in reports.
- Emails cannot load fonts: mail renders icons to PNG through `/mail/font_to_img/<icon>/...`.
- Website: each website picks Outlined, Rounded or Sharp (`website._get_icon_font_family()`); same
  names in all three.

Source: addons/web/__manifest__.py:529-556, addons/web/views/webclient_templates.xml:43-44, addons/web/static/src/webclient/actions/reports/icons_report.scss, addons/mail/controllers/mail.py:295-300, addons/website/views/website_templates.xml:441-447

## Tests

Select icons by `data-icon`, not by class:

```javascript
expect(`.o_searchview_facet_label .oi[data-icon='arrow_downward']`).toHaveCount(1);
expect(`.o_switch_view:eq(1) [data-icon='oi_view-kanban']`).toHaveCount(1);
await contains(".oi[data-icon='swap_vert']").click();
```

Tours use the same selectors: `trigger: ".o_user_switch [data-icon='account_circle']"`,
`".modal-body i[data-icon='star'].oi-filled:eq(2)"`.

Source: addons/web/static/tests/search/search_from_url.test.js:140-160, addons/web/static/tests/search/control_panel.test.js:91-94, addons/web/static/tests/tours/user_switch_tour.js:69, addons/website_slides/static/tests/tours/slides_course_review_modification.js:77

## Migrating from Font Awesome

Run the upgrade script `19.5-00-material-symbols-icons` (MCP: `odoo_upgrade_code`); it rewrites
`fa fa-*` / `oi oi-*` markup, button `icon=` attributes, JS strings and CSS selectors using
`odoo/upgrade_code/material_symbols_icons_mapping.py`. It is best effort: dynamic class names and
icons stored in data need a manual pass, then `odoo_validate` (XML004, XML005, OWL006, JS015,
SCSS001).

| Font Awesome 4.7 | Material Symbols | | Font Awesome 4.7 | Material Symbols |
|---|---|---|---|---|
| `fa-times`, `fa-close` | `close` | | `fa-pencil` | `edit` + `oi-filled` |
| `fa-trash` / `fa-trash-o` | `delete` filled / outlined | | `fa-plus` | `add` |
| `fa-check` | `check` | | `fa-star` / `fa-star-o` | `star` filled / outlined |
| `fa-user` / `fa-users` | `person` / `group` (filled) | | `fa-cog`, `fa-gear` | `settings` (filled) |
| `fa-spinner` | `progress_activity` | | `fa-circle-o-notch` | `autorenew` |
| `fa-envelope` | `mail` (filled) | | `fa-info-circle` | `info` (filled) |
| `fa-exclamation-triangle` | `warning` | | `fa-question-circle` | `help` (filled) |
| `fa-external-link` | `open_in_new` | | `fa-chevron-down` | `expand_more` |
| `fa-caret-down` | `arrow_drop_down` | | `fa-ellipsis-v` | `more_vert` |
| `fa-bars` | `menu` | | `fa-calendar` | `calendar_today` (filled) |
| `fa-clock-o` | `schedule` | | `fa-globe` | `public` |
| `fa-eye` / `fa-eye-slash` | `visibility` / `visibility_off` | | `fa-filter` | `filter_alt` (filled) |
| `fa-copy` | `content_copy` | | `fa-floppy-o` | `save` |
| `fa-tag` / `fa-tags` | `label` / `sell` | | `fa-map-marker` | `location_on` |
| `fa-money` | `payments` | | `fa-twitter` | `oi_x` |

Modifiers: `fa-fw`, `fa-spin`, `fa-pulse`, `fa-lg`, `fa-sm`, `fa-2x`..`fa-10x`, `fa-stack*`,
`fa-rotate-*`, `fa-flip-*` -> same name with `oi-`; `fa-1x` and `fa-inverse` are dropped.

Source: odoo/upgrade_code/19.5-00-material-symbols-icons.py, odoo/upgrade_code/material_symbols_icons_mapping.py:10-922

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `<i class="fa fa-trash"/>` | `<i class="oi" data-icon="delete"/>` (XML004, OWL006) | odoo/upgrade_code/19.5-00-material-symbols-icons.py |
| `<button icon="fa-star"/>` | `<button icon="star" icon_class="oi-filled"/>` (XML005) | addons/web/static/src/views/view_button/view_button.js |
| `<i class="oi oi-view-kanban"/>` (class-based odoo_ui_icons) | `<i class="oi" data-icon="oi_view-kanban"/>` | addons/web/static/lib/odoo_ui_icons/odoo_ui_icons.css |
| `icon: "fa-copy"` in JS | `icon: "content_copy"` (JS015) | addons/web/static/src/views/list/list_controller.js |
| `.fa-check:before` / `font-family: FontAwesome` | `.oi[data-icon='check']`, `"Material Symbols Outlined"` (SCSS001) | addons/web/static/src/webclient/icons.scss |
| any FA icon is available | only the 484 + 203 names in `icons.py` | addons/web/tooling/icons/icons_wishlist.txt |
| `$('.fa-spin')` / `hasClass('fa-...')` in tests | `.oi[data-icon='name']` selectors | addons/web/static/tests/search/control_panel.test.js |
