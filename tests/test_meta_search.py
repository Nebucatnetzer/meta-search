"""Unit tests for meta search functionality."""

from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest

from search.meta_search import Engine
from search.meta_search import fetch_results
from search.meta_search import filter_blocked
from search.meta_search import filter_results
from search.meta_search import get_blocked_domains
from search.meta_search import parallel_search
from search.models import BlockedDomain
from search.models import BlockList
from search.models import SearchUser

# pylint: disable=redefined-outer-name,unused-argument


@pytest.fixture
def user() -> SearchUser:
    """Create a test user."""
    return SearchUser.objects.create_user(username="testuser", password="testpass123")


@pytest.fixture
def blocklist(user: SearchUser) -> BlockList:
    """Create a blocklist for the test user."""
    blocklist = BlockList.objects.create(user=user)
    domain1 = BlockedDomain.objects.create(domain="spam.com")
    domain2 = BlockedDomain.objects.create(domain="ads.example.com")
    blocklist.blocked_domains.add(domain1, domain2)
    return blocklist


class TestEngine:
    """Tests for Engine dataclass."""

    def test_engine_creation(self) -> None:
        """Test creating an Engine instance."""
        engine = Engine(
            name="TestEngine",
            url="https://test.com",
            params=lambda q: {"query": q},
            parser=lambda html: [],  # Now takes HTML string
        )
        assert engine.name == "TestEngine"
        assert engine.url == "https://test.com"
        assert engine.url_query is False
        assert not engine.headers

    def test_engine_with_custom_headers(self) -> None:
        """Test Engine with custom headers."""
        headers = {"User-Agent": "TestBot"}
        engine = Engine(
            name="TestEngine",
            url="https://test.com",
            params=lambda q: {"query": q},
            parser=lambda html: [],  # Now takes HTML string
            headers=headers,
        )
        assert engine.headers == headers

    def test_engine_with_url_query(self) -> None:
        """Test Engine with url_query enabled."""
        engine = Engine(
            name="TestEngine",
            url="https://test.com",
            params=lambda q: {"query": q},
            parser=lambda html: [],  # Now takes HTML string
            url_query=True,
        )
        assert engine.url_query is True


class TestFetchResults:
    """Tests for fetch_results function."""

    @patch("search.meta_search.get_browser_page")
    def test_fetch_results_url_query_mode(self, mock_get_page: AsyncMock) -> None:
        """Test fetch_results with url_query mode."""
        # Mock the page and response
        mock_page = AsyncMock()
        mock_response = Mock()
        mock_response.status = 200
        mock_page.goto.return_value = mock_response
        mock_page.content.return_value = "<html>test content</html>"
        mock_get_page.return_value = mock_page

        def parser(
            html: str,
        ) -> list[dict[str, str]]:  # pylint: disable=unused-argument
            return [{"title": "test", "url": "https://example.com"}]

        engine = Engine(
            name="TestEngine",
            url="https://test.com",
            params=lambda q: {"q": q},
            parser=parser,
            url_query=True,
        )

        results = fetch_results(engine, "test query")

        # Verify the page was called with correct URL
        mock_page.goto.assert_called_once()
        call_args = mock_page.goto.call_args
        assert call_args[0][0] == "https://test.com?q=test+query"
        assert results == [{"title": "test", "url": "https://example.com"}]
        mock_page.close.assert_called_once()

    @patch("search.meta_search.get_browser_page")
    def test_fetch_results_params_mode(self, mock_get_page: AsyncMock) -> None:
        """Test fetch_results with params mode."""
        # Mock the page and response
        mock_page = AsyncMock()
        mock_response = Mock()
        mock_response.status = 200
        mock_page.goto.return_value = mock_response
        mock_page.content.return_value = "<html>test content</html>"
        mock_get_page.return_value = mock_page

        def parser(
            html: str,
        ) -> list[dict[str, str]]:  # pylint: disable=unused-argument
            return [{"title": "result", "url": "https://example.com"}]

        engine = Engine(
            name="TestEngine",
            url="https://test.com/search",
            params=lambda q: {"query": q, "format": "json"},
            parser=parser,
            url_query=False,
        )

        results = fetch_results(engine, "test query")

        # Verify the page was called with correct URL with params
        mock_page.goto.assert_called_once()
        call_args = mock_page.goto.call_args
        expected_url = "https://test.com/search?query=test+query&format=json"
        assert call_args[0][0] == expected_url
        assert results == [{"title": "result", "url": "https://example.com"}]
        mock_page.close.assert_called_once()

    @patch("search.meta_search.get_browser_page")
    def test_fetch_results_with_headers(self, mock_get_page: AsyncMock) -> None:
        """Test fetch_results passes custom headers."""
        # Mock the page and response
        mock_page = AsyncMock()
        mock_response = Mock()
        mock_response.status = 200
        mock_page.goto.return_value = mock_response
        mock_page.content.return_value = "<html>test content</html>"
        mock_get_page.return_value = mock_page

        headers = {"User-Agent": "CustomBot"}
        engine = Engine(
            name="TestEngine",
            url="https://test.com",
            params=lambda q: {"q": q},
            parser=lambda html: [],
            headers=headers,
        )

        fetch_results(engine, "query")

        # Verify headers were set on the page
        mock_page.set_extra_http_headers.assert_called_once_with(headers)
        mock_page.close.assert_called_once()

    @patch("search.meta_search.get_browser_page")
    def test_fetch_results_strips_trailing_question_mark(
        self, mock_get_page: AsyncMock
    ) -> None:
        """Test that trailing ?

        is stripped from URL before adding query.
        """
        # Mock the page and response
        mock_page = AsyncMock()
        mock_response = Mock()
        mock_response.status = 200
        mock_page.goto.return_value = mock_response
        mock_page.content.return_value = "<html>test content</html>"
        mock_get_page.return_value = mock_page

        engine = Engine(
            name="TestEngine",
            url="https://test.com/?",
            params=lambda q: {"q": q},
            parser=lambda html: [],
            url_query=True,
        )

        fetch_results(engine, "test search")

        call_args = mock_page.goto.call_args
        # The URL should have trailing ? stripped, then new query added
        assert call_args[0][0] == "https://test.com/?q=test+search"
        mock_page.close.assert_called_once()


