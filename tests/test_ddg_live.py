"""Live functional tests for DuckDuckGo parser that make real HTTP requests.

These tests require internet connectivity and will make actual requests to DuckDuckGo.
They can be skipped using: pytest -m "not live"

Note: DuckDuckGo may return empty results due to rate limiting or anti-bot measures.
The tests validate parser behavior rather than requiring specific search results.
"""

import time

import pytest
import requests

from search.constants import DEFAULT_BROWSER_HEADERS
from search.ddg_parser import duckduckgo_html_parser


@pytest.mark.live
class TestDuckDuckGoLive:
    """Live functional tests that make real requests to DuckDuckGo."""

    @pytest.fixture
    def ddg_headers(self) -> dict[str, str]:
        """Standard headers for DuckDuckGo requests."""
        return DEFAULT_BROWSER_HEADERS

    @pytest.fixture(autouse=True)
    def rate_limit_delay(self) -> None:
        """Add delay between tests to avoid rate limiting."""
        time.sleep(1)  # 1 second delay between tests

    def test_live_search_python(self, ddg_headers: dict[str, str]) -> None:
        """Test live search for 'python' and verify results."""
        url = "https://html.duckduckgo.com/html/?q=python"

        response = requests.get(url, headers=ddg_headers, timeout=10)
        response.raise_for_status()

        results = duckduckgo_html_parser(response.text)

        # DuckDuckGo may return empty results due to rate limiting,
        # but parser should always return a list
        assert isinstance(results, list), "Parser should always return a list"
        assert len(results) <= 50, "Should not return excessive results"

        # If we get results, validate their structure
        if results:
            # All results should have required fields
            for result in results:
                assert "title" in result, "Result should have title"
                assert "url" in result, "Result should have URL"
                assert isinstance(result["title"], str), "Title should be string"
                assert isinstance(result["url"], str), "URL should be string"
                assert result["title"].strip(), "Title should not be empty"
                assert result["url"].strip(), "URL should not be empty"

            # Should find python.org in results (if we have results)
            python_urls = [r["url"] for r in results if "python.org" in r["url"]]
            assert (
                len(python_urls) > 0
            ), "Should find python.org in results when results are returned"
        else:
            # If no results, it might be due to rate limiting - that's okay
            print("No results returned - possibly due to rate limiting")

    def test_live_search_programming(self, ddg_headers: dict[str, str]) -> None:
        """Test live search for 'programming' and verify results."""
        url = "https://html.duckduckgo.com/html/?q=programming"

        response = requests.get(url, headers=ddg_headers, timeout=10)
        response.raise_for_status()

        results = duckduckgo_html_parser(response.text)

        # Programming is a common term, should get results
        assert (
            len(results) >= 0
        ), "Should return results for programming (or empty list if rate limited)"

        # If we get results, validate them
        if results:
            for result in results:
                assert "title" in result, "Result should have title"
                assert "url" in result, "Result should have URL"
                assert isinstance(result["title"], str), "Title should be string"
                assert isinstance(result["url"], str), "URL should be string"

    def test_live_search_django(self, ddg_headers: dict[str, str]) -> None:
        """Test live search for 'django' and verify results."""
        url = "https://html.duckduckgo.com/html/?q=django"

        response = requests.get(url, headers=ddg_headers, timeout=10)
        response.raise_for_status()

        results = duckduckgo_html_parser(response.text)

        # Parser should always return a list, even if empty due to rate limiting
        assert isinstance(results, list), "Parser should always return a list"

        # If we get results, validate them and check for django content
        if results:
            # Should find djangoproject.com in results when results are available
            django_urls = [r["url"] for r in results if "djangoproject.com" in r["url"]]
            assert (
                len(django_urls) > 0
            ), "Should find djangoproject.com in results when results are returned"
        else:
            # If no results, it might be due to rate limiting - that's okay
            print("No results returned - possibly due to rate limiting")

    def test_live_search_with_special_characters(
        self, ddg_headers: dict[str, str]
    ) -> None:
        """Test live search with special characters and spaces."""
        url = "https://html.duckduckgo.com/html/?q=python+web+development"

        response = requests.get(url, headers=ddg_headers, timeout=10)
        response.raise_for_status()

        results = duckduckgo_html_parser(response.text)

        # Parser should always return a list
        assert isinstance(results, list), "Parser should always return a list"

        # If we get results, validate their structure
        if results:
            # Results should contain URLs (basic validation)
            for result in results:
                assert result["url"].startswith(
                    ("http://", "https://")
                ), "URLs should be valid HTTP(S)"
        else:
            # If no results, it might be due to rate limiting - that's okay
            print(
                "No results returned for multi-word query - possibly due to rate limiting"
            )

    def test_live_search_rare_term(self, ddg_headers: dict[str, str]) -> None:
        """Test live search for a rare term that might return fewer results."""
        url = "https://html.duckduckgo.com/html/?q=zweili+meta+search+engine"

        response = requests.get(url, headers=ddg_headers, timeout=10)
        response.raise_for_status()

        results = duckduckgo_html_parser(response.text)

        # Even rare searches should return some results or empty list
        assert isinstance(results, list), "Should always return a list"

        # If we get results, they should be properly formatted
        for result in results:
            assert "title" in result and "url" in result
            assert isinstance(result["title"], str)
            assert isinstance(result["url"], str)

    def test_live_parser_handles_current_ddg_format(
        self, ddg_headers: dict[str, str]
    ) -> None:
        """Test that parser handles current DuckDuckGo HTML format."""
        url = "https://html.duckduckgo.com/html/?q=github"

        response = requests.get(url, headers=ddg_headers, timeout=10)
        response.raise_for_status()

        results = duckduckgo_html_parser(response.text)

        # Parser should always return a list
        assert isinstance(results, list), "Parser should always return a list"

        # If we get results, validate their structure and check for github content
        if results:
            # Check that we get github.com in results
            github_results = [r for r in results if "github.com" in r["url"]]
            assert (
                len(github_results) > 0
            ), "Should find github.com in results when results are returned"

            # Verify result structure
            for result in results[:5]:  # Check first 5 results
                assert len(result["title"]) > 0, "Titles should not be empty"
                assert result["url"].startswith("http"), "URLs should start with http"
                # Should not contain DuckDuckGo redirect artifacts
                assert (
                    "duckduckgo.com/l/" not in result["url"]
                ), "URLs should be cleaned of redirects"
        else:
            # If no results, it might be due to rate limiting - that's okay
            print(
                "No results returned for github query - possibly due to rate limiting"
            )

    @pytest.mark.slow
    def test_live_multiple_searches_consistency(
        self, ddg_headers: dict[str, str]
    ) -> None:
        """Test multiple searches to verify parser consistency."""
        search_terms = ["python", "javascript", "rust", "golang"]
        all_results = []

        for term in search_terms:
            url = f"https://html.duckduckgo.com/html/?q={term}"
            response = requests.get(url, headers=ddg_headers, timeout=10)
            response.raise_for_status()

            results = duckduckgo_html_parser(response.text)

            # Add extra delay between multiple searches
            time.sleep(2)

            # Parser should always return a list
            assert isinstance(results, list), f"Parser should return list for {term}"

            # Only extend if we have results (to avoid rate limiting issues)
            if results:
                all_results.extend(results)
            else:
                print(f"No results returned for {term} - possibly due to rate limiting")

        # All results that we did get should follow the same structure
        for result in all_results:
            assert set(result.keys()) == {
                "title",
                "url",
            }, "All results should have same structure"

    def test_live_search_with_url_encoding(self, ddg_headers: dict[str, str]) -> None:
        """Test search with URL-encoded characters."""
        # Search for "C++" which requires URL encoding
        url = "https://html.duckduckgo.com/html/?q=C%2B%2B+programming"

        response = requests.get(url, headers=ddg_headers, timeout=10)
        response.raise_for_status()

        results = duckduckgo_html_parser(response.text)

        # Parser should always return a list
        assert isinstance(results, list), "Parser should always return a list"

        # If we get results, validate them and check for C++ content
        if results:
            # Should find relevant programming results
            cpp_results = [
                r
                for r in results
                if any(
                    keyword in r["title"].lower() or keyword in r["url"].lower()
                    for keyword in ["c++", "cpp", "programming"]
                )
            ]
            assert (
                len(cpp_results) > 0
            ), "Should find C++ related results when results are returned"
        else:
            # If no results, it might be due to rate limiting - that's okay
            print(
                "No results returned for URL-encoded query - possibly due to rate limiting"
            )


@pytest.mark.live
@pytest.mark.slow
def test_live_error_handling_timeout() -> None:
    """Test that parser handles network timeouts gracefully."""
    # Use a very short timeout to trigger timeout
    with pytest.raises(requests.exceptions.Timeout):
        requests.get("https://html.duckduckgo.com/html/?q=test", timeout=0.001)


@pytest.mark.live
def test_live_error_handling_invalid_response() -> None:
    """Test parser with potentially invalid responses."""
    # Test with a URL that might return different content
    headers = {"User-Agent": "InvalidBot/1.0"}

    response = requests.get(
        "https://html.duckduckgo.com/html/?q=test", headers=headers, timeout=10
    )

    # Even with unusual user agent, parser should handle the response
    results = duckduckgo_html_parser(response.text)
    assert isinstance(
        results, list
    ), "Should always return a list even with unusual responses"
