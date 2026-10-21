"""Tests for the server start options."""

import os
from unittest.mock import patch

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
