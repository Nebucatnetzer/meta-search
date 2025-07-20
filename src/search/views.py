from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.http import HttpResponse
from django.shortcuts import redirect
from django.shortcuts import render

from search.bangs import resolve_bang
from search.meta_search import parallel_search


@login_required
def index(request: HttpRequest) -> HttpResponse:
    query = request.GET.get("query", "")
    results = None

    if query:
        # Check for user bang
        url, _ = resolve_bang(
            query=query,
            user=request.user,
        )
        if url:
            return redirect(url)
        # Otherwise, normal search
        results = parallel_search(query=query, user=request.user)

    return render(request, "search/index.html", {"results": results})
