import concurrent.futures
import urllib.parse
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Sequence
from typing import Set
from typing import TypedDict

import requests
from bs4 import BeautifulSoup
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import AbstractUser
from django.http import HttpRequest

from search.models import BlockList


@dataclass
class Engine:
    name: str
    url: str
    params: Callable[[str], Dict[str, Any]]
    parser: Callable[[requests.Response], List[Any]]
    url_query: bool = False
    headers: Dict[str, str] = field(default_factory=dict)


def duckduckgo_html_parser(response: requests.Response) -> List[Dict[str, str]]:
    soup = BeautifulSoup(response.text, "html.parser")
    results = []
    for res in soup.select("div.result"):
        classes = res.get("class", [])
        # Skip results with ad class
        if (
            "results_links" in classes
            and "results_links_deep" in classes
            and ("result--ad" or "result--ad--small") in classes
        ):
            continue
        a_tag = res.select_one("a.result__a")
        if not a_tag:
            continue
        url = a_tag.attrs.get("href")
        title = a_tag.get_text(strip=True)
        if url and title:
            # Remove redirect url if present
            if url.startswith("/l/?kh=-1&uddg="):
                params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                url = urllib.parse.unquote(params.get("uddg", [""])[0])
            results.append({"title": title, "url": url})
    return results


SEARCH_ENGINES: List[Engine] = [
    Engine(
        name="DuckDuckGo",
        url="https://html.duckduckgo.com/html/",
        url_query=True,
        params=lambda query: {"q": query},
        parser=duckduckgo_html_parser,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"
        },
    )
    # Other engines can be added here as usual
]


def fetch_results(engine: Engine, query: str) -> List[Any]:
    headers: Dict[str, str] = engine.headers
    if engine.url_query:
        base_url = engine.url.rstrip("?&")
        query = urllib.parse.quote_plus(query)
        url = f"{base_url}?q={query}"
        resp: requests.Response = requests.get(url, headers=headers, timeout=8)
    else:
        params: Dict[str, Any] = engine.params(query)
        resp: requests.Response = requests.get(
            engine.url, params=params, headers=headers, timeout=8
        )
    return engine.parser(resp)


def get_domain_from_url(url: str) -> Optional[str]:
    parts = urllib.parse.urlparse(url)
    return parts.netloc.lower()


def filter_blocked(
    results: Sequence[Any],
    block_domains: Sequence[str],
) -> List[Any]:
    if not block_domains:
        return list(results)
    block_domains_set: Set[str] = set(d.lstrip("www.") for d in block_domains)
    filtered: List[Any] = []
    for r in results:
        url: Optional[str] = None
        if isinstance(r, dict):
            url = r.get("url") or r.get("link") or r.get("href")
        elif isinstance(r, str):
            url = r
        if url:
            domain = get_domain_from_url(url)
            domain = (domain or "").lstrip("www.")
        else:
            domain = None
        if domain and any(
            domain == blk or domain.endswith("." + blk) for blk in block_domains_set
        ):
            continue
        filtered.append(r)
    return filtered


def parallel_search(query: str, user: AbstractUser):
    query = query.strip()
    blocked_domains = BlockList.objects.get(user=user)
    block_domains: List[str] = (
        blocked_domains.domains if hasattr(blocked_domains, "domains") else []
    )
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(fetch_results, engine, query) for engine in SEARCH_ENGINES
        ]
        all_results: List[Any] = []
        for fut in concurrent.futures.as_completed(futures):
            res = fut.result()
            all_results.extend(res if isinstance(res, list) else [])
    # Remove duplicates (by URL lowercased)
    seen: Set[str] = set()
    unique_results: List[Any] = []
    for r in all_results:
        if isinstance(r, dict) and "url" in r:
            r_id = (r.get("url") or "").strip().lower()
        else:
            r_id = str(r).strip().lower()
        if r_id and r_id not in seen:
            seen.add(r_id)
            unique_results.append(r)
    filtered_results: List[Any] = filter_blocked(unique_results, block_domains)
    return filtered_results
