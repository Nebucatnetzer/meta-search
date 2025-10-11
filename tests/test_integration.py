"""Integration and functional tests for the meta-search application."""

from unittest.mock import Mock
from unittest.mock import patch

import pytest
from django.test import Client
from django.urls import reverse

from search.models import Bang
from search.models import BlockedDomain
from search.models import BlockList
from search.models import SearchUser

# pylint: disable=redefined-outer-name


@pytest.fixture
def user() -> SearchUser:
    """Create a test user."""
    return SearchUser.objects.create_user(username="testuser", password="testpass123")


@pytest.fixture
def authenticated_client(user: SearchUser) -> Client:
    """Create an authenticated Django test client."""
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.django_db
class TestEndToEndSearchFlow:
    """End-to-end tests for search functionality."""

    @patch("search.meta_search.requests.get")
    def test_complete_search_workflow(
        self,
        mock_get: Mock,
        authenticated_client: Client,
    ) -> None:
        """Test complete search workflow from request to response."""
        # Mock DuckDuckGo response
        mock_response = Mock()
        mock_response.text = """
        <html>
            <article data-testid="result">
                <h2>
                    <a href="https://example.com">Example Result</a>
                </h2>
            </article>
        </html>
        """
        mock_get.return_value = mock_response

        response = authenticated_client.get(reverse("index"), {"query": "test"})

        assert response.status_code == 200
        assert "results" in response.context
        results = response.context["results"]
        assert len(results) == 1
        assert results[0]["title"] == "Example Result"
        assert results[0]["url"] == "https://example.com"

    @patch("search.meta_search.requests.get")
    def test_search_with_blocked_domains(
        self,
        mock_get: Mock,
        authenticated_client: Client,
        user: SearchUser,
    ) -> None:
        """Test that blocked domains are filtered from search results."""
        # Set up blocked domains
        blocklist = BlockList.objects.create(user=user)
        blocked = BlockedDomain.objects.create(domain="spam.com")
        blocklist.blocked_domains.add(blocked)

        # Mock response with both good and blocked results
        mock_response = Mock()
        mock_response.text = """
        <html>
            <article data-testid="result-1">
                <h2><a href="https://example.com">Good Result</a></h2>
            </article>
            <article data-testid="result-2">
                <h2><a href="https://spam.com">Spam Result</a></h2>
            </article>
        </html>
        """
        mock_get.return_value = mock_response

        response = authenticated_client.get(reverse("index"), {"query": "test"})

        assert response.status_code == 200
        results = response.context["results"]
        assert len(results) == 1
        assert results[0]["url"] == "https://example.com"
        assert not any(r["url"] == "https://spam.com" for r in results)

    def test_bang_redirect_flow(
        self,
        authenticated_client: Client,
        user: SearchUser,
    ) -> None:
        """Test bang redirect flow."""
        Bang.objects.create(
            user=user,
            shortcut="g",
            url_template="https://google.com/search?q={query}",
        )

        response = authenticated_client.get(
            reverse("index"),
            {"query": "!g django testing"},
        )

        assert response.status_code == 302
        assert response.url == "https://google.com/search?q=django+testing"

    @patch("search.meta_search.requests.get")
    def test_invalid_bang_falls_back_to_search(
        self,
        mock_get: Mock,
        authenticated_client: Client,
    ) -> None:
        """Test that invalid bang falls back to regular search."""
        mock_response = Mock()
        mock_response.text = """
        <html>
            <article data-testid="result">
                <h2><a href="https://example.com">Result</a></h2>
            </article>
        </html>
        """
        mock_get.return_value = mock_response

        response = authenticated_client.get(
            reverse("index"),
            {"query": "!invalid search query"},
        )

        assert response.status_code == 200
        results = response.context["results"]
        assert len(results) == 1

    @patch("search.meta_search.requests.get")
    def test_duplicate_results_removed(
        self,
        mock_get: Mock,
        authenticated_client: Client,
    ) -> None:
        """Test that duplicate results are removed."""
        mock_response = Mock()
        mock_response.text = """
        <html>
            <article data-testid="result-1">
                <h2><a href="https://example.com">Result 1</a></h2>
            </article>
            <article data-testid="result-2">
                <h2><a href="https://example.com">Result 1 Duplicate</a></h2>
            </article>
            <article data-testid="result-3">
                <h2><a href="https://different.com">Result 2</a></h2>
            </article>
        </html>
        """
        mock_get.return_value = mock_response

        response = authenticated_client.get(reverse("index"), {"query": "test"})

        assert response.status_code == 200
        results = response.context["results"]
        assert len(results) == 2
        urls = [r["url"] for r in results]
        assert urls.count("https://example.com") == 1


