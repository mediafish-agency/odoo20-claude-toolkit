# Hoot JS unit tests (Odoo 20)

Odoo 20 JS unit tests use Hoot only (QUnit and the legacy test helpers are gone). This file covers
where `*.test.js` files go, the `@odoo/hoot` / `@odoo/hoot-dom` APIs, the mock server and app
helpers from `@web/../tests/web_test_helpers`, a complete field-widget example, and how to run
the suite. JS style rules: [Odoo web guidelines](../../odoo-web-guidelines/guidelines/javascript.md).

## Contents

- Files and bundles
- `@odoo/hoot`: suites, hooks, modifiers, mocks
- `expect`: matchers and steps
- `@odoo/hoot-dom`: queries, interactions, time
- `@web/../tests/web_test_helpers`
- Complete example: a field widget in a form view
- Testing a plugin or service without a view
- Running the tests
- v19 habit -> Odoo 20

## Files and bundles

```text
my_module/static/
  src/fields/upper_char_field.js      # code under test (in web.assets_backend)
  src/fields/upper_char_field.xml
  tests/upper_char_field.test.js      # unit tests: *.test.js
  tests/my_module_test_helpers.js     # optional shared helpers / mock models
  tests/tours/*.js                    # tours: NOT unit tests (web.assets_tests)
```

```python
# __manifest__.py
'assets': {
    'web.assets_backend': ['my_module/static/src/**/*'],
    'web.assets_unit_tests': [
        'my_module/static/tests/**/*',
        ('remove', 'my_module/static/tests/tours/**/*'),
    ],
    'web.assets_tests': ['my_module/static/tests/tours/**/*'],
},
```

- Files under `static/src` and `static/tests` are ES modules automatically (no `odoo.define`);
  a test imports code as `@my_module/fields/upper_char_field` and helpers as
  `@my_module/../tests/my_module_test_helpers`.
- The test page loads `web.assets_unit_tests_setup` (OWL, Hoot, and `web.assets_backend` +
  `web.assets_backend_lazy`), then `web.assets_unit_tests`. Each addon's tests run against a
  "module set" built from that addon and its dependencies, so backend code of your addon
  (field registrations, templates) is available without importing it.
- Check what a bundle really contains with `odoo_assets("web.assets_unit_tests")`.

Source: addons/web/__manifest__.py:422-464, addons/project/__manifest__.py:105-112,
addons/hr/__manifest__.py:89-96, addons/web/static/tests/_framework/module_set.hoot.js

## `@odoo/hoot`: suites, hooks, modifiers, mocks

```javascript
import { after, afterEach, before, beforeEach, describe, expect, test } from "@odoo/hoot";
```

| Export | Use |
|---|---|
| `test(name, fn)` / `describe(name, fn)` | Test / suite. Each test file is already wrapped in a suite named after its path. |
| `beforeEach`, `afterEach`, `before`, `after`, `onError` | Hooks (inside or outside `describe`); `after(fn)` inside a test registers a cleanup. |
| `test.tags("desktop")` then `test(...)` | Modifiers apply to the **next** `test`/`describe` call. Also `.skip`, `.todo`, `.only`, `.debug` (getters), `.config({...})`, `.timeout(ms)`, `.multi(n)`. |
| `describe.current.tags("desktop")` | Tag the current (file) suite. Common tags: `desktop`, `mobile`, `headless`. |
| `getFixture()` | DOM container of the current test. |
| `mockDate`, `mockTimeZone`, `mockLocale`, `onTimeZoneChange` | Time and locale mocks. |
| `mockFetch`, `withFetch`, `mockLocation`, `mockWebSocket`, `mockWorker` | Network mocks (the mock server already handles RPCs). |
| `mockMatchMedia`, `mockTouch`, `mockUserAgent`, `mockPermission`, `mockSendBeacon`, `mockVibrate` | Browser mocks. |
| `disableAnimations`, `enableTransitions`, `makeSeededRandom`, `flushNotifications`, `watchListeners`, `watchKeys`, `watchAddedNodes` | Misc. |
| everything from `@odoo/hoot-dom` | Re-exported, so `import { click, animationFrame } from "@odoo/hoot"` works. |

