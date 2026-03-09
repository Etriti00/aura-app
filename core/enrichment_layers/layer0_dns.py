"""
Aura v2.0 — Layer 0: DNS / WHOIS / SSL / Tech Stack
Free, no-API enrichment from domain analysis.
"""

import json
import re
import ssl
import socket
from urllib.parse import urlparse

from utils.logger import get_logger

logger = get_logger(__name__)


def enrich_layer0(domain: str, html_content: str = "") -> dict:
    """Run Layer 0 enrichment: DNS, WHOIS, SSL, tech stack, social links.

    Args:
        domain: The domain to analyze (e.g. "example.com")
        html_content: Optional HTML of the homepage for tech/social extraction

    Returns:
        dict with enrichment fields for Layer 0
    """
    result = {}

    # WHOIS
    result.update(_check_whois(domain))

    # MX records
    result["mx_records_valid"] = _check_mx(domain)

    # SSL
    result["has_ssl"] = _check_ssl(domain)

    # Tech stack from HTML
    if html_content:
        result["tech_stack"] = json.dumps(_detect_tech_stack(html_content))
        result["social_links"] = json.dumps(_extract_social_links(html_content))
        result["is_mobile_responsive"] = _check_mobile_responsive(html_content)

    return result


def _check_whois(domain: str) -> dict:
    """Query WHOIS for registrar info."""
    try:
        import whois
        w = whois.whois(domain)
        registrar = w.registrar if hasattr(w, "registrar") else None
        return {"whois_registrar": registrar}
    except Exception as e:
        logger.debug(f"WHOIS lookup failed for {domain}: {e}")
        return {"whois_registrar": None}


def _check_mx(domain: str) -> bool:
    """Check if domain has valid MX records."""
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, "MX")
        return len(answers) > 0
    except Exception:
        return False


def _check_ssl(domain: str) -> bool:
    """Check if domain has a valid SSL certificate."""
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=domain) as s:
            s.settimeout(5)
            s.connect((domain, 443))
            return True
    except Exception:
        return False


def _detect_tech_stack(html: str) -> list[str]:
    """Detect technologies from HTML meta tags, headers, and patterns."""
    techs = []
    html_lower = html.lower()

    patterns = {
        "WordPress": ["wp-content", "wp-includes", "wordpress"],
        "Shopify": ["cdn.shopify.com", "shopify.com", "myshopify"],
        "Wix": ["wix.com", "wixstatic.com", "wixsite"],
        "Squarespace": ["squarespace.com", "sqsp.com"],
        "React": ["react", "_next/static", "react-dom"],
        "Vue.js": ["vue.js", "vue.min.js", "__vue__"],
        "Angular": ["ng-version", "angular.js", "angular.min.js"],
        "jQuery": ["jquery.min.js", "jquery-"],
        "Bootstrap": ["bootstrap.min.css", "bootstrap.min.js"],
        "Tailwind": ["tailwindcss", "tailwind.min.css"],
        "Google Analytics": ["google-analytics.com", "gtag/js", "googletagmanager"],
        "Google Tag Manager": ["googletagmanager.com/gtm.js"],
        "HubSpot": ["js.hs-scripts.com", "hubspot.com"],
        "Mailchimp": ["mailchimp.com", "chimpstatic.com"],
        "Cloudflare": ["cloudflare", "cf-ray"],
        "PHP": [".php", "x-powered-by: php"],
        "Next.js": ["_next/", "__next"],
        "Gatsby": ["gatsby"],
        "Webflow": ["webflow.com"],
    }

    for tech, markers in patterns.items():
        if any(marker in html_lower for marker in markers):
            techs.append(tech)

    # Generator meta tag
    gen_match = re.search(r'<meta[^>]*name=["\']generator["\'][^>]*content=["\']([^"\']+)', html, re.I)
    if gen_match:
        gen = gen_match.group(1).strip()
        if gen and gen not in techs:
            techs.append(gen)

    return techs


def _extract_social_links(html: str) -> dict:
    """Extract social media URLs from HTML."""
    socials = {}
    patterns = {
        "linkedin": r'https?://(?:www\.)?linkedin\.com/(?:company|in)/[^\s"\'<>]+',
        "twitter": r'https?://(?:www\.)?(?:twitter|x)\.com/[^\s"\'<>]+',
        "facebook": r'https?://(?:www\.)?facebook\.com/[^\s"\'<>]+',
        "instagram": r'https?://(?:www\.)?instagram\.com/[^\s"\'<>]+',
        "youtube": r'https?://(?:www\.)?youtube\.com/[^\s"\'<>]+',
    }
    for platform, pattern in patterns.items():
        match = re.search(pattern, html, re.I)
        if match:
            socials[platform] = match.group(0)
    return socials


def _check_mobile_responsive(html: str) -> bool:
    """Check for viewport meta tag (mobile responsiveness indicator)."""
    return bool(re.search(r'<meta[^>]*name=["\']viewport["\']', html, re.I))
