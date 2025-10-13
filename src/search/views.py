"""Views for the search application."""

import urllib.parse
from typing import TYPE_CHECKING
from typing import cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.http import HttpResponse
from django.shortcuts import redirect
from django.shortcuts import render

from search.bangs import resolve_bang

if TYPE_CHECKING:
    from search.models import SearchUser


@login_required
def index(request: HttpRequest) -> HttpResponse:
    """Handle search requests and display results."""
    query = request.GET.get("query", "")

    if query:
        # Check for user bang
        url, query_without_bang = resolve_bang(
            query=query,
            user=request.user,
        )
        if url:
            return redirect(url)

        # If no bang found, redirect to user's default search engine
        query_enc = urllib.parse.quote_plus(query)
        user = cast("SearchUser", request.user)
        url = user.default_search_engine_url.replace("{query}", query_enc)
        return redirect(url)

    return render(request, "search/index.html", {"results": None})


@login_required
def settings(request: HttpRequest) -> HttpResponse:
    """Handle user settings page."""
    user = cast("SearchUser", request.user)

    if request.method == "POST":
        new_url = request.POST.get("default_search_engine_url", "").strip()

        if new_url:
            if "{query}" not in new_url:
                messages.error(
                    request, "URL template must contain {query} placeholder."
                )
            else:
                user.default_search_engine_url = new_url
                user.save()
                messages.success(request, "Default search engine updated successfully.")
        else:
            messages.error(request, "URL template cannot be empty.")

    return render(
        request,
        "search/settings.html",
        {"current_url": user.default_search_engine_url},
    )
