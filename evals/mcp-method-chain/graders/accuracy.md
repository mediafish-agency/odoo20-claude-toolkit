---
type: llm
---
The answer lists overrides of `sale.order.action_confirm` consistent with the Odoo 20 source: among them
sale_project, website_sale, event_sale, sale_management, sale_loyalty, sale_crm, and the base
implementation in `sale` (which does not call super). It must NOT claim that sale_stock overrides
action_confirm (sale_stock overrides `_action_confirm`). Pass if the list is substantially correct and
contains no invented module.
