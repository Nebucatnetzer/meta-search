"""Unit tests for Google HTML parser."""

from search.google_parser import _clean_google_url
from search.google_parser import _extract_results_from_google_html
from search.google_parser import google_html_parser


# Tests for _clean_google_url function


def test_clean_google_redirect_url() -> None:
    """Test cleaning Google redirect URL."""
    redirect_url = "/url?q=https%3A%2F%2Fexample.com%2Fpage&sa=U&ved=..."
    result = _clean_google_url(redirect_url)
    assert result == "https://example.com/page"


def test_clean_google_redirect_url_with_complex_params() -> None:
    """Test cleaning Google redirect URL with complex parameters."""
    redirect_url = "/url?q=https%3A%2F%2Fwww.python.org%2Fdownloads%2F%3Fversion%3D3.12&sa=U&ved=123"
    result = _clean_google_url(redirect_url)
    assert result == "https://www.python.org/downloads/?version=3.12"


def test_clean_direct_url_unchanged() -> None:
    """Test that direct URLs pass through unchanged."""
    direct_url = "https://example.com/page"
    result = _clean_google_url(direct_url)
    assert result == direct_url


def test_clean_relative_url_to_absolute() -> None:
    """Test converting relative URLs to absolute."""
    relative_url = "/search?q=test"
    result = _clean_google_url(relative_url)
    assert result == "https://www.google.com/search?q=test"


def test_clean_empty_url() -> None:
    """Test handling of empty URL."""
    result = _clean_google_url("")
    assert result == ""


def test_clean_url_with_special_characters() -> None:
    """Test URL with special characters that need decoding."""
    redirect_url = "/url?q=https%3A%2F%2Fexample.com%2Fpath%3Fq%3Dtest%26foo%3Dbar"
    result = _clean_google_url(redirect_url)
    assert result == "https://example.com/path?q=test&foo=bar"


# Tests for _extract_results_from_google_html function


def test_modern_google_format_single_result() -> None:
    """Test parsing a single result from modern Google format."""
    html = """
    <html>
        <div data-ved="123">
            <h3>
                <a href="https://example.com">Example Title</a>
            </h3>
        </div>
    </html>
    """
    results = _extract_results_from_google_html(html)
    assert len(results) == 1
    assert results[0]["title"] == "Example Title"
    assert results[0]["url"] == "https://example.com"


def test_modern_google_format_multiple_results() -> None:
    """Test parsing multiple results from modern Google format."""
    html = """
    <html>
        <div data-ved="123">
            <h3>
                <a href="https://example1.com">First Result</a>
            </h3>
        </div>
        <div data-ved="456">
            <h3>
                <a href="https://example2.com">Second Result</a>
            </h3>
        </div>
    </html>
    """
    results = _extract_results_from_google_html(html)
    assert len(results) == 2
    assert results[0]["title"] == "First Result"
    assert results[0]["url"] == "https://example1.com"
    assert results[1]["title"] == "Second Result"
    assert results[1]["url"] == "https://example2.com"


def test_google_format_with_redirect_url() -> None:
    """Test parsing Google format with redirect URL."""
    html = """
    <html>
        <div data-ved="123">
            <h3>
                <a href="/url?q=https%3A%2F%2Fexample.com%2Fpage&sa=U">Test</a>
            </h3>
        </div>
    </html>
    """
    results = _extract_results_from_google_html(html)
    assert len(results) == 1
    assert results[0]["url"] == "https://example.com/page"


def test_google_format_missing_link() -> None:
    """Test Google format div without h3 > a link is skipped."""
    html = """
    <html>
        <div data-ved="123">
            <h3>No link here</h3>
        </div>
        <div data-ved="456">
            <h3>
                <a href="https://example.com">Valid Result</a>
            </h3>
        </div>
    </html>
    """
    results = _extract_results_from_google_html(html)
    assert len(results) == 1
    assert results[0]["title"] == "Valid Result"


def test_fallback_google_format() -> None:
    """Test fallback to generic div parsing when no data-ved found."""
    html = """
    <html>
        <div class="result">
            <h3>
                <a href="https://example.com">Fallback Result</a>
            </h3>
        </div>
    </html>
    """
    results = _extract_results_from_google_html(html)
    assert len(results) == 1
    assert results[0]["title"] == "Fallback Result"
    assert results[0]["url"] == "https://example.com"


def test_selector_based_parsing() -> None:
    """Test parsing using CSS selectors as fallback."""
    html = """
    <html>
        <div class="g">
            <h3>
                <a href="https://example.com">Selector Result</a>
            </h3>
        </div>
    </html>
    """
    results = _extract_results_from_google_html(html)
    assert len(results) == 1
    assert results[0]["title"] == "Selector Result"
    assert results[0]["url"] == "https://example.com"


