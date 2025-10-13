import urllib.parse

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.http import HttpResponse
from django.shortcuts import redirect
from django.shortcuts import render

from search.bangs import resolve_bang


@login_required
def index(request: HttpRequest) -> HttpResponse:
    query = request.GET.get("query", "")

    if query:
        # Check for user bang
        url, query_without_bang = resolve_bang(
            query=query,
            user=request.user,
        )
        if url:
            return redirect(url)

        # If no bang found, redirect to default search engine (DuckDuckGo)
        query_enc = urllib.parse.quote_plus(query)
        url = f"http://gwyn.2li.local:8080/search?q={query_enc}"
        return redirect(url)

    return render(request, "search/index.html", {"results": None})
