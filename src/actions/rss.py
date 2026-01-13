"""RSS feed fetching for Aida."""

import logging
import feedparser
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
        # Default feeds if configuration is missing
        self.default_feeds = [
            {"name": "NRK", "url": "https://www.nrk.no/toppsaker.rss"},
            {"name": "VG", "url": "https://www.vg.no/rss/feed/?categories=1068&keywords=&limit=10"}
        ]

    def fetch_feed(self, url: str, limit: int = 5) -> str:
        """Fetch an RSS feed and return a summary string."""
        logger.info(f"Fetching RSS feed: {url}")
        try:
            feed = feedparser.parse(url)
            
            if feed.bozo and feed.bozo_exception:
                logger.warning(f"Feedparser reported issue: {feed.bozo_exception}")

            if not feed.entries:
                return f"I found the feed at {url}, but it seems to have no news items."

            feed_title = feed.feed.get("title", "RSS Feed")
            
            results = [f"Latest news from {feed_title}:"]
            
            for entry in feed.entries[:limit]:
                title = entry.get("title", "No title")
                # link = entry.get("link", "")
                results.append(f"- {title}")
            
            logger.info(f"Successfully parsed {len(results)-1} items from {url}")
            return "\n".join(results) + "\n\nVil du at jeg skal lese mer om en av disse?"

        except Exception as e:
            logger.error(f"Failed to fetch RSS feed {url}: {e}")
            return f"Sorry, I couldn't fetch the RSS feed from {url}. Error: {e}"

    def fetch_all_feeds(self, feeds: list[dict], limit_per_feed: int = 3) -> str:
        """Fetch headlines from all configured feeds.

        Args:
            feeds: List of {"name": str, "url": str} dicts
            limit_per_feed: Max items per feed

        Returns:
            Formatted string with news grouped by feed name
        """
        # Fallback to defaults if list is empty
        feeds_to_use = feeds if feeds else self.default_feeds

        if not feeds_to_use:
             return "No RSS feeds configured and no defaults available."

        logger.info(f"Fetching {len(feeds_to_use)} feeds")
        results = ["Her er siste nytt:\n"]

        for feed_config in feeds_to_use:
            name = feed_config.get("name", "Unknown")
            url = feed_config.get("url", "")

            if not url:
                continue

            try:
                feed = feedparser.parse(url)
                
                # Check for parsing errors but try to proceed if entries exist
                if feed.bozo and not feed.entries:
                     logger.warning(f"Failed to parse {name}: {feed.bozo_exception}")
                     results.append(f"**{name}:** (klarte ikke lese feed)")
                     continue

                if feed.entries:
                    results.append(f"**{name}:**")
                    for entry in feed.entries[:limit_per_feed]:
                        title = entry.get("title", "Uten tittel")
                        results.append(f"  - {title}")
                    results.append("")  # Empty line between feeds
                else:
                    results.append(f"**{name}:** (ingen saker funnet)")

            except Exception as e:
                logger.error(f"Failed to fetch {name} ({url}): {e}")
                results.append(f"**{name}:** (feilet: {str(e)[:20]}...)")
                results.append("")

        return "\n".join(results)
