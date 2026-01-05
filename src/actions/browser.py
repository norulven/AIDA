"""Browser control for Aida using Playwright."""

import urllib.parse
import logging
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

# Configure logging
logger = logging.getLogger("aida.browser")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    fh = logging.FileHandler('/tmp/aida_browser.log')
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)

class BrowserController:
    """Control web browser using Playwright."""

    def __init__(self, headless: bool = False):
        self._headless = headless
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        logger.info(f"BrowserController initialized (headless={headless})")

    def _ensure_browser(self):
        """Ensure browser is running."""
        try:
            if self._playwright is None:
                logger.info("Starting Playwright...")
                self._playwright = sync_playwright().start()

            if self._browser is None:
                logger.info("Launching Browser (Firefox)...")
                # Launch browser (Firefox)
                self._browser = self._playwright.firefox.launch(
                    headless=self._headless,
                )
                logger.info("Browser launched.")

            if self._context is None:
                logger.info("Creating Context...")
                self._context = self._browser.new_context(no_viewport=True)

            if self._page is None:
                logger.info("Creating Page...")
                self._page = self._context.new_page()
                
        except Exception as e:
            logger.error(f"Error in _ensure_browser: {e}", exc_info=True)
            raise e

    def open_url(self, url: str) -> bool:
        """Open a URL in the browser."""
        logger.info(f"Attempting to open URL: {url}")
        try:
            self._ensure_browser()
            
            # Decide whether to use existing page or open new one
            target_page = None
            if self._page and self._page.url == "about:blank":
                target_page = self._page
            else:
                logger.info("Opening new tab...")
                target_page = self._context.new_page()
                self._page = target_page

            if target_page:
                target_page.bring_to_front()
                logger.info(f"Navigating to {url}...")
                target_page.goto(url)
                logger.info("Navigation successful.")
                return True
            return False
        except Exception as e:
            logger.error(f"Error opening URL: {e}", exc_info=True)
            print(f"Error opening URL: {e}")
            # If we lost connection to browser, try to reset
            self.stop()
            # Try once more
            try:
                logger.info("Retrying navigation...")
                self._ensure_browser()
                if self._page:
                    self._page.goto(url)
                    return True
            except Exception as e2:
                logger.error(f"Retry failed: {e2}")
                pass
            return False

    def navigate(self, url: str) -> None:
        """Navigate to a URL."""
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        self.open_url(url)

    def search(self, query: str, engine: str = "duckduckgo") -> None:
        """Perform a web search."""
        encoded_query = urllib.parse.quote_plus(query)

        search_urls = {
            "duckduckgo": f"https://duckduckgo.com/?q={encoded_query}",
            "google": f"https://www.google.com/search?q={encoded_query}",
            "bing": f"https://www.bing.com/search?q={encoded_query}",
        }

        url = search_urls.get(engine, search_urls["duckduckgo"])
        self.open_url(url)

    def stop(self) -> None:
        """Close the browser and release resources."""
        logger.info("Stopping browser...")
        if self._page:
            try:
                self._page.close()
            except Exception:
                pass
            self._page = None

        if self._context:
            try:
                self._context.close()
            except Exception:
                pass
            self._context = None

        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None

        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        logger.info("Browser stopped.")

    def close(self) -> None:
        """Alias for stop."""
        self.stop()


# Alias for backwards compatibility
BrowserControllerSync = BrowserController
