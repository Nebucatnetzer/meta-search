"""DuckDuckGo HTML and JavaScript parser for search results."""

import logging
import shutil
import urllib.parse
from typing import Any

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


def _clean_ddg_url(url: str) -> str:
    """Clean a DuckDuckGo redirect URL and return the actual target URL."""
    if url.startswith(("/l/?uddg=", "//duckduckgo.com/l/?uddg=")):
        clean_url = url
        if url.startswith("//"):
            clean_url = clean_url[2:]
        parsed = urllib.parse.urlparse(
            (
                f"https://{clean_url}"
                if clean_url.startswith("duckduckgo.com")
                else clean_url
            ),
        )
        params = urllib.parse.parse_qs(parsed.query)
        url = urllib.parse.unquote(params.get("uddg", [""])[0])
    return url


def _extract_results_from_ddg_html(html: str) -> list[dict[str, str]]:
    """Extract results from DuckDuckGo HTML and return a list of title/url dicts."""
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, str]] = []

    # Try modern DuckDuckGo format first (article with data-testid)
    for article in soup.select("article[data-testid]"):
        # Find the main link (h2 > a)
        link = article.select_one("h2 a[href]")
        if not link:
            continue

        href = link.get("href", "")
        title = link.get_text(strip=True)

        if isinstance(href, str) and href and title:
            url = _clean_ddg_url(href)
            results.append({"title": title, "url": url})

    # Fallback to old HTML format if no results found
    if not results:
        for result in soup.select("div.result"):
            classes: str | list[str] = result.get("class", [])
            # Skip results with ad class
            if (
                "results_links" in classes
                and "results_links_deep" in classes
                and ("result--ad" in classes or "result--ad--small" in classes)
            ):
                continue
            a_tag = result.select_one("a.result__a")
            if not a_tag:
                continue
            href_attr = a_tag.attrs.get("href")
            title = a_tag.get_text(strip=True)
            if isinstance(href_attr, str) and href_attr and title:
                url = _clean_ddg_url(href_attr)
                results.append({"title": title, "url": url})

    return results


def duckduckgo_html_parser(response: requests.Response) -> list[dict[str, str]]:
    """Parse a DuckDuckGo search response and return a list of cleaned results."""
    return _extract_results_from_ddg_html(response.text)


def duckduckgo_js_parser(query: str, **kwargs: Any) -> list[dict[str, str]]:
    """Parse DuckDuckGo search results using JavaScript rendering with Playwright."""
    logger.info("Fetching DuckDuckGo results with JS rendering for query: '%s'", query)

    try:
        with sync_playwright() as p:
            # Try to find chromium in PATH first (Nix environment)
            chromium_path = shutil.which("chromium")
            if chromium_path:
                logger.debug("Using Chromium from PATH: %s", chromium_path)
                browser = p.chromium.launch(
                    headless=True,
                    executable_path=chromium_path,
                    args=[
                        "--no-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-web-security",
                        "--disable-features=VizDisplayCompositor",
                    ],
                )
            else:
                # Fallback to default playwright browser
                logger.debug("Using default Playwright browser")
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-web-security",
                        "--disable-features=VizDisplayCompositor",
                    ],
                )

            context = browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0",
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/New_York",
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
            )
            page = context.new_page()

            # Navigate to DuckDuckGo search with English language settings
            search_url = (
                f"https://duckduckgo.com/?q={urllib.parse.quote_plus(query)}"
                f"&kl=us-en&lr=lang_en"
            )
            logger.debug("Navigating to: %s", search_url)

            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=15000)

                # Wait a bit for JavaScript to load content
                page.wait_for_timeout(2000)

                # Try multiple selectors for DuckDuckGo results in order of preference
                selectors_to_try = [
                    "article[data-testid]",  # Modern DuckDuckGo result container
                    ".result",  # Classic DuckDuckGo result
                    "h2 a",  # Any h2 link (fallback)
                ]

                results_found = False
                for selector in selectors_to_try:
                    try:
                        page.wait_for_selector(selector, timeout=5000)
                        logger.debug("Found results using selector: %s", selector)
                        results_found = True
                        break
                    except Exception:
                        logger.debug("Selector '%s' not found, trying next", selector)
                        continue

                if not results_found:
                    logger.warning(
                        "No result selectors found, proceeding with content extraction"
                    )

            except Exception as nav_error:
                logger.warning("Navigation or selector wait failed: %s", nav_error)
                # Continue anyway, we might still get some content

            # Get the HTML content
            html_content = page.content()
            browser.close()

            logger.debug("Retrieved HTML content length: %d", len(html_content))
            results = _extract_results_from_ddg_html(html_content)

            logger.info(
                "DuckDuckGo JS parser extracted %d results for query: '%s'",
                len(results),
                query,
            )
            return results

    except Exception as e:
        logger.error(
            "Error fetching DuckDuckGo results with JS for query '%s': %s", query, e
        )
        return []
