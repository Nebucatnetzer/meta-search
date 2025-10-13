"""Test cases for bang handling functionality."""

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
    """Test cases for bang resolution functionality."""

    def setUp(self) -> None:
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.bang = Bang.objects.create(
            user=self.user,
            shortcut="g",
            url_template="https://www.google.com/search?q={query}",
        )

    def test_resolve_bang_no_bang_prefix(self) -> None:
        """Test that queries without bang prefix return None."""
        url, query = resolve_bang(self.user, "regular query")
        assert url is None
        assert query is None

    def test_resolve_bang_with_query(self) -> None:
        """Test bang resolution with a search query."""
        url, query = resolve_bang(self.user, "!g test search")
        assert url == "https://www.google.com/search?q=test+search"
        assert query == "test search"

    def test_resolve_bang_with_empty_query(self) -> None:
        """Test bang resolution with empty query."""
        url, query = resolve_bang(self.user, "!g")
        assert url == "https://www.google.com/search?q="
        assert query == ""

    def test_resolve_bang_nonexistent_shortcut(self) -> None:
        """Test bang resolution with non-existent shortcut."""
        url, query = resolve_bang(self.user, "!nonexistent search query")
        assert url is None
        assert query == "search query"

    def test_resolve_bang_anonymous_user(self) -> None:
        """Test bang resolution with anonymous user."""
        anonymous_user = AnonymousUser()
        url, query = resolve_bang(anonymous_user, "!g test search")
        assert url is None
        assert query == "test search"

    def test_resolve_bang_only_shortcut_no_space(self) -> None:
        """Test bang with just shortcut and no space."""
        url, query = resolve_bang(self.user, "!g")
        assert url == "https://www.google.com/search?q="
        assert query == ""

    def test_resolve_bang_url_encoding(self) -> None:
        """Test URL encoding of special characters in query."""
        url, query = resolve_bang(self.user, "!g test with spaces & symbols")
        assert url == "https://www.google.com/search?q=test+with+spaces+%26+symbols"
        assert query == "test with spaces & symbols"

    def test_resolve_bang_strips_whitespace(self) -> None:
        """Test that whitespace is stripped from query for URL encoding."""
        url, query = resolve_bang(self.user, "!g   test query   ")
        assert url == "https://www.google.com/search?q=test+query"
        assert query == "  test query   "
