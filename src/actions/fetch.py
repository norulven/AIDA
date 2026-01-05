"""Web fetching for information retrieval."""

import re
import logging
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Configure logging
logger = logging.getLogger("aida.fetch")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    fh = logging.FileHandler('/tmp/aida_fetch.log')
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)

@dataclass
class FetchResult:
    """Result of a web fetch."""

    url: str
    title: str
    content: str
    success: bool
    error: str | None = None


class WebFetcher:
    """Fetch and extract content from web pages."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def fetch(self, url: str) -> FetchResult:
        """Fetch a URL and extract text content."""
        logger.info(f"Fetching URL: {url}")
        
        # Method 1: Try HTTPX (fast)
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(url, headers=self.headers)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "html.parser")
                text = self._extract_text_from_soup(soup)

                # If successful and substantial, return it
                if len(text) > 500:
                    logger.info(f"HTTPX fetch successful for {url}. Length: {len(text)}")
                    return FetchResult(
                        url=url,
                        title=soup.title.string.strip() if soup.title else "",
                        content=text[:8000],
                        success=True,
                    )
                logger.warning(f"HTTPX fetched content too short ({len(text)} chars). Trying Playwright...")

        except Exception as e:
            logger.warning(f"HTTPX fetch failed for {url}: {e}. Trying Playwright...")

        # Method 2: Try Playwright (robust)
        try:
            with sync_playwright() as p:
                browser = p.firefox.launch(headless=True)
                page = browser.new_page(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                
                # Navigate and wait for content
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                
                # Extract title and text
                title = page.title()
                
                # Try to get readable text
                # evaluate is safer than inner_text on body which might be huge/cluttered
                content = page.evaluate("""() => {
                    // Remove clutter
                    const elements = document.querySelectorAll('script, style, nav, footer, header, iframe, ads');
                    elements.forEach(el => el.remove());
                    return document.body.innerText;
                }""")
                
                browser.close()

                # Clean up whitespace
                lines = [line.strip() for line in content.split("\n") if line.strip()]
                clean_content = "\n".join(lines)
                
                logger.info(f"Playwright fetch successful for {url}. Length: {len(clean_content)}")
                return FetchResult(
                    url=url,
                    title=title.strip(),
                    content=clean_content[:8000],
                    success=True,
                )

        except Exception as e:
            logger.error(f"Playwright fetch failed for {url}: {e}")
            return FetchResult(
                url=url,
                title="",
                content="",
                success=False,
                error=f"Both methods failed. Last error: {e}",
            )

    def _extract_text_from_soup(self, soup: BeautifulSoup) -> str:
        """Helper to extract clean text from soup."""
        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        # Get main content
        main_content = (
            soup.find("main") or
            soup.find("article") or
            soup.find(class_=re.compile(r"content|article|post")) or
            soup.find("body")
        )

        if main_content:
            text = main_content.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)

        # Clean up whitespace
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return "\n".join(lines)

    def search_duckduckgo(self, query: str, num_results: int = 3) -> list[FetchResult]:
        """Search DuckDuckGo and fetch top results."""
        logger.info(f"Searching DuckDuckGo for: '{query}'")
        search_url = f"https://html.duckduckgo.com/html/?q={query}"

        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(search_url, headers=self.headers)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "html.parser")
                results = []
                
                links = soup.select(".result__a")[:num_results]
                logger.info(f"Found {len(links)} raw results")

                # Find result links
                for result in links:
                    href = result.get("href", "")
                    if href:
                        # DuckDuckGo wraps URLs, extract the actual URL
                        if "uddg=" in href:
                            from urllib.parse import parse_qs, urlparse
                            parsed = urlparse(href)
                            params = parse_qs(parsed.query)
                            if "uddg" in params:
                                href = params["uddg"][0]
                        
                        logger.debug(f"Processing result URL: {href}")
                        fetch_result = self.fetch(href)
                        results.append(fetch_result)

                return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return [FetchResult(
                url=search_url,
                title="",
                content="",
                success=False,
                error=str(e),
            )]

    def summarize_for_llm(self, results: list[FetchResult]) -> str:
        """Format fetch results for LLM context."""
        summaries = []

        for result in results:
            if result.success:
                summary = f"**{result.title}** ({result.url})\n{result.content[:2000]}"
                summaries.append(summary)
            else:
                summaries.append(f"Failed to fetch {result.url}: {result.error}")

        return "\n\n---\n\n".join(summaries)
