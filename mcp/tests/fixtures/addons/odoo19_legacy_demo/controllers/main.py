from odoo import http
from odoo.http import Stream, request


class Legacy(http.Controller):
    @http.route('/legacy/data', type='json', auth='user')
    def data(self):
        website = request.website
        return request.env['legacy.thing'].search_read([]), Stream, website

    def _prepare_home_portal_values(self, counters):
        return Stream.from_binary_field(request.env.user, 'avatar_128')
