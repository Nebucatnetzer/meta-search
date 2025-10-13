"""Test cases for Django settings."""

import importlib
import os
from unittest.mock import patch

import pytest
from django.test import TestCase

import zweili_search.settings


class SettingsTest(TestCase):
    """Test cases for Django settings configuration."""

    def test_secret_key_missing_raises_error(self) -> None:
        """Test that missing SECRET_KEY environment variable raises error."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(
                ValueError, match="SECRET_KEY environment variable is required"
            ) as context:
                importlib.reload(zweili_search.settings)

            assert "SECRET_KEY environment variable is required" in str(
                context.value
            )

    def test_debug_mode_csrf_origins(self) -> None:
        """Test CSRF trusted origins in debug mode."""
        with patch.dict(os.environ, {"SECRET_KEY": "test-key", "DEBUG": "True"}):
            importlib.reload(zweili_search.settings)

            assert (
                "http://localhost:8000" in zweili_search.settings.CSRF_TRUSTED_ORIGINS
            )
