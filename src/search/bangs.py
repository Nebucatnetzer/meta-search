from urllib.parse import quote_plus

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ObjectDoesNotExist

from search.models import Bang


def resolve_bang(
    user: AbstractUser | AnonymousUser,
    query: str,
) -> tuple[str | None, str | None]:
    """Process possible bang in query.

    Return (redirect_url or None, search_query_without_bang or None)
    """
    if not query.startswith("!"):
        return None, None
    # split "!g foo" to "g", "foo"
    parts = query[1:].split(" ", 1)
    if len(parts) == 1:
        shortcut = parts[0]
        search_query = ""
    else:
        shortcut, search_query = parts

    try:
        bang = Bang.objects.get(shortcut=shortcut, user=user)
    except ObjectDoesNotExist:
        return None, search_query

    search_query_escaped = quote_plus(search_query.strip())
    url = bang.url_template.replace("{query}", search_query_escaped)
    return url, search_query
