# Removed and added modules (Odoo 19 -> 20)

Diff of the community `addons/` trees (a directory with a `__manifest__.py`): 54 modules removed,
59 added. For each removed module, the v20 code that now provides its models/fields, found by
searching the old module's model names, fields and methods in the v20 tree. A custom addon that
`depends` on a removed module must depend on the merge target instead (and its data/views must
target the new xmlids). Confirm with `odoo_module(<name>)` and `odoo_model(<model>)`.

## Contents

- How to port a dependency on a removed module
- Removed modules: merged into an existing module
- Removed modules: replaced by a new module
- Removed modules: dropped (no trace in Community 20)
- Dependency changes of kept modules
- Added modules
- Test-only modules under `odoo/addons`

## How to port a dependency on a removed module

1. Replace the module in `depends` with the merge target below (or drop it if the feature is gone).
2. Fix xmlid prefixes in XML/CSV/Python (`ref('base_vat.xxx')` -> new module prefix): check each
   with `odoo_xmlid`; the record may also have been renamed.
3. Re-check inherited views and fields with `odoo_views` / `odoo_model` (fields moved into `base`,
   `account`, `hr`, ... may have new names or groups).
4. Database upgrades of existing installations are handled by Odoo's upgrade service, not by
   module code; this file is about source dependencies.

## Removed modules: merged into an existing module

Confidence: "verified" = same model `_name` / field / method found in v20 at the cited path.

