import pytz

from odoo import fields, models, tools
from odoo.http import content_disposition
from odoo.osv import expression
from odoo.tools import ormcache_context


class LegacyThing(models.Model):
    _name = 'legacy.thing'
    _description = 'Legacy thing'
    _rec_names_search = ['name', 'code']
    _sql_constraints = [('code_uniq', 'unique(code)', 'Code must be unique')]

    name = fields.Char()
    code = fields.Char()
    amount = fields.Float(group_operator='sum')
    attachment_id = fields.Many2one('ir.attachment')

    def _track_subtype(self, initial_values):
        return super()._track_subtype(initial_values)

    def name_get(self):
        return [(r.id, r.name) for r in self]

    def action_check(self):
        self.check_access_rights('write')
        delay = self.env['ir.config_parameter'].sudo().get_param('legacy.delay')
        self.env.registry.clear_cache()
        self.toggle_active()
        data = self.attachment_id.datas
        groups = self.read_group([], ['amount'], ['code'], lazy=False)
        return delay, data, groups, expression, pytz, content_disposition

    @tools.ormcache_context('self.id', keys=('lang',))
    def _cached(self):
        return ormcache_context
