---
name: port-v19-view
description: Converts an Odoo 19-era view to Odoo 20 syntax
tags: [views, migrate]
runs: 1
max_turns: 20
timeout_seconds: 600
---
Port this view to Odoo 20 and save it as `ported_view.xml` in the current directory:

```xml
<odoo>
  <record id="loan_view_tree" model="ir.ui.view">
    <field name="model">library.loan</field>
    <field name="arch" type="xml">
      <tree decoration-danger="state == 'late'">
        <field name="name"/>
        <field name="state"/>
        <field name="date_return" attrs="{'invisible': [('state', '!=', 'returned')]}"/>
        <button name="action_return" type="object" icon="fa-check" states="borrowed"/>
      </tree>
    </field>
  </record>
  <record id="loan_view_search" model="ir.ui.view">
    <field name="model">library.loan</field>
    <field name="arch" type="xml">
      <search>
        <filter name="date" string="Date" date="date_borrow" start_month="-3" end_month="0"/>
      </search>
    </field>
  </record>
</odoo>
```