`@odoo/hoot-mock` is an alias module exposing the time helpers and the mocks above; core tests
import `animationFrame`/`advanceTime` from either `@odoo/hoot-mock` or `@odoo/hoot`.

Never commit `.only` / `.debug`: `web/tests/test_js.py` fails the suite on `test.*\.(only|debug)\(`.

Source: addons/web/static/lib/hoot/hoot.js, addons/web/static/lib/hoot/hoot-mock.js,
addons/web/static/lib/hoot/core/runner.js:1336-1465, addons/web/tests/test_js.py:12

## `expect`: matchers and steps

`expect(value)` then exactly one matcher; every matcher accepts a last `{ message }` option.
Modifiers: `.not`, `.resolves`, `.rejects` (await the latter two).

| Value matchers | DOM matchers (value = selector string or element) |
|---|---|
| `toBe`, `toEqual`, `toMatchObject`, `toMatch`, `toInclude`, `toHaveLength` | `toHaveCount(n)`, `toBeVisible`, `toBeDisplayed`, `toBeEnabled`, `toBeFocused`, `toBeChecked` |
| `toBeEmpty`, `toBeOfType`, `toBeInstanceOf`, `toThrow` | `toHaveText(text)`, `toHaveValue(v)`, `toHaveClass(c)`, `toHaveAttribute(a, v?)`, `toHaveProperty(p, v?)` |
| `toBeCloseTo`, `toBeGreaterThan`, `toBeLessThan`, `toBeWithin` | `toHaveStyle(s)`, `toHaveRect(r)`, `toHaveInnerHTML(h)`, `toHaveOuterHTML(h)` |

Static helpers on `expect`:

| Helper | Meaning |
|---|---|
| `expect.step(value)` | Record a step (string, array, object). |
| `expect.verifySteps([...])` | Assert and consume the recorded steps (synchronous). |
| `await expect.waitForSteps([...])` | Wait until those steps were recorded (async flows). |
| `expect.assertions(n)` | Expected number of assertions. |
| `expect.errors(n)` + `expect.verifyErrors([/re/])` / `await expect.waitForErrors([...])` | Expected uncaught errors. |

A test fails if it ends with unverified steps, if `expect()` was called without a matcher, or if
it ran no assertion and no query (`waitFor`/`waitForNone`).

Source: addons/web/static/lib/hoot/core/expect.js:495-1064, 1295-2285

## `@odoo/hoot-dom`: queries, interactions, time

Selectors accept CSS plus Hoot pseudo-classes: `:contains(text)`, `:text(exact)`, `:value(v)`,
`:visible`, `:hidden`, `:displayed`, `:first`, `:last`, `:eq(i)`, `:only`, `:has(sel)`,
`:not(sel)`, `:empty`, `:focusable`, `:selected`, `:scrollable`, `:iframe`, `:shadow`,
`:count(n)`, `:viewPort`, `:interactive`.

| Kind | Functions |
|---|---|
| Queries | `queryAll`, `queryOne` (exactly one), `queryFirst`, `queryAny`, `queryText`, `queryAllTexts`, `queryValue`, `queryAttribute`, `queryRect`, `queryAll*`, `waitFor`, `waitForNone`, `waitUntil(fn)`, `matches`, `isVisible`, `isDisplayed`, `isFocusable`, `isInDOM`, `getActiveElement`, `formatXml` |
| Interactions (await them) | `click`, `dblclick`, `rightClick`, `middleClick`, `hover`, `leave`, `pointerDown`, `pointerUp`, `press(keys)`, `keyDown`, `keyUp`, `edit(value)`, `fill(value)`, `clear()`, `select(value)`, `check`, `uncheck`, `drag(...)`, `scroll`, `resize`, `setInputFiles`, `setInputRange`, `unload`, `on(target, type, fn)` |
| Time | `animationFrame()`, `advanceTime(ms)`, `advanceFrame(n)`, `runAllTimers()`, `tick()`, `microTick()`, `delay(ms)`, `freezeTime()`, `unfreezeTime()`, `cancelAllTimers()`, `setFrameRate(fps)` |

