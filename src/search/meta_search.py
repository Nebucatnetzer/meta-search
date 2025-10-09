"""Meta-search engine implementation for parallel searching."""

import concurrent.futures
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from typing import Any

import requests
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import AnonymousUser

from search.ddg_parser import duckduckgo_html_parser
from search.models import BlockList


@dataclass
class Engine:
    """Configuration for a search engine."""

    name: str
    url: str
    params: Callable[[str], dict[str, Any]]
    parser: Callable[[requests.Response], list[Any]]
    url_query: bool = False
    headers: dict[str, str] = field(default_factory=dict)


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
    # Other engines can be added here as usual
]


def fetch_results(engine: Engine, query: str) -> list[Any]:
    """Fetch search results from a single engine."""
    headers: dict[str, str] = engine.headers
    resp: requests.Response
    if engine.url_query:
        base_url = engine.url.rstrip("?&")
        query_enc = urllib.parse.quote_plus(query)
        url = f"{base_url}?q={query_enc}"
        resp = requests.get(url, headers=headers, timeout=8)
    else:
        params: dict[str, Any] = engine.params(query)
        resp = requests.get(engine.url, params=params, headers=headers, timeout=8)
    return engine.parser(resp)


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
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(fetch_results, engine, query) for engine in SEARCH_ENGINES
        ]
        all_results: list[Any] = []
        for fut in concurrent.futures.as_completed(futures):
            res = fut.result()
            all_results.extend(res if isinstance(res, list) else [])

    # Remove duplicates (by URL lowercased)
    blocked_domains = get_blocked_domains(user)
    return filter_results(
        all_results=all_results,
        blocked_domains=blocked_domains,
    )
