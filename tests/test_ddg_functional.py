"""Functional tests that demonstrate DuckDuckGo parser works with real responses.

These tests make actual HTTP requests to verify:
1. The parser handles real DuckDuckGo HTML without errors
2. The application can make proper requests to search engines
3. The parser is robust against rate limiting and anti-bot measures

Note: DuckDuckGo may return empty results due to rate limiting, IP blocking,
or anti-bot detection. The tests validate parser robustness rather than
requiring specific search results.
"""

import pytest
import requests

from search.constants import DEFAULT_BROWSER_HEADERS
from search.ddg_parser import duckduckgo_html_parser


@pytest.mark.live
def test_parser_handles_real_ddg_response() -> None:
    """Test that parser can handle a real DuckDuckGo HTML response without errors."""
    headers = DEFAULT_BROWSER_HEADERS

    # Use the HTML version that actually works
    url = "https://duckduckgo.com/html/"
    params = {"q": "test"}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()

        # The main test: parser should handle the response without errors
        results = duckduckgo_html_parser(response)

        # Basic validation
        assert isinstance(results, list), "Parser should always return a list"

        # If we get results, validate their structure
        for result in results:
            assert isinstance(result, dict), "Each result should be a dict"
            assert "title" in result, "Result should have title field"
            assert "url" in result, "Result should have url field"
            assert isinstance(result["title"], str), "Title should be string"
            assert isinstance(result["url"], str), "URL should be string"

        print(f"Successfully parsed {len(results)} results from DuckDuckGo")

    except requests.exceptions.RequestException as e:
        pytest.skip(f"Could not connect to DuckDuckGo: {e}")


@pytest.mark.live
def test_parser_robust_against_ddg_changes() -> None:
    """Test that parser gracefully handles unexpected DuckDuckGo HTML structure."""
    headers = DEFAULT_BROWSER_HEADERS

    url = "https://duckduckgo.com/html/"
    params = {"q": "python"}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()

        # This should not raise any exceptions, even if HTML structure changes
        results = duckduckgo_html_parser(response)

        # Parser should always return a list
        assert isinstance(results, list)

        print(
            f"Parser handled DuckDuckGo response robustly, returned {len(results)} results"
        )

    except requests.exceptions.RequestException as e:
        pytest.skip(f"Could not connect to DuckDuckGo: {e}")


@pytest.mark.live
def test_real_search_engine_integration() -> None:
    """Test using the actual search engine configuration from meta_search.py."""
    # pylint: disable=import-outside-toplevel
    from search.meta_search import SEARCH_ENGINES
    from search.meta_search import fetch_results

    # Use the actual engine configuration
    ddg_engine = SEARCH_ENGINES[0]  # DuckDuckGo is the first engine

    try:
        # Test the actual fetch_results function
        results = fetch_results(ddg_engine, "test")

        # Should return a list (may be empty due to rate limiting)
        assert isinstance(results, list)

        # If we get results, validate structure
        for result in results:
            assert isinstance(result, dict)
            assert "title" in result
            assert "url" in result

        print(f"Real engine integration test: {len(results)} results")

    except requests.exceptions.RequestException as e:
        pytest.skip(f"Could not connect to search engine: {e}")
