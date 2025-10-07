"""Unit tests for DuckDuckGo HTML parser."""

from search.ddg_parser import _clean_ddg_url
from search.ddg_parser import _extract_results_from_ddg_html
from search.ddg_parser import duckduckgo_html_parser


# Tests for _clean_ddg_url function


def test_clean_redirect_url_with_slash_prefix() -> None:
    """Test cleaning URL with /l/?uddg= prefix."""
    redirect_url = "/l/?uddg=https%3A%2F%2Fexample.com%2Fpage"
    result = _clean_ddg_url(redirect_url)
    assert result == "https://example.com/page"


def test_clean_redirect_url_with_double_slash_prefix() -> None:
    """Test cleaning URL with //duckduckgo.com/l/?uddg= prefix."""
    redirect_url = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Ftest"
    result = _clean_ddg_url(redirect_url)
    assert result == "https://example.com/test"


def test_non_redirect_url_unchanged() -> None:
    """Test that non-redirect URLs pass through unchanged."""
    direct_url = "https://example.com/page"
    result = _clean_ddg_url(direct_url)
    assert result == direct_url


def test_empty_url() -> None:
    """Test handling of empty URL."""
    result = _clean_ddg_url("")
    assert result == ""


def test_url_with_special_characters() -> None:
    """Test URL with special characters that need decoding."""
    redirect_url = "/l/?uddg=https%3A%2F%2Fexample.com%2Fpath%3Fq%3Dtest%26foo%3Dbar"
    result = _clean_ddg_url(redirect_url)
    assert result == "https://example.com/path?q=test&foo=bar"


# Tests for _extract_results_from_ddg_html function


def test_modern_format_single_result() -> None:
    """Test parsing a single result from modern DuckDuckGo format."""
    html = """
    <html>
        <article data-testid="result">
            <h2>
                <a href="https://example.com">Example Title</a>
            </h2>
        </article>
    </html>
    """
    results = _extract_results_from_ddg_html(html)
    assert len(results) == 1
    assert results[0]["title"] == "Example Title"
    assert results[0]["url"] == "https://example.com"


def test_modern_format_multiple_results() -> None:
    """Test parsing multiple results from modern DuckDuckGo format."""
    html = """
    <html>
        <article data-testid="result-1">
            <h2>
                <a href="https://example1.com">First Result</a>
            </h2>
        </article>
        <article data-testid="result-2">
            <h2>
                <a href="https://example2.com">Second Result</a>
            </h2>
        </article>
    </html>
    """
    results = _extract_results_from_ddg_html(html)
    assert len(results) == 2
    assert results[0]["title"] == "First Result"
    assert results[0]["url"] == "https://example1.com"
    assert results[1]["title"] == "Second Result"
    assert results[1]["url"] == "https://example2.com"


def test_modern_format_with_redirect_url() -> None:
    """Test parsing modern format with DuckDuckGo redirect URL."""
    html = """
    <html>
        <article data-testid="result">
            <h2>
                <a href="/l/?uddg=https%3A%2F%2Fexample.com%2Fpage">Test</a>
            </h2>
        </article>
    </html>
    """
    results = _extract_results_from_ddg_html(html)
    assert len(results) == 1
    assert results[0]["url"] == "https://example.com/page"


def test_modern_format_missing_link() -> None:
    """Test modern format article without h2 > a link is skipped."""
    html = """
    <html>
        <article data-testid="result">
            <h2>No link here</h2>
        </article>
        <article data-testid="result-2">
            <h2>
                <a href="https://example.com">Valid Result</a>
            </h2>
        </article>
    </html>
    """
    results = _extract_results_from_ddg_html(html)
    assert len(results) == 1
    assert results[0]["title"] == "Valid Result"


def test_old_html_format_single_result() -> None:
    """Test parsing a single result from old HTML format."""
    html = """
    <html>
        <div class="result results_links results_links_deep">
            <a class="result__a" href="https://example.com">Old Format Title</a>
        </div>
    </html>
    """
    results = _extract_results_from_ddg_html(html)
    assert len(results) == 1
    assert results[0]["title"] == "Old Format Title"
    assert results[0]["url"] == "https://example.com"


