"""Global Playwright browser manager for web scraping."""

import asyncio
import contextlib
import logging
import threading
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from playwright.async_api import Browser
from playwright.async_api import BrowserContext
from playwright.async_api import Page
from playwright.async_api import Playwright
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


class BrowserManager:  # pylint: disable=too-many-instance-attributes
    """Singleton manager for Playwright browser instance."""

    _instance: "BrowserManager | None" = None
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
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._is_started = False
        self._lock = threading.Lock()
        self._page_pool: list[Page] = []
        self._page_pool_lock = asyncio.Lock()
        self._max_pool_size = 10

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

                # Use Firefox for better stealth capabilities
                self._browser = await self._playwright.firefox.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                    ],
                )

                # Create a persistent context with realistic browser headers
                self._context = await self._browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) "
                        "Gecko/20100101 Firefox/140.0"
                    ),
                    viewport={"width": 1920, "height": 1080},
                    locale="en-US",
                    timezone_id="UTC",
                )

                self._is_started = True
                logger.info("Playwright browser started successfully")

            except Exception:
                logger.exception("Failed to start Playwright browser")
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
            # Close all pages in the pool
            async with self._page_pool_lock:
                for page in self._page_pool:
                    with contextlib.suppress(Exception):
                        await page.close()
                self._page_pool.clear()

            if self._context:
                await self._context.close()
                self._context = None

            if self._browser:
                await self._browser.close()
                self._browser = None

            if self._playwright:
                await self._playwright.stop()
                self._playwright = None

        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Error during browser cleanup")

    @asynccontextmanager
    async def get_page(self) -> AsyncGenerator[Page, None]:
        """Get a page from the pool or create a new one."""
        if not self._is_started or not self._context:
            msg = "Browser manager not started. Call start() first."
            raise RuntimeError(msg)

        page: Page | None = None

        # Try to get a page from the pool
        async with self._page_pool_lock:
            if self._page_pool:
                page = self._page_pool.pop()
                logger.debug(
                    "Reused page from pool (pool size: %d)", len(self._page_pool)
                )
            else:
                logger.debug("Creating new page (pool empty)")

        # Create new page if none available in pool
        if page is None:
            page = await self._context.new_page()

        try:
            yield page
        finally:
            # Return page to pool if it's still valid and pool isn't full
            try:
                if not page.is_closed():
                    async with self._page_pool_lock:
                        if len(self._page_pool) < self._max_pool_size:
                            # Clear any existing content/state
                            await page.goto("about:blank")
                            self._page_pool.append(page)
                            logger.debug(
                                "Returned page to pool (pool size: %d)",
                                len(self._page_pool),
                            )
                        else:
                            await page.close()
                            logger.debug("Pool full, closed page")
                else:
                    logger.debug("Page was already closed")
            except Exception:  # pylint: disable=broad-exception-caught
                logger.exception("Error returning page to pool, closing page")
                with contextlib.suppress(Exception):
                    await page.close()

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


@asynccontextmanager
async def get_browser_page() -> AsyncGenerator[Page, None]:
    """Get a browser page from the global browser manager."""
    await ensure_browser_started()
    async with browser_manager.get_page() as page:
        yield page


async def stop_browser() -> None:
    """Stop the global browser manager."""
    await browser_manager.stop()
