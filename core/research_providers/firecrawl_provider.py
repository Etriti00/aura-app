"""
Aura — Firecrawl Research Provider
Crawls websites and returns clean markdown content for LLM processing.
"""

from utils.logger import get_logger

logger = get_logger("firecrawl_provider")

try:
    from firecrawl import FirecrawlApp
    FIRECRAWL_AVAILABLE = True
except ImportError:
    FIRECRAWL_AVAILABLE = False
    logger.info("firecrawl-py not installed — Firecrawl provider unavailable")


class FirecrawlProvider:
    """Crawls and scrapes websites into clean markdown."""

    def __init__(self, api_key: str = ""):
        self._api_key = api_key
        self._client = None
        if api_key and FIRECRAWL_AVAILABLE:
            try:
                self._client = FirecrawlApp(api_key=api_key)
            except Exception as e:
                logger.warning(f"Failed to init Firecrawl client: {e}")

    @property
    def is_available(self) -> bool:
        return self._client is not None

    def crawl_url(self, url: str) -> dict:
        """Scrape a single URL and return its markdown content."""
        if not self.is_available:
            return {"success": False, "error": "Firecrawl not configured"}
        try:
            result = self._client.scrape_url(url, params={"formats": ["markdown"]})
            markdown = ""
            if isinstance(result, dict):
                markdown = result.get("markdown", "") or result.get("content", "")
            elif hasattr(result, "markdown"):
                markdown = result.markdown or ""
            return {
                "success": True,
                "data": {
                    "url": url,
                    "markdown": markdown[:50000],  # Cap at 50k chars
                    "title": result.get("metadata", {}).get("title", "") if isinstance(result, dict) else "",
                },
            }
        except Exception as e:
            logger.error(f"Firecrawl crawl failed for {url}: {e}")
            return {"success": False, "error": str(e)}

    def crawl_site(self, url: str, max_pages: int = 5) -> dict:
        """Crawl multiple pages of a website."""
        if not self.is_available:
            return {"success": False, "error": "Firecrawl not configured"}
        try:
            result = self._client.crawl_url(
                url,
                params={"limit": max_pages, "scrapeOptions": {"formats": ["markdown"]}},
            )
            pages = []
            data_list = result if isinstance(result, list) else result.get("data", []) if isinstance(result, dict) else []
            for page in data_list:
                if isinstance(page, dict):
                    pages.append({
                        "url": page.get("metadata", {}).get("sourceURL", url),
                        "markdown": (page.get("markdown", "") or "")[:20000],
                    })
            return {
                "success": True,
                "data": {"url": url, "pages": pages},
            }
        except Exception as e:
            logger.error(f"Firecrawl site crawl failed for {url}: {e}")
            return {"success": False, "error": str(e)}
