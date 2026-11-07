/** @odoo-module **/
import { Component, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { escape } from "@web/core/utils/strings";
import { missing } from "@web/core/does_not_exist";
import { stepUtils } from "@web_tour/js/tour_step_utils";

export class LegacyWidget extends Component {
    static template = "odoo19_legacy_demo.LegacyWidget";
    static props = { value: { type: String, optional: true } };

    setup() {
        this.state = useState({ open: false });
        this.input = useRef("input");
        useEffect(() => {
            this.small = this.env.isSmall;
        }, () => [this.state.open]);
    }
}

publicWidget.registry.legacy = {};
$("body").addClass("o_legacy");
QUnit.module("legacy");
registry.category("fields").add("kanban.many2many_tags", { missing, stepUtils, escape });
