"""Tests for the server start options."""

import os
from unittest.mock import patch

import pytest

from search.models import SearchUser
from zweili_search import server


def test_gunicorn_options_defaults() -> None:
    """Test the defaults when no environment variable is set."""
    with (
        patch.dict(os.environ, {}, clear=True),
        patch("multiprocessing.cpu_count", return_value=3),
    ):
        options = server.gunicorn_options()

    assert options == {"bind": "0.0.0.0:8000", "reload": False, "workers": 4}


def test_gunicorn_options_from_environment() -> None:
    """Test that the environment overrides the defaults."""
    environment = {
        "ZWEILI_SEARCH_BIND": "127.0.0.1:9000",
        "ZWEILI_SEARCH_WORKERS": "2",
        "GUNICORN_RELOAD": "true",
    }
    with patch.dict(os.environ, environment, clear=True):
        options = server.gunicorn_options()

    assert options == {"bind": "127.0.0.1:9000", "reload": True, "workers": 2}


@pytest.mark.django_db
def test_setup_admin_creates_superuser() -> None:
    """Test that a missing admin user is created as superuser."""
    created = server.setup_admin("root-admin")

    admin = SearchUser.objects.get(username="root-admin")
    assert created
    assert admin.is_superuser
    assert admin.is_staff
    assert admin.check_password("password")


def test_setup_admin_keeps_existing_user(user: SearchUser) -> None:
    """Test that an existing user keeps its password and permissions."""
    created = server.setup_admin(user.username)

    user.refresh_from_db()
    assert not created
    assert not user.is_superuser
    assert user.check_password("testpass123")
