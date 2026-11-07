import { expect, test } from "@odoo/hoot";

import { formatIsbn } from "@odoo20_clean_demo/isbn_field/isbn_field";

test("formatIsbn groups a 13-digit ISBN", () => {
    expect(formatIsbn("9780140268867")).toBe("978-0-14026-886-7");
});

test("formatIsbn keeps other values", () => {
    expect(formatIsbn("123")).toBe("123");
    expect(formatIsbn(false)).toBe("");
});
