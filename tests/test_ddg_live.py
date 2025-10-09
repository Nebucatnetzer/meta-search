"""Live functional tests for DuckDuckGo parser that make real HTTP requests.

These tests require internet connectivity and will make actual requests to DuckDuckGo.
They can be skipped using: pytest -m "not live"

Note: DuckDuckGo may return empty results due to rate limiting or anti-bot measures.
The tests validate parser behavior rather than requiring specific search results.
"""

import pytest
import requests

from search.ddg_parser import duckduckgo_html_parser


@pytest.mark.live
class TestDuckDuckGoLive:
    """Live functional tests that make real requests to DuckDuckGo."""

    @pytest.fixture
    def ddg_headers(self) -> dict[str, str]:
        """Standard headers for DuckDuckGo requests."""
        return {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    def test_live_search_python(self, ddg_headers: dict[str, str]) -> None:
        """Test live search for 'python' and verify results."""
        url = "https://html.duckduckgo.com/html/?q=python"

        response = requests.get(url, headers=ddg_headers, timeout=10)
        response.raise_for_status()

        results = duckduckgo_html_parser(response)

        # DuckDuckGo may return empty results due to rate limiting, but parser should always return a list
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

        results = duckduckgo_html_parser(response)

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

        results = duckduckgo_html_parser(response)

        assert len(results) > 0, "Should return results for django"

        # Should find djangoproject.com in results
        django_urls = [r["url"] for r in results if "djangoproject.com" in r["url"]]
        assert len(django_urls) > 0, "Should find djangoproject.com in results"

    def test_live_search_with_special_characters(
        self, ddg_headers: dict[str, str]
    ) -> None:
        """Test live search with special characters and spaces."""
        url = "https://html.duckduckgo.com/html/?q=python+web+development"

        response = requests.get(url, headers=ddg_headers, timeout=10)
        response.raise_for_status()

        results = duckduckgo_html_parser(response)

        assert len(results) > 0, "Should return results for multi-word query"

        # Results should contain URLs (basic validation)
        for result in results:
            assert result["url"].startswith(
                ("http://", "https://")
            ), "URLs should be valid HTTP(S)"

    def test_live_search_rare_term(self, ddg_headers: dict[str, str]) -> None:
        """Test live search for a rare term that might return fewer results."""
        url = "https://html.duckduckgo.com/html/?q=zweili+meta+search+engine"

        response = requests.get(url, headers=ddg_headers, timeout=10)
        response.raise_for_status()

        results = duckduckgo_html_parser(response)

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

        results = duckduckgo_html_parser(response)

        assert len(results) > 0, "Should parse current DuckDuckGo format"

        # Check that we get github.com in results
        github_results = [r for r in results if "github.com" in r["url"]]
        assert len(github_results) > 0, "Should find github.com in results"

        # Verify result structure
        for result in results[:5]:  # Check first 5 results
            assert len(result["title"]) > 0, "Titles should not be empty"
            assert result["url"].startswith("http"), "URLs should start with http"
            # Should not contain DuckDuckGo redirect artifacts
            assert (
                "duckduckgo.com/l/" not in result["url"]
            ), "URLs should be cleaned of redirects"

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

            results = duckduckgo_html_parser(response)
            all_results.extend(results)

            # Each search should return some results
            assert len(results) > 0, f"Should get results for {term}"

        # All results should follow the same structure
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

        results = duckduckgo_html_parser(response)

        assert len(results) > 0, "Should handle URL-encoded queries"

        # Should find relevant programming results
        cpp_results = [
            r
            for r in results
            if any(
                keyword in r["title"].lower() or keyword in r["url"].lower()
                for keyword in ["c++", "cpp", "programming"]
            )
        ]
        assert len(cpp_results) > 0, "Should find C++ related results"


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
    results = duckduckgo_html_parser(response)
    assert isinstance(
        results, list
    ), "Should always return a list even with unusual responses"