| Removed (v19) | v20 location | Evidence | Confidence |
|---|---|---|---|
| `account_add_gln` | `account` | `res.partner.global_location_number`, addons/account/models/partner.py:615 | verified |
| `account_peppol_response` | `account_peppol` | `account.peppol.response`, addons/account_peppol/models/account_peppol_response.py:5 (+ clarification model, rejection wizard) | verified |
| `base_iban` | `account` + `odoo.tools` | `validate_iban` in odoo/tools/bank_account_number.py:51; IBAN type on `res.partner.bank` in addons/account/models/res_partner_bank.py; widget addons/account/static/src/components/account_number_widget | verified |
| `base_vat` | `base` (VAT check) + `l10n_eu_account_vies` (VIES) | `_check_vat` odoo/addons/base/models/res_partner.py:1413, `_check_vat_number` :1509, `check_vat_<cc>` methods; `vies_valid` addons/l10n_eu_account_vies/models/res_partner.py:17 | verified |
| `delivery_stock_picking_batch` | `stock_delivery` | `batch_group_by_carrier`, `batch_max_weight` addons/stock_delivery/models/stock_picking_type.py:23-24 | verified |
| `stock_picking_batch` | `stock` | `stock.picking.batch` addons/stock/models/stock_picking_batch.py:13 (+ `stock_add_to_wave`, `stock_picking_to_batch` wizards) | verified |
| `hr_homeworking` | `hr` | `hr.employee.location` addons/hr/models/hr_employee_location.py:10; work-location day fields on `hr.employee` | verified |
| `hr_homeworking_calendar` | `hr_calendar` | `homework.location.wizard` addons/hr_calendar/wizard/homework_location_wizard.py:9 | verified |
| `hr_holidays_homeworking` | `hr` + `hr_holidays` | presence/location icon logic in addons/hr/models/hr_employee.py and addons/hr_holidays/models/hr_employee.py | verified (split) |
| `hr_hourly_cost` | `hr` | `hr.employee.hourly_cost` addons/hr/models/hr_employee.py:279 | verified |
| `hr_org_chart` | `hr` (now depends on `web_hierarchy`) | addons/hr/controllers/hr_org_chart.py, addons/hr/static/src/fields/hr_org_chart.js | verified |
| `hr_work_entry_holidays` | `hr_holidays` (now depends on `hr_work_entry`) | addons/hr_holidays/models/hr_work_entry_type.py, `work_entry_type_id` on `hr.leave` | verified (refactored) |
| `l10n_fr_hr_work_entry_holidays` | `l10n_fr_hr_holidays` | addons/l10n_fr_hr_holidays/models/hr_version.py (part-time logic partly gone) | likely |
| `l10n_cn_city` | `l10n_cn` | addons/l10n_cn/data/res_city_data.xml (in the manifest) | verified |
| `l10n_dk_nemhandel`, `l10n_dk_nemhandel_response` | `l10n_dk` | `nemhandel.registration` addons/l10n_dk/wizard/nemhandel_registration.py:15, addons/l10n_dk/models/nemhandel_response.py | verified |
| `l10n_dk_oioubl` | `l10n_dk` (OIOUBL 2.1 only; 2.01 format gone) | addons/l10n_dk/models/account_edi_xml_oioubl_21.py | likely |
| `l10n_ec_stock` | `l10n_ec` | stock location accounts in addons/l10n_ec/models/template_ec.py | verified |
| `l10n_hu_edi_receive` | `l10n_hu_edi` | addons/l10n_hu_edi/wizard/l10n_hu_edi_receive_bills_wizard.py (model renamed `l10n_hu_edi.receive.bills.wizard`) | verified |
| `l10n_lk_invoice` | `l10n_lk` | addons/l10n_lk/models/account_move.py | verified |
| `l10n_pl_bank_verification` | `l10n_pl` | `l10n_pl.bank.account.verification` addons/l10n_pl/models/bank_account_verification.py:17 | verified |
| `l10n_ro_cpv_code` | `l10n_ro_edi` | `l10n_ro.cpv.code` addons/l10n_ro_edi/models/cpv_code.py:5 | verified |
| `l10n_ro_edi_stock_batch` | `l10n_ro_edi_stock` | addons/l10n_ro_edi_stock/models/stock_picking_batch.py | verified |
| `l10n_sa_withholding_tax` | `l10n_sa` (depends on `l10n_account_withholding_tax`) | addons/l10n_sa/__manifest__.py:27 | verified |
| `l10n_tr_nilvera_einvoice_extended` (tax offices only) | `l10n_tr` | `l10n_tr.tax.office` addons/l10n_tr/models/l10n_tr_tax_office.py | verified (partial; e-invoice part dropped) |
| `pos_restaurant_adyen` | `pos_adyen` | `adyen_merchant_account` addons/pos_adyen/models/pos_payment_method.py:27, `_adyen_capture` addons/pos_adyen/models/pos_payment.py:9 | verified |
| `pos_restaurant_stripe` | `pos_stripe` | addons/pos_stripe/static/src/overrides/screens/tip_screen.js | verified |
| `pos_self_order_adyen`, `pos_self_order_stripe`, `pos_self_order_viva_com` | `pos_adyen`, `pos_stripe`, `pos_viva_com` | `_allowed_actions_in_self_order` in each `models/pos_payment_method.py`; bundle `point_of_sale.payment_terminals` | verified |
| `website_sale_wishlist` | `website_sale` | `product.wishlist` addons/website_sale/models/product_wishlist.py:10, addons/website_sale/templates/wishlist_templates.xml | verified |
| `website_sale_comparison` | `website_sale` | `product.attribute.category` addons/website_sale/models/product_attribute_category.py:7, addons/website_sale/controllers/comparison.py | verified |
| `website_sale_comparison_wishlist` | `website_sale` | compare button in addons/website_sale/templates/wishlist_templates.xml | verified |
| `website_sale_stock_wishlist` | `website_sale` | `/shop/add/stock_notification` in addons/website_sale/controllers/wishlist.py (old `stock_notification` field gone) | likely |
| `website_sale_collect_wishlist` | `website_sale_collect` | addons/website_sale_collect/views/delivery_form_templates.xml | verified |
| `mrp_subcontracting_repair` | nothing to move (v19 module was an empty bridge); only an orphan `i18n/` folder remains in v20 | addons/mrp_subcontracting_repair/i18n | verified |
| `account_peppol_advanced_fields` | dropped (v19 manifest: "[DEPRECATED] ... Merged prematurly, not working correctly") | no `peppol_*` fields in v20 | verified |

## Removed modules: replaced by a new module

| Removed (v19) | v20 replacement | Evidence | Confidence |
|---|---|---|---|
| `purchase_requisition_sale` | `purchase_alternative_sale` (new; alternatives moved from `purchase_requisition` to `purchase_alternative`) | `_inherit = 'purchase.alternative.create'` addons/purchase_alternative_sale/wizard/purchase_alternative_create.py:7 (v19: `purchase.requisition.create.alternative`) | verified |
| `website_sale_autocomplete` | `website_address_autocomplete` (depends on `website`, not `website_sale`) | addons/website_address_autocomplete/models/website.py:7 | verified |
| `l10n_latam_base` | `base` `res.partner.additional_identifiers` (Json) replaces `l10n_latam.identification.type` | odoo/addons/base/models/res_partner.py:335; addons/l10n_ar/models/res_partner.py | likely (new design) |
| `iot_base` | `iot_webserial` (`point_of_sale` now depends on it) | addons/point_of_sale/__manifest__.py:19 | likely (different code) |

## Removed modules: dropped (no trace in Community 20)

Searched by module name, model names and distinctive identifiers; nothing found in `addons/` or
`odoo/addons/`. They may live in Enterprise (not checked): treat as **unknown replacement**.

