"""Unit tests for views."""

from unittest.mock import Mock
from unittest.mock import patch

import pytest
from django.http import HttpResponseRedirect
from django.test import Client
from django.test import RequestFactory
from django.urls import reverse

from search.models import Bang
from search.models import SearchUser
from search.views import index

# pylint: disable=redefined-outer-name,unused-argument


@pytest.fixture
def user() -> SearchUser:
    """Create a test user."""
    return SearchUser.objects.create_user(username="testuser", password="testpass123")


@pytest.fixture
def client() -> Client:
    """Create a Django test client."""
    return Client()


@pytest.fixture
def authenticated_client(user: SearchUser) -> Client:
    """Create an authenticated Django test client."""
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def factory() -> RequestFactory:
    """Create a request factory."""
    return RequestFactory()


@pytest.mark.django_db
class TestIndexView:
    """Tests for index view."""

    def test_index_requires_login(self, client: Client) -> None:
        """Test that index view requires authentication."""
        response = client.get(reverse("index"))
        assert response.status_code == 302  # Redirect to login
        assert isinstance(response, HttpResponseRedirect)
        assert "/accounts/login/" in response.url

    def test_index_get_without_query(self, authenticated_client: Client) -> None:
        """Test GET request without query parameter."""
        response = authenticated_client.get(reverse("index"))
        assert response.status_code == 200
        assert "results" in response.context
        assert response.context["results"] is None

    @patch("search.views.parallel_search")
    def test_index_with_query(
        self,
        mock_search: Mock,
        authenticated_client: Client,
    ) -> None:
        """Test GET request with query parameter."""
        mock_search.return_value = [
            {"title": "Result 1", "url": "https://example.com"},
        ]

        response = authenticated_client.get(reverse("index"), {"query": "test query"})

        assert response.status_code == 200
        assert "results" in response.context
        assert len(response.context["results"]) == 1
        mock_search.assert_called_once()

    @patch("search.views.parallel_search")
    def test_index_redirects_when_no_results(
        self,
        mock_search: Mock,
        authenticated_client: Client,
    ) -> None:
        """Test redirect to DuckDuckGo when no results found."""
        mock_search.return_value = []

        response = authenticated_client.get(reverse("index"), {"query": "rare query"})

        assert response.status_code == 302
        assert isinstance(response, HttpResponseRedirect)
        assert response.url == "https://duckduckgo.com?q=rare+query"

    @patch("search.views.resolve_bang")
    def test_index_redirects_for_valid_bang(
        self,
        mock_resolve: Mock,
        authenticated_client: Client,
        user: SearchUser,
    ) -> None:
        """Test redirect when valid bang is found."""
        mock_resolve.return_value = ("https://google.com/search?q=test", "test")

        response = authenticated_client.get(reverse("index"), {"query": "!g test"})

        assert response.status_code == 302
        assert isinstance(response, HttpResponseRedirect)
        assert response.url == "https://google.com/search?q=test"
        mock_resolve.assert_called_once()

    @patch("search.views.resolve_bang")
    @patch("search.views.parallel_search")
    def test_index_searches_with_invalid_bang(
        self,
        mock_search: Mock,
        mock_resolve: Mock,
        authenticated_client: Client,
        user: SearchUser,
    ) -> None:
        """Test search when bang doesn't exist."""
        mock_resolve.return_value = (None, "test query")
        mock_search.return_value = [{"title": "Result", "url": "https://example.com"}]

        response = authenticated_client.get(
            reverse("index"),
            {"query": "!invalid test query"},
        )

        assert response.status_code == 200
        # Just verify it was called once with the correct query argument
        mock_search.assert_called_once()
        call_kwargs = mock_search.call_args[1]
        assert call_kwargs["query"] == "test query"

    @patch("search.views.resolve_bang")
    @patch("search.views.parallel_search")
    def test_index_empty_query_after_bang(
        self,
        mock_search: Mock,
        mock_resolve: Mock,
        authenticated_client: Client,
    ) -> None:
        """Test handling of bang without search terms."""
        mock_resolve.return_value = ("https://google.com", "")

        response = authenticated_client.get(reverse("index"), {"query": "!g"})

        assert response.status_code == 302
        assert isinstance(response, HttpResponseRedirect)
        assert response.url == "https://google.com"

    def test_index_empty_query_string(self, authenticated_client: Client) -> None:
        """Test with empty query string."""
        response = authenticated_client.get(reverse("index"), {"query": ""})

        assert response.status_code == 200
        assert response.context["results"] is None

    @patch("search.views.parallel_search")
    def test_index_query_with_special_characters(
        self,
        mock_search: Mock,
        authenticated_client: Client,
    ) -> None:
        """Test query with special characters."""
        mock_search.return_value = []

        response = authenticated_client.get(
            reverse("index"),
            {"query": "test&foo=bar"},
        )

        assert response.status_code == 302
        assert isinstance(response, HttpResponseRedirect)
        assert "test%26foo%3Dbar" in response.url

    def test_index_uses_correct_template(self, authenticated_client: Client) -> None:
        """Test that correct template is used."""
        response = authenticated_client.get(reverse("index"))

        assert response.status_code == 200
        assert "search/index.html" in [t.name for t in response.templates]

    @patch("search.views.parallel_search")
    @patch("search.views.resolve_bang")
    def test_index_view_function_directly(
        self,
        mock_resolve: Mock,
        mock_search: Mock,
        factory: RequestFactory,
        user: SearchUser,
    ) -> None:
        """Test index view function directly."""
        mock_resolve.return_value = (None, None)
        mock_search.return_value = [{"title": "Test", "url": "https://example.com"}]

        request = factory.get("/", {"query": "test"})
        request.user = user

        response = index(request)

        assert response.status_code == 200
        mock_search.assert_called_once_with(query="test", user=user)

    @patch("search.views.parallel_search")
    @patch("search.views.resolve_bang")
    def test_index_passes_user_to_functions(
        self,
        mock_resolve: Mock,
        mock_search: Mock,
        factory: RequestFactory,
        user: SearchUser,
    ) -> None:
        """Test that user is passed to resolve_bang and parallel_search."""
        mock_resolve.return_value = (None, None)
        mock_search.return_value = [{"title": "Test", "url": "https://example.com"}]

        request = factory.get("/", {"query": "test query"})
        request.user = user

        index(request)

        # Check that user was passed to both functions
        mock_resolve.assert_called_once()
        call_kwargs = mock_resolve.call_args[1]
        assert call_kwargs["user"] == user

        mock_search.assert_called_once()
        call_kwargs = mock_search.call_args[1]
        assert call_kwargs["user"] == user


@pytest.mark.django_db
class TestIndexViewIntegration:
    """Integration tests for index view."""

    def test_full_search_flow(
        self,
        authenticated_client: Client,
        user: SearchUser,
    ) -> None:
        """Test full search flow with real bang."""
        Bang.objects.create(
            user=user,
            shortcut="test",
            url_template="https://example.com/search?q={query}",
        )

        response = authenticated_client.get(
            reverse("index"),
            {"query": "!test my query"},
        )

        assert response.status_code == 302
        assert isinstance(response, HttpResponseRedirect)
        assert response.url == "https://example.com/search?q=my+query"

    @patch("search.views.parallel_search")
    def test_authenticated_user_can_search(
        self,
        mock_search: Mock,
        authenticated_client: Client,
    ) -> None:
        """Test that authenticated user can perform search."""
        mock_search.return_value = [
            {"title": "Result", "url": "https://example.com"},
        ]

        response = authenticated_client.get(reverse("index"), {"query": "python"})

        assert response.status_code == 200
        assert mock_search.called
