"""Tests for v2.0 enrichment layers and scoring."""

import json
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from core.enrichment_scoring import calculate_completeness


# ═══════════════════════════════════════════════════════════════════════════════
# Enrichment Scoring Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalculateCompleteness:
    """Test the weighted completeness scoring function."""

    def test_empty_dict(self):
        assert calculate_completeness({}) == 0

    def test_full_data(self):
        data = {
            "email": "a@b.com",
            "decision_maker_name": "John Doe",
            "pain_points": '["no website", "low traffic"]',
            "tech_stack": '["WordPress"]',
            "phone": "555-1234",
        }
        assert calculate_completeness(data) == 100

    def test_email_only(self):
        assert calculate_completeness({"email": "a@b.com"}) == 40

    def test_decision_maker_only(self):
        assert calculate_completeness({"decision_maker_name": "Jane"}) == 20

    def test_pain_points_only(self):
        assert calculate_completeness({"pain_points": '["slow site"]'}) == 15

    def test_tech_stack_only(self):
        assert calculate_completeness({"tech_stack": '["React"]'}) == 10

    def test_phone_only(self):
        assert calculate_completeness({"phone": "555-0000"}) == 15

    def test_gmaps_phone_fallback(self):
        assert calculate_completeness({"gmaps_phone": "555-9999"}) == 15

    def test_empty_strings_ignored(self):
        data = {
            "email": "",
            "decision_maker_name": "",
            "pain_points": "[]",
            "tech_stack": "",
            "phone": "",
        }
        assert calculate_completeness(data) == 0

    def test_partial_data(self):
        data = {
            "email": "test@example.com",
            "phone": "555-1234",
            "tech_stack": '["Shopify"]',
        }
        # email(40) + phone(15) + tech(10) = 65
        assert calculate_completeness(data) == 65

    def test_none_values(self):
        data = {"email": None, "decision_maker_name": None}
        assert calculate_completeness(data) == 0

    def test_capped_at_100(self):
        """Even if somehow weights exceeded, cap at 100."""
        data = {
            "email": "a@b.com",
            "decision_maker_name": "John",
            "pain_points": '["x"]',
            "tech_stack": '["y"]',
            "phone": "555",
        }
        assert calculate_completeness(data) <= 100


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 0: DNS / WHOIS / SSL
# ═══════════════════════════════════════════════════════════════════════════════

class TestLayer0TechStack:
    """Test tech stack detection from HTML."""

    def test_detect_wordpress(self):
        from core.enrichment_layers.layer0_dns import _detect_tech_stack
        html = '<link rel="stylesheet" href="/wp-content/themes/foo/style.css">'
        techs = _detect_tech_stack(html)
        assert "WordPress" in techs

    def test_detect_shopify(self):
        from core.enrichment_layers.layer0_dns import _detect_tech_stack
        html = '<script src="https://cdn.shopify.com/s/files/1/abc.js"></script>'
        techs = _detect_tech_stack(html)
        assert "Shopify" in techs

    def test_detect_react(self):
        from core.enrichment_layers.layer0_dns import _detect_tech_stack
        html = '<div id="root"><script src="/_next/static/chunks/main.js"></script></div>'
        techs = _detect_tech_stack(html)
        assert any(t in techs for t in ["React", "Next.js"])

    def test_detect_google_analytics(self):
        from core.enrichment_layers.layer0_dns import _detect_tech_stack
        html = '<script src="https://www.google-analytics.com/analytics.js"></script>'
        techs = _detect_tech_stack(html)
        assert "Google Analytics" in techs

    def test_generator_meta_tag(self):
        from core.enrichment_layers.layer0_dns import _detect_tech_stack
        html = '<meta name="generator" content="Hugo 0.115.0">'
        techs = _detect_tech_stack(html)
        assert "Hugo 0.115.0" in techs

    def test_empty_html(self):
        from core.enrichment_layers.layer0_dns import _detect_tech_stack
        assert _detect_tech_stack("") == []

    def test_multiple_techs(self):
        from core.enrichment_layers.layer0_dns import _detect_tech_stack
        html = ('<script src="/wp-content/themes/x.js"></script>'
                '<script src="https://cdn.shopify.com/s/x.js"></script>')
        techs = _detect_tech_stack(html)
        assert "WordPress" in techs
        assert "Shopify" in techs


