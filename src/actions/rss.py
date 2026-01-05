"""RSS feed fetching for Aida."""

import logging
import httpx
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List, Optional

# Configure logging
logger = logging.getLogger("aida.rss")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    fh = logging.FileHandler('/tmp/aida_rss.log')
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)

@dataclass
class RSSItem:
    title: str
    link: str
    description: str
    pub_date: str

class RSSFetcher:
    """Fetch and parse RSS feeds."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def fetch_feed(self, url: str, limit: int = 5) -> str:
        """Fetch an RSS feed and return a summary string."""
        logger.info(f"Fetching RSS feed: {url}")
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(url, headers=self.headers)
                response.raise_for_status()

                # Parse XML
                soup = BeautifulSoup(response.text, "xml")
                
                # Check for atom or rss
                items = soup.find_all("item") or soup.find_all("entry")
                
                if not items:
                    return f"I found the feed at {url}, but it seems to have no news items."

                feed_title = soup.find("title").text if soup.find("title") else "RSS Feed"
                
                results = [f"Latest news from {feed_title}:"]
                
                for item in items[:limit]:
                    title = item.find("title").text if item.find("title") else "No title"
                    link = item.find("link").text if item.find("link") else ""
                    # handle atom links which might be in href attribute
                    if not link and item.find("link"):
                        link = item.find("link").get("href", "")
                    
                    results.append(f"- {title}")
                
                logger.info(f"Successfully parsed {len(results)-1} items from {url}")
                return "\n".join(results) + "\n\nWould you like me to open one of these or summarize the full content?"

        except Exception as e:
            logger.error(f"Failed to fetch RSS feed {url}: {e}")
            return f"Sorry, I couldn't fetch the RSS feed from {url}. Error: {e}"
