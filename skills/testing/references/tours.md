# Tours (Odoo 20)

Tours drive a real browser through the UI step by step. Odoo 20 keeps the v19 step format but
validates tours and steps strictly (unknown keys are errors), drops the `/js/` segment from
`@web_tour` imports, adds the `robot` activation keyword and uses Material Symbols icons in
selectors. Read this to write a tour, run it from a Python `HttpCase`, or debug a failing one.
House rules for tours: [Odoo test guidelines](../../odoo-guidelines/guidelines/tests.md).

## Contents

- Files and bundle
- Registering a tour
- Step keys
- `run` actions
- `isActive`
- Helpers: `stepUtils`, `searchOrCreateMany2X`
- Triggers and icons
- Running from Python
- Onboarding tours (database)
- Debugging
- v19 habit -> Odoo 20

## Files and bundle

```text
my_module/static/tests/tours/library_tour.js      # test tour
my_module/tests/test_library_ui.py               # HttpCase that starts it
```

```python
'assets': {
    'web.assets_tests': ['my_module/static/tests/tours/**/*'],
    # if static/tests also holds Hoot tests, remove tours from the unit bundle:
    'web.assets_unit_tests': ['my_module/static/tests/**/*', ('remove', 'my_module/static/tests/tours/**/*')],
},
```

`web.assets_tests` is loaded by test runs (`start_tour`); it also includes
`web_tour/static/src/tour_helpers/tour_helpers.js` and the `web_tour.automatic` bundle.

Source: addons/web_tour/__manifest__.py:34-37, addons/project/__manifest__.py:110-112, addons/hr/__manifest__.py:89-96

## Registering a tour

```javascript
import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

registry.category("web_tour.tours").add("my_module_library_tour", {
    url: "/odoo",                                   // optional
    steps: () => [                                  // required: a FUNCTION returning the steps
        stepUtils.showAppsMenuItem(),
        {
            trigger: '.o_app[data-menu-xmlid="my_module.menu_root"]',
            run: "click",
        },
        {
            trigger: ".o_list_button_add",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name=name] input",
            run: "edit Dune && press Tab",
        },
        ...stepUtils.saveForm(),
        {
            content: "the record is listed in the breadcrumb",
            trigger: ".o_breadcrumb:contains(Dune)",   // no run: just wait for it
        },
    ],
});
```

The registry validates with `t.strictObject({ steps: t.function(), url: t.string().optional() })`:
any other key (`name`, `wait_for`, `test`, `sequence`, ...) makes `add()` throw.

Source: addons/web_tour/static/src/tour_plugin.js:16-60, addons/project/static/tests/tours/project_task_templates_tour.js

## Step keys

Steps are checked with a strict schema when the tour starts; a violation is `console.error`ed,
which fails an automated run.

| Key | Type | Mode | Meaning |
|---|---|---|---|
| `trigger` | string (required) | all | Hoot-dom selector to wait for; the action runs on its first match. Waits until the element is found, enabled, not under a UI block, in the top-most modal, and (for iframes / website) `is-ready`. |
| `run` | string or non-empty function | all | Action (below). Omitted = only wait for `trigger`. `run: true` is invalid. |
| `content` | string | auto (string or `_t`/markup object in onboarding) | Description, shown in logs and tooltips. |
| `isActive` | string[] | all | Activation filter (below). |
| `id` | string | all | Step identifier. |
| `timeout` | number 0..60000 | auto | Per-step timeout in ms (default 10000). |
| `expectUnloadPage` | boolean | auto | The action reloads/leaves the page; the tour resumes after reload. Fails if no unload happens within 20 s. |
| `tooltipPosition` | `"top"`/`"bottom"`/`"left"`/`"right"` | all | Pointer position (onboarding). |
| `pause`, `break` | boolean | debug only | Pause (`play()` in the console to resume) / `debugger` before the step. |

Source: addons/web_tour/static/src/tour_plugin.js:16-53, 285-305;
addons/web_tour/static/src/tour_automatic/tour_step_automatic.js:15-70

## `run` actions

String form: `"<action> <argument>"`, several actions chained with `&&`. Without a selector argument
the action targets the trigger element (the "anchor").

