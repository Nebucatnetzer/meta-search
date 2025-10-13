import os
from unittest.mock import patch

from django.test import TestCase


class SettingsTest(TestCase):
    def test_secret_key_missing_raises_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError) as context:
                import importlib

                import zweili_search.settings

                importlib.reload(zweili_search.settings)

            self.assertIn(
                "SECRET_KEY environment variable is required", str(context.exception)
            )

    def test_debug_mode_csrf_origins(self):
        with patch.dict(os.environ, {"SECRET_KEY": "test-key", "DEBUG": "True"}):
            import importlib

            import zweili_search.settings

            importlib.reload(zweili_search.settings)

            self.assertIn(
                "http://localhost:8000", zweili_search.settings.CSRF_TRUSTED_ORIGINS
            )
