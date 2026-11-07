# Assets and bundles (Odoo 20)

How static files reach the browser in Odoo 20: manifest `assets` directives, the real bundle names,
the ES module system, custom bundles (and the OWL 3 compatibility-layer trap), lazy loading and
debugging. Read before touching `'assets'` in a `__manifest__.py` or calling `loadBundle`.
House rule for third-party files: [Assets guideline](../../odoo-web-guidelines/guidelines/assets.md#assets).

## Contents

- [Declaring assets](#declaring-assets)
- [Bundle catalogue](#bundle-catalogue)
- [Where to put your files](#where-to-put-your-files)
- [JS module system](#js-module-system)
- [Custom bundles and the OWL 3 compatibility layer](#custom-bundles-and-the-owl-3-compatibility-layer)
- [Lazy loading](#lazy-loading)
- [Rendering a bundle in QWeb](#rendering-a-bundle-in-qweb)
- [Debugging assets](#debugging-assets)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## Declaring assets

`'assets': {bundle_name: [command, ...]}`. A command is a path/glob string or a tuple:

| Command | Effect |
|---|---|
| `'my_addon/static/src/**/*'` | append (default directive) |
| `('include', 'web._assets_helpers')` | inline another bundle (recursive; cycles raise "Circular assets bundle declaration") |
| `('prepend', path)` | insert at the start of the *current* bundle (not of the including one) |
| `('before', target, path)` / `('after', target, path)` | insert next to `target`; target must already be in the bundle |
| `('replace', target, path)` | insert at `target` position, then remove `target` |
| `('remove', path)` | drop matching files; raises `File(s) ... not found in bundle` when files resolve but none is in the bundle |

Rules (from `ir_asset.py`):

- Globs use Python `glob(recursive=True)`; only files under `<addon>/static/` of **installed** addons
  resolve (a path in a non-installed addon raises). A glob matching nothing only logs
  `IrAsset: the path "..." did not resolve to anything.`
- Accepted extensions: `js`, `css scss sass less`, `xml` (OWL templates), and since 20.0 `woff woff2`
  (binary assets, see icon bundles). Other files are silently filtered out.
- `http(s)://...` and `/web/content/...` paths are kept as external links, not aggregated.
- A path is added once: the first occurrence wins, later appends of the same file are no-ops.
- Processing order: `ir.asset` records with `sequence < 16`, then every installed module's manifest in
  dependency order, then `ir.asset` records with `sequence >= 16`. So you can only `before/after/
  replace/remove` files added by modules you (transitively) `depends` on.
- All SCSS of one bundle is concatenated and compiled in a single libsass pass: file order decides
  which variables exist (see [scss-theming.md](scss-theming.md)).

`ir.asset` records (fields `name, bundle, directive, path, target, active, sequence`) apply the same
directives from data; `website` and `base_import_module` use them.

```python
'assets': {
    'web.assets_backend': [
        'my_addon/static/src/**/*',
        ('remove', 'my_addon/static/src/**/*.dark.scss'),   # light bundle must not get dark files
        ('remove', 'my_addon/static/src/views/graph/**'),   # graph lives in the lazy bundle
    ],
    'web.assets_backend_lazy': ['my_addon/static/src/views/graph/**'],
    'web.assets_web_dark': ['my_addon/static/src/**/*.dark.scss'],
    'web._assets_primary_variables': ['my_addon/static/src/scss/my_addon.variables.scss'],
    'web.assets_unit_tests': ['my_addon/static/tests/**/*.test.js'],
    'web.assets_tests': ['my_addon/static/tests/tours/**/*'],
},
```

Check the resolved list with `odoo_assets(bundle="web.assets_backend", scope_module="my_addon")`
(static) or `resolve="db"` (final ordered list from a database).

Source: odoo/addons/base/models/ir_asset.py, odoo/tools/constants.py, odoo/addons/base/models/assetsbundle.py:611, addons/hr_holidays/__manifest__.py, addons/project/__manifest__.py

## Bundle catalogue

| Bundle | Content / loaded by |
|---|---|
| `web.assets_backend` | web client code (core, views, search, webclient). **Add backend JS/XML/SCSS here** |
| `web.assets_web` | `web.assets_backend` + `main.js`/`start.js`; the bundle `/odoo` actually renders |
| `web.assets_web_dark` | `web.assets_web` + `web/static/src/**/*.dark.scss`; CSS only, when `color_scheme == 'dark'` |
| `web.assets_web_print` | print stylesheet (`primary_variables_print.scss`, `**/*.print_variables.scss`), `media="print"` |
| `web.assets_backend_lazy` / `_lazy_dark` | graph and pivot views, loaded on demand (see Lazy loading) |
| `web.assets_frontend` | public pages: OWL + compat layer, core, Interactions (`web/static/src/public/**`) |
| `web.assets_frontend_minimal` | module loader, session, `public/utils.js`, lazyloader (deferred) |
| `web.assets_frontend_lazy` | `web.assets_frontend` minus the minimal files (lazy JS) |
| `web.report_assets_common` / `web.report_assets_pdf` | QWeb report styles (with `icons_report.scss` for wkhtmltopdf) |
| `web.assets_unit_tests` | Hoot `*.test.js` files; setup in `web.assets_unit_tests_setup` |
| `web.assets_tests` | tours (`static/tests/tours/**`), loaded with `?debug=tests` or in test mode |
| `web.assets_emoji`, `web.ace_lib`, `web.chartjs_lib`, `web.fullcalendar_lib`, `web.assets_clickbot` | libraries loaded with `loadBundle` |
| `web.material_symbols_outlined` / `_rounded` / `_sharp`, `web.odoo_ui_icons` | icon font (`woff2`) + `@font-face` CSS |
| `web.icons_fonts` | the four icon bundles + `icons_mappings/**` + `icons.scss`; include this in custom bundles |

Private sub-bundles (underscore, never `t-call-assets` them directly): `web._assets_core` (module
loader, luxon, OWL + compat layer, `env.js`, `session.js`, `core/**`), `web._assets_helpers`
(Bootstrap functions/mixins, Odoo functions/mixins/utils + primary and secondary variables),
`web._assets_primary_variables`, `web._assets_secondary_variables`, `web._assets_backend_helpers`,
`web._assets_frontend_helpers`, `web._assets_bootstrap`, `web._assets_bootstrap_backend`,
`web._assets_bootstrap_frontend`.

Source: addons/web/__manifest__.py, addons/web/views/webclient_templates.xml:290-305

## Where to put your files

| You add | Bundle | Note |
|---|---|---|
| Component, field widget, view, systray item, client action | `web.assets_backend` | never `web.assets_web` (unit tests and dark mode include `assets_backend`) |
| A `js_class` extending graph or pivot | `web.assets_backend_lazy` | `graphView`/`pivotView` are not in `assets_backend`; core example `project` |
| Dark-mode overrides `*.dark.scss` | `web.assets_web_dark` + `('remove', ...)` from `web.assets_backend` | see [scss-theming.md](scss-theming.md) |
| `$o-*` variable definitions | `web._assets_primary_variables` | compiled before Bootstrap, visible everywhere |
| Bootstrap variable overrides (backend) | `web._assets_backend_helpers` | runs before Bootstrap `_variables.scss` |
| Website / portal JS (Interactions) | `web.assets_frontend` | see `../../website-pos/references/interactions.md` |
| Hoot tests / tours | `web.assets_unit_tests` / `web.assets_tests` | see the testing skill |
| Report styles | `web.report_assets_common` | |

Source: addons/project/__manifest__.py:91, addons/account/__manifest__.py:99, addons/html_editor/__manifest__.py:108-117, addons/web/static/src/views/view.js:360

## JS module system

- Every `.js` under `<addon>/static/src/` or `<addon>/static/tests/` is an ES module, transpiled
  server-side to `odoo.define(name, deps, fn)`. The `/** @odoo-module */` comment is optional there.
  Files under `static/lib/` are transpiled only if they carry the comment. Do not write
  `odoo.define` yourself (validator JS016).
- Module names from the path: `my_addon/static/src/a/b.js` -> `@my_addon/a/b`;
  `static/tests/x.js` -> `@my_addon/../tests/x`; `static/lib/y.js` -> `@my_addon/../lib/y`.
- `folder/index.js` is addressable as `@my_addon/folder` (e.g.
  `import { createRelatedModels } from "@point_of_sale/app/models/related_models"`).
- Relative imports (`./foo`) are rewritten to the `@addon/...` name; prefer the absolute form.
- Comment flags: `// @odoo-module ignore` (do not transpile, plain script),
  `/** @odoo-module alias=@web/../tests/utils default=false */` (also define an alias name).
- `_t` must be imported by its own name, `import { _t } from "@web/core/l10n/translation"`: the
  transpiler rewrites exactly that import so translations are looked up in your addon
  (not done for `.test.js`). An aliased import (`_t as t`) skips the rewrite.
- OWL templates (`.xml`) of a JS bundle are embedded in it (`registerTemplate` /
  `registerTemplateExtension`): a template must be in the same bundle as its component (or one
  loaded before it renders).
- `@odoo/owl` itself is the module defined by `web/static/lib/owl/odoo_module.js`.

Find a module's exports and importers with `odoo_js(module_path="@web/core/assets")`.

Source: odoo/tools/js_transpiler.py:59-95, odoo/tools/js_transpiler.py:241-256, odoo/tools/js_transpiler.py:691-715, addons/point_of_sale/static/src/app/models/related_models/index.js, addons/mail/static/tests/mail_test_helpers_contains.js:1, odoo/addons/base/models/assetsbundle.py:360-372

## Custom bundles and the OWL 3 compatibility layer

A standalone bundle (own page, iframe, kiosk) that ships `web/static/lib/owl/owl.js` itself must load,
in this exact order:

```python
'my_addon.assets_kiosk': [
    'web/static/src/module_loader.js',
    'web/static/src/session.js',
    'web/static/lib/luxon/luxon.js',
    'web/static/src/libs/luxon.js',
    'web/static/lib/owl/owl.js',
    'web/static/src/owl2/owl3_compatibility_layer.js',   # patches globalThis.owl
    'web/static/src/owl2/utils.js',                      # module @web/owl2/utils
    'web/static/lib/owl/odoo_module.js',                 # defines @odoo/owl, depends on @web/owl2/utils
    # ... ('include', 'web.icons_fonts'), core files, your files
],
```

Why: `odoo_module.js` is `odoo.define("@odoo/owl", ["@web/owl2/utils"], ...)`. Without `utils.js`
the module loader reports `@web/owl2/utils` as "needed by other modules but have not been defined"
and nothing that imports `@odoo/owl` starts. Without the compatibility layer, `Component` does not
set `this.env`, does not reject `static props`, `useEnv`/`useSubEnv`/`useLayoutEffect`/
`onWillRender` are `undefined`, and `t-custom-portal` does not exist. Simplest: `('include',
'web._assets_core')`, which already has the four files. Validator rule **MAN003** flags a manifest
that ships `owl.js` without them. Real examples: `project.webclient`, `point_of_sale` and
`mrp_subcontracting` bundles.

Source: addons/web/static/lib/owl/odoo_module.js, addons/web/static/src/owl2/owl3_compatibility_layer.js, addons/web/__manifest__.py:350-364, addons/project/__manifest__.py:113-140, addons/point_of_sale/__manifest__.py:192

## Lazy loading

`@web/core/assets` exports `loadBundle`, `loadJS`, `loadCSS`, `getBundle`, `AssetsLoadingError`
(and the overridable `assets` object). Every load is cached per document.

```javascript
import { onWillStart } from "@odoo/owl";
import { loadBundle, loadJS } from "@web/core/assets";

// in setup()
onWillStart(() => loadBundle("web.chartjs_lib"));             // core: core/utils/chart_hook.js
onWillStart(() => loadJS("/my_addon/static/lib/foo/foo.js"));  // single file
```

- `loadBundle(name, { css, js, targetDoc })` fetches `/web/bundle/<name>` (JSON list of files) then
  loads CSS and JS; the bundle must be declared in a manifest.
- `LazyComponent` (`@web/core/lazy_component`): props `Component` (registry key, string), `bundle`
  (string), `props` (object or function). It awaits `loadBundle(bundle)` then renders
  `registry.category("lazy_components").get(Component)`. The lazily loaded bundle registers the
  component:

```xml
<LazyComponent t-if="this.state.isEditing" Component="'website.WebsiteBuilder'"
    bundle="'website.website_builder_assets'" props="() => this.websiteBuilderProps"/>
```

```javascript
registry.category("lazy_components").add("website.WebsiteBuilder", WebsiteBuilder);
```

- Lazy views: when a view's `js_class` is not in the `views` registry, `View` loads
  `web.assets_backend_lazy` (or `_lazy_dark` when the `color_scheme` cookie is `dark`) before giving up.

Source: addons/web/static/src/core/assets.js:69-190, addons/web/static/src/core/lazy_component.js, addons/website/static/src/client_actions/website_preview/website_builder_action.xml:25, addons/website/static/src/builder/website_builder.js:273, addons/web/static/src/views/view.js:357-366, addons/web/static/src/core/utils/chart_hook.js:33

## Rendering a bundle in QWeb

```xml
<t t-call-assets="my_addon.assets_kiosk" t-js="false"/>              <!-- CSS links only -->
<t t-call-assets="my_addon.assets_kiosk" t-css="false" defer_load="True"/>
<t t-call-assets="web.material_symbols_outlined" t-binary="True"/>  <!-- <link rel="preload" as="font"> -->
```

Attributes: `t-css`, `t-js`, `t-binary`, `defer_load`, `lazy_load`, `media`, `t-autoprefix`. No children
allowed. Bundle names must have exactly two dot-separated parts (`addon.name`).

Source: odoo/addons/base/models/ir_qweb.py:2743-2765, odoo/addons/base/models/ir_qweb.py:2985-3040, odoo/addons/base/models/ir_asset.py:91-112, addons/web/views/webclient_templates.xml:38-45

## Debugging assets

- `?debug=assets`: bundles served unminified at `/web/assets/debug/<bundle>.js|.css` with source maps
  (`//# sourceMappingURL=...js.map`); without it you get `/web/assets/<hash>/<bundle>.min.js` and no
  map. Static files are also served with `max_age=0`. Modes are `1`, `assets`, `tests`
  (comma-separated); `tests` adds `web.assets_tests`.
- Server side: `--dev=xml` disables the asset-path and asset-link caches, so new files matched by an
  existing glob show up on reload. Editing `__manifest__.py` needs a server restart (manifests are
  cached per process).
- A SCSS compile error does not break the page: Odoo serves the previous CSS and shows the banner
  "A css error occurred, using an old style to render this page"; the error text is in the server log.
- JS module errors are printed by the module loader in the browser console: "failed to load because
  of an error", "needed by other modules but have not been defined" (file not in the bundle, or
  wrong `@addon/path`), "dependency cycle", "unmet dependencies" (secondary).
- In the console: `odoo.loader.modules.get("@my_addon/foo")`, `[...odoo.loader.modules.keys()]`.
- Validate statically with `odoo_validate` (rule MAN003, JS imports that resolve to no file).

Browser-side walkthrough with the chrome-devtools MCP: [tooling.md](tooling.md#debugging-the-web-client).

Source: odoo/addons/base/models/assetsbundle.py:140-147, odoo/addons/base/models/assetsbundle.py:353-425, odoo/addons/base/models/assetsbundle.py:525-570, addons/web/models/ir_http.py:34-61, odoo/http/router.py:330-340, odoo/addons/base/models/ir_qweb.py:2948-2955, odoo/modules/module.py:329, addons/web/static/src/module_loader.js:154-180

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `('include', 'web._assets_jquery')`, `web/static/lib/jquery/jquery.js` | removed, use DOM APIs (JS006) | addons/web/__manifest__.py |
| `web/static/src/legacy/js/public/*` (public_widget, minimal_dom, lazyloader) | `web/static/src/public/*` (Interactions, `public/utils.js`, `public/lazyloader.js`) | addons/web/__manifest__.py |
| `web/static/src/libs/fontawesome/css/font-awesome.css`, `web/static/lib/odoo_ui_icons/*` | `('include', 'web.icons_fonts')` | addons/web/__manifest__.py |
| `web.qunit_suite_tests`, `web/static/tests/legacy/**` | `web.assets_unit_tests` (Hoot) | addons/web/__manifest__.py |
| bundle ships `owl.js` + `odoo_module.js` only | add `owl2/owl3_compatibility_layer.js` + `owl2/utils.js` between them (MAN003) | addons/web/static/lib/owl/odoo_module.js |
| only js/css/xml in bundles | `woff`/`woff2` allowed, rendered as font preload with `t-binary="True"` | odoo/tools/constants.py |
| `'web/static/src/polyfills/**/*.js'` in backend | only `polyfills/clipboard.js` | addons/web/__manifest__.py |
