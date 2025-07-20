from django.http import HttpRequest
from django.http import HttpResponse
from django.shortcuts import render


def index(request: HttpRequest) -> HttpResponse:
    return render(request, "search/index.html")
