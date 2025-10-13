import os
from unittest.mock import patch

import django
from django.conf import settings

if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zweili_search.settings")
    django.setup()

from django.contrib.auth import get_user_model
from django.test import TestCase

from search.models import Bang

User = get_user_model()


class IndexViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_index_view_requires_login(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)

    def test_index_view_no_query(self):
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Search:")

    def test_index_view_with_bang_redirect(self):
        Bang.objects.create(
            user=self.user,
            shortcut="g",
            url_template="https://www.google.com/search?q={query}",
        )

        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/", {"query": "!g test search"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "https://www.google.com/search?q=test+search")

    def test_index_view_with_query_no_bang(self):
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/", {"query": "test search"})

        self.assertEqual(response.status_code, 302)
        self.assertIn("searxng.zweili.org", response.url)
        self.assertIn("test+search", response.url)

    def test_index_view_with_custom_search_engine(self):
        self.user.default_search_engine_url = "https://www.bing.com/search?q={query}"
        self.user.save()

        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/", {"query": "test search"})

        self.assertEqual(response.status_code, 302)
        self.assertIn("bing.com", response.url)
        self.assertIn("test+search", response.url)


class SettingsViewAdditionalTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_settings_rejects_empty_url(self):
        self.client.login(username="testuser", password="testpass123")
        response = self.client.post("/settings/", {"default_search_engine_url": ""})

        self.user.refresh_from_db()
        self.assertEqual(
            self.user.default_search_engine_url,
            "https://searxng.zweili.org/search?q={query}",
        )

    def test_settings_rejects_whitespace_only_url(self):
        self.client.login(username="testuser", password="testpass123")
        response = self.client.post("/settings/", {"default_search_engine_url": "   "})

        self.user.refresh_from_db()
        self.assertEqual(
            self.user.default_search_engine_url,
            "https://searxng.zweili.org/search?q={query}",
        )
