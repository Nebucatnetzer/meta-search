"""Bang handling for search shortcuts."""

import logging
from urllib.parse import quote_plus

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ObjectDoesNotExist

from search.models import Bang

logger = logging.getLogger(__name__)


def resolve_bang(
    user: AbstractUser | AnonymousUser,
    query: str,
) -> tuple[str | None, str | None]:
    """Process possible bang in query.

    Return (redirect_url or None, search_query_without_bang or None)
    """
    user_identifier = (
        getattr(user, "username", "anonymous")
        if hasattr(user, "username")
        else "anonymous"
    )

    if not query.startswith("!"):
        logger.debug("Query '%s' is not a bang query (user: %s)", query, user_identifier)
        return None, None

    logger.debug("Processing bang query '%s' (user: %s)", query, user_identifier)

    # split "!g foo" to "g", "foo"
    parts = query[1:].split(" ", 1)
    if len(parts) == 1:
        shortcut = parts[0]
        search_query = ""
    else:
        shortcut, search_query = parts

    logger.debug("Bang shortcut: '%s', search query: '%s' (user: %s)",
                shortcut, search_query, user_identifier)

    try:
        bang = Bang.objects.get(shortcut=shortcut, user=user)
        logger.info("Bang '%s' found for user %s, redirecting with query: '%s'",
                   shortcut, user_identifier, search_query)
    except ObjectDoesNotExist:
        logger.info("Bang '%s' not found for user %s, will search for: '%s'",
                   shortcut, user_identifier, search_query)
        return None, search_query

    search_query_escaped = quote_plus(search_query.strip())
    url = bang.url_template.replace("{query}", search_query_escaped)

    logger.info("Bang '%s' resolved to URL: %s (user: %s)",
               shortcut, url, user_identifier)

    return url, search_query
