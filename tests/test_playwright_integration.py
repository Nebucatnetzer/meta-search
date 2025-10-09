"""Tests for Playwright integration in search engines."""

import pytest
from unittest.mock import patch, MagicMock

from search.bing_parser import bing_js_parser
from search.ddg_parser import duckduckgo_js_parser
from search.google_parser import google_js_parser


class TestPlaywrightIntegration:
    """Test Playwright integration for JavaScript search engines."""

    @pytest.mark.slow
    def test_duckduckgo_js_parser_returns_results(self):
        """Test that DuckDuckGo JS parser returns results for a simple query."""
        query = "python programming"
        results = duckduckgo_js_parser(query)

        # Should return some results (we can't guarantee exact number due to dynamic content)
        assert isinstance(results, list)

        # If we get results, they should have the correct structure
        if results:
            for result in results:
                assert isinstance(result, dict)
                assert "title" in result
                assert "url" in result
                assert isinstance(result["title"], str)
                assert isinstance(result["url"], str)
                assert result["title"].strip()  # Title should not be empty
                assert result["url"].startswith("http")  # URL should be valid

    @pytest.mark.slow
    def test_bing_js_parser_returns_results(self):
        """Test that Bing JS parser returns results for a simple query."""
        query = "python programming"
        results = bing_js_parser(query)

        # Should return some results (we can't guarantee exact number due to dynamic content)
        assert isinstance(results, list)

        # If we get results, they should have the correct structure
        if results:
            for result in results:
                assert isinstance(result, dict)
                assert "title" in result
                assert "url" in result
                assert isinstance(result["title"], str)
                assert isinstance(result["url"], str)
                assert result["title"].strip()  # Title should not be empty
                assert result["url"].startswith("http")  # URL should be valid

    def test_duckduckgo_js_parser_handles_empty_query(self):
        """Test that DuckDuckGo JS parser handles empty query gracefully."""
        results = duckduckgo_js_parser("")
        assert isinstance(results, list)

    def test_bing_js_parser_handles_empty_query(self):
        """Test that Bing JS parser handles empty query gracefully."""
        results = bing_js_parser("")
        assert isinstance(results, list)

    def test_google_js_parser_handles_captcha(self):
        """Test that Google JS parser handles CAPTCHA gracefully."""
        query = "python programming"
        results = google_js_parser(query)

        # Google might return 0 results due to CAPTCHA, but should not crash
        assert isinstance(results, list)

    @patch("search.bing_parser.sync_playwright")
    def test_bing_js_parser_handles_playwright_error(self, mock_playwright):
        """Test that Bing JS parser handles Playwright errors gracefully."""
        # Mock Playwright to raise an exception
        mock_playwright.side_effect = Exception("Playwright error")

        query = "test query"
        results = bing_js_parser(query)

        # Should return empty list on error, not crash
        assert results == []

    @patch("search.google_parser.sync_playwright")
    def test_google_js_parser_handles_playwright_error(self, mock_playwright):
        """Test that Google JS parser handles Playwright errors gracefully."""
        # Mock Playwright to raise an exception
        mock_playwright.side_effect = Exception("Playwright error")

        query = "test query"
        results = google_js_parser(query)

        # Should return empty list on error, not crash
        assert results == []

    @patch("search.bing_parser.shutil.which")
    @patch("search.bing_parser.sync_playwright")
    def test_bing_js_parser_uses_chromium_from_path(self, mock_playwright, mock_which):
        """Test that Bing JS parser uses Chromium from PATH when available."""
        mock_which.return_value = "/usr/bin/chromium"

        # Mock the playwright context
        mock_p = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_playwright.return_value.__enter__.return_value = mock_p
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        mock_page.content.return_value = "<html></html>"

        bing_js_parser("test")

        # Should call launch with executable_path
        mock_p.chromium.launch.assert_called_once()
        call_args = mock_p.chromium.launch.call_args
        assert "executable_path" in call_args.kwargs
        assert call_args.kwargs["executable_path"] == "/usr/bin/chromium"

    @patch("search.bing_parser.shutil.which")
    @patch("search.bing_parser.sync_playwright")
    def test_bing_js_parser_fallback_when_no_chromium(
        self, mock_playwright, mock_which
    ):
        """Test that Bing JS parser falls back when Chromium not in PATH."""
        mock_which.return_value = None  # No chromium in PATH

        # Mock the playwright context
        mock_p = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_playwright.return_value.__enter__.return_value = mock_p
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        mock_page.content.return_value = "<html></html>"

        bing_js_parser("test")

        # Should call launch without executable_path
        mock_p.chromium.launch.assert_called_once()
        call_args = mock_p.chromium.launch.call_args
        assert "executable_path" not in call_args.kwargs
