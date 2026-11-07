# Field widgets and view widgets (Odoo 20)

Field widgets usable in `widget="..."`, grouped by field type, with their key `options`, built from the
`registry.category("fields")` registrations of the Odoo 20 tree (web first, then other addons), plus
the `view_widgets` registry used by `<widget name="...">` and the v19 -> v20 renames.
Verify any key at work time with `odoo_js(registry="fields", key="<name>")`; the generated list of every
registered key with its file is [widget-index.md](widget-index.md).

## Contents
- How a widget is resolved
- Default widget per field type
- char / text / html
- integer / float / monetary
- boolean / selection
- date / datetime
- binary / image
- many2one
- many2many / one2many
- reference, properties, json, misc
- Widgets from other core addons
- `<widget>` (view_widgets registry)
- Renamed / removed in Odoo 20

## How a widget is resolved

For `<field name="x" widget="w"/>` the client looks up, in order: `<js_class>.w`, `<view_type>.w`, `w`
(view types: `list`, `form`, `card` for kanban/popover cards, `calendar`, `hierarchy`, `activity`...).
An unknown widget logs `Missing widget: w` and falls back to the field-type default; a widget used on
an unsupported type logs a warning. `options` is a python dict literal; unknown keys are ignored.

```xml
<field name="tag_ids" widget="many2many_tags" options="{'color_field': 'color', 'no_create_edit': True}"/>
<field name="amount_total" widget="monetary" options="{'currency_field': 'company_currency_id'}"/>
```

Source: addons/web/static/src/views/fields/field.js:115-136,222-290

## Default widget per field type

The type name itself is a registered widget (`char`, `text`, `integer`, `float`, `monetary`, `boolean`,
`selection`, `date`, `datetime`, `binary`, `many2one`, `one2many`, `many2many`, `reference`,
`many2one_reference`, `properties`, `properties_definition`, `json`). In forms, one2many/many2many
default to the relational table (`one2many`/`many2many`); in cards a many2many without widget becomes
`many2many_tags`. `html` is registered by `html_editor` (a dependency of `mail`).

Source: addons/web/static/src/views/card/card_arch_parser.js:22-27, addons/html_editor/static/src/fields/html_field.js:421

## char / text / html

| Widget | Types | Key options / attributes |
|---|---|---|
| `char` | char, text | `placeholder_field`; attr `password`, `placeholder` |
| `text` (`list.text`) | text, char, html | `line_breaks`, `placeholder_field` |
| `email` / `form.email` | char | `placeholder_field` |
| `phone` | char | `formatted_field`, `dial_field`, `display_buttons` |
| `url` / `form.url` | char | `website_path`, `placeholder_field` |
| `CopyClipboardChar`, `CopyClipboardURL`, `CopyClipboardButton` | char | `btn_class`, `icon` |
| `badge` | char, selection, many2one | `color_field`; decorations |
| `color` | char (hex) | |
| `image_url` | char | `size` |
| `password` | char, text | |
| `domain` | char, text | `model` (field name or model), `in_dialog`, `foldable`, `allow_expressions`, `count_limit` |
| `field_selector` | char | `model`, `follow_relations` |
| `google_slide_viewer` | char, text | |
| `ace` / `code` | text, html | `mode` (`python`, `xml`, `qweb`...), `lineWrapping` |
| `iframe_wrapper` | text, html | raw HTML in an iframe |
| `html` (html_editor) | html | `height`, `collaborative`, `codeview` (debug), `dynamic_placeholder`, `allowImage`, `allowVideo`, `allowFile`, `sandboxedPreview`, `cssReadonly`, `embedded_components` |

Source: addons/web/static/src/views/fields/{char,text,email,phone,url,copy_clipboard,badge,color,image_url,password,domain,field_selector,ace}/, addons/html_editor/static/src/fields/html_field.js:421-490

## integer / float / monetary

