# Icons in views, buttons and templates (Odoo 20)

Odoo 20 dropped Font Awesome: every icon is a **Material Symbols** ligature (or an `oi_*` brand/Odoo
glyph) rendered by `<i class="oi" data-icon="name"/>`. This file covers the markup, modifier classes,
button and option attributes, accessibility checks, the shipped icon subset and a FontAwesome ->
Material table. Validator rules: XML004 (fa classes in XML), XML005 (`icon="fa-..."`), JS015, OWL006,
SCSS001; `odoo_upgrade_code` script `19.5-00-material-symbols-icons` converts old code.

## Contents
- Markup
- Modifier classes
- Buttons, fields and other icon attributes
- Accessibility
- The shipped subset and how to check a name
- FontAwesome -> Material (40 most common)
- v19 habit -> Odoo 20

## Markup

```xml
<i class="oi" data-icon="person"/>                               <!-- outlined -->
<i class="oi oi-filled" data-icon="star" title="Favorite"/>      <!-- filled variant -->
<i class="oi oi-fw me-1" data-icon="schedule" aria-hidden="true"/> Worked Hours
<i class="oi oi-spin" data-icon="progress_activity"/>            <!-- spinner -->
<i class="oi" data-icon="oi_whatsapp" title="WhatsApp"/>          <!-- brand glyph -->
<!-- dynamic (QWeb / OWL) -->
<i class="oi oi-fw" t-att-data-icon="record.locked.raw_value ? 'lock' : 'lock_open'"/>
```
- `.oi` renders `content: attr(data-icon)` with the Material Symbols font; names starting with `oi_`
  use the `odoo_ui_icons` font instead (brands such as `oi_x`, `oi_youtube`, and Odoo glyphs such as
  `oi_view-kanban`, `oi_view-pivot`).
- The same markup works in backend views, OWL templates, server QWeb (website, portal, mail) and PDF
  reports (`web.icons_fonts` is included in `web.report_assets_common`).
- Some icons are mirrored automatically in RTL.

Source: addons/web/static/src/webclient/icons.scss:1-100, addons/web/__manifest__.py:244-303, addons/web/static/src/webclient/actions/reports/icons_report.scss, addons/hr_attendance/views/hr_attendance_view.xml:325-334, addons/calendar/static/src/views/attendee_calendar/attendee_calendar_controller.xml:20

## Modifier classes

| Class | Effect |
|---|---|
| `oi-filled` | `font-variation-settings: 'FILL' 1` (only icons with a distinct filled shape change; `has_fill` in `addons/web/icons.py`) |
| `oi-fw` | fixed width (aligned lists) |
| `oi-sm`, `oi-lg`, `oi-2x` ... `oi-10x` | sizes 0.8em, 1.25em, 2em ... 10em; or set the CSS variable `--oi-font-size` |
| `oi-spin`, `oi-pulse` | rotation animations |
| `oi-rotate-90`, `oi-rotate-180`, `oi-rotate-270`, `oi-flip-horizontal`, `oi-flip-vertical` | transforms |
| `oi-stack` + `oi-stack-1x` / `oi-stack-2x` | stacked icons |

`fa-xs` has no counterpart; `fa-1x`/`fa-inverse` have no equivalent and are dropped by the upgrade script.

Source: addons/web/static/src/webclient/icons.scss:9-175, odoo/upgrade_code/material_symbols_icons_mapping.py:880-907

## Buttons, fields and other icon attributes

| Where | Syntax |
|---|---|
| view `<button>` | `icon="edit"` + optional `icon_class="oi-filled"` (RNG attribute) -> `<i class="o_button_icon oi ..." data-icon="edit">` |
| stat button | `<button class="oe_stat_button" icon="payments" .../>` |
| `boolean_icon` widget | `options="{'icon': 'redo', 'icon_class': 'oi-filled'}"` |
| copy-to-clipboard widgets | `options="{'icon': '...', 'btn_class': '...'}"` |
| calendar default popover | field `options="{'icon': 'location_on'}"` shows the icon instead of the label |
| search panel `<field>` | `icon="group" icon_class="oi-filled"` |
| `badges_many2one` | `options="{'default_icon': '...', 'related_icon_field': '...'}"` |
| `documentation_link` widget | `icon="help"` |
| `mail.activity.type.icon` | Material name (`mail`, `phone`, `calendar_today`) |

`icon=` only accepts a Material/`oi_` name: no `fa-*` and no image path.

```xml
<button name="action_lost_leads" type="object" class="oe_stat_button" icon="star" icon_class="oi-filled">
    <div class="o_stat_info"><field name="leads_count" class="o_stat_value"/><span class="o_stat_text">Leads</span></div>
</button>
<groupby name="partner_id">
    <button name="edit" type="edit" icon="edit" icon_class="oi-filled" title="Edit"/>
</groupby>
```

Source: odoo/addons/base/rng/common.rng:322-323, addons/web/static/src/views/view_button/view_button.js:24-62, addons/web/static/src/views/view_button/view_button.xml:21, addons/web/static/src/views/fields/boolean_icon/boolean_icon_field.js:32-33, addons/web/static/src/views/calendar/calendar_common/calendar_common_popover.js:169-172, addons/web/static/src/search/search_arch_parser.js:395-440, addons/mail/models/mail_activity_type.py:43, addons/crm/views/crm_lost_reason_views.xml:22-28

## Accessibility