| Removed (v19) | Notes |
|---|---|
| `delivery_mondialrelay`, `website_sale_mondialrelay` | no "mondialrelay" anywhere |
| `transifex` | no `transifex.translation` / `transifex_url` |
| `iot_box_image` | IoT box build scripts gone |
| `l10n_uy_pos` | no Uruguay POS invoicing override |
| `l10n_tr_nilvera`, `l10n_tr_nilvera_einvoice`, `l10n_tr_nilvera_edispatch`, `l10n_tr_gib_invoice_scenarios`, `l10n_tr_nilvera_base_vat` | Turkish Nilvera/GIB e-invoicing; base keeps only `check_vat_tr` (odoo/addons/base/models/res_partner.py:2236) |

Leftover references to old names exist (e.g. `delivery_stock_picking_batch` in
addons/stock/views/res_config_settings_views.xml:10): do not take them as proof the module exists.

## Dependency changes of kept modules

| Module | v19 depends | v20 depends | Impact |
|---|---|---|---|
| `point_of_sale` | `resource, stock_account, barcodes, html_editor, digest, phone_validation, partner_autocomplete, iot_base, google_address_autocomplete` | `resource, product, account, barcodes_gs1_nomenclature, html_editor, digest, phone_validation, google_address_autocomplete, base_report_wkhtmltox, iot_webserial` | POS stock logic moved to the new `pos_stock` (`pos_order.py`, `pos_session.py`, ... in addons/pos_stock/models); a POS addon using pickings/stock must depend on `pos_stock`; partner autocomplete is in `pos_partner_autocomplete` |
| `hr` | `base_setup, digest, phone_validation, resource_mail, web` | adds `web_hierarchy` | org chart merged |
| `hr_holidays` | - | `hr_work_entry, hr_calendar, resource` | work entry logic merged |

Source: `__manifest__.py` of each module in both trees (`odoo_module` shows depends/dependents).

## Added modules

| Module | Purpose (manifest) |
|---|---|
| `base_report_wkhtmltox` | PDF engine wkhtmltopdf (auto-install, default) |
| `base_report_paper_muncher` | PDF engine Paper Muncher |
| `populate`, `test_populate` | `odoo-bin populate` blueprints (synthetic data) |
| `printer` | external printers (ePOS, ZPL) |
| `iot_webserial` | serial devices through Web Serial |
| `mail_tracking`, `mail_tracking_mass_mailing`, `mail_tracking_sms` | technical tracking of messages |
| `portal_discuss` | portal + discuss bridge |
| `mysubscription` | backend subscription app |
| `purchase_alternative`, `purchase_alternative_sale`, `purchase_alternative_stock` | purchase alternatives (split from `purchase_requisition`) |
| `pos_stock`, `pos_sale_stock`, `pos_sale_delivery`, `pos_partner_autocomplete` | POS integrations split out of `point_of_sale` / `pos_sale` |
| `pos_sumup`, `pos_bancontact_pay`, `pos_self_order_bancontact_pay`, `pos_self_order_event`, `pos_self_order_sms` | POS payment terminals / self-order bridges |
| `website_address_autocomplete`, `website_partnership`, `website_mass_mailing_event`, `website_sale_project` | website features / bridges |
| `crm_sale_project`, `sale_project_margin`, `fleet_maintenance`, `mrp_delivery`, `hr_address_extended`, `hr_calendar_google`, `account_payment_custom`, `marketing_card_event` | bridges |
| `l10n_eu_account_vies` | VIES VAT validation (from `base_vat`) |
| `l10n_be_pos`, `l10n_eg_edi_pos`, `l10n_es_website_sale`, `l10n_es_website_sale_id_type`, `l10n_fr_payment`, `l10n_gr_edi_delivery_note`, `l10n_id_pos_self_order_qris`, `l10n_in_boe`, `l10n_kr_sale`, `l10n_la`, `l10n_mk`, `l10n_mm`, `l10n_ph_invoice`, `l10n_ph_sale`, `l10n_pk_edi`, `l10n_pk_edi_pos`, `l10n_tw_edi_ecpay_sale`, `l10n_vn_edi_viettel_stock` | localizations |
| `test_translation_mode`, `test_utm` | test modules |

## Test-only modules under `odoo/addons`

Removed: `test_access_rights`, `test_action_bindings`, `test_auth_custom`, `test_convert`,
`test_converter`, `test_inherits`, `test_mimetypes`, `test_orm`, `test_read_group`, `test_rpc`,
`test_search_panel`, `test_testing_utilities`, `test_translation_import`.
Added: `test_base`, `test_l10n`, `test_tests`, `test_translation`, `test_web`.
Look in the new ones for v20 examples of ORM/test-framework usage (e.g. `odoo/addons/test_tests`).

Source: directory listings of `addons/` and `odoo/addons/` in an Odoo 19.0 checkout and the v20 tree.