class TestFilterBlocked:
    """Tests for filter_blocked function."""

    def test_filter_blocked_empty_list(self) -> None:
        """Test filtering with empty blocked domains list."""
        results = [
            {"url": "https://example.com"},
            {"url": "https://test.com"},
        ]
        filtered = filter_blocked(results, [])
        assert len(filtered) == 2

    def test_filter_blocked_dict_results(self) -> None:
        """Test filtering dict results with url key."""
        results = [
            {"url": "https://example.com/page1"},
            {"url": "https://spam.com/page2"},
            {"url": "https://test.com/page3"},
        ]
        blocked = ["spam.com"]
        filtered = filter_blocked(results, blocked)
        assert len(filtered) == 2
        assert filtered[0]["url"] == "https://example.com/page1"
        assert filtered[1]["url"] == "https://test.com/page3"

    def test_filter_blocked_link_key(self) -> None:
        """Test filtering with link key instead of url."""
        results = [
            {"link": "https://example.com"},
            {"link": "https://spam.com"},
        ]
        blocked = ["spam.com"]
        filtered = filter_blocked(results, blocked)
        assert len(filtered) == 1
        assert filtered[0]["link"] == "https://example.com"

    def test_filter_blocked_href_key(self) -> None:
        """Test filtering with href key."""
        results = [
            {"href": "https://example.com"},
            {"href": "https://spam.com"},
        ]
        blocked = ["spam.com"]
        filtered = filter_blocked(results, blocked)
        assert len(filtered) == 1

    def test_filter_blocked_string_results(self) -> None:
        """Test filtering string results."""
        results = [
            "https://example.com",
            "https://spam.com",
            "https://test.com",
        ]
        blocked = ["spam.com"]
        filtered = filter_blocked(results, blocked)
        assert len(filtered) == 2
        assert "https://spam.com" not in filtered

    def test_filter_blocked_multiple_domains(self) -> None:
        """Test filtering multiple blocked domains."""
        results = [
            {"url": "https://good.com"},
            {"url": "https://spam.com"},
            {"url": "https://ads.example.com"},
        ]
        blocked = ["spam.com", "ads.example.com"]
        filtered = filter_blocked(results, blocked)
        assert len(filtered) == 1
        assert filtered[0]["url"] == "https://good.com"

    def test_filter_blocked_partial_domain_match(self) -> None:
        """Test that domain matching works with partial matches."""
        results = [
            {"url": "https://subdomain.spam.com/page"},
            {"url": "https://example.com"},
        ]
        blocked = ["spam.com"]
        filtered = filter_blocked(results, blocked)
        assert len(filtered) == 1
        assert filtered[0]["url"] == "https://example.com"

    def test_filter_blocked_no_url_field(self) -> None:
        """Test handling of results without URL fields."""
        results = [
            {"title": "No URL here"},
            {"url": "https://example.com"},
        ]
        blocked = ["spam.com"]
        filtered = filter_blocked(results, blocked)
        assert len(filtered) == 2


@pytest.mark.django_db
class TestGetBlockedDomains:
    """Tests for get_blocked_domains function."""

    def test_get_blocked_domains_with_blocklist(
        self,
        user: SearchUser,
        blocklist: BlockList,
    ) -> None:
        """Test getting blocked domains for user with blocklist."""
        domains = get_blocked_domains(user)
        assert len(domains) == 2
        assert "spam.com" in domains
        assert "ads.example.com" in domains

    def test_get_blocked_domains_no_blocklist(self, user: SearchUser) -> None:
        """Test getting blocked domains for user without blocklist."""
        domains = get_blocked_domains(user)
        assert not domains

    def test_get_blocked_domains_anonymous_user(self, user: SearchUser) -> None:
        """Test getting blocked domains for user without any blocklists."""
        # Use a regular user without blocklists instead of AnonymousUser
        domains = get_blocked_domains(user)
        assert not domains

    def test_get_blocked_domains_empty_blocklist(self, user: SearchUser) -> None:
        """Test user with empty blocklist."""
        BlockList.objects.create(user=user)
        domains = get_blocked_domains(user)
        assert not domains


