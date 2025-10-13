"""Test cases for Django views."""

import os
from typing import TYPE_CHECKING

import django
from django.conf import settings

if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zweili_search.settings")
    django.setup()

from django.contrib.auth import get_user_model

from search.models import Bang

from . import constants

if TYPE_CHECKING:
    from django.test import Client

    from search.models import SearchUser

User = get_user_model()


def test_index_view_requires_login(client: "Client") -> None:
    """Test that index view requires user login."""
    response = client.get("/")
    assert response.status_code == constants.HTTP_FOUND


def test_index_view_no_query(user: "SearchUser", client: "Client") -> None:
    """Test index view with no query parameter."""
    client.login(username="testuser", password="testpass123")
    response = client.get("/")
    assert response.status_code == constants.HTTP_OK
    assert "Search:" in response.content.decode()


def test_index_view_with_bang_redirect(user: "SearchUser", client: "Client") -> None:
    """Test index view redirects correctly with bang shortcuts."""
    Bang.objects.create(
        user=user,
        shortcut="g",
        url_template="https://www.google.com/search?q={query}",
    )

    client.login(username="testuser", password="testpass123")
    response = client.get("/", {"query": "!g test search"})

    assert response.status_code == constants.HTTP_FOUND
    redirect_response = response
    assert redirect_response.url == "https://www.google.com/search?q=test+search"


def test_index_view_with_query_no_bang(user: "SearchUser", client: "Client") -> None:
    """Test index view with regular search query."""
    client.login(username="testuser", password="testpass123")
    response = client.get("/", {"query": "test search"})

    assert response.status_code == constants.HTTP_FOUND
    redirect_response = response
    assert "searxng.zweili.org" in redirect_response.url
    assert "test+search" in redirect_response.url


def test_index_view_with_custom_search_engine(
    user: "SearchUser", client: "Client"
) -> None:
    """Test index view with custom search engine."""
    user.default_search_engine_url = "https://www.bing.com/search?q={query}"
    user.save()

    client.login(username="testuser", password="testpass123")
    response = client.get("/", {"query": "test search"})

    assert response.status_code == constants.HTTP_FOUND
    redirect_response = response
    assert "bing.com" in redirect_response.url
    assert "test+search" in redirect_response.url


def test_settings_rejects_empty_url(user: "SearchUser", client: "Client") -> None:
    """Test that settings rejects empty URL."""
    client.login(username="testuser", password="testpass123")
    client.post("/settings/", {"default_search_engine_url": ""})

    user.refresh_from_db()
    assert (
        user.default_search_engine_url == "https://searxng.zweili.org/search?q={query}"
    )


def test_settings_rejects_whitespace_only_url(
    user: "SearchUser", client: "Client"
) -> None:
    """Test that settings rejects whitespace-only URL."""
    client.login(username="testuser", password="testpass123")
    client.post("/settings/", {"default_search_engine_url": "   "})

    user.refresh_from_db()
    assert (
        user.default_search_engine_url == "https://searxng.zweili.org/search?q={query}"
    )
