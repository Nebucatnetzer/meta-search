"""Test cases for Django models."""

import os
from typing import TYPE_CHECKING

import django
from django.conf import settings

if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zweili_search.settings")
    django.setup()

from django.contrib.auth import get_user_model

from search.models import Bang

if TYPE_CHECKING:
    from search.models import SearchUser

User = get_user_model()


def test_bang_str_method(user: "SearchUser") -> None:
    """Test the string representation of Bang model."""
    bang = Bang.objects.create(
        user=user,
        shortcut="g",
        url_template="https://www.google.com/search?q={query}",
    )
    expected_str = "!g -> https://www.google.com/search?q={query}"
    assert str(bang) == expected_str


def test_bang_unique_together_constraint(user: "SearchUser") -> None:
    """Test that the same shortcut can be used by different users."""
    Bang.objects.create(
        user=user,
        shortcut="test",
        url_template="https://example.com/search?q={query}",
    )

    user2 = User.objects.create_user(
        username="testuser2", password="testpass123"
    )
    Bang.objects.create(
        user=user2,
        shortcut="test",
        url_template="https://another.com/search?q={query}",
    )

    bang1 = Bang.objects.get(user=user, shortcut="test")
    bang2 = Bang.objects.get(user=user2, shortcut="test")

    assert bang1.pk != bang2.pk
    assert bang1.shortcut == bang2.shortcut
    assert bang1.user != bang2.user
