"""Test cases for Django views."""

import os
from typing import TYPE_CHECKING
from typing import cast

import django
from django.conf import settings

if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zweili_search.settings")
    django.setup()

from django.contrib.auth import get_user_model
from django.test import TestCase

from search.models import Bang

from . import constants

if TYPE_CHECKING:
    from django.http import HttpResponseRedirect

    from search.models import SearchUser

User = get_user_model()


class IndexViewTest(TestCase):
    """Test cases for index view functionality."""

    def setUp(self) -> None:
        self.user = cast(
            "SearchUser",
            User.objects.create_user(username="testuser", password="testpass123"),
        )

    def test_index_view_requires_login(self) -> None:
        """Test that index view requires user login."""
        response = self.client.get("/")
        assert response.status_code == constants.HTTP_FOUND

    def test_index_view_no_query(self) -> None:
        """Test index view with no query parameter."""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/")
        assert response.status_code == constants.HTTP_OK
        assert "Search:" in response.content.decode()

    def test_index_view_with_bang_redirect(self) -> None:
        """Test index view redirects correctly with bang shortcuts."""
        Bang.objects.create(
            user=self.user,
            shortcut="g",
            url_template="https://www.google.com/search?q={query}",
        )

        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/", {"query": "!g test search"})

        assert response.status_code == constants.HTTP_FOUND
        redirect_response = cast("HttpResponseRedirect", response)
        assert redirect_response.url == "https://www.google.com/search?q=test+search"

    def test_index_view_with_query_no_bang(self) -> None:
        """Test index view with regular search query."""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/", {"query": "test search"})

        assert response.status_code == constants.HTTP_FOUND
        redirect_response = cast("HttpResponseRedirect", response)
        assert "searxng.zweili.org" in redirect_response.url
        assert "test+search" in redirect_response.url

    def test_index_view_with_custom_search_engine(self) -> None:
        """Test index view with custom search engine."""
        self.user.default_search_engine_url = "https://www.bing.com/search?q={query}"
        self.user.save()

        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/", {"query": "test search"})

        assert response.status_code == constants.HTTP_FOUND
        redirect_response = cast("HttpResponseRedirect", response)
        assert "bing.com" in redirect_response.url
        assert "test+search" in redirect_response.url


class SettingsViewAdditionalTest(TestCase):
    """Additional test cases for settings view functionality."""

    def setUp(self) -> None:
        self.user = cast(
            "SearchUser",
            User.objects.create_user(username="testuser", password="testpass123"),
        )

    def test_settings_rejects_empty_url(self) -> None:
        """Test that settings rejects empty URL."""
        self.client.login(username="testuser", password="testpass123")
        _ = self.client.post("/settings/", {"default_search_engine_url": ""})

        self.user.refresh_from_db()
        assert (
            self.user.default_search_engine_url
            == "https://searxng.zweili.org/search?q={query}"
        )

    def test_settings_rejects_whitespace_only_url(self) -> None:
        """Test that settings rejects whitespace-only URL."""
        self.client.login(username="testuser", password="testpass123")
        _ = self.client.post("/settings/", {"default_search_engine_url": "   "})

        self.user.refresh_from_db()
        assert (
            self.user.default_search_engine_url
            == "https://searxng.zweili.org/search?q={query}"
        )
