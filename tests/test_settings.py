"""Test cases for Django settings."""

import importlib
import os
from unittest.mock import patch

import pytest

import zweili_search.settings


def test_secret_key_missing_raises_error() -> None:
    """Test that missing SECRET_KEY environment variable raises error."""
    with (
        patch.dict(os.environ, {}, clear=True),
        pytest.raises(ValueError, match="SECRET_KEY environment variable is required"),
    ):
        importlib.reload(zweili_search.settings)


def test_debug_mode_csrf_origins() -> None:
    """Test CSRF trusted origins in debug mode."""
    with patch.dict(os.environ, {"SECRET_KEY": "test-key", "DEBUG": "True"}):
        importlib.reload(zweili_search.settings)

        assert "http://localhost:8000" in zweili_search.settings.CSRF_TRUSTED_ORIGINS
