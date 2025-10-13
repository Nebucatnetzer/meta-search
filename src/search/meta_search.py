"""Meta-search engine implementation for parallel searching."""

import asyncio
import concurrent.futures
import logging
import threading
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from typing import Any

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import AnonymousUser

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

    try:
        async with get_browser_page() as page:
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

    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception(
            "Request failed for engine %s with query '%s'", engine.name, query
        )
        return []


# Global event loop for async operations
_event_loop: asyncio.AbstractEventLoop | None = None
_loop_thread: concurrent.futures.ThreadPoolExecutor | None = None
_loop_lock = threading.Lock()


def _get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """Get or create a shared event loop for async operations."""
    global _event_loop, _loop_thread  # noqa: PLW0603  # pylint: disable=global-statement

    with _loop_lock:
        if _event_loop is None or _event_loop.is_closed():
            # Create a new event loop in a dedicated thread
            def setup_loop() -> asyncio.AbstractEventLoop:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                return loop

            _loop_thread = concurrent.futures.ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="async-loop"
            )
            _event_loop = _loop_thread.submit(setup_loop).result()

    return _event_loop


def fetch_results(engine: Engine, query: str) -> list[Any]:
    """Wrap fetch_results_async for synchronous execution using shared event loop."""
    try:
        loop = _get_or_create_event_loop()

        def run_async() -> list[Any]:
            """Run the async function in the shared loop."""
            if not loop.is_running():
                return loop.run_until_complete(fetch_results_async(engine, query))
            # If loop is already running (in thread), submit as task
            future = asyncio.run_coroutine_threadsafe(
                fetch_results_async(engine, query), loop
            )
            return future.result(timeout=30)

        # Execute in the shared loop thread
        if _loop_thread is None:
            msg = "Loop thread not initialized"
            raise RuntimeError(msg)  # noqa: TRY301
        future = _loop_thread.submit(run_async)
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
    """Get list of blocked domains for a user (sync version)."""
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


async def get_blocked_domains_async(
    user: AbstractUser | AnonymousUser,
) -> list[str | None]:
    """Get list of blocked domains for a user (async version)."""
    # AnonymousUser doesn't have blocklists
    if isinstance(user, AnonymousUser):
        return []

    # Run the database query in a thread to avoid sync/async issues
    def _get_blocked_domains_sync() -> list[str | None]:
        return get_blocked_domains(user)

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_blocked_domains_sync)


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


async def parallel_search_async(  # pylint: disable=too-many-locals
    query: str, user: AbstractUser | AnonymousUser
) -> list[Any]:
    """Execute parallel search asynchronously and return filtered results."""
    query = query.strip()
    user_identifier = (
        getattr(user, "username", "anonymous")
        if hasattr(user, "username")
        else "anonymous"
    )

    logger.info(
        "Starting async parallel search for query: '%s' (user: %s)",
        query,
        user_identifier,
    )
    logger.info(
        "Using %d search engines: %s",
        len(SEARCH_ENGINES),
        [engine.name for engine in SEARCH_ENGINES],
    )

    # Execute all searches concurrently using asyncio
    tasks = [fetch_results_async(engine, query) for engine in SEARCH_ENGINES]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_results: list[Any] = []
    engine_results = {}

    for i, result in enumerate(results):
        engine_name = SEARCH_ENGINES[i].name
        if isinstance(result, Exception):
            logger.exception("Engine %s failed", engine_name)
            engine_results[engine_name] = 0
        else:
            engine_results[engine_name] = len(result) if isinstance(result, list) else 0
            all_results.extend(result if isinstance(result, list) else [])

    logger.info("Async parallel search completed. Engine results: %s", engine_results)
    logger.info("Total raw results before filtering: %d", len(all_results))

    # Remove duplicates and filter blocked domains
    blocked_domains = await get_blocked_domains_async(user)
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

    block_domains_list: list[str] = [d for d in blocked_domains if d is not None]
    filtered_results = filter_blocked(unique_results, block_domains_list)

    logger.info("Async parallel search finished with %d results", len(filtered_results))
    return filtered_results


def parallel_search(query: str, user: AbstractUser | AnonymousUser) -> list[Any]:
    """Execute parallel search and return filtered results using async backend."""
    try:
        loop = _get_or_create_event_loop()

        def run_async_search() -> list[Any]:
            """Run the async search in the shared loop."""
            if not loop.is_running():
                return loop.run_until_complete(parallel_search_async(query, user))
            # If loop is already running (in thread), submit as task
            future = asyncio.run_coroutine_threadsafe(
                parallel_search_async(query, user), loop
            )
            return future.result(timeout=60)

        # Execute in the shared loop thread
        if _loop_thread is None:
            msg = "Loop thread not initialized"
            raise RuntimeError(msg)  # noqa: TRY301
        future = _loop_thread.submit(run_async_search)
        return future.result(timeout=60)

    except concurrent.futures.TimeoutError:
        logger.exception("Timeout during parallel search for query '%s'", query)
        return []
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Failed to execute parallel search for query '%s'", query)
        return []
