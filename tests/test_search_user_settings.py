import os

import django
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase

# Configure Django settings for tests
if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zweili_search.settings")
    django.setup()

User = get_user_model()


class SearchUserModelTest(TestCase):
    def test_default_search_engine_url_field(self):
        user = User.objects.create_user(username="testuser", password="testpass123")
        self.assertEqual(
            user.default_search_engine_url,
            "https://searxng.zweili.org/search?q={query}",
        )

    def test_custom_search_engine_url(self):
        user = User.objects.create_user(
            username="testuser",
            password="testpass123",
            default_search_engine_url="https://www.google.com/search?q={query}",
        )
        self.assertEqual(
            user.default_search_engine_url, "https://www.google.com/search?q={query}"
        )


class SearchViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_search_redirects_to_default_search_engine(self):
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/", {"query": "test search"})

        self.assertEqual(response.status_code, 302)
        self.assertIn("searxng.zweili.org", response.url)
        self.assertIn("test+search", response.url)

    def test_search_uses_custom_search_engine(self):
        self.user.default_search_engine_url = "https://www.google.com/search?q={query}"
        self.user.save()

        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/", {"query": "test search"})

        self.assertEqual(response.status_code, 302)
        self.assertIn("google.com", response.url)
        self.assertIn("test+search", response.url)


class SettingsViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_settings_view_requires_login(self):
        response = self.client.get("/settings/")
        self.assertEqual(response.status_code, 302)

    def test_settings_view_renders_correctly(self):
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/settings/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Default Search Engine URL")

    def test_settings_update_valid_url(self):
        self.client.login(username="testuser", password="testpass123")
        response = self.client.post(
            "/settings/",
            {"default_search_engine_url": "https://www.bing.com/search?q={query}"},
        )

        self.user.refresh_from_db()
        self.assertEqual(
            self.user.default_search_engine_url, "https://www.bing.com/search?q={query}"
        )

    def test_settings_rejects_url_without_query_placeholder(self):
        self.client.login(username="testuser", password="testpass123")
        response = self.client.post(
            "/settings/",
            {"default_search_engine_url": "https://www.bing.com/search?q=fixed"},
        )

        self.user.refresh_from_db()
        self.assertEqual(
            self.user.default_search_engine_url,
            "https://searxng.zweili.org/search?q={query}",
        )