| Action | Example |
|---|---|
| `click`, `dblclick`, `hover` | `run: "click"`, `run: "click .o_rows:first"` |
| `edit <text>` | `run: "edit Hello"` (clears then types into the anchor) |
| `fill <text>` | autocomplete inputs (`fill` does not clear first) |
| `clear` | `run: "clear"` |
| `press <keys>` | `run: "press Enter"`, `run: "edit 42 && press Tab"` |
| `check`, `uncheck` | checkboxes / radios (fails if the state does not change) |
| `select <value>`, `selectByIndex <i>`, `selectByLabel <text>` | `<select>` elements |
| `range <value>` | `input[type=range]` |
| `drag_and_drop <selector>` | drag the anchor onto the selector |
| `goToUrl <url>` | navigate (pair with `expectUnloadPage: true`) |
| `editor <text>` | contenteditable (html editor) |
| `scroll`, `canvasNotEmpty`, `inputFiles` | see tour_helpers_hoot.js |

Function form: `async run(helpers)` where `this.anchor` is the trigger element and `helpers` has
the actions above plus `queryAll`, `queryFirst`, `queryOne`, `waitFor`, `waitUntil`,
`animationFrame`:

```javascript
{
    trigger: ".o_kanban_record:contains(Dune)",
    async run({ click, queryFirst }) {
        if (queryFirst(".o_kanban_record .o_dropdown_kanban")) {
            await click(".o_kanban_record .o_dropdown_kanban");
        }
    },
},
```

Source: addons/web_tour/static/src/tour_step.js:242-259, addons/web_tour/static/src/tour_helpers/tour_helpers_hoot.js

## `isActive`

| Value | Step runs when |
|---|---|
| `"auto"` / `"manual"` | the tour runs automatically (tests) / interactively (onboarding) |
| `"robot"` (new in 20.0) | automatic mode, or a manual tour started with `robot: true` (onboarding replayed by a robot) |
| `"desktop"` / `"mobile"` | screen is not small / is small |
| `"community"` / `"enterprise"` | edition (from `server_version_info`) |
| any other string | a selector that must exist, else the step is skipped |

All listed conditions must hold. `[]` or no key = always active.

Source: addons/web_tour/static/src/tour_step.js:32-76

## Helpers: `stepUtils`, `searchOrCreateMany2X`

`import { stepUtils } from "@web_tour/tour_utils";`

| Helper | Returns |
|---|---|
| `showAppsMenuItem()` | step opening the apps menu (community, desktop) |
| `toggleHomeMenu()` | steps (enterprise home menu / mobile) |
| `goToAppSteps(menuXmlid, description)` | open an app from the apps menu |
| `autoExpandMoreButtons(isActiveMobile=false)` | expand the form button box "More" (auto) |
| `statusbarButtonsSteps(text, description, trigger?)` | click a statusbar button, opening the split dropdown if needed |
| `mobileKanbanSearchMany2X(modalTitle, value)` | mobile many2x search dialog |
| `saveForm()` / `discardForm()` | click save / discard and wait for completion |
| `goToUrl(url)` | auto step with `goToUrl` + `expectUnloadPage` |

`import { searchOrCreateMany2X } from "@web_tour/tour_scenarios";` (new) returns steps that type in
a many2one and either select an existing record (`selectExisting: true`) or create it through
"Create and edit" (`fields: { name: "..." }`, robot-only steps), on desktop and mobile.

Source: addons/web_tour/static/src/tour_utils.js, addons/web_tour/static/src/tour_scenarios.js:74-140

## Triggers and icons

- Selectors are Hoot-dom selectors: CSS plus `:contains(text)`, `:visible`, `:first`, `:eq(n)`,
  `:has(...)`, `:not(...)`, `:iframe` (see [hoot.md](hoot.md)). Steps match visible elements unless
  the selector mentions `:hidden`/`:visible`.
- Icons are Material Symbols: target `[data-icon='close']`, `.btn [data-icon='search']`, not `.fa-*`.
- Prefer stable hooks (`name` attributes, `data-menu-xmlid`, `o_*` classes) over texts that get
  translated.

Source: addons/web_tour/static/src/tour_step.js:93-110, addons/web_tour/static/src/tour_utils.js:113,
addons/mail/static/tests/tours/mail_poll_tour.js, addons/calendar/static/tests/tours/calendar_tour.js

## Running from Python

```python
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestLibraryUi(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['library.book'].create({'name': 'Existing'})

    def test_library_tour(self):
        self.start_tour("/odoo", "my_module_library_tour", login="admin")
```

