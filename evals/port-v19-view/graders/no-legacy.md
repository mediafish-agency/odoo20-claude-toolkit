---
type: regex
pattern: "<tree|attrs=|states=|icon=\"fa-|start_month|end_month"
match: not_contains
target: {source: file, path: ported_view.xml}
---