| Widget | Types | Key options |
|---|---|---|
| `integer` | integer | `enable_formatting`, `human_readable`, `decimals`, `step`, `type` |
| `float` | float, monetary | `digits`, `enable_formatting`, `human_readable`, `hide_trailing_zeros`, `step`, `type` |
| `float_time` | float | `show_seconds`, `numeric`, `unit` |
| `float_time_tz` (**new**) | float | like `float_time`, stored UTC, shown in the user's timezone |
| `float_factor` | float, monetary | `factor` |
| `float_toggle` | float | `range`, `factor`, `force_button`, `digits` |
| `monetary` | monetary, float, integer | `currency_field`, `no_symbol`, `hide_trailing_zeros` |
| `percentage` | integer, float | |
| `percentpie` | float, integer | |
| `progressbar` | integer, float | `max_value` (field name or number, default 100); editable unless readonly; attr `title` |
| `gauge` | numeric | `max_value`, `max_value_field`, `title`, `max_tooltip` |
| `handle` | integer | drag handle; sets the default order of the list/kanban |
| `color_picker` / `kanban_color_picker` | integer | colour index (kanban one goes in the card `menu`) |
| `statinfo` | float, integer, monetary, char, one2many, many2one | `label_field`, `hide_trailing_zeros`; stat buttons |

Source: addons/web/static/src/views/fields/{integer,float,float_time,float_time_tz,float_factor,float_toggle,monetary,percentage,percent_pie,progress_bar,gauge,handle,color_picker,kanban_color_picker,stat_info}/

## boolean / selection

| Widget | Types | Key options |
|---|---|---|
| `boolean` | boolean | checkbox (default) |
| `boolean_checkbox` (**new**) | boolean | explicit checkbox |
| `boolean_toggle` | boolean | switch |
| `boolean_favorite` | boolean | star |
| `boolean_icon` | boolean | `icon` (Material name), `icon_class` |
| `upgrade_boolean` | boolean | settings: proposes a module install |
| `selection` | selection, many2one | `placeholder_field` |
| `radio` | selection, many2one | `horizontal` |
| `badges_selection` (**renamed**) | selection | `badge_limit` |
| `priority` | selection | stars |
| `state_selection` | selection | `hide_label` (kanban state bullet) |
| `label_selection` | selection | `classes` (`{'value': 'success'}`) |
| `statusbar` | selection, many2one | `clickable`, `fold_field`; attr `statusbar_visible="a,b"` |
| `filterable_selection` | selection, many2one | `whitelisted_values`, `blacklisted_values`, `whitelist_fname` |
| `timezone_mismatch` | selection, many2one | `tz_offset_field`, `mismatch_title` |

Source: addons/web/static/src/views/fields/{boolean,boolean_checkbox,boolean_toggle,boolean_favorite,boolean_icon,selection,radio,badges_selection,priority,state_selection,label_selection,statusbar,timezone_mismatch}/, addons/web/static/src/webclient/settings_form_view

## date / datetime

| Widget | Types | Key options |
|---|---|---|
| `date` (`list.date`) | date | `min_date`, `max_date`, `warning`, `numeric`, `min_precision`, `max_precision`, `placeholder_field` |
| `datetime` (`list.datetime`) | datetime | `rounding` (minutes), `show_time`, `show_seconds` |
| `daterange` (`list.daterange`) | date, datetime | `start_date_field` / `end_date_field` (the other bound), `always_range` |
| `relative_date` (**renamed**) | date, datetime | distance to today (days/weeks/months), red when past; `classes` |

```xml
<field name="date_begin" widget="daterange" options="{'end_date_field': 'date_end'}"/>
```

Source: addons/web/static/src/views/fields/datetime/datetime_field.js:480-683, addons/web/static/src/views/fields/datetime/list_datetime_field.js, addons/web/static/src/views/fields/relative_date/relative_date_field.js

## binary / image

| Widget | Types | Key options / attributes |
|---|---|---|
| `binary` (`list.binary`) | binary | `accepted_file_extensions`, `allowed_mime_type`; attr `filename="<char field>"` |
| `image` | binary, many2one | `size` `[w, h]`, `preview_image`, `zoom`, `zoom_delay`, `reload`, `convert_to_webp`, `img_class`, `accepted_file_extensions` |
| `contact_image` | binary, many2one | same as `image` |
| `pdf_viewer` | binary | `preview_image` |
| `signature` | binary | `full_name`, `default_font`, `size` |
| `attachment_image` | many2one (ir.attachment) | |

