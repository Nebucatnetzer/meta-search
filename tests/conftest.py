"""Global pytest configuration for tests."""

import os
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

import django
import pytest
from django.conf import settings as django_settings

if not django_settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zweili_search.settings")
    django.setup()

from django.contrib.auth import get_user_model
from pytest_django.fixtures import SettingsWrapper

if TYPE_CHECKING:
    from search.models import SearchUser

User = get_user_model()


@pytest.fixture(autouse=True)
def plain_static_storage(settings: SettingsWrapper) -> None:
    """Use plain static file storage, because the tests run without collectstatic."""
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }


@pytest.fixture
def user(db: Any) -> "SearchUser":  # noqa: ARG001
    """Create a test user with database access."""
    return cast(
        "SearchUser",
        User.objects.create_user(username="testuser", password="testpass123"),
    )
