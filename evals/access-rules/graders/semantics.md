---
type: llm
---
The produced CSV is a valid Odoo 20 `security/ir.access.csv`:
1. a permission row (group `base.group_user`) on `library.loan` with an operation like `cr` or `cru` and the
   domain `[('user_id', '=', user.id)]`;
2. a permission row for `library_loans.group_librarian` with operation `crud` and no domain;
3. a restriction row (empty group) with a company domain using `company_ids`;
4. `model_id` holds the technical name `library.loan` (not `model_library_loan`);
5. the answer says to list the file last in the manifest `data`.
Pass only if all five hold.