`edit`/`fill`/`clear` act on the focused element: click (or use `contains(...)`) first. After an
interaction that re-renders OWL, `await animationFrame()` before asserting.

Source: addons/web/static/lib/hoot-dom/hoot-dom.js, addons/web/static/lib/hoot-dom/helpers/dom.js:1215-1251

## `@web/../tests/web_test_helpers`

All names below are exported by addons/web/static/tests/web_test_helpers.js (checked).

| Area | Exports |
|---|---|
| Mock models | `models.Model` (also `models.ServerModel`), `fields.Char/Text/Html/Integer/Float/Monetary/Boolean/Date/Datetime/Selection/Many2one/One2many/Many2many/Reference/Many2oneReference/Binary/Image/Json/Properties/PropertiesDefinition/Generic`, `defineModels([...])`, `defineWebModels()`, `webModels` (incl. `IrAccess`), `Command`, `registerInlineViewArchs` |
| Mock server | `onRpc(...)`, `stepAllNetworkCalls()`, `MockServer` (`MockServer.env["model"]`), `makeMockServer()`, `defineActions`, `defineMenus`, `defineParams`, `serverState`, `authenticate`, `logout`, `withUser(uid, fn)`, `makeServerError`, `MockServerError`, `getKwArgs`, `makeKwArgs`, `unmakeKwArgs` |
| App / env | `makeTestApp({ forceNew })` (new), `getTestApp()`, `getMockEnv()`, `getService(nameOrPluginClass)`, `mockService(name, partialOrFactory)`, `runTestScope(fn)`, `destroyApp()`, `mockOffline()`, `clearRegistry`, `restoreRegistry`, deprecated `assignTestEnv`/`assignDialogTestEnv`/`clearTestEnv` |
| Mounting | `mountWithCleanup(ComponentOrTemplateString, { props, componentEnv, target, noMainContainer })`, `mountView({ type, resModel, resId, arch, archs, searchViewArch, context, ... })`, `mountViewInDialog`, `mountWebClient`, `useTestClientAction`, `findComponent`, `waitUntilIdle` |
| DOM shortcuts | `contains(selector).click()/edit(v)/fill(v)/clear()/check()/select(v)/press(k)/hover()/dragAndDrop(t)/selectDropdownItem(v)`, `fieldInput(name)`, `clickSave`, `clickCancel`, `clickButton`, `clickViewButton`, `clickModalButton`, `clickFieldDropdown(Item)`, `selectFieldDropdownItem`, `editSelectMenu`, `expectMarkup`, `getDropdownMenu`, `sortableDrag`, `defineStyle`, `editAce` |
| Search / kanban | `toggleFilterMenu`, `toggleMenuItem`, `editSearch`, `validateSearch`, `getFacetTexts`, `pagerNext`, ... ; `getKanbanRecord`, `quickCreateKanbanRecord`, ... |
| Misc | `patchWithCleanup` (deprecated alias of `patch` from `@web/core/utils/patch`, which is auto-restored after each test), `patchTranslations`, `allowTranslations`, `installLanguages`, `xml_translate`, `registerTemplate`, `isSmall()`, `swipeLeft/Right`, `preloadBundle(name)`, `preventResizeObserverError`, `dataURItoBlob` |

Mock model conventions: the model name defaults to the class name (`class Partner` -> `"partner"`);
set `_name = "library.book"` otherwise. Data in `_records = [{ id, ... }]`, default archs in
`_views = { form: "<form>...</form>", list: ... }`, onchanges in `_onChanges.field = (record) => {...}`.
Custom server methods are plain class methods (see `addons/project/static/tests/project_models.js`).

