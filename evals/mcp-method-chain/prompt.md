---
name: mcp-method-chain
description: Uses the odoo20 MCP tools as evidence instead of guessing
tags: [mcp]
runs: 1
max_turns: 15
timeout_seconds: 600
---
In this Odoo 20 source tree, which modules override `sale.order.action_confirm`, in which order are they called,
and does each of them call super()?
