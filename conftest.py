"""Pytest configuration for Django tests."""

import os

# Configure Django settings before importing anything Django-related
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zweili_search.settings")


def pytest_configure() -> None:
    """Configure Django for pytest."""
    import django

    django.setup()
