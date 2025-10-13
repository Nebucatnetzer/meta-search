"""Test cases for search user settings functionality."""

import os
from typing import TYPE_CHECKING
from typing import cast

import django
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase

from . import constants

if TYPE_CHECKING:
    from django.http import HttpResponseRedirect

    from search.models import SearchUser

# Configure Django settings for tests
if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zweili_search.settings")
    django.setup()

User = get_user_model()


class SearchUserModelTest(TestCase):
    """Test cases for SearchUser model functionality."""

    def test_default_search_engine_url_field(self) -> None:
        """Test the default search engine URL field."""
        user = cast(
            "SearchUser",
            User.objects.create_user(username="testuser", password="testpass123"),
        )
        assert (
            user.default_search_engine_url
            == "https://searxng.zweili.org/search?q={query}"
        )

    def test_custom_search_engine_url(self) -> None:
        """Test setting a custom search engine URL."""
        user = cast(
            "SearchUser",
            User.objects.create_user(
                username="testuser",
                password="testpass123",
                default_search_engine_url="https://www.google.com/search?q={query}",
            ),
        )
        assert (
            user.default_search_engine_url == "https://www.google.com/search?q={query}"
        )


class SearchViewTest(TestCase):
    """Test cases for search view functionality."""

    def setUp(self) -> None:
        self.user = cast(
            "SearchUser",
            User.objects.create_user(username="testuser", password="testpass123"),
        )

    def test_search_redirects_to_default_search_engine(self) -> None:
        """Test search redirects to the default search engine."""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/", {"query": "test search"})

        assert response.status_code == constants.HTTP_FOUND
        redirect_response = cast("HttpResponseRedirect", response)
        assert "searxng.zweili.org" in redirect_response.url
        assert "test+search" in redirect_response.url

    def test_search_uses_custom_search_engine(self) -> None:
        """Test search uses custom search engine when set."""
        self.user.default_search_engine_url = "https://www.google.com/search?q={query}"
        self.user.save()

        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/", {"query": "test search"})

        assert response.status_code == constants.HTTP_FOUND
        redirect_response = cast("HttpResponseRedirect", response)
        assert "google.com" in redirect_response.url
        assert "test+search" in redirect_response.url


class SettingsViewTest(TestCase):
    """Test cases for settings view functionality."""

    def setUp(self) -> None:
        self.user = cast(
            "SearchUser",
            User.objects.create_user(username="testuser", password="testpass123"),
        )

    def test_settings_view_requires_login(self) -> None:
        """Test that settings view requires user login."""
        response = self.client.get("/settings/")
        assert response.status_code == constants.HTTP_FOUND

    def test_settings_view_renders_correctly(self) -> None:
        """Test that settings view renders correctly for authenticated users."""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/settings/")
        assert response.status_code == constants.HTTP_OK
        assert "Default Search Engine URL" in response.content.decode()

    def test_settings_update_valid_url(self) -> None:
        """Test updating settings with a valid URL."""
        self.client.login(username="testuser", password="testpass123")
        self.client.post(
            "/settings/",
            {"default_search_engine_url": "https://www.bing.com/search?q={query}"},
        )

        self.user.refresh_from_db()
        assert (
            self.user.default_search_engine_url
            == "https://www.bing.com/search?q={query}"
        )

    def test_settings_rejects_url_without_query_placeholder(self) -> None:
        """Test that settings rejects URL without query placeholder."""
        self.client.login(username="testuser", password="testpass123")
        self.client.post(
            "/settings/",
            {"default_search_engine_url": "https://www.bing.com/search?q=fixed"},
        )

        self.user.refresh_from_db()
        assert (
            self.user.default_search_engine_url
            == "https://searxng.zweili.org/search?q={query}"
        )
