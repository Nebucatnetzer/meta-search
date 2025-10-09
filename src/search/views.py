"""Views for the search application."""

import logging
import urllib.parse

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.http import HttpResponse
from django.shortcuts import redirect
from django.shortcuts import render

from search.bangs import resolve_bang
from search.meta_search import parallel_search

logger = logging.getLogger(__name__)


@login_required
def index(request: HttpRequest) -> HttpResponse:
    """Handle search requests and display results."""
    query = request.GET.get("query", "")
    results = None
    user_identifier = getattr(request.user, 'username', 'anonymous')

    if query:
        logger.info("Search request received: query='%s', user=%s, IP=%s",
                   query, user_identifier, request.META.get('REMOTE_ADDR', 'unknown'))

        # Check for user bang
        url, query_without_bang = resolve_bang(
            query=query,
            user=request.user,
        )

        if url:
            logger.info("Bang resolved for query '%s' (user: %s) -> redirecting to: %s",
                       query, user_identifier, url)
            return redirect(url)

        # Otherwise, normal search
        search_query = query_without_bang if query_without_bang else query

        if query_without_bang:
            logger.info("Bang query '%s' resolved to search query '%s' (user: %s)",
                       query, query_without_bang, user_identifier)

        logger.info("Executing meta-search for query: '%s' (user: %s)",
                   search_query, user_identifier)

        results = parallel_search(query=search_query, user=request.user)

        if not results:
            # If for some reason the search engine doesn't return anything we
            # redirect the search query to DuckDuckGo (default search engine).
            query_enc = urllib.parse.quote_plus(query)
            fallback_url = f"https://duckduckgo.com?q={query_enc}"

            logger.warning("No results found for query '%s' (user: %s) - "
                          "redirecting to default search engine: %s",
                          query, user_identifier, fallback_url)

            return redirect(fallback_url)
        else:
            logger.info("Successfully found %d results for query '%s' (user: %s)",
                       len(results), query, user_identifier)

    else:
        logger.debug("Empty search request (user: %s, IP: %s)",
                    user_identifier, request.META.get('REMOTE_ADDR', 'unknown'))

    return render(request, "search/index.html", {"results": results})
