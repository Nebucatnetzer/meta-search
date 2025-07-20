from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.shortcuts import render

from search.bangs import resolve_bang


@login_required
def index(request: HttpRequest) -> HttpResponse:
    query = request.GET.get("query", "")
    results = None

    if query:
        # Check for user bang
        url, _ = resolve_bang(request.user, query)
        if url:
            return redirect(url)
        # Otherwise, normal search
        results = [
            {"link": "http://foo", "title": "foo"},
            {"link": "http://bar", "title": "bar"},
        ]

    return render(request, "search/index.html", {"results": results})
