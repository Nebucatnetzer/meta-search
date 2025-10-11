"""Global Playwright browser manager for web scraping."""

import logging
import threading
from typing import Optional

from playwright.async_api import Browser
from playwright.async_api import BrowserContext
from playwright.async_api import Page
from playwright.async_api import Playwright
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


class BrowserManager:
    """Singleton manager for Playwright browser instance."""

    _instance: Optional["BrowserManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "BrowserManager":
        """Create or return the singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize browser manager."""
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._is_started = False
        self._lock = threading.Lock()

    async def start(self) -> None:
        """Start the Playwright browser."""
        if self._is_started:
            return

        with self._lock:
            if self._is_started:
                return

            try:
                logger.info("Starting Playwright browser")
                self._playwright = await async_playwright().start()

                # Use Chromium for better compatibility and performance
                self._browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--disable-extensions",
                        "--disable-background-timer-throttling",
                        "--disable-backgrounding-occluded-windows",
                        "--disable-renderer-backgrounding",
                    ],
                )

                # Create a persistent context with realistic browser headers
                self._context = await self._browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1920, "height": 1080},
                    locale="en-US",
                    timezone_id="UTC",
                )

                self._is_started = True
                logger.info("Playwright browser started successfully")

            except Exception as e:
                logger.exception("Failed to start Playwright browser: %s", e)
                await self._cleanup()
                raise

    async def stop(self) -> None:
        """Stop the Playwright browser."""
        if not self._is_started:
            return

        with self._lock:
            if not self._is_started:
                return

            logger.info("Stopping Playwright browser")
            await self._cleanup()
            self._is_started = False
            logger.info("Playwright browser stopped")

    async def _cleanup(self) -> None:
        """Clean up browser resources."""
        try:
            if self._context:
                await self._context.close()
                self._context = None

            if self._browser:
                await self._browser.close()
                self._browser = None

            if self._playwright:
                await self._playwright.stop()
                self._playwright = None

        except Exception:  # noqa: BLE001
            logger.exception("Error during browser cleanup")

    async def get_page(self) -> Page:
        """Get a new page from the browser context."""
        if not self._is_started or not self._context:
            raise RuntimeError("Browser manager not started. Call start() first.")

        page = await self._context.new_page()

        # Set common page settings
        await page.set_extra_http_headers(
            {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )

        return page

    @property
    def is_started(self) -> bool:
        """Check if browser is started."""
        return self._is_started


# Global browser manager instance
browser_manager = BrowserManager()


async def ensure_browser_started() -> None:
    """Ensure the global browser manager is started."""
    if not browser_manager.is_started:
        await browser_manager.start()


async def get_browser_page() -> Page:
    """Get a new browser page, starting the browser if needed."""
    await ensure_browser_started()
    return await browser_manager.get_page()


async def stop_browser() -> None:
    """Stop the global browser manager."""
    await browser_manager.stop()
