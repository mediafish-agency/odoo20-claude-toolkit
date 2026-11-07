# Point of Sale frontend (Odoo 20)

How the v20 POS app is built (OWL 3 app with its own bundle), how to extend it: `PosStore` patches, OWL
plugins (which replaced most POS services), related models, Python data loading through
`pos.load.mixin`, screens/buttons, payment providers, server-QWeb receipts, and the self-order app.

## Contents
- [Architecture](#architecture)
- [POS plugins](#pos-plugins)
- [PosStore and patching it](#posstore-and-patching-it)
- [Loading data (Python)](#loading-data-python)
- [JS models](#js-models)
- [Screens, buttons, dialogs](#screens-buttons-dialogs)
- [Payment providers](#payment-providers)
- [Receipts (server QWeb)](#receipts-server-qweb)
- [Assets and tests](#assets-and-tests)
- [Self-order (pos_self_order)](#self-order-pos_self_order)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## Architecture

| Piece | Where | Notes |
|---|---|---|
| Boot | `app/main.js` | `mountComponent(Chrome, document.body, ...)` from `@web/env`; only in `point_of_sale.assets_prod`. |
| Root component | `app/pos_app.js` (`Chrome`) | `this.pos = usePos()`, `router = usePlugin(PosRouterPlugin)`. |
| Store | `app/services/pos_store.js` (`PosStore`) | Still a legacy service `"pos"`; `usePos()` (`app/hooks/pos_hook.js`) = `useService("pos")`. Reactive (`proxy`). |
| Plugins | `app/plugins/*.js` | OWL 3 `Plugin`s: data, router, printing, payment methods, alerts, numpad buffer, ... |
| Models | `app/models/*.js` + `related_models/` | Classes extending `Base`, registered in `pos_available_models`. |
| Pages | `app/screens/**` | Registered in `pos_pages` with a route. |
| Receipts | `point_of_sale/receipt/*.xml|py` | Server QWeb templates also rendered client-side. |

All components follow OWL 3 rules (`props = useProps({...})`, `proxy`, `signal.ref()`, `this.` in
templates): see [owl3-core.md](../../owl/references/owl3-core.md) and
[plugins-services.md](../../owl/references/plugins-services.md).

Source: addons/point_of_sale/static/src/app/main.js, addons/point_of_sale/static/src/app/pos_app.js,
addons/point_of_sale/static/src/app/hooks/pos_hook.js, addons/point_of_sale/static/src/app/services/pos_store.js:3333

## POS plugins

| Plugin (import from `@point_of_sale/app/plugins/...`) | On the store | Main API |
|---|---|---|
| `PosDataPlugin` (`pos_data_plugin`) | `pos.data` | `models` (also `pos.models`), `call/silentCall(model, method, args, kwargs)`, `searchRead`, `read`, `create`, `ormWrite`, `ormDelete`, `loadServerOrders(domain)`, `network.offline`, `connectWebSocket(channel, cb)` |
| `PosRouterPlugin` (`pos_router_plugin`) | `pos.router` | `currentScreen()` / `currentScreenParams()` (signals), `navigate(name, params)`, `back()` |
| `PosTicketPrinterPlugin` (`pos_ticket_printer_plugin`) | `pos.ticketPrinter` | `printOrderReceipt({ order, basic, simplified })`, `printOrderChanges(...)`, `printTipReceipt`, `printCashMoveReceipt`, `openCashbox()`, `getOrderReceiptData(order)` |
| `PosPaymentMethodPlugin` (`pos_payment_method_plugin`) | `pos.paymentMethods` | builds `pm.payment_interface` from `pos_payment_providers` |
| `PosAlertPlugin` (`pos_alert_plugin`) | `pos.alert` | `add(message, options)`, `remove()` |
| `PosNumberBufferPlugin` (`pos_number_buffer_plugin`) | `pos.numberBuffer` | `get()`, `set()`, `reset()`, `getFloat()`, `use(config)`, `sendKey(key)` |
| `PosAccessRightPlugin` (`access_right_plugin`) | `pos.accessRight` | cashier and rights (`canApplyDiscount`, ...) |
| `CustomerDisplayTerminalPlugin` (`customer_display_terminal_plugin`) | `pos.customerDisplay` | customer screen sync |

- `PosDataPlugin`, `PosRouterPlugin`, `PosAlertPlugin`, `PosNumberBufferPlugin`,
  `PosTicketPrinterPlugin` are registered globally with `services.add(...)` (`@web/core/services`), so
  components may `usePlugin(...)` them. Others are started on demand from the store; reach them through
  the store (`this.pos.paymentMethods`). From a component, `usePlugin(X)` throws `Unknown plugin` if `X`
  was never started: register your own plugin with `services.add(MyPlugin)`.
- Plugins order with `static sequence` (PosDataPlugin is 20, after the localization plugin).

Source: addons/point_of_sale/static/src/app/plugins/*.js, addons/web/static/lib/owl/owl.js (usePlugin),
addons/web/static/src/core/services.js

## PosStore and patching it

`PosStore` initializes in `async setup(env, services)`; the class has `static serviceDependencies`.
Patch the prototype and **await `super.setup`** before using loaded data:

```javascript
// addons/pos_discount/static/src/app/services/pos_store.js (trimmed)
import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);          // data is loaded after this line
        this.models["pos.order.line"].addEventListener("update", (data) => {
            const line = this.models["pos.order.line"].get(data.id);
            // ...
        });
    },
    selectOrderLine(order, line) {
        super.selectOrderLine(order, line);
        if (line?.isDiscountLine) {
            this.numpadMode = "price";
        }
    },
});
```

- To set fields before loading (as pos_restaurant does), assign them before `await super.setup(...)`.
- Useful store API: `config`, `session`, `company`, `models`, `getOrder()`, `addNewOrder()`,
  `addLineToCurrentOrder(vals, opts, configure)`, `navigate(page, params)`, `navigateToFirstPage()`,
  `syncAllOrders()`, `pay()`, `formatCurrency(amount)`, `parseValidFloat(str)`, `dialog`, `notification`.
- Patching is the accepted extension mechanism outside core POS, but keep patches small:
  [Avoid patching](../../odoo-web-guidelines/guidelines/javascript.md#avoid-patching-javascript-code).

Source: addons/point_of_sale/static/src/app/services/pos_store.js:71, addons/pos_restaurant/static/src/app/services/pos_store.js,
addons/pos_discount/static/src/app/services/pos_store.js

## Loading data (Python)

`pos.session.load_data(local_data)` returns, per model, `records`, `fields`, `relations`,
`dependencies` (+ `to_remove`). The model list comes from `pos.session._load_pos_data_models(config)`;
each model must inherit `pos.load.mixin`:

| Hook (`@api.model`) | Default | Purpose |
|---|---|---|
| `_load_pos_data_domain(self, data)` | `[]` | `data` maps model name to the **recordset** already loaded: `data['pos.config']` is the config record. Return `False` to load nothing. |
| `_load_pos_data_fields(self, config)` | `[]` (all fields) | Fields to read; `write_date` is added automatically. |
| `_load_pos_data_read(self, records, config)` | `records._filtered_access("read").read(fields, load=False)` | Post-process the dicts. |
| `_load_pos_data_dependencies(self)` | `[]` | Models this one depends on. |
| `load_pos_data_force_loading(self)` | `False` | Ignore the IndexedDB cache. |

```python
# addons/pos_restaurant/models/pos_session.py and pos_restaurant.py
class PosSession(models.Model):
    _inherit = 'pos.session'

    @api.model
    def _load_pos_data_models(self, config):
        data = super()._load_pos_data_models(config)
        if config.module_pos_restaurant:
            data += ['restaurant.floor', 'restaurant.table', 'restaurant.order.course', 'pos.course']
        return data

class RestaurantFloor(models.Model):
    _name = 'restaurant.floor'
    _inherit = ['pos.load.mixin']

    @api.model
    def _load_pos_data_domain(self, data):
        return [('pos_config_ids', '=', data['pos.config'].id)]

    @api.model
    def _load_pos_data_fields(self, config):
        return ['name', 'table_ids', 'sequence', 'pos_config_ids']
```

Adding a field to an existing model: `return super()._load_pos_data_fields(config) + ['my_field']`
(addons/pos_cashmatic/models/pos_payment_method.py). Inspect the merged method with
`odoo_method pos.load.mixin _load_pos_data_domain` and test with `odoo_shell`.

Source: addons/point_of_sale/models/pos_load_mixin.py, addons/point_of_sale/models/pos_session.py:165,
addons/pos_restaurant/models/pos_session.py, addons/pos_restaurant/models/pos_restaurant.py

## JS models

Every loaded model gets a JS model automatically; add a class only for methods/state:

```javascript
// addons/pos_restaurant/static/src/app/models/restaurant_table.js (trimmed)
import { registry } from "@web/core/registry";
import { Base } from "@point_of_sale/app/models/related_models";

export class RestaurantTable extends Base {
    static pythonModel = "restaurant.table";

    setup(vals) {                 // called on create and update
        super.setup(vals);
        this.table_number = vals.table_number || 0;
    }
    initState() {                 // called once on creation: device-local uiState
        super.initState();
        this.uiState = { orderCount: 0, changeCount: 0 };
    }
    getOrder() {
        return this.backLink("<-pos.order.table_id").find((o) => !o.finalized);
    }
}
registry.category("pos_available_models").add(RestaurantTable.pythonModel, RestaurantTable);
```

- Extend a core model with `patch(PosOrder.prototype, { setup() { super.setup(...arguments); ... } })`
  (addons/pos_restaurant/static/src/app/models/pos_order.js).
- Model collection API (`pos.models["pos.order"]`): `get(id)`, `getBy(field, value)`, `getAll()`,
  `getFirst()`, `filter/find/some/every/map/forEach`, `create(vals)`, `createMany`, `update(record, vals)`,
  `delete(record)`, `readMany(ids)`, `addEventListener("create"|"update"|"delete", cb)`, `length`.
- Records: relational fields are records (`order.table_id.table_number`), `record.raw` is immutable
  server data, `record.update(vals)`, `record.delete()`, `record.isSynced`, `record.uiState`.

Source: addons/point_of_sale/static/src/app/models/related_models/index.js, addons/point_of_sale/static/src/app/models/related_models/base.js,
addons/point_of_sale/static/src/app/models/pos_order.js:1155, addons/point_of_sale/static/src/app/plugins/pos_data_plugin.js:487

## Screens, buttons, dialogs

Pages are registered with a route; navigate through the store so the order remembers its screen:

```javascript
// addons/point_of_sale/static/src/app/screens/product_screen/product_screen.js:516
registry.category("pos_pages").add("ProductScreen", {
    name: "ProductScreen",
    component: ProductScreen,
    route: `/pos/ui/${odoo.pos_config_id}/product/{string:orderUuid}`,
    params: { orderUuid: true, orderFinalized: false },
});
// elsewhere
this.pos.navigate("ProductScreen", { orderUuid: order.uuid });
```

Add a control button by extending `point_of_sale.ControlButtons` (parametric `t-call` with attributes,
`.translate` for literal strings) and patching `ControlButtons` for the handler:

```xml
<!-- addons/pos_discount/static/src/app/screens/product_screen/control_buttons/control_buttons.xml -->
<t t-name="pos_discount.ControlButtons" t-inherit="point_of_sale.ControlButtons" t-inherit-mode="extension">
    <xpath expr="//t[@t-if='this.props.showRemainingButtons']/div/t[@name='o_pricelist_button']" position="before">
        <t t-if="this.pos.config.module_pos_discount" t-call="point_of_sale.controlButton"
           icon="'sell'" btnText.translate="Discount" btnClasses="'js_discount btn-secondary '"
           onClick="() => this.clickDiscount()"/>
    </xpath>
</t>
```

Dialogs: `this.dialog.add(NumberPopup, { title, startingValue, getPayload: (v) => ... })`, or await a
result with `makeAwaitable(this.dialog, TextInputPopup, props)` / `ask(this.dialog, props)` from
`@point_of_sale/app/utils/make_awaitable_dialog`. Popup props are declared with `useProps` and include
`getPayload: t.function()` and `close: t.function()`
(addons/point_of_sale/static/src/app/components/popups/text_input_popup/text_input_popup.js).

Source: addons/point_of_sale/static/src/app/services/pos_store.js:360, addons/pos_discount/static/src/app/screens/product_screen/control_buttons/control_buttons.js,
addons/point_of_sale/static/src/app/utils/make_awaitable_dialog.js

## Payment providers

1. Python: add the selection value via `_get_terminal_provider_selection`, `_get_external_qr_provider_selection`
   or `_get_cash_machine_selection` on `pos.payment.method` (they feed the `payment_provider` field), and
   load your config fields with `_load_pos_data_fields`.
2. JS: subclass `PaymentInterface` and register it under the same key.

```javascript
// addons/pos_cashmatic/static/src/app/payment_cashmatic.js (shape)
import { PaymentInterface } from "@point_of_sale/app/utils/payment/payment_interface";
import { registry } from "@web/core/registry";

export class PaymentCashmatic extends PaymentInterface {
    setup() {
        super.setup(...arguments);   // sets this.pos, this.env, this.orm, this.dialog, this.payment_method_id
    }
    async sendPaymentRequest(line) { /* return true on success, false to retry */ }
    async sendPaymentCancel(line) {}
}
registry.category("pos_payment_providers").add("cashmatic", PaymentCashmatic);
```

```python
# addons/pos_cashmatic/models/pos_payment_method.py
def _get_cash_machine_selection(self):
    return super()._get_cash_machine_selection() + [('cashmatic', 'Cashmatic')]
```

Other hooks: `close()`, `amountInserted` getter, `connectWebSocket(channel, cb)`,
`callPaymentMethod(method, params)` (use it instead of calling the ORM), `canBeAdjusted(uuid)`. Put the
provider file in both `point_of_sale._assets_pos` and `point_of_sale.payment_terminals` (the latter is
reused by pos_self_order).

Source: addons/point_of_sale/static/src/app/utils/payment/payment_interface.js,
addons/point_of_sale/static/src/app/plugins/pos_payment_method_plugin.js, addons/point_of_sale/models/pos_payment_method.py:18,
addons/pos_cashmatic/__manifest__.py

## Receipts (server QWeb)

Receipts are `ir.ui.view` QWeb templates (`point_of_sale.pos_order_receipt`, `..._header`,
`..._footer`, `pos_orderline_receipt`, `pos_order_change_receipt`, ...) listed in
`ir.ui.view._get_xml_ids_to_load()`; they are sent with the POS data and converted for client-side
rendering by `registerPythonTemplate` (supports `t-if/t-elif/t-else/t-foreach/t-att/t-attf/t-call/
t-out/t-set`; raises on `t-field`, `t-options`, `t-lang`, ...). The data dict (`order`, `lines`,
`payments`, `conditions`, `extra_data`, ...) is built twice: Python `pos.order.receipt`
(`order_receipt_generate_data`, `_order_receipt_generate_*`) and JS `GeneratePrinterData`.

To add something to the ticket, change all three:

```xml
<!-- addons/pos_safaricom/receipt/pos_order_receipt.xml (in manifest data) -->
<template id="pos_safaricom.pos_order_receipt" inherit_id="point_of_sale.pos_order_receipt">
    <xpath expr="//t[@name='payments']/tr" position="after">
        <tr t-if="payment['safaricom_transaction_id']" class="payment-line">
            <td class="text-start w-70 text-small">Transaction ID:</td>
            <td class="text-end w-30 text-small" t-out="payment['safaricom_transaction_id']"/>
        </tr>
    </xpath>
</template>
```

```python
# addons/pos_safaricom/receipt/pos_order_receipt.py
class PosOrderReceipt(models.AbstractModel):
    _inherit = 'pos.order.receipt'

    def _order_receipt_generate_payment_data(self):
        payments = super()._order_receipt_generate_payment_data()
        ...
        return payments
```

```javascript
// addons/l10n_gcc_pos/static/src/app/utils/printer/generate_printer_data.js
patch(GeneratePrinterData.prototype, {
    generateReceiptData() {
        const data = super.generateReceiptData(...arguments);
        data.conditions.gcc_country = this.order.isGccCountry;
        return data;
    },
});
```

Write receipt templates in server QWeb style (`t-out`, dict access `x['k']` or `x.get('k')`, no
`this.`); they are in `EXCLUDED_TEMPLATES` of the owl3 migration. Print with
`this.pos.ticketPrinter.printOrderReceipt({ order })`.

Source: addons/point_of_sale/models/ir_ui_view.py, addons/point_of_sale/static/src/app/utils/convert_python_template.js,
addons/point_of_sale/receipt/pos_order_receipt.py, addons/point_of_sale/static/src/app/utils/printer/generate_printer_data.js,
addons/point_of_sale/static/src/app/plugins/pos_ticket_printer_plugin.js:297, odoo/upgrade_code/owl3-migration.py

## Assets and tests

```python
'assets': {
    'point_of_sale._assets_pos': ['my_pos/static/src/**/*'],
    'point_of_sale.payment_terminals': ['my_pos/static/src/app/payment_my.js'],  # payment providers only
    'web.assets_unit_tests': ['my_pos/static/tests/unit/**/*'],
    'web.assets_tests': ['my_pos/static/tests/tours/**/*'],
},
```

`point_of_sale._assets_pos` is a standalone bundle that ships `web/static/lib/owl/owl.js` followed by
`owl2/owl3_compatibility_layer.js` and `owl2/utils.js` (MAN003 gotcha, see
[assets.md](../../owl/references/assets.md)); it is included by `point_of_sale.assets_prod` (adds
`main.js`). Hoot helpers: `setupPosEnv()`, `setupAndMountPosApp()`, `waitUntilOrdersSynced(store)` in
`@point_of_sale/../tests/unit/utils`. Check bundle content with `odoo_assets point_of_sale._assets_pos`.

Source: addons/point_of_sale/__manifest__.py:183, addons/pos_cashmatic/__manifest__.py,
addons/point_of_sale/static/tests/unit/utils.js:22

## Self-order (pos_self_order)

- Separate app/bundle `pos_self_order.assets` (includes `point_of_sale.base_app` and
  `point_of_sale.payment_terminals`); store is the legacy service `self_order` (`SelfOrder`, `useSelfOrder()`
  from `@pos_self_order/app/services/self_order_service`) plus a `router` service with
  `navigate("product_list" | "cart" | ...)`. Pages live in `pos_self_order/static/src/app/pages/`.
- It reuses `PosDataPlugin`/`PosTicketPrinterPlugin` (`usePlugin` in `SelfOrder.setup`) and patches
  `PosDataPlugin.prototype.loadInitialData` to fetch `/pos-self/data/<config_id>` (public route).
- Python: models listed by `pos.config._load_self_data_models()`; per-model hooks
  `_load_pos_self_data_domain(data)`, `_load_pos_self_data_fields(config)`, `_load_pos_self_data_read(records, config)`
  default to the `_load_pos_data_*` ones (pos_self_order/models/pos_load_mixin.py). Override them to
  hide data from anonymous customers.
- `SelfOrder` still extends the deprecated `Reactive` (`@web/core/utils/reactive`, now `proxy(this)`);
  new classes should use `proxy()` directly.

Source: addons/pos_self_order/__manifest__.py, addons/pos_self_order/static/src/app/services/self_order_service.js,
addons/pos_self_order/static/src/app/plugins/pos_data_plugin.js, addons/pos_self_order/models/pos_config.py:347,
addons/pos_self_order/controllers/self_entry.py:36, addons/web/static/src/core/utils/reactive.js

## v19 habit -> Odoo 20

| v19 | Odoo 20 | Source |
|---|---|---|
| `useService("pos_data")`, `"pos_router"`, `"number_buffer"`, `"alert"` | `usePlugin(PosDataPlugin)`, `PosRouterPlugin`, `PosNumberBufferPlugin`, `PosAlertPlugin` (or `this.pos.data/router/numberBuffer/alert`) | addons/point_of_sale/static/src/app/plugins |
| services `printer`, `renderer` (`printer_service.js`, `render_service.js`) | `PosTicketPrinterPlugin` (`this.pos.ticketPrinter`); `hardware_proxy` service is gone from the POS JS |  addons/point_of_sale/static/src/app/plugins/pos_ticket_printer_plugin.js |
| `register_payment_method("adyen", PaymentAdyen)` + `use_payment_terminal` | `registry.category("pos_payment_providers").add("adyen", ...)` + `payment_provider` (JS010) | addons/pos_adyen/static/src/app/utils/payment/payment_adyen.js:402 |
| `_load_pos_data_domain(self, data, config)` | `_load_pos_data_domain(self, data)`; config = `data['pos.config']` (recordset) | addons/point_of_sale/models/pos_load_mixin.py |
| `_load_pos_data_search_read`, `load_data(models_to_load)`, `load_data_params()` | `_load_pos_metadata` / `_read_pos_data_from_metadata`, `load_data(local_data)` | addons/point_of_sale/models/pos_session.py:190 |
| `static props = {...}`, `useState`, `useRef` in popups | `props = useProps({...})`, `proxy`, `signal.ref()` (JS001, JS002) | addons/point_of_sale/static/src/app/components/popups/text_input_popup/text_input_popup.js |
| `<t t-call="x"><t t-set="icon" .../></t>` | `<t t-call="x" icon="'sell'" btnText.translate="..."/>` | addons/pos_discount/static/src/app/screens/product_screen/control_buttons/control_buttons.xml |
| OWL receipt components | server QWeb receipts + `GeneratePrinterData` | addons/point_of_sale/receipt |
