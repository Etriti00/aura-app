"""
Aura — Tavily Research Provider
AI-powered web search for lead intelligence gathering.
"""

from utils.logger import get_logger

logger = get_logger("tavily_provider")

try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False
    logger.info("tavily-python not installed — Tavily provider unavailable")


class TavilyProvider:
    """Searches the web using Tavily's AI search API."""

    def __init__(self, api_key: str = ""):
        self._api_key = api_key
        self._client = None
        if api_key and TAVILY_AVAILABLE:
            try:
                self._client = TavilyClient(api_key=api_key)
            except Exception as e:
                logger.warning(f"Failed to init Tavily client: {e}")

    @property
    def is_available(self) -> bool:
        return self._client is not None

    def search(self, query: str, max_results: int = 5) -> dict:
        """Run an AI search query and return structured results."""
        if not self.is_available:
            return {"success": False, "error": "Tavily not configured"}
        try:
            response = self._client.search(
                query=query,
                max_results=max_results,
                search_depth="advanced",
                include_answer=True,
            )
            results = []
            for item in response.get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                    "score": item.get("score", 0),
                })
            return {
                "success": True,
                "data": {
                    "answer": response.get("answer", ""),
                    "results": results,
                    "query": query,
                },
            }
        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            return {"success": False, "error": str(e)}
