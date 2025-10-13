"""Global pytest configuration for tests."""

import os

import django
import pytest
from django.conf import settings

if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zweili_search.settings")
    django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user with database access."""
    return User.objects.create_user(
        username="testuser", password="testpass123"
    )