class TestFilterResults:
    """Tests for filter_results function."""

    def test_filter_results_remove_duplicates(self) -> None:
        """Test removing duplicate URLs."""
        results = [
            {"url": "https://example.com"},
            {"url": "https://example.com"},
            {"url": "https://test.com"},
        ]
        filtered = filter_results(results, [])
        assert len(filtered) == 2

    def test_filter_results_case_insensitive_duplicates(self) -> None:
        """Test duplicate detection is case insensitive."""
        results = [
            {"url": "https://Example.com"},
            {"url": "https://example.com"},
        ]
        filtered = filter_results(results, [])
        assert len(filtered) == 1

    def test_filter_results_whitespace_handling(self) -> None:
        """Test that whitespace is stripped for duplicate detection."""
        results = [
            {"url": "https://example.com  "},
            {"url": "  https://example.com"},
        ]
        filtered = filter_results(results, [])
        assert len(filtered) == 1

    def test_filter_results_with_blocked_domains(self) -> None:
        """Test filtering with blocked domains."""
        results = [
            {"url": "https://example.com"},
            {"url": "https://spam.com"},
            {"url": "https://test.com"},
        ]
        filtered = filter_results(results, ["spam.com"])
        assert len(filtered) == 2
        assert not any(r["url"] == "https://spam.com" for r in filtered)

    def test_filter_results_none_in_blocked_domains(self) -> None:
        """Test handling of None values in blocked domains."""
        results = [
            {"url": "https://example.com"},
            {"url": "https://spam.com"},
        ]
        filtered = filter_results(results, ["spam.com", None])
        assert len(filtered) == 1
        assert filtered[0]["url"] == "https://example.com"

    def test_filter_results_empty_url(self) -> None:
        """Test handling of empty URLs."""
        results = [
            {"url": ""},
            {"url": "https://example.com"},
        ]
        filtered = filter_results(results, [])
        assert len(filtered) == 1

    def test_filter_results_non_dict_results(self) -> None:
        """Test filtering string results."""
        results = [
            "https://example.com",
            "https://example.com",
            "https://test.com",
        ]
        filtered = filter_results(results, [])
        assert len(filtered) == 2


@pytest.mark.django_db
class TestParallelSearch:
    """Tests for parallel_search function."""

    @patch("search.meta_search.fetch_results")
    def test_parallel_search_basic(
        self,
        mock_fetch: Mock,
        user: SearchUser,
    ) -> None:
        """Test basic parallel search functionality."""
        mock_fetch.return_value = [
            {"title": "Result 1", "url": "https://example.com"},
        ]

        results = parallel_search("test query", user)

        assert len(results) == 1
        assert results[0]["title"] == "Result 1"
        mock_fetch.assert_called()

    @patch("search.meta_search.fetch_results")
    def test_parallel_search_strips_query(
        self,
        mock_fetch: Mock,
        user: SearchUser,
    ) -> None:
        """Test that query is stripped before searching."""
        mock_fetch.return_value = []

        parallel_search("  test query  ", user)

        # Verify the query was stripped before being passed to engines
        call_args = mock_fetch.call_args
        assert call_args[0][1] == "test query"

    @patch("search.meta_search.fetch_results")
    def test_parallel_search_deduplicates(
        self,
        mock_fetch: Mock,
        user: SearchUser,
    ) -> None:
        """Test that duplicate results are removed."""
        mock_fetch.return_value = [
            {"title": "Result 1", "url": "https://example.com"},
            {"title": "Result 1", "url": "https://example.com"},
        ]

        results = parallel_search("test", user)

        assert len(results) == 1

    @patch("search.meta_search.fetch_results")
    def test_parallel_search_filters_blocked(
        self,
        mock_fetch: Mock,
        user: SearchUser,
        blocklist: BlockList,
    ) -> None:
        """Test that blocked domains are filtered."""
        mock_fetch.return_value = [
            {"title": "Good", "url": "https://example.com"},
            {"title": "Spam", "url": "https://spam.com"},
        ]

        results = parallel_search("test", user)

        assert len(results) == 1
        assert results[0]["url"] == "https://example.com"

    @patch("search.meta_search.fetch_results")
    def test_parallel_search_handles_non_list_results(
        self,
        mock_fetch: Mock,
        user: SearchUser,
    ) -> None:
        """Test handling of non-list results from engines."""
        mock_fetch.return_value = None

        results = parallel_search("test", user)

        assert not results

    @patch("search.meta_search.fetch_results")
    def test_parallel_search_combines_results(
        self,
        mock_fetch: Mock,
        user: SearchUser,
    ) -> None:
        """Test that results from multiple engines are combined."""
        # Simulate different results from different calls
        mock_fetch.side_effect = [
            [{"title": "Result 1", "url": "https://example1.com"}],
            [{"title": "Result 2", "url": "https://example2.com"}],
        ]

        results = parallel_search("test", user)

        # Should have results from both engines
        assert len(results) >= 1
