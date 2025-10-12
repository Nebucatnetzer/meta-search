"""Django app configuration for the search application."""

import logging
import signal
import sys
from typing import Any

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class SearchConfig(AppConfig):
    """Configuration for the search application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "search"

    def ready(self) -> None:
        """Initialize the application when Django is ready."""
        # Only start browser in main process (not in workers or management commands)
        if self._should_start_browser():
            self._setup_browser_lifecycle()

    def _should_start_browser(self) -> bool:
        """Determine if we should start the browser in this process."""
        # Don't start browser in management commands like migrate, collectstatic
        if len(sys.argv) > 1 and sys.argv[1] in [
            "migrate",
            "makemigrations",
            "collectstatic",
            "createsuperuser",
            "shell",
            "test",
            "check",
            "compilemessages",
            "makemessages",
        ]:
            return False

        # Don't start browser during testing
        return not ("test" in sys.argv or "pytest" in sys.modules)

    def _setup_browser_lifecycle(self) -> None:
        """Set up browser startup and shutdown."""
        # With thread-local browser storage, we don't need to pre-start browsers
        # They are created on-demand per thread
        logger.info("Browser lifecycle configured for thread-local instances")

        # Register shutdown handler
        self._register_shutdown_handler()

    def _register_shutdown_handler(self) -> None:
        """Register signal handlers for clean shutdown."""

        def shutdown_handler(signum: int, _frame: Any) -> None:
            """Handle shutdown signals."""
            signal_names: dict[int, str] = {
                signal.SIGTERM: "SIGTERM",
                signal.SIGINT: "SIGINT",
            }
            signal_name = signal_names.get(signum, f"Signal {signum}")

            logger.info("Received %s, shutting down browsers", signal_name)

            # Note: With thread-local storage, each thread manages its own browser
            # The main thread doesn't need to explicitly clean up other threads'
            # browsers as they will be cleaned up when those threads exit
            logger.info("Application shutting down cleanly")

        # Register handlers for common shutdown signals
        signal.signal(signal.SIGTERM, shutdown_handler)
        signal.signal(signal.SIGINT, shutdown_handler)
