# Portal and website controllers (Odoo 20)

How to add customer-portal pages (`/my/...`) and public website routes in Odoo 20: extending
`portal.CustomerPortal`, the new `portal.entry` home cards and counters, pagers, access tokens, rendering
QWeb pages, POST forms with CSRF, and JSON routes for frontend Interactions. Real reference:
`addons/sale/controllers/portal.py` + `addons/sale/views/sale_portal_templates.xml`.

## Contents
- [Building blocks of a portal feature](#building-blocks-of-a-portal-feature)
- [CustomerPortal API](#customerportal-api)
- [Home cards: portal.entry and counters](#home-cards-portalentry-and-counters)
- [List and detail routes](#list-and-detail-routes)
- [Templates](#templates)
- [Reports and downloads](#reports-and-downloads)
- [Forms and CSRF](#forms-and-csrf)
- [Public website routes](#public-website-routes)
- [JSON routes for Interactions](#json-routes-for-interactions)
- [v19 habit -> Odoo 20](#v19-habit---odoo-20)

## Building blocks of a portal feature

| Piece | v20 way |
|---|---|
| Model | `_inherit = ['portal.mixin', 'mail.thread']`; override `_compute_access_url` (`/my/<thing>/<id>`); define `_get_report_base_filename()` if you serve PDFs |
| Access | an `ir.access` row for `base.group_portal` with a partner domain (no `ir.rule`) |
| Home card | a `portal.entry` record (data XML) whose `placeholder_count` is computed in `_prepare_portal_counter_values()` |
| Routes | `CustomerPortal` subclass: list (`auth='user'`) + detail (`auth='public'` + `access_token`) |
| Templates | `portal.portal_layout`, `portal.portal_searchbar`, `portal.portal_table`, `portal.portal_sidebar`, breadcrumbs via `portal.portal_breadcrumbs` |

```python
# models/library_loan.py
from datetime import timedelta

from odoo import fields, models


class LibraryLoan(models.Model):
    _name = 'my_library.loan'
    _inherit = ['portal.mixin', 'mail.thread']
    _description = "Book Loan"

    name = fields.Char(required=True)
    partner_id = fields.Many2one('res.partner', required=True, index=True)
    book_id = fields.Many2one('my_library.book', required=True)
    date_due = fields.Date()

    def action_extend(self):
        for loan in self:
            loan.date_due = (loan.date_due or fields.Date.today()) + timedelta(days=14)

    def _compute_access_url(self):
        super()._compute_access_url()
        for loan in self:
            loan.access_url = f'/my/loans/{loan.id}'

    def _get_report_base_filename(self):
        self.ensure_one()
        return f'Loan-{self.name}'
```

```csv
id,name,model_id,group_id/id,operation,domain
access_my_library_loan_portal,my_library.loan portal,my_library.loan,base.group_portal,r,"[('partner_id', 'child_of', [user.commercial_partner_id.id])]"
```

The manifest must depend on `portal` (and `website` if you use website-only features). Access rows:
see [ir-access](../../data-security/references/ir-access.md).

Source: addons/portal/models/portal_mixin.py:10-145, addons/sale/models/sale_order.py:1216-1225,
addons/sale/security/ir.access.csv:29

## CustomerPortal API

`from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager`

| Member | Signature / role |
|---|---|
| `_items_per_page` | `80` |
| `_prepare_portal_layout_values()` | base values for every `/my/*` page (`sales_user`, `page_name`, `portal_entries`, `portal_cards`, `portal_hidden_cards`) |
| `_prepare_portal_counter_values(counter)` | **v20**: return `(model_name, domain, access)` for a counter key, `access` = `'read'` or `'sudo'`; default `(False, False, False)` |
| `counters(counters)` | `/my/counters` (jsonrpc, readonly) called by the home page Interaction |
| `_document_check_access(model_name, document_id, access_token=None)` | returns the record **sudo-ed** if the user can read it or the token matches `access_token`; raises `MissingError` / `AccessError` |
| `_get_page_view_values(document, access_token, values, session_history, no_breadcrumbs, **kwargs)` | adds `object`, token, chatter keys and prev/next record pager from `request.session[session_history]` |
| `_show_report(model, report_type, report_ref, download=False)` | `report_type` in `html`, `pdf`, `text` |
| `pager(url, total, page=1, step=30, scope=5, url_args=None)` | module function -> dict with `offset`, `page`, `pages`, `page_previous`, `page_next`... for `portal.pager` |
| `get_records_pager(ids, current)` | module function used by `_get_page_view_values` |

Source: addons/portal/controllers/portal.py:31-130,151-230,1090-1172

## Home cards: portal.entry and counters

In v20 the `/my` home page is data driven: `portal.entry` records (title, description, `url`, `image`,
`placeholder_count`, `category`, `sequence`, `show_in_portal`, `is_config_card`). There is no
`_prepare_home_portal_values()` and no `portal.portal_my_home` xpath per app any more.

```xml
<!-- data/portal_entry_data.xml (listed in the manifest 'data') -->
<odoo noupdate="1">
    <record id="portal_my_loans" model="portal.entry">
        <field name="name">Your Loans</field>
        <field name="description">Books you borrowed</field>
        <field name="url">/my/loans</field>
        <field name="image" type="bytes" file="my_library/static/src/img/loans.svg"/>
        <field name="placeholder_count">loan_count</field>
        <field name="category">client_category</field>
        <field name="sequence" eval="60"/>
    </record>
</odoo>
```

```python
from odoo.addons.portal.controllers.portal import CustomerPortal


class LibraryPortal(CustomerPortal):

    def _prepare_portal_counter_values(self, counter):
        if counter == 'loan_count':
            return 'my_library.loan', self._loans_domain(self.env.user.partner_id), 'read'
        return super()._prepare_portal_counter_values(counter)

    def _loans_domain(self, partner):
        return [('partner_id', 'child_of', [partner.commercial_partner_id.id])]
```

- `category`: `alert` entries are shown as banners with exact counts; core cards use
  `client_category`, `vendor_category`, `service_category` (default `common_category`).
- The card is hidden until its counter is > 0 (the JS calls `/my/counters` with
  `{counter_key: category}`); `is_config_card` cards (addresses, security) are always visible.
- The counter uses `search_count(domain, limit=1)` unless exact counts are needed: keep the domain cheap.

Source: addons/portal/models/portal_entry.py, addons/portal/controllers/portal.py:155-226,
addons/sale/data/portal_entry_data.xml, addons/portal/static/src/interactions/portal_home_counters.js,
addons/portal/views/portal_templates.xml:223-296

## List and detail routes

```python
from odoo.exceptions import AccessError, MissingError
from odoo.http import request, route
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class LibraryPortal(CustomerPortal):          # same class as above

    @route(['/my/loans', '/my/loans/page/<int:page>'], type='http', auth='user', website=True)
    def portal_my_loans(self, page=1, **kw):
        Loan = self.env['my_library.loan']
        domain = self._loans_domain(self.env.user.partner_id)
        values = self._prepare_portal_layout_values()
        pager = portal_pager(url='/my/loans', total=Loan.search_count(domain),
                             page=page, step=self._items_per_page)
        loans = Loan.search(domain, limit=self._items_per_page, offset=pager['offset'])
        request.session['my_loans_history'] = loans.ids[:100]
        values.update({'loans': loans, 'pager': pager, 'page_name': 'loan', 'default_url': '/my/loans'})
        return request.render('my_library.portal_my_loans', values)

    @route('/my/loans/<int:loan_id>', type='http', auth='public', website=True)
    def portal_my_loan(self, loan_id, access_token=None, report_type=None, download=False, **kw):
        try:
            loan_sudo = self._document_check_access('my_library.loan', loan_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        if report_type in ('html', 'pdf', 'text'):
            return self._show_report(model=loan_sudo, report_type=report_type,
                                     report_ref='my_library.action_report_loan', download=download)
        values = self._get_page_view_values(
            loan_sudo, access_token, {'loan': loan_sudo, 'page_name': 'loan'}, 'my_loans_history', False)
        return request.render('my_library.portal_my_loan', values)
```

- Detail routes are `auth='public'` so emailed links with `?access_token=` work for anonymous
  visitors; `_document_check_access` returns a sudo record: only render what the customer may see.
- `record.get_portal_url()` (token included by default) calls `_portal_ensure_token()`, which writes the
  token on first use: pages rendering it must not be `readonly=True` (comment in sale's controller).
- `page`/`sortby`/filters come in as strings from the query string; `portal_pager` sanitizes `page`.

Source: addons/sale/controllers/portal.py:15-130,136-200, addons/portal/controllers/portal.py:1090-1146

## Templates

```xml
<template id="portal_my_loans" name="My Loans">
    <t t-call="portal.portal_layout" breadcrumbs_searchbar="True">
        <t t-call="portal.portal_searchbar" breadcrumbs_searchbar="True" title.translate="Your Loans"/>
        <div t-if="not loans" class="alert alert-warning" role="alert">No loan yet.</div>
        <t t-if="loans" t-call="portal.portal_table">
            <thead><tr><th>Loan</th><th class="text-end">Book</th></tr></thead>
            <tr t-foreach="loans" t-as="loan">
                <td><a t-att-href="loan.access_url" t-out="loan.name"/></td>
                <td class="text-end" t-out="loan.book_id.display_name"/>
            </tr>
        </t>
    </t>
</template>

<template id="portal_breadcrumbs_loans" inherit_id="portal.portal_breadcrumbs" name="Loans breadcrumb">
    <xpath expr="//ol[hasclass('o_portal_submenu')]" position="inside">
        <li t-if="page_name == 'loan'" class="breadcrumb-item active">Loans</li>
    </xpath>
</template>
```

- Server QWeb rules apply: `t-out` only, `t-call` parameters as attributes (`title.translate="..."`,
  `x.f="literal"`); a `t-set` inside a `t-call` body does not reach the callee (rule XML012).
- `portal.portal_table` renders `portal.pager` itself when a `pager` value is present.
- Detail pages usually inherit `portal.portal_sidebar` with `primary="True"` and end with
  `<t t-call="portal.message_thread"/>` (needs `object`/`token` from `_get_page_view_values`).
- Icons are Material Symbols: `<i class="oi" data-icon="close"/>` (rule XML004).

Source: addons/sale/views/sale_portal_templates.xml:4-60,125,411, addons/portal/views/portal_templates.xml:144,166,303-312,720,766

## Reports and downloads

- `_show_report()` renders `ir.actions.report` with sudo (per company), sets `Content-Disposition` via
  `content_disposition(filename, 'attachment' if download else 'inline')` using
  `model._get_report_base_filename()` for PDFs.
- Attachment downloads: `self.env['ir.binary']._get_stream_from(attachment).get_response(as_attachment=True)`
  after `_document_check_access` (see [sessions-streams.md](sessions-streams.md#download-recipes)).

Source: addons/portal/controllers/portal.py:1148-1172, addons/sale/controllers/portal.py:460-475

## Forms and CSRF

`type='http'` POST routes reject requests without a valid `csrf_token` (400 "Session expired (invalid
CSRF token)").

```xml
<form action="/my/loans/extend" method="post">
    <input type="hidden" name="csrf_token" t-att-value="request.csrf_token()"/>
    <input type="hidden" name="loan_id" t-att-value="loan.id"/>
    <button type="submit" class="btn btn-primary">Extend</button>
</form>
```

```python
@route('/my/loans/extend', type='http', auth='user', website=True, methods=['POST'])
def portal_loan_extend(self, loan_id, **post):
    loan = self.env['my_library.loan'].browse(int(loan_id)).exists()
    if not loan:
        raise request.not_found()
    loan.check_access('write')            # as the portal user, never trust the posted id
    loan.sudo().action_extend()
    return request.redirect(loan.access_url)
```

- Never `csrf=False` except for third-party callbacks (webhooks, payment providers); see
  [odoo-security: Routes](../../odoo-security/SKILL.md#routes-auth-post-csrf).
- In JS the token is `odoo.csrf_token`.
- Public forms can add `captcha='<action>'` to the route (e.g. `website_form`, `signup`).

Source: odoo/http/dispatcher.py:244-261, odoo/http/requestlib.py:224-272, addons/portal/views/portal_templates.xml:135,
addons/website/controllers/form.py:30

## Public website routes

```python
from odoo import http
from odoo.fields import Domain
from odoo.http import request


def sitemap_books(env, rule, qs):
    if not qs or qs.lower() in '/library':
        yield {'loc': '/library'}


class LibraryWebsite(http.Controller):

    @http.route('/library', type='http', auth='public', website=True, sitemap=sitemap_books, readonly=True)
    def library(self, **kw):
        # my_library.book inherits 'website.published.multi.mixin' (website_published, website_id)
        domain = Domain('website_published', '=', True) & request.env.website.website_domain()
        books = request.env['my_library.book'].sudo().search(domain, limit=40)
        return request.render('my_library.library_page', {'books': books})
```

| Option / helper | Meaning |
|---|---|
| `website=True` | frontend route: language prefix and `request.lang`, website context (`website_id`, `allowed_company_ids`), error pages rendered by the website, needed for the website editor |
| `auth='public'` | visitors run as the website's public user: read data with `sudo()` + an explicit domain |
| `sitemap=False` / callable | exclude, or yield `{'loc': ...}` entries; an enumerable website route without a `sitemap` key logs a warning during sitemap generation |
| `multilang=False` | URL without `/<lang>/` prefix |
| `request.env.website` | current website record (`website_domain()` restricts multi-website data) |
| page template | `<t t-call="website.layout"><div id="wrap" class="oe_structure">...</div></t>` (`portal.frontend_layout` / `web.frontend_layout` without website) |

`website=True` is also used by portal routes without the website app installed (`http_routing` handles
it). With `website` installed, `request.env.website` is the record; `request.website` no longer exists.

Source: addons/account/controllers/terms.py:8-29, addons/website_blog/controllers/main.py:178-200,
addons/website/models/website.py:118,1710-1830, addons/website/models/mixins.py:796, addons/website/models/ir_http.py:239-268,
addons/website_blog/views/website_blog_templates.xml:6-19, odoo/orm/environments.py:306

## JSON routes for Interactions

Frontend JS (Interactions) calls `type='jsonrpc'` routes with `rpc()`; params are the keyword arguments.

```javascript
import { rpc } from "@web/core/network/rpc";
// inside an Interaction method
const result = await this.waitFor(rpc("/my_library/loan/extend", { loan_id: this.loanId }));
```

```python
@http.route('/my_library/loan/extend', type='jsonrpc', auth='user', website=True, methods=['POST'])
def loan_extend_json(self, loan_id):
    loan = request.env['my_library.loan'].browse(int(loan_id)).exists()
    loan.check_access('write')
    loan.sudo().action_extend()
    return {'date_due': loan.date_due}        # dates are serialized as strings
```

- No CSRF token on `jsonrpc` (`csrf=True` on such a route has no effect); protection is the JSON
  content type, so never expose state changes on GET `http` routes instead.
- Raise `UserError`/`AccessError` to send an error object (`rpc()` rejects with `RPCError`).
- Interaction side (selector, `dynamicContent`, `waitFor`): see
  [interactions](../../website-pos/references/interactions.md).

Source: addons/web/static/src/core/network/rpc.js:93-115, addons/mass_mailing/static/src/interactions/subscribe.js,
addons/website_sale/static/src/interactions/checkout.js:437, odoo/http/dispatcher.py:315-411

## v19 habit -> Odoo 20

| v19 / older | Odoo 20 | Source |
|---|---|---|
| `_prepare_home_portal_values(self, counters)` returning `{'x_count': n}` | `_prepare_portal_counter_values(self, counter)` returning `(model, domain, 'read')` + a `portal.entry` record | addons/portal/controllers/portal.py:193 |
| `<template inherit_id="portal.portal_my_home">` + `t-call="portal.portal_docs_entry"` per app | `portal.entry` data record (`placeholder_count`, `category`, `url`, `image`) | addons/portal/models/portal_entry.py |
| `request.website` | `request.env.website` (or `self.env.website`) | odoo/orm/environments.py:306 |
| `document.check_access_rights('read')` / `check_access_rule('read')` in controllers | `document.check_access('read')` / `has_access('read')` (rule SEC003) | odoo/orm/models.py:3443-3464 |
| `ir.rule` for portal visibility | `ir.access` row with group `base.group_portal` and a domain | addons/sale/security/ir.access.csv:29 |
| `t-esc` in portal templates | `t-out` (rule XML003) | odoo/addons/base/models/ir_qweb.py |
| `<i class="fa fa-times"/>` | `<i class="oi" data-icon="close"/>` (rule XML004) | addons/sale/views/sale_portal_templates.xml:40 |

Inspect what other modules add to the portal with `odoo_xmlid portal.portal_breadcrumbs` (inheriting
views) and `odoo_method _prepare_portal_counter_values` (all overrides in load order).