class TestLayer0SocialLinks:
    """Test social link extraction."""

    def test_extract_linkedin(self):
        from core.enrichment_layers.layer0_dns import _extract_social_links
        html = '<a href="https://www.linkedin.com/company/acme-corp">LinkedIn</a>'
        links = _extract_social_links(html)
        assert "linkedin" in links
        assert "acme-corp" in links["linkedin"]

    def test_extract_twitter(self):
        from core.enrichment_layers.layer0_dns import _extract_social_links
        html = '<a href="https://twitter.com/acmecorp">Twitter</a>'
        links = _extract_social_links(html)
        assert "twitter" in links

    def test_extract_x_dot_com(self):
        from core.enrichment_layers.layer0_dns import _extract_social_links
        html = '<a href="https://x.com/acmecorp">X</a>'
        links = _extract_social_links(html)
        assert "twitter" in links

    def test_extract_facebook(self):
        from core.enrichment_layers.layer0_dns import _extract_social_links
        html = '<a href="https://www.facebook.com/acmecorp">FB</a>'
        links = _extract_social_links(html)
        assert "facebook" in links

    def test_no_social_links(self):
        from core.enrichment_layers.layer0_dns import _extract_social_links
        assert _extract_social_links("<p>Hello</p>") == {}


class TestLayer0MobileResponsive:
    def test_has_viewport(self):
        from core.enrichment_layers.layer0_dns import _check_mobile_responsive
        html = '<meta name="viewport" content="width=device-width, initial-scale=1">'
        assert _check_mobile_responsive(html) is True

    def test_no_viewport(self):
        from core.enrichment_layers.layer0_dns import _check_mobile_responsive
        assert _check_mobile_responsive("<html><body>No viewport</body></html>") is False


