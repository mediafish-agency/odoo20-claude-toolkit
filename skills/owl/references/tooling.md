# JS tooling and debugging (Odoo 20)

Editor and lint setup for Odoo 20 frontend code (ESLint config, `jsconfig.json`, the `.d.ts` typings
under `static/src/@types`) and how to debug the web client: debug modes, OWL dev mode, console
handles, source maps, and the chrome-devtools MCP that Claude can drive against a dev server.

## Contents

- [Installing the tooling](#installing-the-tooling)
- [ESLint rules that matter](#eslint-rules-that-matter)
- [Linting a custom addon](#linting-a-custom-addon)
- [TypeScript typings for the IDE](#typescript-typings-for-the-ide)
- [Debug modes and OWL dev mode](#debug-modes-and-owl-dev-mode)
- [Console handles](#console-handles)
- [Debugging the web client](#debugging-the-web-client)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## Installing the tooling

The templates live in `addons/web/tooling/` and are copied to the repository root:

| Script | Does |
|---|---|
| `enable.sh` | sets `git config core.hooksPath` to `tooling/hooks`, copies `_eslintignore`, `_eslintrc.json`, `_jsconfig.json`, `_package.json` to `.eslintignore`, `.eslintrc.json`, `jsconfig.json`, `package.json`, runs `npm install`; optionally the same in an enterprise checkout |
| `refresh.sh` | re-copies the config files only |
| `reload.sh` | `disable.sh` then `enable.sh` |
| `disable.sh` | removes the files, `node_modules` and the hooks path |
| `hooks/pre-commit` | refreshes/reloads when the templates changed, then `npm run format-staged` (lint-staged + `eslint --fix`) |

`package.json` (node >= 16.11): `eslint ^8.27`, `prettier ^2.7`, `eslint-plugin-prettier`,
`eslint-plugin-diff`, `lint-staged`, `@types/luxon`, `@odoo/o-spreadsheet`, `sip.js`,
`@odoo/owl >=3.0.0-alpha.31 <4.0.0`. Scripts: `lint-all`, `lint-web`, `format-all`, `lint-diff`,
`format-diff` (only changed lines), `format-staged`.

```bash
cd /path/to/odoo && addons/web/tooling/enable.sh   # answers: enterprise? [y, n]
npm run lint-diff
```

Source: addons/web/tooling/enable.sh, addons/web/tooling/refresh.sh, addons/web/tooling/reload.sh, addons/web/tooling/disable.sh, addons/web/tooling/hooks/pre-commit, addons/web/tooling/_package.json

## ESLint rules that matter

`.eslintrc.json` extends `eslint:recommended` + `plugin:prettier/recommended`, `sourceType: module`,
`ecmaVersion: 2022`, browser env.

| Rule | Consequence |
|---|---|
| prettier: `tabWidth 4`, `printWidth 100`, double quotes, semicolons | formatting is enforced as errors |
| `no-restricted-syntax`: `PrivateIdentifier` | no `#private` class fields/methods |
| `no-restricted-syntax`: `useEffect` with more than one argument | OWL 3 ignores the deps argument (same as validator JS004); read signals inside the callback or use `useOnChange` |
| `no-restricted-syntax`: `useEffect` callback with parameters | OWL 3 calls it without arguments |
| `curly: all` | braces on every `if`/`else`/loop |
| `prefer-const`, `arrow-body-style: as-needed` | |
| `no-unused-vars` (`args: none`, `caughtErrors: all`) | unused catch bindings are errors: use `catch {` |
| `no-restricted-globals`: `event`, `self` | |
| `no-undef` | allowed globals: `odoo`, `luxon`, `Chart`, `FullCalendar`, `DOMPurify`, `Prism`, `SIP`, `py`, `fuzzy`, `StackTrace`, Bootstrap `Alert Collapse Dropdown Modal Offcanvas Popover Tooltip`, ... |

`$` and `jQuery` are still listed as globals but jQuery is **not shipped** in Odoo 20: ESLint will not
catch them, the validator does (JS006, JS017).

Source: addons/web/tooling/_eslintrc.json, addons/web/__manifest__.py

## Linting a custom addon

`.eslintignore` ignores everything except a whitelist of core addons (web, mail, point_of_sale,
website, html_editor, ...), so a custom addon placed under the Odoo root is skipped. For a separate
repository:

```bash
cp /path/to/odoo/addons/web/tooling/_eslintrc.json .eslintrc.json
cp /path/to/odoo/addons/web/tooling/_package.json package.json
npm install
npx eslint my_addon/static/src
```

Combine with `odoo_validate(path="my_addon")` (legacy-pattern rules, unresolved JS imports, MAN003).

Source: addons/web/tooling/_eslintignore

## TypeScript typings for the IDE

The typings are IDE-only (never loaded by Odoo). `jsconfig.json` at the repository root:

- `compilerOptions`: `"module": "preserve"`, `"target": "ES2022"`, `noEmit`, `typeRoots`
  (`*/static/src/@types`, `addons/mail/static/src/js/tooling/types`, `addons/web/tooling/types`; the
  last folder does not exist), and `paths` mapping every `@addon/*` to `./addons/addon/static/src/*`
  (`@web/../tests/x` therefore resolves to `addons/web/static/tests/x`).
- `include`: `**/*.js`, `**/*.ts` (so every `.d.ts` is picked up); `exclude`: `node_modules` and the
  vendored libs (`**/lib/owl`, `**/lib/bootstrap`, `**/lib/luxon`, ...).
- `@odoo/owl` resolves through `web/static/src/@types/owl.d.ts`:
  `declare module "@odoo/owl" { export * from "@web/../lib/owl/owl"; }`, i.e. the bundled
  `owl.d.ts` (OWL 3.0.0-alpha.50), not the npm package. Same for `@odoo/hoot` and `@odoo/hoot-dom`.

Addons shipping `static/src/@types`: web, bus, html_builder, html_editor, point_of_sale,
pos_glory_cash, printer, spreadsheet, test_translation_mode, web_tour, website, website_blog (plus
`mail/static/src/core/common/@types`). They declare ambient modules:

| Module | Content |
|---|---|
| `"registries"` | `GlobalRegistryCategories` (category name -> item shape) and `*RegistryItemShape` types |
| `"services"` | `Services` (name -> service) and `ServiceFactories` (name -> started value) |
| `"plugins"` | html_editor / website builder plugin shared APIs |

Use them from JSDoc (core style):

```javascript
/** @type {import("services").ServiceFactories} */
this.services = ...;
/** @typedef {import("@web/core/popover/popover_plugin").PopoverPlugin["add"]} PopoverAdd */
```

Declare your own registry category so `registry.category("my_addon.handlers")` is typed (pattern
from `printer`):

```typescript
// my_addon/static/src/@types/registry.d.ts
declare module "registries" {
    interface GlobalRegistryCategories {
        "my_addon.handlers": (record: Record<string, unknown>) => void | Promise<void>;
    }
}
```

For an addon outside the Odoo root, add `"@my_addon/*": ["./path/my_addon/static/src/*"]` to
`paths` and its folder to `include`. There is no `odoo-bin` command generating a tsconfig in 20.0
(the `@types/readme.md` mention is stale): use `enable.sh`.

Source: addons/web/tooling/_jsconfig.json, addons/web/static/src/@types/owl.d.ts, addons/web/static/src/@types/hoot.d.ts, addons/web/static/src/@types/registry.d.ts, addons/web/static/src/@types/registries/registries.d.ts, addons/web/static/src/@types/services.d.ts, addons/printer/static/src/@types/registry.d.ts, addons/website/static/src/@types/plugins.d.ts, addons/web/static/src/public/interaction.js:140, addons/web/static/src/core/popover/popover_hook.js:5, odoo/cli

## Debug modes and OWL dev mode

| URL | Effect |
|---|---|
| `?debug=1` | technical features, full tracebacks; OWL app runs in **dev mode** |
| `?debug=assets` | also unminified bundles with source maps (implies debug) |
| `?debug=tests` | also loads `web.assets_tests` (tours) |
| `?debug=assets,tests` | combine; `?debug=0` turns it off (value stored in the session) |

- The web client creates its OWL `App` with `dev: odoo.debug || session.test_mode`. In dev mode only,
  OWL validates `useProps` schemas (`Invalid prop 'x' in 'MyComponent'`), plugin config types and
  `props.static()` stability, and logs "Owl is running in 'dev' mode.". Without debug a wrong prop
  type passes silently: **reproduce prop bugs with `?debug=1`**.
- In code: `usePlugin(DebugModePlugin)` from `@web/core/debug_mode_plugin` (`isActive(mode?)`,
  `toList()`, `toString()`); outside a component or plugin read `odoo.debug`. `env.debug` throws
  (validator JS008).
- Command palette (debug on): "Activate debug mode (with assets)", "Deactivate debug mode",
  "Run Unit Tests" (`/web/tests?debug=assets`, the Hoot runner).

Source: addons/web/models/ir_http.py:34-61, addons/web/static/src/env.js:14-24, addons/web/static/src/env.js:111-130, addons/web/static/lib/owl/owl.js:1795-1803, addons/web/static/lib/owl/owl.js:4495-4504, addons/web/static/lib/owl/owl.js:4713-4725, addons/web/static/src/core/debug_mode_plugin.js, addons/web/static/src/core/debug/debug_providers.js, addons/web/controllers/webclient.py:99

## Console handles

| Expression | Gives |
|---|---|
| `odoo.debug` | active debug modes string (`""`, `"1"`, `"assets"`, ...) |
| `odoo.__WOWL_DEBUG__.root` | root component of the web client; `.env.services` for legacy services |
| `odoo.loader.modules.get("@web/core/registry")` | a loaded module's exports |
| `[...odoo.loader.modules.keys()].filter((k) => k.startsWith("@my_addon/"))` | is my code in the bundle? |
| `odoo.loader.factories` / `odoo.loader.failed` | defined / failed module names |
| `owl.App.apps` | every live OWL app (`owl` is a global) |

Module-loader errors are printed once at startup: "failed to load because of an error", "needed by
other modules but have not been defined, they may not be present in the correct asset bundle",
"dependency cycle", "unmet dependencies".

Source: addons/web/static/src/env.js:128, addons/web/static/src/module_loader.js:20-28, addons/web/static/src/module_loader.js:154-180, addons/web/static/lib/owl/owl.js:4481, addons/web/static/src/@types/odoo.d.ts

## Debugging the web client

Server side: start a dev server with the MCP tool `odoo_server(action="start", db=...)` (127.0.0.1,
port 8070 by default, `--dev=xml,qweb,access`). `--dev=xml` makes new asset files appear without a
restart; manifest edits still need one. A SCSS error shows the banner "A css error occurred, using an
old style to render this page" (details in the server log, `odoo_server(action="logs")`).

Browser side with the chrome-devtools MCP (tool names are prefixed
`mcp__plugin_chrome-devtools-mcp_chrome-devtools__`):

1. `new_page` (or `list_pages` + `select_page`; every call takes that `pageId`), then `navigate_page` to `http://127.0.0.1:8070/odoo?debug=assets` (log in first if needed:
   `fill_form` + `click` on `/web/login`).
2. `list_console_messages` (`types: ["error", "warn"]`, `includeStackTraces: true`): module loader
   errors, OWL errors ("Invalid prop ..."), uncaught RPC errors. Stack traces map to source files
   thanks to `?debug=assets`.
3. `evaluate_script` with `function: "() => [...odoo.loader.modules.keys()].filter((k) =>
   k.startsWith('@my_addon/'))"` or `"() => odoo.debug"`; returned values must be JSON-serializable.
4. `take_snapshot` (accessibility tree with element uids) to locate a widget, then `click`, `fill`,
   `hover`, `press_key`, `wait_for`; `take_screenshot` to check rendering (icons, dark mode).
5. `list_network_requests` (`resourceTypes: ["fetch", "xhr"]`) and `get_network_request`: ORM calls
   go to `/web/dataset/call_kw/<model>/<method>`, lazy bundles to `/web/bundle/<name>` then
   `/web/assets/...`.
6. `get_css_styles` on an element uid to see which rule (and which `--o-*` variable) applies.
7. `performance_start_trace` / `performance_stop_trace` for slow renders; `take_heapsnapshot` for
   leaks (components not destroyed).

Then fix, reload with `navigate_page(type="reload", ignoreCache=true)`, and re-check the console.

Source: odoo/addons/base/models/ir_asset.py:115-117, odoo/addons/base/models/assetsbundle.py:525-560, addons/web/controllers/dataset.py:28, addons/web/static/src/core/orm_plugin.js:126, addons/web/controllers/webclient.py:109

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| ESLint env `qunit`, global `QUnit` | removed (Hoot only, validator JS007) | addons/web/tooling/_eslintrc.json |
| `"@odoo/owl": "^2.0.1"` in tooling package | `>=3.0.0-alpha.31 <4.0.0`; IDE types come from the bundled `lib/owl/owl.d.ts` | addons/web/tooling/_package.json |
| `useEffect(fn, () => [deps])` accepted by lint | ESLint error and validator JS004 | addons/web/tooling/_eslintrc.json |
| `@types/jquery`, `@types/qunit` | removed | addons/web/tooling/_package.json |
| `jsconfig` `moduleResolution: node` + `baseUrl` | `"module": "preserve"`, `./`-relative `paths` | addons/web/tooling/_jsconfig.json |
| `env.debug` in components | `usePlugin(DebugModePlugin).isActive()` / `odoo.debug` (JS008) | addons/web/static/src/env.js |
| expecting prop validation errors without debug | only in OWL dev mode (`?debug=1` or test mode) | addons/web/static/src/env.js:117 |
