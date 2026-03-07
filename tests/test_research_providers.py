"""
Tests for research providers: Tavily, Firecrawl, Apify.
Since the SDKs are not installed, we test constructor logic and
unavailable-state behavior.
"""

import pytest


# ─── Tavily Provider ──────────────────────────────────────


class TestTavilyProvider:
    def test_init_no_key(self):
        from core.research_providers.tavily_provider import TavilyProvider
        provider = TavilyProvider(api_key="")
        assert not provider.is_available

    def test_init_with_key_but_no_sdk(self):
        from core.research_providers.tavily_provider import TavilyProvider, TAVILY_AVAILABLE
        provider = TavilyProvider(api_key="fake-key")
        if not TAVILY_AVAILABLE:
            assert not provider.is_available
        # If SDK IS installed, it might or might not init (key invalid)

    def test_search_when_unavailable(self):
        from core.research_providers.tavily_provider import TavilyProvider
        provider = TavilyProvider(api_key="")
        result = provider.search("test query")
        assert result["success"] is False
        assert "not configured" in result["error"].lower() or "not" in result["error"].lower()

    def test_search_custom_max_results_when_unavailable(self):
        from core.research_providers.tavily_provider import TavilyProvider
        provider = TavilyProvider(api_key="")
        result = provider.search("test", max_results=3)
        assert result["success"] is False


# ─── Firecrawl Provider ──────────────────────────────────


class TestFirecrawlProvider:
    def test_init_no_key(self):
        from core.research_providers.firecrawl_provider import FirecrawlProvider
        provider = FirecrawlProvider(api_key="")
        assert not provider.is_available

    def test_init_with_key_but_no_sdk(self):
        from core.research_providers.firecrawl_provider import FirecrawlProvider, FIRECRAWL_AVAILABLE
        provider = FirecrawlProvider(api_key="fake-key")
        if not FIRECRAWL_AVAILABLE:
            assert not provider.is_available

    def test_crawl_url_when_unavailable(self):
        from core.research_providers.firecrawl_provider import FirecrawlProvider
        provider = FirecrawlProvider(api_key="")
        result = provider.crawl_url("https://example.com")
        assert result["success"] is False

    def test_crawl_site_when_unavailable(self):
        from core.research_providers.firecrawl_provider import FirecrawlProvider
        provider = FirecrawlProvider(api_key="")
        result = provider.crawl_site("https://example.com", max_pages=3)
        assert result["success"] is False


# ─── Apify Provider ──────────────────────────────────────


class TestApifyProvider:
    def test_init_no_key(self):
        from core.research_providers.apify_provider import ApifyProvider
        provider = ApifyProvider(api_key="")
        assert not provider.is_available

    def test_init_with_key_but_no_sdk(self):
        from core.research_providers.apify_provider import ApifyProvider, APIFY_AVAILABLE
        provider = ApifyProvider(api_key="fake-key")
        if not APIFY_AVAILABLE:
            assert not provider.is_available

    def test_scrape_google_reviews_when_unavailable(self):
        from core.research_providers.apify_provider import ApifyProvider
        provider = ApifyProvider(api_key="")
        result = provider.scrape_google_reviews("Test Biz", "Austin")
        assert result["success"] is False

    def test_scrape_website_when_unavailable(self):
        from core.research_providers.apify_provider import ApifyProvider
        provider = ApifyProvider(api_key="")
        result = provider.scrape_website_content("https://example.com")
        assert result["success"] is False

    def test_search_company_when_unavailable(self):
        from core.research_providers.apify_provider import ApifyProvider
        provider = ApifyProvider(api_key="")
        result = provider.search_company_info("Test Company")
        assert result["success"] is False
