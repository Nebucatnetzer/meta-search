# Tests

This directory contains unit tests for the meta-search project.

## Running Tests

To run all tests:
```bash
pytest
```

To run tests with coverage:
```bash
pytest --cov=search --cov-report=term-missing
```

To run tests in parallel:
```bash
pytest -n auto
```

To run a specific test file:
```bash
pytest tests/test_ddg_parser.py
```

To run a specific test class:
```bash
pytest tests/test_ddg_parser.py::TestCleanDdgUrl
```

To run a specific test:
```bash
pytest tests/test_ddg_parser.py::TestCleanDdgUrl::test_clean_redirect_url_with_slash_prefix
```

## Test Structure

- `test_ddg_parser.py` - Tests for the DuckDuckGo HTML parser functions
  - `TestCleanDdgUrl` - Tests for URL cleaning and redirect handling
  - `TestExtractResultsFromDdgHtml` - Tests for HTML parsing (both modern and old formats)
  - `TestDuckduckgoHtmlParser` - Integration tests for the main parser function

## Coverage

All parser functions have comprehensive test coverage including:
- Modern DuckDuckGo HTML format parsing
- Legacy HTML format parsing with backward compatibility
- URL redirect cleaning
- Ad filtering
- Edge cases (empty results, missing links, malformed HTML)
