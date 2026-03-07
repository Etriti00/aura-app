"""
Aura — Apify Research Provider
Structured web scraping via Apify actors (LinkedIn profiles, reviews, etc.).
"""

from utils.logger import get_logger

logger = get_logger("apify_provider")

try:
    from apify_client import ApifyClient
    APIFY_AVAILABLE = True
except ImportError:
    APIFY_AVAILABLE = False
    logger.info("apify-client not installed — Apify provider unavailable")


class ApifyProvider:
    """Runs Apify actors for structured scraping (reviews, LinkedIn, etc.)."""

    def __init__(self, api_key: str = ""):
        self._api_key = api_key
        self._client = None
        if api_key and APIFY_AVAILABLE:
            try:
                self._client = ApifyClient(token=api_key)
            except Exception as e:
                logger.warning(f"Failed to init Apify client: {e}")

    @property
    def is_available(self) -> bool:
        return self._client is not None

    def scrape_google_reviews(self, business_name: str, city: str = "",
                              max_reviews: int = 10) -> dict:
        """Scrape Google reviews for a business."""
        if not self.is_available:
            return {"success": False, "error": "Apify not configured"}
        try:
            query = f"{business_name} {city}".strip()
            run_input = {
                "searchStringsArray": [query],
                "maxReviews": max_reviews,
                "language": "en",
            }
            run = self._client.actor("Xb8osYTtOjlsgI6k9").call(run_input=run_input)
            items = list(self._client.dataset(run["defaultDatasetId"]).iterate_items())
            reviews = []
            for item in items[:max_reviews]:
                reviews.append({
                    "author": item.get("name", ""),
                    "rating": item.get("stars", 0),
                    "text": item.get("text", ""),
                    "date": item.get("publishedAtDate", ""),
                })
            return {
                "success": True,
                "data": {
                    "business": business_name,
                    "city": city,
                    "reviews": reviews,
                    "total_found": len(items),
                },
            }
        except Exception as e:
            logger.error(f"Apify Google reviews scrape failed: {e}")
            return {"success": False, "error": str(e)}

    def scrape_website_content(self, url: str) -> dict:
        """Scrape structured content from a website using Apify's web scraper."""
        if not self.is_available:
            return {"success": False, "error": "Apify not configured"}
        try:
            run_input = {
                "startUrls": [{"url": url}],
                "maxPagesPerCrawl": 3,
                "proxyConfiguration": {"useApifyProxy": True},
            }
            run = self._client.actor("apify/website-content-crawler").call(
                run_input=run_input
            )
            items = list(self._client.dataset(run["defaultDatasetId"]).iterate_items())
            pages = []
            for item in items:
                pages.append({
                    "url": item.get("url", url),
                    "title": item.get("metadata", {}).get("title", ""),
                    "text": (item.get("text", "") or "")[:20000],
                })
            return {
                "success": True,
                "data": {"url": url, "pages": pages},
            }
        except Exception as e:
            logger.error(f"Apify website scrape failed: {e}")
            return {"success": False, "error": str(e)}

    def search_company_info(self, company_name: str) -> dict:
        """Search for company information using Apify's Google search scraper."""
        if not self.is_available:
            return {"success": False, "error": "Apify not configured"}
        try:
            run_input = {
                "queries": f"{company_name} company info services",
                "maxPagesPerQuery": 1,
                "resultsPerPage": 5,
            }
            run = self._client.actor("apify/google-search-scraper").call(
                run_input=run_input
            )
            items = list(self._client.dataset(run["defaultDatasetId"]).iterate_items())
            results = []
            for item in items:
                organic = item.get("organicResults", [])
                for result in organic[:5]:
                    results.append({
                        "title": result.get("title", ""),
                        "url": result.get("url", ""),
                        "description": result.get("description", ""),
                    })
            return {
                "success": True,
                "data": {"company": company_name, "results": results},
            }
        except Exception as e:
            logger.error(f"Apify company search failed: {e}")
            return {"success": False, "error": str(e)}