`onRpc` overloads: `onRpc(callback)`, `onRpc("/route", callback)`, `onRpc("method", callback)`,
`onRpc("model", "method", callback)`. ORM callbacks receive
`{ args, kwargs, model, method, route, request, parent }`: return a value (not `null`/`undefined`)
to answer, return nothing to fall through to the next listener and finally the mock model method
(`parent()` calls it explicitly). Route callbacks (`onRpc("/my/route", fn)`) receive
`(request, routeParams)`.

Source: addons/web/static/tests/web_test_helpers.js, addons/web/static/tests/_framework/app_test_helpers.js:100-320,
addons/web/static/tests/_framework/mock_server/mock_server.js:1535-1680,
addons/web/static/tests/_framework/mock_server/mock_fields.js:186-252,
addons/web/static/tests/_framework/dom_test_helpers.js:155-380

## Complete example: a field widget in a form view

Widget (OWL 3: `useProps`, `this.` in templates):

```javascript
// my_module/static/src/fields/upper_char_field.js
import { Component, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class UpperCharField extends Component {
    static template = "my_module.UpperCharField";
    props = useProps({ ...standardFieldProps });

    get value() {
        return (this.props.record.data[this.props.name] || "").toUpperCase();
    }

    onChange(ev) {
        this.props.record.update({ [this.props.name]: ev.target.value.trim() });
    }
}

registry.category("fields").add("upper_char", {
    component: UpperCharField,
    displayName: _t("Upper case text"),
    supportedTypes: ["char"],
});
```

```xml
<!-- my_module/static/src/fields/upper_char_field.xml -->
<templates xml:space="preserve">
    <t t-name="my_module.UpperCharField">
        <span t-if="this.props.readonly" t-out="this.value"/>
        <input t-else="" class="o_input" t-att-id="this.props.id"
               t-att-value="this.value" t-on-change="this.onChange"/>
    </t>
</templates>
```

Test:

```javascript
// my_module/static/tests/upper_char_field.test.js
import { expect, test } from "@odoo/hoot";
import {
    clickSave,
    defineModels,
    fieldInput,
    fields,
    models,
    mountView,
    onRpc,
} from "@web/../tests/web_test_helpers";

class LibraryBook extends models.Model {
    _name = "library.book";
    name = fields.Char();
    _records = [{ id: 1, name: "dune" }];
}

defineModels([LibraryBook]);

test("readonly: displays the value in upper case", async () => {
    await mountView({
        type: "form",
        resModel: "library.book",
        resId: 1,
        arch: `<form><field name="name" widget="upper_char" readonly="1"/></form>`,
    });
    expect(".o_field_widget[name=name] span").toHaveText("DUNE");
});

test("edit: writes the typed value", async () => {
    onRpc("library.book", "web_save", ({ args }) => {
        expect.step(["web_save", args[1]]);
    });
    await mountView({
        type: "form",
        resModel: "library.book",
        resId: 1,
        arch: `<form><field name="name" widget="upper_char"/></form>`,
    });
    expect(".o_field_widget[name=name] input").toHaveValue("DUNE");
    await fieldInput("name").edit("dune messiah"); // focus, type, confirm (Enter -> change)
    await clickSave();
    expect.verifySteps([["web_save", { name: "dune messiah" }]]);
});
```

Pattern taken from core tests (not executed here): addons/web/static/tests/views/fields/boolean_field.test.js,
addons/web/static/tests/views/fields/char_field.test.js:145, addons/project/static/tests/project_is_favorite_field.test.js;
widget shape from addons/web/static/src/views/fields/badge/badge_field.js and
addons/web/static/src/views/fields/standard_field_props.js.

## Testing a plugin or service without a view

```javascript
import { expect, test } from "@odoo/hoot";
import { getService, makeTestApp, onRpc } from "@web/../tests/web_test_helpers";

test("orm read goes through call_kw", async () => {
    onRpc(({ route }) => {
        expect.step(route);
    });
    await makeTestApp();                       // starts the plugins/services once per test
    await getService("orm").read("res.partner", [3], ["id"]);
    expect.verifySteps(["/web/dataset/call_kw/res.partner/read"]);
});
```

