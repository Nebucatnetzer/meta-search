"""Django app configuration for the search application."""

import asyncio
import logging
import signal
import sys
import threading
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
        if "test" in sys.argv or "pytest" in sys.modules:
            return False

        return True

    def _setup_browser_lifecycle(self) -> None:
        """Set up browser startup and shutdown."""

        def start_browser_thread() -> None:
            """Start browser in a separate thread."""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                async def start_browser() -> None:
                    from search.browser_manager import browser_manager

                    await browser_manager.start()

                loop.run_until_complete(start_browser())
                logger.info("Browser manager started successfully")

            except Exception:  # noqa: BLE001
                logger.exception("Failed to start browser manager")

        # Start browser in background thread
        browser_thread = threading.Thread(
            target=start_browser_thread, name="BrowserManagerThread", daemon=True
        )
        browser_thread.start()

        # Register shutdown handler
        self._register_shutdown_handler()

    def _register_shutdown_handler(self) -> None:
        """Register signal handlers for clean shutdown."""

        def shutdown_handler(signum: int, frame: Any) -> None:  # noqa: ARG001
            """Handle shutdown signals."""
            logger.info("Received signal %d, shutting down browser", signum)

            def stop_browser_sync() -> None:
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    async def stop_browser() -> None:
                        from search.browser_manager import browser_manager

                        await browser_manager.stop()

                    loop.run_until_complete(stop_browser())
                    logger.info("Browser manager stopped successfully")

                except Exception:  # noqa: BLE001
                    logger.exception("Error stopping browser manager")

            stop_browser_sync()

        # Register handlers for common shutdown signals
        signal.signal(signal.SIGTERM, shutdown_handler)
        signal.signal(signal.SIGINT, shutdown_handler)
