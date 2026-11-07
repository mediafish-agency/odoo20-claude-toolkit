import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

import { Component, useProps } from "@odoo/owl";

export function formatIsbn(value) {
    const digits = (value || "").replace(/[^0-9X]/gi, "");
    return digits.length === 13
        ? `${digits.slice(0, 3)}-${digits.slice(3, 4)}-${digits.slice(4, 9)}-${digits.slice(9, 12)}-${digits.slice(12)}`
        : value || "";
}

export class IsbnField extends Component {
    static template = "odoo20_clean_demo.IsbnField";
    props = useProps({ ...standardFieldProps });

    formatted() {
        return formatIsbn(this.props.record.data[this.props.name]);
    }
}

export const isbnField = {
    component: IsbnField,
    displayName: _t("ISBN"),
    supportedTypes: ["char"],
};

registry.category("fields").add("odoo20_isbn", isbnField);