def test_javascript_links_filtered() -> None:
    """Test that JavaScript links are filtered out."""
    html = """
    <html>
        <div data-ved="123">
            <h3>
                <a href="javascript:void(0)">JS Link</a>
            </h3>
        </div>
        <div data-ved="456">
            <h3>
                <a href="https://example.com">Valid Link</a>
            </h3>
        </div>
    </html>
    """
    results = _extract_results_from_google_html(html)
    assert len(results) == 1
    assert results[0]["url"] == "https://example.com"


def test_empty_html() -> None:
    """Test parsing empty HTML returns empty list."""
    results = _extract_results_from_google_html("<html></html>")
    assert results == []


def test_html_with_no_results() -> None:
    """Test parsing HTML with no result elements."""
    html = """
    <html>
        <div class="other-content">Not a result</div>
    </html>
    """
    results = _extract_results_from_google_html(html)
    assert results == []


def test_duplicate_removal() -> None:
    """Test that duplicate URLs are removed while preserving order."""
    html = """
    <html>
        <div data-ved="123">
            <h3>
                <a href="https://example.com">First Instance</a>
            </h3>
        </div>
        <div data-ved="456">
            <h3>
                <a href="https://example.com">Duplicate</a>
            </h3>
        </div>
        <div data-ved="789">
            <h3>
                <a href="https://other.com">Different URL</a>
            </h3>
        </div>
    </html>
    """
    results = _extract_results_from_google_html(html)
    assert len(results) == 2
    assert results[0]["title"] == "First Instance"
    assert results[0]["url"] == "https://example.com"
    assert results[1]["title"] == "Different URL"
    assert results[1]["url"] == "https://other.com"


def test_whitespace_handling() -> None:
    """Test that whitespace is properly stripped from titles."""
    html = """
    <html>
        <div data-ved="123">
            <h3>
                <a href="https://example.com">
                    Title with   whitespace
                </a>
            </h3>
        </div>
    </html>
    """
    results = _extract_results_from_google_html(html)
    assert len(results) == 1
    assert results[0]["title"] == "Title with   whitespace"


def test_empty_href_and_title_filtered() -> None:
    """Test that results with empty href or title are filtered out."""
    html = """
    <html>
        <div data-ved="123">
            <h3>
                <a href="">Empty href</a>
            </h3>
        </div>
        <div data-ved="456">
            <h3>
                <a href="https://example.com"></a>
            </h3>
        </div>
        <div data-ved="789">
            <h3>
                <a href="https://valid.com">Valid Result</a>
            </h3>
        </div>
    </html>
    """
    results = _extract_results_from_google_html(html)
    assert len(results) == 1
    assert results[0]["url"] == "https://valid.com"


