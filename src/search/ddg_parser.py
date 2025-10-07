import urllib.parse

import requests
from bs4 import BeautifulSoup


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
