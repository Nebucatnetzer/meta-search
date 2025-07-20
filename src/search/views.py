from django.http import HttpRequest
from django.http import HttpResponse


def index(request: HttpRequest) -> HttpResponse:
    return HttpResponse("Hello, world.")
