---
name: access-rules
description: Odoo 20 security file uses ir.access semantics (permission vs restriction rows)
tags: [security, data]
runs: 1
max_turns: 25
timeout_seconds: 600
---
In this Odoo 20 project I have a module `library_loans` (folder `library_loans/` in the current directory) with
a new model `library.loan` that has `user_id` (Many2one res.users) and `company_id` fields.

Write its security file and tell me which manifest entry to add:
- internal users can read and create their own loans only (user_id = current user);
- members of `library_loans.group_librarian` have full access to all loans;
- loans are always restricted to the user's allowed companies.

Only write the security file (create the folders you need).