@pytest.mark.django_db
class TestUserIsolation:
    """Tests for user data isolation."""

    def test_user_bangs_are_isolated(self) -> None:
        """Test that users can only access their own bangs."""
        user1 = SearchUser.objects.create_user(username="user1", password="pass1")
        user2 = SearchUser.objects.create_user(username="user2", password="pass2")

        bang1 = Bang.objects.create(
            user=user1,
            shortcut="private1",
            url_template="https://user1.com?q={query}",
        )
        bang2 = Bang.objects.create(
            user=user2,
            shortcut="private2",
            url_template="https://user2.com?q={query}",
        )

        # User1 can only see their bang
        user1_bangs = Bang.objects.filter(user=user1)
        assert bang1 in user1_bangs
        assert bang2 not in user1_bangs

        # User2 can only see their bang
        user2_bangs = Bang.objects.filter(user=user2)
        assert bang2 in user2_bangs
        assert bang1 not in user2_bangs

    @patch("search.meta_search.requests.get")
    def test_user_blocklists_are_isolated(self, mock_get: Mock) -> None:
        """Test that users have separate blocklists."""
        user1 = SearchUser.objects.create_user(username="user1", password="pass1")
        user2 = SearchUser.objects.create_user(username="user2", password="pass2")

        # User1 blocks spam.com
        blocklist1 = BlockList.objects.create(user=user1)
        domain1 = BlockedDomain.objects.create(domain="spam.com")
        blocklist1.blocked_domains.add(domain1)

        # User2 blocks ads.com
        blocklist2 = BlockList.objects.create(user=user2)
        domain2 = BlockedDomain.objects.create(domain="ads.com")
        blocklist2.blocked_domains.add(domain2)

        # Mock response with both domains
        mock_response = Mock()
        mock_response.text = """
        <html>
            <article data-testid="result-1">
                <h2><a href="https://spam.com">Spam</a></h2>
            </article>
            <article data-testid="result-2">
                <h2><a href="https://ads.com">Ads</a></h2>
            </article>
        </html>
        """
        mock_get.return_value = mock_response

        # User1 client
        client1 = Client()
        client1.force_login(user1)
        response1 = client1.get(reverse("index"), {"query": "test"})
        results1 = response1.context["results"]

        # User1 should not see spam.com but should see ads.com
        assert not any(r["url"] == "https://spam.com" for r in results1)
        assert any(r["url"] == "https://ads.com" for r in results1)

        # User2 client
        client2 = Client()
        client2.force_login(user2)
        response2 = client2.get(reverse("index"), {"query": "test"})
        results2 = response2.context["results"]

        # User2 should not see ads.com but should see spam.com
        assert not any(r["url"] == "https://ads.com" for r in results2)
        assert any(r["url"] == "https://spam.com" for r in results2)


@pytest.mark.django_db
class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @patch("search.meta_search.requests.get")
    def test_empty_search_results_redirect(
        self,
        mock_get: Mock,
        authenticated_client: Client,
    ) -> None:
        """Test redirect when search returns no results."""
        mock_response = Mock()
        mock_response.text = "<html></html>"
        mock_get.return_value = mock_response

        response = authenticated_client.get(
            reverse("index"),
            {"query": "nonexistent query"},
        )

        assert response.status_code == 302
        assert "duckduckgo.com" in response.url

    @patch("search.meta_search.requests.get")
    def test_malformed_html_response(
        self,
        mock_get: Mock,
        authenticated_client: Client,
    ) -> None:
        """Test handling of malformed HTML response."""
        mock_response = Mock()
        mock_response.text = "<html><broken>"
        mock_get.return_value = mock_response

        response = authenticated_client.get(reverse("index"), {"query": "test"})

        # Should redirect to DDG when no results parsed
        assert response.status_code == 302

    def test_multiple_bangs_same_shortcut_different_users(self) -> None:
        """Test that different users can have bangs with same shortcut."""
        user1 = SearchUser.objects.create_user(username="user1", password="pass")
        user2 = SearchUser.objects.create_user(username="user2", password="pass")

        Bang.objects.create(
            user=user1,
            shortcut="g",
            url_template="https://google.com?q={query}",
        )
        Bang.objects.create(
            user=user2,
            shortcut="g",
            url_template="https://different.com?q={query}",
        )

        # Should have 2 bangs with same shortcut
        assert Bang.objects.filter(shortcut="g").count() == 2

    @patch("search.meta_search.requests.get")
    def test_special_characters_in_search_query(
        self,
        mock_get: Mock,
        authenticated_client: Client,
    ) -> None:
        """Test search with special characters."""
        mock_response = Mock()
        mock_response.text = """
        <html>
            <article data-testid="result">
                <h2><a href="https://example.com">Result</a></h2>
            </article>
        </html>
        """
        mock_get.return_value = mock_response

        response = authenticated_client.get(
            reverse("index"),
            {"query": "test & special <chars>"},
        )

        assert response.status_code == 200
        mock_get.assert_called()

    def test_bang_with_no_search_terms(
        self,
        authenticated_client: Client,
        user: SearchUser,
    ) -> None:
        """Test bang without search terms."""
        Bang.objects.create(
            user=user,
            shortcut="g",
            url_template="https://google.com/search?q={query}",
        )

        response = authenticated_client.get(reverse("index"), {"query": "!g"})

        assert response.status_code == 302
        assert response.url == "https://google.com/search?q="


@pytest.mark.django_db
class TestConcurrentSearch:  # pylint: disable=too-few-public-methods
    """Tests for concurrent search functionality."""

    @patch("search.meta_search.requests.get")
    def test_parallel_search_aggregates_results(
        self,
        mock_get: Mock,
        authenticated_client: Client,
    ) -> None:
        """Test that parallel search aggregates results from engines."""
        mock_response = Mock()
        mock_response.text = """
        <html>
            <article data-testid="result">
                <h2><a href="https://example.com">Result</a></h2>
            </article>
        </html>
        """
        mock_get.return_value = mock_response

        response = authenticated_client.get(reverse("index"), {"query": "test"})

        assert response.status_code == 200
        assert mock_get.called
        results = response.context["results"]
        assert len(results) >= 1
