---
type: llm
---
The sub-template receives its title as an attribute of the `t-call` element (for example
`<t t-call="library_loans.loan_title" title.f="Loan {{doc.name}}"/>` or `title="..."`), not through a
`<t t-set>` inside the t-call body; the report action uses `report_type` `qweb-pdf` and a
`report_name` matching the template id. Pass only if both hold.
