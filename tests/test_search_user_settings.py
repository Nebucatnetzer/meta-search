"""Test cases for search user settings functionality."""

import os
from typing import TYPE_CHECKING

import django
from django.conf import settings
from django.contrib.auth import get_user_model

from . import constants

if TYPE_CHECKING:
    from django.test import Client

    from search.models import SearchUser

# Configure Django settings for tests
if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zweili_search.settings")
    django.setup()

User = get_user_model()


def test_default_search_engine_url_field(db) -> None:
    """Test the default search engine URL field."""
    user = User.objects.create_user(username="testuser1", password="testpass123")
    assert (
        user.default_search_engine_url == "https://searxng.zweili.org/search?q={query}"
    )


def test_custom_search_engine_url(db) -> None:
    """Test setting a custom search engine URL."""
    user = User.objects.create_user(
        username="testuser2",
        password="testpass123",
        default_search_engine_url="https://www.google.com/search?q={query}",
    )
    assert user.default_search_engine_url == "https://www.google.com/search?q={query}"


def test_search_redirects_to_default_search_engine(
    user: "SearchUser", client: "Client"
) -> None:
    """Test search redirects to the default search engine."""
    client.login(username="testuser", password="testpass123")
    response = client.get("/", {"query": "test search"})

    assert response.status_code == constants.HTTP_FOUND
    redirect_response = response
    assert "searxng.zweili.org" in redirect_response.url
    assert "test+search" in redirect_response.url


def test_search_uses_custom_search_engine(user: "SearchUser", client: "Client") -> None:
    """Test search uses custom search engine when set."""
    user.default_search_engine_url = "https://www.google.com/search?q={query}"
    user.save()

    client.login(username="testuser", password="testpass123")
    response = client.get("/", {"query": "test search"})

    assert response.status_code == constants.HTTP_FOUND
    redirect_response = response
    assert "google.com" in redirect_response.url
    assert "test+search" in redirect_response.url


def test_settings_view_requires_login(client: "Client") -> None:
    """Test that settings view requires user login."""
    response = client.get("/settings/")
    assert response.status_code == constants.HTTP_FOUND


def test_settings_view_renders_correctly(user: "SearchUser", client: "Client") -> None:
    """Test that settings view renders correctly for authenticated users."""
    client.login(username="testuser", password="testpass123")
    response = client.get("/settings/")
    assert response.status_code == constants.HTTP_OK
    assert "Default Search Engine URL" in response.content.decode()


def test_settings_update_valid_url(user: "SearchUser", client: "Client") -> None:
    """Test updating settings with a valid URL."""
    client.login(username="testuser", password="testpass123")
    client.post(
        "/settings/",
        {"default_search_engine_url": "https://www.bing.com/search?q={query}"},
    )

    user.refresh_from_db()
    assert user.default_search_engine_url == "https://www.bing.com/search?q={query}"


def test_settings_rejects_url_without_query_placeholder(
    user: "SearchUser", client: "Client"
) -> None:
    """Test that settings rejects URL without query placeholder."""
    client.login(username="testuser", password="testpass123")
    client.post(
        "/settings/",
        {"default_search_engine_url": "https://www.bing.com/search?q=fixed"},
    )

    user.refresh_from_db()
    assert (
        user.default_search_engine_url == "https://searxng.zweili.org/search?q={query}"
    )
