---
name: owl3-field-widget
description: OWL 3 field widget written the Odoo 20 way (useProps, this. in templates, no OWL 2 APIs)
tags: [owl, frontend]
runs: 1
max_turns: 30
timeout_seconds: 900
---
In the Odoo 20 addon `rating_widget` (folder `rating_widget/` in the current directory, depends on `web`),
create a field widget `rating_stars` for Integer fields that shows 5 stars, filled up to the value, and lets
the user click a star to set the value (read-only mode just displays). Write the JS component, its OWL
template, and the manifest `assets` entry you would add. Keep it minimal.
