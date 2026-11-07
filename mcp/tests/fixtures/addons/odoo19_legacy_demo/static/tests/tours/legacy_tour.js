import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("legacy_tour", {
    url: "/odoo",
    wait_for: Promise.resolve(),
    steps: () => [{ trigger: ".o_main_navbar", run: "click" }],
});
