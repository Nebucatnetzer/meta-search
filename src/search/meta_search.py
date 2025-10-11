"""Meta-search engine implementation for parallel searching."""

import asyncio
import concurrent.futures
import logging
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from typing import Any

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import AnonymousUser
from playwright.async_api import Page

from search.browser_manager import get_browser_page
from search.constants import DEFAULT_BROWSER_HEADERS
from search.ddg_parser import duckduckgo_html_parser
from search.models import BlockList

logger = logging.getLogger(__name__)


@dataclass
class Engine:
    """Configuration for a search engine."""

    name: str
    url: str
    params: Callable[[str], dict[str, Any]]
    parser: Callable[[str], list[Any]]  # Now takes HTML string instead of Response
    url_query: bool = False
    headers: dict[str, str] = field(default_factory=dict)


SEARCH_ENGINES: list[Engine] = [
    Engine(
        name="DuckDuckGo",
        url="https://duckduckgo.com/html/",
        url_query=False,  # Use params instead of URL query
        params=lambda query: {"q": query},
        parser=duckduckgo_html_parser,
        headers=DEFAULT_BROWSER_HEADERS,
    ),
    # Other engines can be added here as usual
]


async def fetch_results_async(engine: Engine, query: str) -> list[Any]:
    """Fetch search results from a single engine using Playwright."""
    logger.info("Fetching results from %s for query: '%s'", engine.name, query)

    page: Page | None = None
    try:
        page = await get_browser_page()

        # Set custom headers if specified
        if engine.headers:
            await page.set_extra_http_headers(engine.headers)

        if engine.url_query:
            base_url = engine.url.rstrip("?&")
            query_enc = urllib.parse.quote_plus(query)
            url = f"{base_url}?q={query_enc}"
            logger.debug("Making URL query request to %s: %s", engine.name, url)

            response = await page.goto(url, timeout=8000, wait_until="networkidle")
        else:
            params: dict[str, Any] = engine.params(query)
            # Convert params to URL query string
            query_string = urllib.parse.urlencode(params)
            url = f"{engine.url}?{query_string}"

            logger.debug(
                "Making params request to %s: %s with params: %s",
                engine.name,
                url,
                params,
            )
            response = await page.goto(url, timeout=8000, wait_until="networkidle")

        if not response:
            logger.error("No response received from %s", engine.name)
            return []

        html_content = await page.content()

        logger.debug(
            "Response from %s: status=%d, length=%d",
            engine.name,
            response.status,
            len(html_content),
        )

        results = engine.parser(html_content)
        logger.info(
            "Engine %s returned %d results for query: '%s'",
            engine.name,
            len(results),
            query,
        )

        if len(results) == 0:
            logger.warning(
                "Engine %s returned 0 results for query: '%s' (status: %d)",
                engine.name,
                query,
                response.status,
            )

        return results

    except Exception:  # noqa: BLE001
        logger.exception(
            "Request failed for engine %s with query '%s'", engine.name, query
        )
        return []
    finally:
        if page:
            await page.close()


def fetch_results(engine: Engine, query: str) -> list[Any]:
    """Synchronous wrapper for fetch_results_async."""
    try:
        # Try to use existing event loop, otherwise create a new one
        try:
            # Check if we're already in an async context
            loop = asyncio.get_running_loop()
            # If we get here, we're in an async context - this shouldn't happen
            # in our sync wrapper, but handle it gracefully
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, fetch_results_async(engine, query)
                )
                return future.result()
        except RuntimeError:
            # No running loop, so we can safely use asyncio.run()
            return asyncio.run(fetch_results_async(engine, query))
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to fetch results for engine %s with query '%s'", engine.name, query
        )
        return []


def filter_blocked(
    results: list[Any],
    blocked_domains: list[str],
) -> list[Any]:
    """Filter out results from blocked domains."""
    if not blocked_domains:
        return list(results)
    filtered: list[Any] = []
    for result in results:
        url: str | None = None
        if isinstance(result, dict):
            url = result.get("url") or result.get("link") or result.get("href")
        elif isinstance(result, str):
            url = result
        if url and any(domain in url for domain in blocked_domains):
            continue
        filtered.append(result)
    return filtered


def get_blocked_domains(user: AbstractUser | AnonymousUser) -> list[str | None]:
    """Get list of blocked domains for a user."""
    blocklists = BlockList.objects.filter(user=user)
    blocked_domains: set[str] = set()
    for blocklist in blocklists:
        blocked_domains.update(
            blocklist.blocked_domains.values_list(
                "domain",
                flat=True,
            ),
        )
    return list(blocked_domains)


def filter_results(
    all_results: list[Any],
    blocked_domains: list[str | None],
) -> list[Any]:
    """Remove duplicates and filter blocked domains from results."""
    seen: set[str] = set()
    unique_results: list[Any] = []
    for r in all_results:
        if isinstance(r, dict) and "url" in r:
            r_id = (r.get("url") or "").strip().lower()
        else:
            r_id = str(r).strip().lower()
        if r_id and r_id not in seen:
            seen.add(r_id)
            unique_results.append(r)
    # block domains that may be None
    block_domains_list: list[str] = [d for d in blocked_domains if d is not None]
    return filter_blocked(unique_results, block_domains_list)


def parallel_search(query: str, user: AbstractUser | AnonymousUser) -> list[Any]:
    """Execute parallel search and return filtered results."""
    query = query.strip()
    user_identifier = (
        getattr(user, "username", "anonymous")
        if hasattr(user, "username")
        else "anonymous"
    )

    logger.info(
        "Starting parallel search for query: '%s' (user: %s)", query, user_identifier
    )
    logger.info(
        "Using %d search engines: %s",
        len(SEARCH_ENGINES),
        [engine.name for engine in SEARCH_ENGINES],
    )

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(fetch_results, engine, query) for engine in SEARCH_ENGINES
        ]
        all_results: list[Any] = []
        engine_results = {}

        for i, fut in enumerate(concurrent.futures.as_completed(futures)):
            try:
                res = fut.result()
                engine_name = SEARCH_ENGINES[i].name
                engine_results[engine_name] = len(res) if isinstance(res, list) else 0
                all_results.extend(res if isinstance(res, list) else [])
            except Exception:  # noqa: BLE001
                engine_name = (
                    SEARCH_ENGINES[i].name if i < len(SEARCH_ENGINES) else "unknown"
                )
                logger.exception("Engine %s failed", engine_name)

    logger.info("Parallel search completed. Engine results: %s", engine_results)
    logger.info("Total raw results before filtering: %d", len(all_results))

    # Remove duplicates (by URL lowercased)
    blocked_domains = get_blocked_domains(user)
    logger.debug(
        "User %s has %d blocked domains", user_identifier, len(blocked_domains)
    )

    filtered_results = filter_results(
        all_results=all_results,
        blocked_domains=blocked_domains,
    )

    logger.info(
        "Final results after filtering for query '%s': %d results (user: %s)",
        query,
        len(filtered_results),
        user_identifier,
    )

    return filtered_results
