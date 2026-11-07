---
name: qweb-report
description: Server QWeb report uses Odoo 20 directives (t-out, t-call parameters)
tags: [qweb, reports]
runs: 1
max_turns: 25
timeout_seconds: 600
---
For the Odoo 20 model `library.loan` (fields: name, partner_id, date_borrow, date_return) in module
`library_loans`, write `library_loans/report/loan_reports.xml` with the report action and
`library_loans/report/loan_templates.xml` with a PDF template using the company external layout, showing
the borrower, the dates and the title "Loan <name>" passed as a parameter to a reusable sub-template.
