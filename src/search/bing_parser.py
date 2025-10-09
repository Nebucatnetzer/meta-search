"""Bing search parser for both HTML and JavaScript rendering."""

import logging
import shutil
import urllib.parse
from typing import Any

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


def _extract_results_from_bing_html(html: str) -> list[dict[str, str]]:
    """Extract results from Bing HTML and return a list of title/url dicts."""
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, str]] = []

    # Bing search results are typically in li elements with class "b_algo"
    for result_li in soup.select("li.b_algo"):
        # Look for the main result link (h2 > a)
        link = result_li.select_one("h2 a")
        if not link:
            continue

        href = link.get("href", "")
        title = link.get_text(strip=True)

        if href and title and href.startswith("http"):
            results.append({"title": title, "url": href})

    # Fallback: Look for any h2 a links in the main content
    if not results:
        for link in soup.select("#b_results h2 a"):
            href = link.get("href", "")
            title = link.get_text(strip=True)

            if href and title and href.startswith("http"):
                results.append({"title": title, "url": href})

    # Remove duplicates while preserving order
    seen_urls = set()
    unique_results = []
    for result in results:
        if result["url"] not in seen_urls:
            seen_urls.add(result["url"])
            unique_results.append(result)

    logger.debug("Extracted %d unique results from Bing HTML", len(unique_results))
    return unique_results


def bing_html_parser(response: requests.Response) -> list[dict[str, str]]:
    """Parse a Bing search response and return a list of cleaned results."""
    logger.debug(
        "Parsing Bing response: status=%d, length=%d",
        response.status_code,
        len(response.text),
    )

    try:
        results = _extract_results_from_bing_html(response.text)
        logger.info("Bing HTML parser extracted %d results", len(results))
        return results
    except Exception as e:
        logger.error("Error parsing Bing response: %s", e)
        return []


def bing_js_parser(query: str, **kwargs: Any) -> list[dict[str, str]]:
    """Parse Bing search results using JavaScript rendering with Playwright."""
    logger.info("Fetching Bing results with JS rendering for query: '%s'", query)

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
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/New_York"
            )
            page = context.new_page()

            # Navigate to Bing search
            search_url = f"https://www.bing.com/search?q={urllib.parse.quote_plus(query)}"
            logger.debug("Navigating to: %s", search_url)

            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=15000)

                # Wait a bit for JavaScript to load content
                page.wait_for_timeout(2000)

                # Try multiple selectors for Bing results in order of preference
                selectors_to_try = [
                    'li.b_algo',     # Standard Bing result container
                    '.b_algo',       # Alternative class selector
                    '#b_results h2', # Header links in results
                    'h2 a',          # Any h2 link (fallback)
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
            results = _extract_results_from_bing_html(html_content)

            logger.info("Bing JS parser extracted %d results for query: '%s'", len(results), query)
            return results

    except Exception as e:
        logger.error("Error fetching Bing results with JS for query '%s': %s", query, e)
        return []