from urllib.parse import quote_plus

from search.models import Bang


def resolve_bang(user, query):
    """
    If query starts with !<shortcut> find user's bang.
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
    bang_qs = Bang.objects.filter(user=user, shortcut=shortcut)
    if not bang_qs.exists():
        return None, None
    bang = bang_qs.first()
    # Substitute {query} with the actual user query (escaped)

    search_query_escaped = quote_plus(search_query.strip())
    url = bang.url_template.replace("{query}", search_query_escaped)
    return url, search_query
