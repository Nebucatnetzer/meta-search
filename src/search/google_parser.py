"""Google HTML parser for search results."""

import logging
import shutil
import urllib.parse
from typing import Any

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


def _clean_google_url(url: str) -> str:
    """Clean a Google redirect URL and return the actual target URL."""
    if not url:
        return url

    # Handle Google redirect URLs
    if url.startswith("/url?q="):
        # Extract the actual URL from Google's redirect
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        actual_url = params.get("q", [""])[0]
        return urllib.parse.unquote(actual_url)

    # Handle relative URLs by making them absolute
    if url.startswith("/"):
        return f"https://www.google.com{url}"

    return url


def _extract_results_from_google_html(html: str) -> list[dict[str, str]]:
    """Extract results from Google HTML and return a list of title/url dicts."""
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, str]] = []

    # Google search results are typically in divs with specific data attributes
    # Try modern Google format first (div[data-ved] or div with h3)
    for result_div in soup.select("div[data-ved]"):
        # Look for any link with h3 inside the result div (can be nested deeply)
        link = result_div.select_one("a h3") or result_div.select_one("h3 a")
        if link:
            # If we found a h3 inside an a, get the parent a element
            if link.name == "h3":
                a_element = link.parent
            else:
                # If we found h3 > a, use the a element
                a_element = link

            if a_element and a_element.name == "a":
                href = a_element.get("href", "")
                title = (
                    link.get_text(strip=True)
                    if link.name == "h3"
                    else a_element.get_text(strip=True)
                )

                if href and title:
                    url = _clean_google_url(href)
                    if url and not url.startswith("javascript:"):
                        results.append({"title": title, "url": url})

    # Fallback: Look for any div containing h3 > a links (older Google format)
    if not results:
        for result_div in soup.select("div"):
            link = result_div.select_one("h3 a")
            if not link:
                continue

            href = link.get("href", "")
            title = link.get_text(strip=True)

            if href and title:
                url = _clean_google_url(href)
                if url and not url.startswith("javascript:"):
                    results.append({"title": title, "url": url})

    # Alternative approach: Look for links in result containers
    if not results:
        # Try searching for links in common Google result selectors
        selectors = [
            ".g h3 a",  # Standard Google result
            ".rc h3 a",  # Result container
            "[data-ved] h3 a",  # Data attribute approach
            ".r h3 a",  # Classic selector
        ]

        for selector in selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get("href", "")
                title = link.get_text(strip=True)

                if href and title:
                    url = _clean_google_url(href)
                    if url and not url.startswith("javascript:"):
                        results.append({"title": title, "url": url})

            # If we found results with this selector, stop trying others
            if results:
                break

    # Remove duplicates while preserving order
    seen_urls = set()
    unique_results = []
    for result in results:
        if result["url"] not in seen_urls:
            seen_urls.add(result["url"])
            unique_results.append(result)

    logger.debug("Extracted %d unique results from Google HTML", len(unique_results))
    return unique_results


def google_html_parser(response: requests.Response) -> list[dict[str, str]]:
    """Parse a Google search response and return a list of cleaned results."""
    logger.debug(
        "Parsing Google response: status=%d, length=%d",
        response.status_code,
        len(response.text),
    )

    try:
        results = _extract_results_from_google_html(response.text)
        logger.info("Google parser extracted %d results", len(results))
        return results
    except Exception as e:
        logger.error("Error parsing Google response: %s", e)
        return []


def google_js_parser(query: str, **kwargs: Any) -> list[dict[str, str]]:
    """Parse Google search results using JavaScript rendering with Playwright."""
    logger.info("Fetching Google results with JS rendering for query: '%s'", query)

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
                        "--disable-features=VizDisplayCompositor"
                    ]
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
                        "--disable-features=VizDisplayCompositor"
                    ]
                )

            context = browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/New_York"
            )
            page = context.new_page()

            # Navigate to Google search
            search_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
            logger.debug("Navigating to: %s", search_url)

            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=15000)

                # Wait a bit for JavaScript to load content
                page.wait_for_timeout(2000)

                # Try multiple selectors for Google results in order of preference
                selectors_to_try = [
                    '[data-ved]',  # Modern Google results
                    '.g',          # Classic Google result container
                    '.rc',         # Result container
                    'h3',          # Any h3 (fallback)
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
                    logger.warning("No result selectors found, proceeding with content extraction")

            except Exception as nav_error:
                logger.warning("Navigation or selector wait failed: %s", nav_error)
                # Continue anyway, we might still get some content

            # Get the HTML content
            html_content = page.content()
            browser.close()

            logger.debug("Retrieved HTML content length: %d", len(html_content))
            results = _extract_results_from_google_html(html_content)

            logger.info("Google JS parser extracted %d results for query: '%s'", len(results), query)
            return results

    except Exception as e:
        logger.error("Error fetching Google results with JS for query '%s': %s", query, e)
        return []
