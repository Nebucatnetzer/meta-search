"""Unit tests for bang handling."""

import pytest

from search.bangs import resolve_bang
from search.models import Bang
from search.models import SearchUser

# pylint: disable=redefined-outer-name,unused-argument


@pytest.fixture
def user() -> SearchUser:
    """Create a test user."""
    return SearchUser.objects.create_user(username="testuser", password="testpass123")


@pytest.fixture
def bang(user: SearchUser) -> Bang:
    """Create a test bang."""
    return Bang.objects.create(
        user=user,
        shortcut="g",
        url_template="https://www.google.com/search?q={query}",
    )


@pytest.mark.django_db
class TestResolveBang:
    """Tests for resolve_bang function."""

    def test_non_bang_query_returns_none(self, user: SearchUser) -> None:
        """Test that non-bang queries return (None, None)."""
        url, query = resolve_bang(user=user, query="regular search query")
        assert url is None
        assert query is None

    def test_empty_query_returns_none(self, user: SearchUser) -> None:
        """Test that empty query returns (None, None)."""
        url, query = resolve_bang(user=user, query="")
        assert url is None
        assert query is None

    def test_bang_without_search_query(self, user: SearchUser, bang: Bang) -> None:
        """Test bang shortcut without search terms."""
        url, query = resolve_bang(user=user, query="!g")
        assert url == "https://www.google.com/search?q="
        assert query == ""

    def test_bang_with_search_query(self, user: SearchUser, bang: Bang) -> None:
        """Test bang shortcut with search terms."""
        url, query = resolve_bang(user=user, query="!g python testing")
        assert url == "https://www.google.com/search?q=python+testing"
        assert query == "python testing"

    def test_bang_with_url_special_characters(
        self,
        user: SearchUser,
        bang: Bang,
    ) -> None:
        """Test bang with special characters in query."""
        url, query = resolve_bang(user=user, query="!g test&foo=bar")
        assert url == "https://www.google.com/search?q=test%26foo%3Dbar"
        assert query == "test&foo=bar"

    def test_bang_with_extra_whitespace(self, user: SearchUser, bang: Bang) -> None:
        """Test bang with extra whitespace in query."""
        url, query = resolve_bang(user=user, query="!g   spaced  query  ")
        assert url == "https://www.google.com/search?q=spaced++query"
        assert query == "  spaced  query  "

    def test_nonexistent_bang_returns_none_url(self, user: SearchUser) -> None:
        """Test that nonexistent bang returns None for URL."""
        url, query = resolve_bang(user=user, query="!xyz test query")
        assert url is None
        assert query == "test query"

    def test_nonexistent_bang_without_query(self, user: SearchUser) -> None:
        """Test nonexistent bang without search query."""
        url, query = resolve_bang(user=user, query="!xyz")
        assert url is None
        assert query == ""

    def test_anonymous_user_no_bangs(self, bang: Bang) -> None:
        """Test that anonymous users don't have access to bangs."""
        # Create a user that doesn't have this bang
        other_user = SearchUser.objects.create_user(username="other", password="pass123")
        url, query = resolve_bang(user=other_user, query="!g test")
        assert url is None
        assert query == "test"

    def test_bang_belongs_to_different_user(self) -> None:
        """Test that bang from different user is not accessible."""
        user1 = SearchUser.objects.create_user(username="user1", password="pass1")
        user2 = SearchUser.objects.create_user(username="user2", password="pass2")
        Bang.objects.create(
            user=user1,
            shortcut="private",
            url_template="https://example.com?q={query}",
        )

        url, query = resolve_bang(user=user2, query="!private test")
        assert url is None
        assert query == "test"

    def test_multiple_bangs_same_user(self, user: SearchUser) -> None:
        """Test multiple bangs for the same user."""
        Bang.objects.create(
            user=user,
            shortcut="gh",
            url_template="https://github.com/search?q={query}",
        )
        Bang.objects.create(
            user=user,
            shortcut="so",
            url_template="https://stackoverflow.com/search?q={query}",
        )

        url1, query1 = resolve_bang(user=user, query="!gh django")
        assert url1 == "https://github.com/search?q=django"
        assert query1 == "django"

        url2, query2 = resolve_bang(user=user, query="!so python error")
        assert url2 == "https://stackoverflow.com/search?q=python+error"
        assert query2 == "python error"

    def test_bang_with_unicode_query(self, user: SearchUser, bang: Bang) -> None:
        """Test bang with unicode characters."""
        url, query = resolve_bang(user=user, query="!g 日本語 test")
        assert "{query}" not in url
        assert query == "日本語 test"

    def test_bang_only_exclamation(self, user: SearchUser) -> None:
        """Test single exclamation mark."""
        url, query = resolve_bang(user=user, query="!")
        assert url is None
        assert query == ""