class TestLayer0Integration:
    """Test the main enrich_layer0 function."""

    @patch("core.enrichment_layers.layer0_dns._check_whois")
    @patch("core.enrichment_layers.layer0_dns._check_mx")
    @patch("core.enrichment_layers.layer0_dns._check_ssl")
    def test_enrich_layer0_with_html(self, mock_ssl, mock_mx, mock_whois):
        from core.enrichment_layers.layer0_dns import enrich_layer0
        mock_whois.return_value = {"whois_registrar": "GoDaddy"}
        mock_mx.return_value = True
        mock_ssl.return_value = True

        html = '<meta name="viewport" content="width=device-width"><link href="/wp-content/x">'
        result = enrich_layer0("example.com", html)

        assert result["whois_registrar"] == "GoDaddy"
        assert result["mx_records_valid"] is True
        assert result["has_ssl"] is True
        assert result["is_mobile_responsive"] is True
        assert "WordPress" in json.loads(result["tech_stack"])

    @patch("core.enrichment_layers.layer0_dns._check_whois")
    @patch("core.enrichment_layers.layer0_dns._check_mx")
    @patch("core.enrichment_layers.layer0_dns._check_ssl")
    def test_enrich_layer0_no_html(self, mock_ssl, mock_mx, mock_whois):
        from core.enrichment_layers.layer0_dns import enrich_layer0
        mock_whois.return_value = {"whois_registrar": None}
        mock_mx.return_value = False
        mock_ssl.return_value = False

        result = enrich_layer0("example.com")
        assert "tech_stack" not in result
        assert result["mx_records_valid"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 1: Ollama / LLM Extraction
# ═══════════════════════════════════════════════════════════════════════════════

class TestLayer1Parsing:
    def test_parse_valid_json(self):
        from core.enrichment_layers.layer1_ollama import _parse_extraction
        text = '{"decision_maker_name": "John", "icp_fit_score": 85}'
        result = _parse_extraction(text)
        assert result["decision_maker_name"] == "John"
        assert result["icp_fit_score"] == 85

    def test_parse_json_in_text(self):
        from core.enrichment_layers.layer1_ollama import _parse_extraction
        text = 'Here is the result:\n{"company_description": "A plumbing company"}\nDone.'
        result = _parse_extraction(text)
        assert result["company_description"] == "A plumbing company"

    def test_parse_pain_points(self):
        from core.enrichment_layers.layer1_ollama import _parse_extraction
        text = '{"pain_points": ["no website", "low SEO"]}'
        result = _parse_extraction(text)
        assert "no website" in result["pain_points"]

    def test_parse_clamps_score(self):
        from core.enrichment_layers.layer1_ollama import _parse_extraction
        text = '{"icp_fit_score": 150}'
        result = _parse_extraction(text)
        assert result["icp_fit_score"] == 100

    def test_parse_negative_score(self):
        from core.enrichment_layers.layer1_ollama import _parse_extraction
        text = '{"icp_fit_score": -10}'
        result = _parse_extraction(text)
        assert result["icp_fit_score"] == 0

    def test_parse_invalid_json(self):
        from core.enrichment_layers.layer1_ollama import _parse_extraction
        result = _parse_extraction("This is not JSON at all")
        assert result == {}

    def test_parse_empty(self):
        from core.enrichment_layers.layer1_ollama import _parse_extraction
        assert _parse_extraction("") == {}


class TestLayer1Integration:
    def test_no_router(self):
        import asyncio
        from core.enrichment_layers.layer1_ollama import enrich_layer1
        result = asyncio.run(enrich_layer1("<html>content</html>", "Acme", router_engine=None))
        assert result == {}

    def test_no_html(self):
        import asyncio
        from core.enrichment_layers.layer1_ollama import enrich_layer1
        result = asyncio.run(enrich_layer1("", "Acme", router_engine=MagicMock()))
        assert result == {}


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 2: Free APIs
# ═══════════════════════════════════════════════════════════════════════════════

class TestLayer2EmployeeRange:
    def test_small(self):
        from core.enrichment_layers.layer2_free_apis import _employees_to_range
        assert _employees_to_range(5) == "1-10"

    def test_medium(self):
        from core.enrichment_layers.layer2_free_apis import _employees_to_range
        assert _employees_to_range(30) == "11-50"

    def test_large(self):
        from core.enrichment_layers.layer2_free_apis import _employees_to_range
        assert _employees_to_range(100) == "51-200"

    def test_xlarge(self):
        from core.enrichment_layers.layer2_free_apis import _employees_to_range
        assert _employees_to_range(2000) == "1000+"

    def test_invalid(self):
        from core.enrichment_layers.layer2_free_apis import _employees_to_range
        assert _employees_to_range("invalid") == ""


class TestLayer2DailyLimits:
    def test_check_limit(self):
        from core.enrichment_layers.layer2_free_apis import _check_daily_limit, _increment_counter
        # Reset counter
        assert _check_daily_limit("test_source", 3) is True
        _increment_counter("test_source")
        _increment_counter("test_source")
        _increment_counter("test_source")
        assert _check_daily_limit("test_source", 3) is False


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 4: Deep Crawl
# ═══════════════════════════════════════════════════════════════════════════════

class TestLayer4EmailExtraction:
    def test_extract_emails(self):
        from core.enrichment_layers.layer4_deep_crawl import _extract_emails
        text = "Contact us at info@acme.com or sales@acme.com"
        emails = _extract_emails(text)
        assert "info@acme.com" in emails
        assert "sales@acme.com" in emails

    def test_filter_false_positives(self):
        from core.enrichment_layers.layer4_deep_crawl import _extract_emails
        text = "Use user@example.com for testing and real@company.com for production"
        emails = _extract_emails(text)
        assert "user@example.com" not in emails
        assert "real@company.com" in emails

    def test_no_emails(self):
        from core.enrichment_layers.layer4_deep_crawl import _extract_emails
        assert _extract_emails("No emails here") == []

    def test_deduplication(self):
        from core.enrichment_layers.layer4_deep_crawl import _extract_emails
        text = "Contact info@acme.com and also info@acme.com"
        emails = _extract_emails(text)
        assert len(emails) == 1


class TestLayer4SkipThreshold:
    def test_skip_above_threshold(self):
        import asyncio
        from core.enrichment_layers.layer4_deep_crawl import enrich_layer4
        result = asyncio.run(enrich_layer4("example.com", 50.0))
        assert result == {}

    def test_skip_no_browser(self):
        import asyncio
        from core.enrichment_layers.layer4_deep_crawl import enrich_layer4
        result = asyncio.run(enrich_layer4("example.com", 10.0, browser_page=None))
        assert result == {}