def test_realistic_google_html() -> None:
    """Test parsing realistic Google HTML structure."""
    html = """
    <!DOCTYPE html>
    <html>
    <body>
        <div id="search">
            <div data-ved="2ahUKEwj..." class="g">
                <div class="tF2Cxc">
                    <div class="yuRUbf">
                        <a href="/url?q=https%3A//www.python.org/&sa=U&ved=...">
                            <h3 class="LC20lb MBeuO DKV0Md">
                                Welcome to Python.org
                            </h3>
                        </a>
                    </div>
                    <div class="VwiC3b yXK7lf MUxGbd yDYNvb lyLwlc lEBKkf">
                        <span>The official home of the Python Programming Language</span>
                    </div>
                </div>
            </div>

            <div data-ved="2ahUKEwj..." class="g">
                <div class="tF2Cxc">
                    <div class="yuRUbf">
                        <a href="https://docs.python.org/">
                            <h3 class="LC20lb MBeuO DKV0Md">
                                Python Documentation
                            </h3>
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    results = _extract_results_from_google_html(html)
    assert len(results) == 2

    assert results[0]["title"] == "Welcome to Python.org"
    assert results[0]["url"] == "https://www.python.org/"

    assert results[1]["title"] == "Python Documentation"
    assert results[1]["url"] == "https://docs.python.org/"


def test_unicode_and_special_characters() -> None:
    """Test parsing results with Unicode and special characters."""
    html = """
    <html>
        <div data-ved="123">
            <h3>
                <a href="https://example.com/café">Café Testing — Python & Data Science</a>
            </h3>
        </div>
        <div data-ved="456">
            <h3>
                <a href="https://example.org/测试">测试页面 (Test Page)</a>
            </h3>
        </div>
    </html>
    """
    results = _extract_results_from_google_html(html)
    assert len(results) == 2

    assert results[0]["title"] == "Café Testing — Python & Data Science"
    assert results[0]["url"] == "https://example.com/café"

    assert results[1]["title"] == "测试页面 (Test Page)"
    assert results[1]["url"] == "https://example.org/测试"


def test_malformed_html_handling() -> None:
    """Test parser gracefully handles malformed HTML."""
    html = """
    <html>
        <div data-ved="123">
            <h3>
                <a href="https://example.com">Title with <missing close tag
            </h3>
        </div>
        <div data-ved="456">
            <h3>
                <a href="https://good.com">Good Result</a>
            </h3>
        </div>
    </html>
    """
    results = _extract_results_from_google_html(html)
    # BeautifulSoup should handle malformed HTML gracefully
    assert len(results) >= 1
    # At least the good result should be parsed
    assert any(r["url"] == "https://good.com" for r in results)


# Tests for google_html_parser function


class FakeResponse:
    """Simple fake Response object for testing."""

    def __init__(self, text: str, status_code: int = 200) -> None:
        """Initialize FakeResponse with text content and status code."""
        self.text = text
        self.status_code = status_code


def test_parser_with_fake_response() -> None:
    """Test parser processes response.text correctly."""
    fake_response = FakeResponse(
        """
    <html>
        <div data-ved="123">
            <h3>
                <a href="https://example.com">Test Result</a>
            </h3>
        </div>
    </html>
    """,
        200
    )
    results = google_html_parser(fake_response)  # type: ignore[arg-type]
    assert len(results) == 1
    assert results[0]["title"] == "Test Result"
    assert results[0]["url"] == "https://example.com"


def test_parser_handles_errors_gracefully() -> None:
    """Test parser handles parsing errors gracefully."""
    fake_response = FakeResponse("invalid html", 200)

    # This should not raise an exception
    results = google_html_parser(fake_response)  # type: ignore[arg-type]
    assert isinstance(results, list)
    # May be empty due to no valid results found


def test_parser_returns_list_of_dicts() -> None:
    """Test that parser returns correct data structure."""
    fake_response = FakeResponse(
        """
    <html>
        <div data-ved="123">
            <h3>
                <a href="https://example.com">Title</a>
            </h3>
        </div>
    </html>
    """,
        200
    )
    results = google_html_parser(fake_response)  # type: ignore[arg-type]
    assert isinstance(results, list)
    assert all(isinstance(r, dict) for r in results)
    assert all("title" in r and "url" in r for r in results)


def test_parser_with_different_status_codes() -> None:
    """Test parser with different HTTP status codes."""
    # Should work with various 2xx status codes
    for status_code in [200, 201, 202]:
        fake_response = FakeResponse(
            """
        <html>
            <div data-ved="123">
                <h3>
                    <a href="https://example.com">Test</a>
                </h3>
            </div>
        </html>
        """,
            status_code
        )
        results = google_html_parser(fake_response)  # type: ignore[arg-type]
        assert isinstance(results, list)


def test_large_result_set() -> None:
    """Test parsing a large number of results efficiently."""
    # Generate HTML with many results
    divs = []
    for i in range(50):
        divs.append(f"""
            <div data-ved="result-{i}">
                <h3>
                    <a href="https://example{i}.com">Result {i} Title</a>
                </h3>
            </div>
        """)

    html = f"<html>{''.join(divs)}</html>"
    results = _extract_results_from_google_html(html)

    assert len(results) == 50
    assert results[0]["title"] == "Result 0 Title"
    assert results[0]["url"] == "https://example0.com"
    assert results[49]["title"] == "Result 49 Title"
    assert results[49]["url"] == "https://example49.com"


def test_mixed_google_formats() -> None:
    """Test parsing HTML with mixed Google formats."""
    html = """
    <html>
        <!-- Modern format -->
        <div data-ved="123">
            <h3>
                <a href="https://modern.com">Modern Result</a>
            </h3>
        </div>

        <!-- Fallback format -->
        <div class="result">
            <h3>
                <a href="https://fallback.com">Fallback Result</a>
            </h3>
        </div>

        <!-- Selector-based format -->
        <div class="g">
            <h3>
                <a href="https://selector.com">Selector Result</a>
            </h3>
        </div>
    </html>
    """
    results = _extract_results_from_google_html(html)

    # Should find all results regardless of format
    assert len(results) >= 1
    urls = [r["url"] for r in results]
    assert "https://modern.com" in urls