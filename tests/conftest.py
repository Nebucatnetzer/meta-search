"""Global pytest configuration for tests."""

import os
from typing import TYPE_CHECKING, Any, cast

import django
import pytest
from django.conf import settings

if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zweili_search.settings")
    django.setup()

from django.contrib.auth import get_user_model

if TYPE_CHECKING:
    from search.models import SearchUser

User = get_user_model()


@pytest.fixture
def user(db: Any) -> "SearchUser":  # noqa: ARG001
    """Create a test user with database access."""
    return cast("SearchUser", User.objects.create_user(
        username="testuser", password="testpass123"
    ))
