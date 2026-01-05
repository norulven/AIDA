"""Web search functionality for Aida."""

import urllib.parse
from dataclasses import dataclass


@dataclass
class SearchResult:
    """A search result."""

    title: str
    url: str
    snippet: str


class WebSearch:
    """Web search utilities."""

    @staticmethod
    def build_search_url(query: str, engine: str = "duckduckgo") -> str:
        """Build a search URL for the given query."""
        encoded_query = urllib.parse.quote_plus(query)

        engines = {
            "duckduckgo": f"https://duckduckgo.com/?q={encoded_query}",
            "google": f"https://www.google.com/search?q={encoded_query}",
            "bing": f"https://www.bing.com/search?q={encoded_query}",
            "youtube": f"https://www.youtube.com/results?search_query={encoded_query}",
            "wikipedia": f"https://en.wikipedia.org/wiki/Special:Search?search={encoded_query}",
            "github": f"https://github.com/search?q={encoded_query}",
        }

        return engines.get(engine.lower(), engines["duckduckgo"])

    @staticmethod
    def build_direct_url(query: str) -> str | None:
        """Check if query is a direct URL or can be converted to one."""
        query = query.strip()

        # Already a URL
        if query.startswith(("http://", "https://")):
            return query

        # Looks like a domain
        if "." in query and " " not in query:
            return f"https://{query}"

        return None
