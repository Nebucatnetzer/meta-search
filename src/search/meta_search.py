"""Meta-search engine implementation for parallel searching."""

import asyncio
import concurrent.futures
import logging
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING
from typing import Any

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import AnonymousUser

from search.browser_manager import get_browser_page
from search.constants import DEFAULT_BROWSER_HEADERS
from search.ddg_parser import duckduckgo_html_parser
from search.models import BlockList

if TYPE_CHECKING:
    from playwright.async_api import Page

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
        url="https://html.duckduckgo.com/html",  # Correct URL without trailing slash
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

        return results  # noqa: TRY300

    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception(
            "Request failed for engine %s with query '%s'", engine.name, query
        )
        return []
    finally:
        if page:
            try:
                # Only close the page, not the browser - browser is reused
                await page.close()
            except Exception:  # pylint: disable=broad-exception-caught
                logger.exception("Error closing page")


def fetch_results(engine: Engine, query: str) -> list[Any]:
    """Wrap fetch_results_async for synchronous execution."""

    def run_async_in_thread() -> list[Any]:
        """Run async code in a dedicated thread with optimized browser management."""
        # Create event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(fetch_results_async(engine, query))
        finally:
            loop.close()

    try:
        # Use ThreadPoolExecutor to run async code in a separate thread
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_async_in_thread)
            return future.result(timeout=30)
    except concurrent.futures.TimeoutError:
        logger.exception(
            "Timeout fetching results for engine %s with query '%s'", engine.name, query
        )
        return []
    except Exception:  # pylint: disable=broad-exception-caught
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
    # AnonymousUser doesn't have blocklists
    if isinstance(user, AnonymousUser):
        return []

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
            except Exception:  # pylint: disable=broad-exception-caught
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