When views are validated, every element with `data-icon` and every `<button icon=...>` must be
described, otherwise a warning is logged ("... must have title in its tag, parents, descendants or have
text"). Accepted descriptions:
- `title`, `aria-label` or `aria-labelledby` on the element, an ancestor or a descendant;
- text right before/after the icon, or a neighbouring `<span>` with text, a `<field>`/`<label>` with
  `string`, a `<t t-out>`;
- `string` on the button.

`role="presentation"` / `role="none"` logs a warning; use `aria-hidden="true"` on purely decorative
icons that sit next to text, and `role="img"` + `aria-label` for standalone meaningful icons.

Source: odoo/addons/base/models/ir_ui_view.py:2081-2122,2296-2310,2370-2430

## The shipped subset and how to check a name

- Only **484** Material Symbols names are shipped (fonts are subsets generated from
  `addons/web/tooling/icons/icons_wishlist.txt`), plus about 200 `oi_*` glyphs. A name outside the list
  is not in the font and does not render as an icon.
- `addons/web/icons.py` (`ICONS`) lists every shipped name with `has_fill`, codepoint and search tags
  (used by the icon picker).
- Check before using a name: `odoo_grep("'<name>':", module="web", glob="icons.py")` or
  `odoo_grep("<name>", module="web", glob="icons_wishlist.txt")`; prefer a name already used by core
  (`odoo_grep('data-icon="<name>"')`).
- Adding icons means regenerating the fonts with `addons/web/tooling/icons/generate_icons.py` (core
  tooling, not something a custom module can do): pick from the shipped list instead.

Source: addons/web/tooling/icons/icons_wishlist.txt, addons/web/tooling/icons/generate_icons.py:1-45, addons/web/icons.py:1-15

## FontAwesome -> Material (40 most common)

From `FA_TO_MATERIAL` (`(name, filled)`; "filled" = add `oi-filled`). All targets are in the shipped subset.

| fa-* | data-icon | filled |
|---|---|---|
| `pencil` | `edit` | yes |
| `trash` / `trash-o` | `delete` | yes / no |
| `plus` | `add` | |
| `times` | `close` | |
| `check` | `check` | |
| `user` | `person` | yes |
| `users` | `group` | yes |
| `envelope` / `envelope-o` | `mail` | yes / no |
| `phone` | `phone` | yes |
| `cog`, `gear` | `settings` | yes |
| `calendar` | `calendar_today` | yes |
| `clock-o` | `schedule` | |
| `search` | `search` | |
| `home` | `home` | |
| `lock` / `unlock` | `lock` / `lock_open` | |
| `star` / `star-o` | `star` | yes / no |
| `heart` | `favorite` | yes |
| `info-circle` | `info` | yes |
| `question-circle` | `help` | yes |
| `exclamation-triangle`, `warning` | `warning` | |
| `download` / `upload` | `download` / `upload` | |
| `print` | `print` | |
| `paperclip` | `attach_file` | |
| `link` | `link` | |
| `external-link` | `open_in_new` | |
| `arrow-right` / `arrow-left` | `arrow_forward` / `arrow_back` | |
| `refresh` | `refresh` | |
| `caret-down` | `arrow_drop_down` | |
| `chevron-right` | `chevron_right` | |
| `bars` | `menu` | |
| `filter` | `filter_alt` | yes |
| `folder` / `folder-open` | `folder` / `folder_open` | yes |
| `file-o` | `description` | |
| `map-marker` | `location_on` | |
| `globe` | `public` | |
| `building` | `business` | |
| `tag` / `tags` | `label` / `sell` | |
| `money` | `payments` | |
| `truck` | `local_shipping` | |
| `eye` / `eye-slash` | `visibility` / `visibility_off` | |
| `comment` / `comments` | `chat_bubble` / `forum` | yes |
| `bell` | `notifications` | yes |
| `spinner` | `progress_activity` (+ `oi-spin`) | |
| `check-circle` / `times-circle` | `check_circle` / `cancel` | yes |
| `ellipsis-v` | `more_vert` | |
| `copy`, `files-o` | `content_copy` | |
| `archive` | `archive` | |
| `history` | `history` | |
| `briefcase` | `work` | |

Full table (about 800 entries, plus old `oi-*` class names in `OI_TO_MATERIAL`):
`odoo/upgrade_code/material_symbols_icons_mapping.py`.

Source: odoo/upgrade_code/material_symbols_icons_mapping.py:10-805

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `<i class="fa fa-user"/>` | `<i class="oi oi-filled" data-icon="person"/>` (XML004) | odoo/upgrade_code/19.5-00-material-symbols-icons.py |
| `<button icon="fa-star"/>` | `icon="star" icon_class="oi-filled"` (XML005) | odoo/upgrade_code/19.5-00-material-symbols-icons.py:303-322 |
| `options="{'icon': 'fa fa-x'}"` | `{'icon': 'x'}` (+ `icon_class`) | odoo/upgrade_code/19.5-00-material-symbols-icons.py:325-340 |
| `.fa-star` selectors in SCSS | `[data-icon='star']`, `.oi-spin` (SCSS001) | odoo/upgrade_code/19.5-00-material-symbols-icons.py:352-366 |
| `t-att-class="x and 'fa-eye' or 'fa-eye-slash'"` | `t-att-data-icon="x and 'visibility' or 'visibility_off'"` | odoo/upgrade_code/19.5-00-material-symbols-icons.py:177-189 |
| `fa-fw`, `fa-spin`, `fa-2x` | `oi-fw`, `oi-spin`, `oi-2x` | odoo/upgrade_code/material_symbols_icons_mapping.py:885-901 |
