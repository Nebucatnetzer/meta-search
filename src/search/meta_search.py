"""Meta-search engine implementation for parallel searching."""

import concurrent.futures
import logging
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from typing import Any

import requests
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import AnonymousUser

from search.ddg_parser import duckduckgo_html_parser
from search.google_parser import google_html_parser, google_js_parser
from search.bing_parser import bing_html_parser, bing_js_parser
from search.models import BlockList

logger = logging.getLogger(__name__)


@dataclass
class Engine:
    """Configuration for a search engine."""

    name: str
    url: str
    params: Callable[[str], dict[str, Any]]
    parser: Callable[[requests.Response], list[Any]]
    url_query: bool = False
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class JSEngine:
    """Configuration for a JavaScript-enabled search engine."""

    name: str
    js_parser: Callable[[str], list[Any]]


SEARCH_ENGINES: list[Engine] = [
    Engine(
        name="DuckDuckGo",
        url="https://duckduckgo.com/html/",
        url_query=False,  # Use params instead of URL query
        params=lambda query: {"q": query},
        parser=duckduckgo_html_parser,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        },
    ),
    Engine(
        name="Bing",
        url="https://www.bing.com/search",
        url_query=False,  # Use params instead of URL query
        params=lambda query: {"q": query},
        parser=bing_html_parser,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        },
    ),
]

JS_SEARCH_ENGINES: list[JSEngine] = [
    JSEngine(
        name="Bing (JS)",
        js_parser=bing_js_parser,
    ),
    JSEngine(
        name="Google (JS)",
        js_parser=google_js_parser,
    ),
]


def fetch_results(engine: Engine, query: str) -> list[Any]:
    """Fetch search results from a single engine."""
    logger.info("Fetching results from %s for query: '%s'", engine.name, query)

    headers: dict[str, str] = engine.headers
    resp: requests.Response

    try:
        if engine.url_query:
            base_url = engine.url.rstrip("?&")
            query_enc = urllib.parse.quote_plus(query)
            url = f"{base_url}?q={query_enc}"
            logger.debug("Making URL query request to %s: %s", engine.name, url)
            resp = requests.get(url, headers=headers, timeout=8)
        else:
            params: dict[str, Any] = engine.params(query)
            logger.debug("Making params request to %s: %s with params: %s",
                        engine.name, engine.url, params)
            resp = requests.get(engine.url, params=params, headers=headers, timeout=8)

        logger.debug("Response from %s: status=%d, length=%d",
                    engine.name, getattr(resp, 'status_code', 0), len(resp.text))

        results = engine.parser(resp)
        logger.info("Engine %s returned %d results for query: '%s'",
                   engine.name, len(results), query)

        if len(results) == 0:
            logger.warning("Engine %s returned 0 results for query: '%s' (status: %d)",
                          engine.name, query, getattr(resp, 'status_code', 0))

        return results

    except requests.exceptions.RequestException as e:
        logger.error("Request failed for engine %s with query '%s': %s",
                    engine.name, query, e)
        return []
    except Exception as e:
        logger.error("Unexpected error fetching from engine %s with query '%s': %s",
                    engine.name, query, e)
        return []


def fetch_js_results(js_engine: JSEngine, query: str) -> list[Any]:
    """Fetch search results from a JavaScript-enabled engine."""
    logger.info("Fetching JS results from %s for query: '%s'", js_engine.name, query)

    try:
        results = js_engine.js_parser(query)
        logger.info("JS Engine %s returned %d results for query: '%s'",
                   js_engine.name, len(results), query)

        if len(results) == 0:
            logger.warning("JS Engine %s returned 0 results for query: '%s'",
                          js_engine.name, query)

        return results

    except Exception as e:
        logger.error("Unexpected error fetching from JS engine %s with query '%s': %s",
                    js_engine.name, query, e)
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
    # AnonymousUser doesn't have blocked domains
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
    user_identifier = getattr(user, 'username', 'anonymous') if hasattr(user, 'username') else 'anonymous'

    all_engines = [engine.name for engine in SEARCH_ENGINES] + [js_engine.name for js_engine in JS_SEARCH_ENGINES]
    logger.info("Starting parallel search for query: '%s' (user: %s)", query, user_identifier)
    logger.info("Using %d search engines: %s", len(all_engines), all_engines)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Submit regular engines
        futures = [
            executor.submit(fetch_results, engine, query) for engine in SEARCH_ENGINES
        ]
        # Submit JavaScript engines
        js_futures = [
            executor.submit(fetch_js_results, js_engine, query) for js_engine in JS_SEARCH_ENGINES
        ]

        all_results: list[Any] = []
        engine_results = {}

        # Process regular engine results
        for i, fut in enumerate(concurrent.futures.as_completed(futures)):
            try:
                res = fut.result()
                engine_name = SEARCH_ENGINES[i].name
                engine_results[engine_name] = len(res) if isinstance(res, list) else 0
                all_results.extend(res if isinstance(res, list) else [])
            except Exception as e:
                engine_name = SEARCH_ENGINES[i].name if i < len(SEARCH_ENGINES) else "unknown"
                logger.error("Engine %s failed: %s", engine_name, e)

        # Process JavaScript engine results
        for i, fut in enumerate(concurrent.futures.as_completed(js_futures)):
            try:
                res = fut.result()
                js_engine_name = JS_SEARCH_ENGINES[i].name
                engine_results[js_engine_name] = len(res) if isinstance(res, list) else 0
                all_results.extend(res if isinstance(res, list) else [])
            except Exception as e:
                js_engine_name = JS_SEARCH_ENGINES[i].name if i < len(JS_SEARCH_ENGINES) else "unknown"
                logger.error("JS Engine %s failed: %s", js_engine_name, e)

    logger.info("Parallel search completed. Engine results: %s", engine_results)
    logger.info("Total raw results before filtering: %d", len(all_results))

    # Remove duplicates (by URL lowercased)
    blocked_domains = get_blocked_domains(user)
    logger.debug("User %s has %d blocked domains", user_identifier, len(blocked_domains))

    filtered_results = filter_results(
        all_results=all_results,
        blocked_domains=blocked_domains,
    )

    logger.info("Final results after filtering for query '%s': %d results (user: %s)",
               query, len(filtered_results), user_identifier)

    return filtered_results
