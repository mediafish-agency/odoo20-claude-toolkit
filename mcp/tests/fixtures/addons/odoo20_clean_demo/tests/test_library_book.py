from psycopg2 import IntegrityError

from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestLibraryBook(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.book = cls.env['library.book'].create({'name': "The Odyssey", 'isbn': '9780140268867', 'page_count': 560})

    def test_publish(self):
        self.book.action_publish()
        self.assertEqual(self.book.state, 'published')
        self.assertTrue(self.book.date_published)

    def test_is_long(self):
        self.assertTrue(self.book.is_long)
        self.book.page_count = 120
        self.assertFalse(self.book.is_long)

    def test_isbn_unique(self):
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'), self.env.cr.savepoint():
            self.env['library.book'].create({'name': "Copy", 'isbn': '9780140268867'})
            self.env.flush_all()

    def test_user_access(self):
        user = new_test_user(self.env, login='reader_odoo20_demo', groups='base.group_user')
        books = self.env['library.book'].with_user(user)
        self.assertTrue(books.has_access('read'))
        self.assertTrue(books.has_access('create'))
