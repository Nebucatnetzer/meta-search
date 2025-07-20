from django.http import HttpRequest
from django.http import HttpResponse
from django.shortcuts import render


def index(request: HttpRequest) -> HttpResponse:
    query = request.GET.get("query")
    results = None
    if query:
        results = [
            {"link": "http://foo", "title": "foo"},
            {"link": "http://bar", "title": "bar"},
        ]
    return render(request, "search/index.html", {"results": results})
