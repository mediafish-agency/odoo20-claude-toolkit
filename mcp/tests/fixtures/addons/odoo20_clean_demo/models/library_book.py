from odoo import api, fields, models


class LibraryBook(models.Model):
    _name = 'library.book'
    _description = "Library Book"
    _inherit = ['mail.thread']
    _order = 'name, id'

    name = fields.Char(required=True, tracking=True)
    isbn = fields.Char(string="ISBN", index='btree_not_null')
    author_ids = fields.Many2many('res.partner', string="Authors")
    state = fields.Selection(
        [('draft', "Draft"), ('published', "Published")],
        default='draft', required=True, tracking=True,
    )
    date_published = fields.Date()
    page_count = fields.Integer()
    is_long = fields.Boolean(compute='_compute_is_long', store=True)

    _isbn_uniq = models.Constraint('UNIQUE(isbn)', "The ISBN must be unique.")

    @api.depends('page_count')
    def _compute_is_long(self):
        for book in self:
            book.is_long = book.page_count > 500

    def action_publish(self):
        self.write({'state': 'published', 'date_published': fields.Date.context_today(self)})