def test_old_html_format_multiple_results() -> None:
    """Test parsing multiple results from old HTML format."""
    html = """
    <html>
        <div class="result results_links results_links_deep">
            <a class="result__a" href="https://example1.com">First</a>
        </div>
        <div class="result results_links results_links_deep">
            <a class="result__a" href="https://example2.com">Second</a>
        </div>
    </html>
    """
    results = _extract_results_from_ddg_html(html)
    assert len(results) == 2
    assert results[0]["title"] == "First"
    assert results[1]["title"] == "Second"


def test_old_html_format_skip_ads() -> None:
    """Test that ad results are skipped in old HTML format."""
    html = """
    <html>
        <div class="result results_links results_links_deep result--ad">
            <a class="result__a" href="https://ad.com">Ad Result</a>
        </div>
        <div class="result results_links results_links_deep">
            <a class="result__a" href="https://example.com">Real Result</a>
        </div>
    </html>
    """
    results = _extract_results_from_ddg_html(html)
    assert len(results) == 1
    assert results[0]["url"] == "https://example.com"


def test_old_html_format_skip_small_ads() -> None:
    """Test that small ad results are skipped in old HTML format."""
    html = """
    <html>
        <div class="result results_links results_links_deep result--ad--small">
            <a class="result__a" href="https://ad.com">Small Ad</a>
        </div>
        <div class="result results_links results_links_deep">
            <a class="result__a" href="https://example.com">Real Result</a>
        </div>
    </html>
    """
    results = _extract_results_from_ddg_html(html)
    assert len(results) == 1
    assert results[0]["url"] == "https://example.com"


def test_old_html_format_missing_link() -> None:
    """Test old format result without link is skipped."""
    html = """
    <html>
        <div class="result results_links results_links_deep">
            <span>No link</span>
        </div>
        <div class="result results_links results_links_deep">
            <a class="result__a" href="https://example.com">Valid</a>
        </div>
    </html>
    """
    results = _extract_results_from_ddg_html(html)
    assert len(results) == 1
    assert results[0]["title"] == "Valid"


def test_empty_html() -> None:
    """Test parsing empty HTML returns empty list."""
    results = _extract_results_from_ddg_html("<html></html>")
    assert results == []


def test_html_with_no_results() -> None:
    """Test parsing HTML with no result elements."""
    html = """
    <html>
        <div class="other-content">Not a result</div>
    </html>
    """
    results = _extract_results_from_ddg_html(html)
    assert results == []


def test_modern_format_with_whitespace_in_title() -> None:
    """Test that whitespace is properly stripped from titles."""
    html = """
    <html>
        <article data-testid="result">
            <h2>
                <a href="https://example.com">
                    Title with   whitespace
                </a>
            </h2>
        </article>
    </html>
    """
    results = _extract_results_from_ddg_html(html)
    assert len(results) == 1
    assert results[0]["title"] == "Title with   whitespace"


# Tests for duckduckgo_html_parser function


class FakeResponse:
    """Simple fake Response object for testing."""

    def __init__(self, text: str) -> None:
        self.text = text


def test_parser_with_fake_response() -> None:
    """Test parser processes response.text correctly."""
    fake_response = FakeResponse(
        """
    <html>
        <article data-testid="result">
            <h2>
                <a href="https://example.com">Test Result</a>
            </h2>
        </article>
    </html>
    """
    )
    results = duckduckgo_html_parser(fake_response)  # type: ignore[arg-type]
    assert len(results) == 1
    assert results[0]["title"] == "Test Result"
    assert results[0]["url"] == "https://example.com"


def test_parser_returns_list_of_dicts() -> None:
    """Test that parser returns correct data structure."""
    fake_response = FakeResponse(
        """
    <html>
        <article data-testid="result">
            <h2>
                <a href="https://example.com">Title</a>
            </h2>
        </article>
    </html>
    """
    )
    results = duckduckgo_html_parser(fake_response)  # type: ignore[arg-type]
    assert isinstance(results, list)
    assert all(isinstance(r, dict) for r in results)
    assert all("title" in r and "url" in r for r in results)
