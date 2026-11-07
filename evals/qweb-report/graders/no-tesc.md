---
type: regex
pattern: "t-esc=|t-raw=|external_layout_(bold|boxed|striped)"
match: not_contains
target: {source: file, path: library_loans/report/loan_templates.xml}
---