```xml
<field name="product_id" widget="image"
       options="{'size': [38, 38], 'preview_image': 'image_128', 'img_class': 'object-fit-contain rounded'}"/>
```

Source: addons/web/static/src/views/fields/{binary,image,contact_image,pdf_viewer,signature,attachment_image}/, addons/sale/views/sale_order_views.xml:943

## many2one

| Widget | Key options |
|---|---|
| `many2one` (default) | `no_open`, `no_create`, `no_quick_create`, `no_create_edit`, `search_threshold`, `placeholder_field`, `create_name_field`, `can_scan_barcode`; attrs `can_create`, `can_write` (python expr) |
| `many2one_avatar` | same, shows the record avatar |
| `many2one_barcode` | scanner button |
| `many2one_binary` (**new**) | file upload creating `ir.attachment`; `accepted_file_extensions` |
| `badges_many2one` (**new**) | values as badges: `badge_limit`, `related_icon_field`, `default_icon` |
| `badge`, `radio`, `selection`, `statusbar`, `filterable_selection` | see above |
| `image`, `contact_image`, `attachment_image` | image of the related record |

`context` on the field is passed to name_search/create; `domain` restricts choices.

Source: addons/web/static/src/views/fields/many2one/many2one_field.js:9-124, addons/web/static/src/views/fields/{many2one_avatar,many2one_barcode,many2one_binary,badges_many2one}/

## many2many / one2many

| Widget | Types | Key options |
|---|---|---|
| `many2many` / `one2many` | x2many | relational table (or kanban with `mode`); field attrs `create`, `delete`, `link`, `unlink`, `write`, `add-label`; inline `<list>`/`<form>`/`<kanban>` sub-views |
| `many2many_tags` | many2many, one2many | `no_create`, `no_quick_create`, `no_create_edit`, `create` (domain), `color_field`, `search_threshold`, `placeholder_field`, `tag_limit`, `on_tag_click` (`edit_color`/`open_form`) |
| `many2many_tags_avatar` | many2many, one2many | same, with avatars |
| `many2many_tags_color_dot` (**new**) | many2many | same, coloured dots |
| `many2many_checkboxes` | many2many | all values as checkboxes |
| `many2many_binary` | many2many (ir.attachment) | `accepted_file_extensions`, `number_of_files` |
| `card.many2many`, `card.one2many`, `list.many2many`, `list.one2many` | | view-specific variants picked automatically |

Source: addons/web/static/src/views/fields/many2many_tags/many2many_tags_field.js, addons/web/static/src/views/fields/x2many/x2many_field.js:326-347, addons/web/static/src/views/fields/{many2many_tags_avatar,many2many_tags_color_dot,many2many_checkboxes,many2many_binary}/

## reference, properties, json, misc

| Widget | Types | Notes |
|---|---|---|
| `reference` | reference, char | `hide_model`, `model_field` |
| `many2one_reference`, `many2one_reference_integer` | many2one_reference | |
| `properties` (`card.properties`, `calendar.properties`, `hierarchy.properties`) | properties | |
| `properties_definition` | properties_definition | |
| `property_tags`, `property_selection` | internal to properties | |
| `json`, `json_checkboxes` (`stacked`) | json | |
| `res_user_group_ids`, `res_user_group_ids_privilege` | res.users groups editor | |

Source: addons/web/static/src/views/fields/{reference,many2one_reference,many2one_reference_integer,properties,json,json_checkboxes}/

## Widgets from other core addons

| Addon | Widgets |
|---|---|
| mail | `many2one_avatar_user`, `many2many_avatar_user` (+ `card.`/`list.`/`activity.` variants), `kanban_activity`, `list_activity` (on `activity_ids`), `activity_exception`, `many2many_tags_email`, `text_emojis`, `char_emojis`, `statusbar_duration`, `html_mail` |
| html_editor | `html`, `image_with_media_dialog`, `x2_many_media_viewer` |
| resource_mail | `many2one_avatar_resource`, `many2many_avatar_resource` |
| hr | `many2one_avatar_employee`, `many2many_avatar_employee`, `background_image`, `hr_presence_status`, `boolean_radio` |
| analytic | `analytic_distribution` |
| account | `account-tax-totals-field`, `many2many_tax_tags`, `x2many_buttons`, `payment`, `account_type_selection` |
| uom | `many2one_uom`, `many2many_uom_tags` |
| sale | `sol_o2m`, `sol_product_many2one`, `labeled_monetary_field`, `labeled_percentage_field` |
| project | `project_task_state_selection`, `task_stage_with_state_selection`, `priority_switch` |
| website | `website_publish_button`, `website_redirect_button`, `page_url`, `image_radio` |
| partner_autocomplete | `res_partner_many2one`, `field_partner_autocomplete` |