`start_tour(url_path, tour_name, step_delay=None, **kwargs)` wraps `browser_js`: it opens
`url_path` logged in as `login` (default: not logged in), waits for `odoo.isTourReady(name)`, runs
`odoo.startTour(name, {stepDelay, debug})` and succeeds on the console message
`tour succeeded`. Extra kwargs go to `browser_js`: `timeout` (default 60 s), `watch=True` (visible
browser), `debug=True` (devtools + breakpoint, `debug=assets`), `cookies`, `error_checker`,
`cpu_throttling`. Onboarding tours are disabled for users during the run (`tour_enabled`
patched). Nothing is committed: data created in `setUpClass` or earlier in the test is visible to
the browser because `HttpCase` serves requests through a `TestCursor` wrapping the test
transaction (`registry_test_mode`), and `browser_js` flushes before starting.

Source: odoo/tests/common.py:2881-3008, addons/project/tests/test_task_templates_ui.py

## Onboarding tours (database)

Interactive tours are `web_tour.tour` records (`name`, `url`, `sequence`, `rainbow_man_message`,
`step_ids`, `custom`) whose JS steps come from the registry when the record has none. They run in
`manual` mode (`?tour=<name>` in the URL, or started for new users); use `isActive: ["auto"]` /
`["manual"]` / `["robot"]` to split behaviour between the test run and the onboarding.

Source: addons/web_tour/models/tour.py:6-50, addons/web_tour/static/src/tour_plugin.js:80-185,
addons/crm/data/crm_tour.xml

## Debugging

| Technique | How |
|---|---|
| Watch it run | `self.start_tour(..., watch=True)` or `step_delay=500` (local only) |
| DevTools + breakpoint | `self.start_tour(..., debug=True)`; add `pause: true` / `break: true` on a step (debug mode only) |
| Run in your browser | on a dev server (`odoo_server`), console: `odoo.startTour("my_module_library_tour", { mode: "auto", stepDelay: 300, debug: true })` |
| Read the failure | log shows `[i/n] Tour <name> -> Step <content> (trigger: ...)` then the error; a timeout means the trigger never matched (wrong selector, element disabled, UI blocked, modal on top) |
| Screenshots / video | failures save a screenshot under `--screenshots` (default `/tmp/odoo_tests/<db>/screenshots`); `--screencasts=DIR` records the run |
| No timeouts while stepping | `ODOO_TEST_DISABLE_TIMEOUT=1 odoo-bin ...` |
| Inspect the live DOM | chrome-devtools MCP against a running `odoo_server` |
| Unexpected reload | the step that navigates needs `expectUnloadPage: true`; leave the client stable at the last step |

Source: odoo/tests/common.py:116, 2881-2950; addons/web_tour/static/src/tour_plugin.js:232-276;
addons/web_tour/static/src/tour_automatic/tour_automatic.js:140-165; odoo/tools/config.py:346-352

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `import ... from "@web_tour/js/tour_state"` (any `@web_tour/js/...`) | `@web_tour/tour_state`, `@web_tour/tour_step`, `@web_tour/tour_automatic/tour_automatic`, `@web_tour/tour_pointer/tour_pointer` (JS011) | addons/web_tour/static/src |
| `@web_tour/js/utils/tour_utils` helpers | no equivalent file (unverified replacement); `stepUtils` stays in `@web_tour/tour_utils` | addons/web_tour/static/src/tour_utils.js |
| tour keys `name`, `wait_for` | removed; only `steps` (function) and `url` | addons/web_tour/static/src/tour_plugin.js:55-60 |
| step key `debugHelp`, `run: true` | removed / invalid (`run` = string or non-empty function) | addons/web_tour/static/src/tour_plugin.js:16-53 |
| `tour_service` (`useService("tour_service")`) | `TourPlugin` (`@web_tour/tour_plugin`); `tour_service` remains as a temporary compat service | addons/web_tour/static/src/tour_plugin.js:309-323 |
| `.fa-times`, `.fa-search` triggers | `[data-icon='close']`, `[data-icon='search']` | odoo/upgrade_code/material_symbols_icons_mapping.py |
| onboarding-only steps with `isActive: ["manual"]` | also `"robot"` for steps a replaying robot must perform | addons/web_tour/static/src/tour_step.js:43, 62 |

Validate a tour file with `odoo_validate` (JS011 and icon rules), then run the `HttpCase` with
`odoo_test` (see [running-tests.md](running-tests.md)).
