"""Test cases for bang handling functionality."""

import os
from typing import TYPE_CHECKING
from typing import Any

import django
import pytest
from django.conf import settings

if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zweili_search.settings")
    django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from search.bangs import resolve_bang
from search.models import Bang

if TYPE_CHECKING:
    from search.models import SearchUser

User = get_user_model()


@pytest.fixture
def bang(user: "SearchUser", db: Any) -> Bang:  # noqa: ARG001
    """Create a test bang for the user."""
    return Bang.objects.create(
        user=user,
        shortcut="g",
        url_template="https://www.google.com/search?q={query}",
    )


def test_resolve_bang_no_bang_prefix(user: "SearchUser") -> None:
    """Test that queries without bang prefix return None."""
    url, query = resolve_bang(user, "regular query")
    assert url is None
    assert query is None


def test_resolve_bang_with_query(
    user: "SearchUser", bang: Bang
) -> None:  # noqa: ARG001
    """Test bang resolution with a search query."""
    url, query = resolve_bang(user, "!g test search")
    assert url == "https://www.google.com/search?q=test+search"
    assert query == "test search"


def test_resolve_bang_with_empty_query(
    user: "SearchUser", bang: Bang
) -> None:  # noqa: ARG001
    """Test bang resolution with empty query."""
    url, query = resolve_bang(user, "!g")
    assert url == "https://www.google.com/search?q="
    assert query == ""


def test_resolve_bang_nonexistent_shortcut(user: "SearchUser") -> None:
    """Test bang resolution with non-existent shortcut."""
    url, query = resolve_bang(user, "!nonexistent search query")
    assert url is None
    assert query == "search query"


def test_resolve_bang_anonymous_user() -> None:
    """Test bang resolution with anonymous user."""
    anonymous_user = AnonymousUser()
    url, query = resolve_bang(anonymous_user, "!g test search")
    assert url is None
    assert query == "test search"


def test_resolve_bang_only_shortcut_no_space(
    user: "SearchUser", bang: Bang
) -> None:  # noqa: ARG001
    """Test bang with just shortcut and no space."""
    url, query = resolve_bang(user, "!g")
    assert url == "https://www.google.com/search?q="
    assert query == ""


def test_resolve_bang_url_encoding(
    user: "SearchUser", bang: Bang
) -> None:  # noqa: ARG001
    """Test URL encoding of special characters in query."""
    url, query = resolve_bang(user, "!g test with spaces & symbols")
    assert url == "https://www.google.com/search?q=test+with+spaces+%26+symbols"
    assert query == "test with spaces & symbols"


def test_resolve_bang_strips_whitespace(
    user: "SearchUser", bang: Bang
) -> None:  # noqa: ARG001
    """Test that whitespace is stripped from query for URL encoding."""
    url, query = resolve_bang(user, "!g   test query   ")
    assert url == "https://www.google.com/search?q=test+query"
    assert query == "  test query   "