`getService(SomePlugin)` (a class) returns the running plugin instance; prefer it for code
converted to OWL plugins (e.g. `getService(OfflinePlugin)`). `mountWithCleanup` and `mountView`
create the app on demand; call `makeTestApp({ forceNew: true })` only to replace an existing one.

Source: addons/web/static/tests/core/orm_service.test.js:20-36, addons/bus/static/tests/bus_monitoring_plugin.test.js,
addons/web/static/tests/_framework/app_test_helpers.js:178-229

## Running the tests

| How | Command / URL | Notes |
|---|---|---|
| Browser (fastest loop) | `http://127.0.0.1:8069/web/tests?debug=assets` | Route `/web/tests` (`auth='user'`: log in first). URL params: `filter` (alias `name`, text search on test names, e.g. `@my_module`), `tag`, `id`, `preset=desktop|mobile`, `headless`, `loglevel`, `timeout`, `manual`, `bail`, `notrycatch`, `debugTest`. Start a server with `odoo_server`. |
| CLI, module already installed | `odoo-bin -d DB --test-tags hoot/my_module --stop-after-init` | Runs `WebSuite.test_unit_desktop` and `MobileWebSuite.test_unit_mobile` (tag `hoot`, cross-module) filtered to `@my_module`. Add `:WebSuite` for desktop only. `--test-tags /my_module` runs Python **and** Hoot tests. |
| CLI with `-i/-u` | add `web` to the updated modules (`-u web,my_module`) | Post-install tests are only collected from updated modules; with `-i my_module` on a DB where `web` is already installed, `web/tests/test_js.py` (the Hoot launcher) is not collected, so no Hoot test runs. |
| Toolkit | `odoo_test(modules="my_module", js_tests=True)` | Throwaway DB; adds `-u web` so web's `WebSuite`/`MobileWebSuite` are collected and scoped to `my_module` by the `/my_module` tag (headless Chrome). |

Failures appear in the server log as `[HOOT] Test "@my_module/..." failed:` with the failed
assertion; success ends with `[HOOT] Test suite succeeded`. Headless Chrome is required; without
Chrome (or the `websocket-client` package) the Hoot `HttpCase` is skipped, not failed.

Source: addons/web/controllers/webclient.py:99, addons/web/tests/test_js.py:191-217,
addons/web/static/lib/hoot/core/config.js:125-310, odoo/service/server.py:1529-1536, odoo/tests/common.py:2483

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| QUnit tests (`QUnit.module`, `QUnit.test`, `assert.*`), `web.qunit_suite_tests` | Hoot `*.test.js` in `web.assets_unit_tests` (JS007) | addons/web/static/lib/hoot/hoot.js |
| `makeMockEnv()` / `makeDialogMockEnv()` | `await makeTestApp()` then `getService(...)` / `getMockEnv()` (JS012) | addons/web/static/tests/_framework/app_test_helpers.js:193 |
| `asyncStep("x")` + `await waitForSteps([...])` from web_test_helpers | `expect.step("x")` + `await expect.waitForSteps([...])` (or `expect.verifySteps`) (JS012) | addons/web/static/lib/hoot/core/expect.js:835-1000 |
| `patchWithCleanup(obj, {...})` | still works (deprecated alias); `patch` from `@web/core/utils/patch` is auto-cleaned | addons/web/static/tests/web_test_helpers.js |
| `env.isSmall` in tests | `isSmall()` helper / `useService("ui").isSmall` (JS008) | addons/web/static/tests/_framework/ui_test_helpers.js |
| `static props = {...}` in test components | `props = useProps({...})` (JS001) | addons/web/static/src/owl2/owl3_compatibility_layer.js |
| `t-esc`, bare `props.x` in `xml` test templates | `t-out`, `this.props.x` (OWL001/OWL005) | odoo/upgrade_code/owl3-migration.py |
| Assertions on `fa-*` classes | `toHaveAttribute("data-icon", "person")` (Material Symbols) | odoo/upgrade_code/19.5-00-material-symbols-icons.py:540-560 |

Check a test file with `odoo_validate` (JS007, JS012, OWL rules) before running it.