Add the addon to your module `depends` before using its widget.

Source: addons/mail/static/src/views/web/fields/, addons/html_editor/static/src/fields/, addons/resource_mail/static/src, addons/hr/static/src, addons/analytic/static/src, addons/account/static/src/components, addons/uom/static/src, addons/sale/static/src, addons/project/static/src, addons/website/static/src, addons/partner_autocomplete/static/src

## `<widget>` (view_widgets registry)

`<widget name="..." .../>` renders a component that is not bound to one field. RNG attributes:
`name`, `options`, `width`, `invisible`, `column_invisible` (other attributes pass through in forms and
cards).

| `name` (web) | Attributes |
|---|---|
| `web_ribbon` | `title` (text), `bg_color` (e.g. `text-bg-danger`), `tooltip`; `invisible` |
| `documentation_link` | `path`, `label`, `icon`, `class` |
| `attach_document` | `action`, `string`, `highlight`; option `accepted_file_extensions` |
| `signature` | `full_name`, `signature_field`, `string`, `highlight` |
| `week_days` | (resource-style mon..sun booleans) |
| `notification_alert` | |
| `res_config_edition`, `res_config_dev_tool`, `res_config_invite_users` | settings screen |

Other addons register e.g. `line_number` and `simple_qty_at_date_widget` (sale), `qty_at_date_widget`
(sale_stock), `hr_leave_stats` (hr_holidays), `gauge_chart` (hr_recruitment_skills).
Lookup: `odoo_js(registry="view_widgets")`.

```xml
<widget name="web_ribbon" title="Archived" bg_color="text-bg-danger" invisible="active"/>
<widget name="documentation_link" path="/applications/general/users.html" icon="help"/>
```

Source: odoo/addons/base/rng/common.rng:432-441, addons/web/static/src/views/widgets/widget.js:61-86, addons/web/static/src/views/widgets/ribbon/ribbon.js:40-67, addons/web/static/src/views/widgets/documentation_link/documentation_link.js:42-54, addons/web/static/src/views/widgets/attach_document/attach_document.js:79-90, addons/web/static/src/views/widgets/signature/signature.js:68-79

## Renamed / removed in Odoo 20

| v19 key | Odoo 20 | Source |
|---|---|---|
| `selection_badge`, `list.selection_badge` | `badges_selection` (XML015) | addons/web/static/src/views/fields/badges_selection |
| `remaining_days` | `relative_date` (XML015) | addons/web/static/src/views/fields/relative_date/relative_date_field.js |
| `kanban.many2many_tags`, `kanban.many2many_tags_avatar`, `kanban.many2one_avatar`, `kanban.properties` | `card.*` (JS009) | addons/web/static/src/views/fields |
| `kanban.many2one_avatar_user`, `kanban.many2many_avatar_user` (mail) | `card.*` | addons/mail/static/src/views/web/fields |
| `kanban.progressbar` | removed (plain `progressbar`) | addons/web/static/src/views/fields/progress_bar |
| `list.boolean_toggle` | removed (plain `boolean_toggle`) | addons/web/static/src/views/fields/boolean_toggle |
| `form.phone`, `form.many2many_tags` | removed (plain `phone`, `many2many_tags`) | addons/web/static/src/views/fields |
| `calendar.many2many`, `calendar.one2many` | removed (calendar popovers render cards) | addons/web/static/src/views/card |
| `many2many_tags_avatar_popover`, `base_settings.radio` | removed | addons/web/static/src/views/fields |
| `iban` (base_iban) | module removed in 20 (no `addons/base_iban`) | odoo/addons/base/models/res_partner_bank.py |
| `selection_badge_with_filter` (web) | now only in hr_holidays | addons/hr_holidays/static/src/components/selection_badge_with_filter |
