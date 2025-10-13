import os

import django
from django.conf import settings

if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zweili_search.settings")
    django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from search.bangs import resolve_bang
from search.models import Bang

User = get_user_model()


class ResolveBangTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.bang = Bang.objects.create(
            user=self.user,
            shortcut="g",
            url_template="https://www.google.com/search?q={query}",
        )

    def test_resolve_bang_no_bang_prefix(self):
        url, query = resolve_bang(self.user, "regular query")
        self.assertIsNone(url)
        self.assertIsNone(query)

    def test_resolve_bang_with_query(self):
        url, query = resolve_bang(self.user, "!g test search")
        self.assertEqual(url, "https://www.google.com/search?q=test+search")
        self.assertEqual(query, "test search")

    def test_resolve_bang_with_empty_query(self):
        url, query = resolve_bang(self.user, "!g")
        self.assertEqual(url, "https://www.google.com/search?q=")
        self.assertEqual(query, "")

    def test_resolve_bang_nonexistent_shortcut(self):
        url, query = resolve_bang(self.user, "!nonexistent search query")
        self.assertIsNone(url)
        self.assertEqual(query, "search query")

    def test_resolve_bang_anonymous_user(self):
        anonymous_user = AnonymousUser()
        url, query = resolve_bang(anonymous_user, "!g test search")
        self.assertIsNone(url)
        self.assertEqual(query, "test search")

    def test_resolve_bang_only_shortcut_no_space(self):
        url, query = resolve_bang(self.user, "!g")
        self.assertEqual(url, "https://www.google.com/search?q=")
        self.assertEqual(query, "")

    def test_resolve_bang_url_encoding(self):
        url, query = resolve_bang(self.user, "!g test with spaces & symbols")
        self.assertEqual(
            url, "https://www.google.com/search?q=test+with+spaces+%26+symbols"
        )
        self.assertEqual(query, "test with spaces & symbols")

    def test_resolve_bang_strips_whitespace(self):
        url, query = resolve_bang(self.user, "!g   test query   ")
        self.assertEqual(url, "https://www.google.com/search?q=test+query")
        self.assertEqual(query, "  test query   ")
