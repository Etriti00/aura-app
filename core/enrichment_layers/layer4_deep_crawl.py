"""
Aura v2.0 — Layer 4: Deep Crawl + LLM Synthesis
Multi-page Playwright crawl of key site pages, then Ollama-powered synthesis.
Only triggered when completeness score < ENRICHMENT_COMPLETENESS_THRESHOLD.
"""

import json
import re

from config import ENRICHMENT_COMPLETENESS_THRESHOLD
from utils.logger import get_logger

logger = get_logger(__name__)

# Target subpages for deep crawl
_TARGET_PATHS = ["/about", "/contact", "/team", "/services", "/pricing",
                 "/about-us", "/our-team", "/our-services"]


def enrich_layer4_sync(domain: str, completeness_score: float,
                       router_engine=None) -> dict:
    """Synchronous deep crawl using sync Playwright."""
    if completeness_score >= ENRICHMENT_COMPLETENESS_THRESHOLD:
        return {}

    result = {}
    page_contents = {}
    base_url = f"https://{domain}"

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                for path in _TARGET_PATHS:
                    url = f"{base_url}{path}"
                    try:
                        resp = page.goto(url, wait_until="domcontentloaded", timeout=10000)
                        if resp and resp.status == 200:
                            text = page.evaluate("() => document.body.innerText")
                            if text and len(text.strip()) > 50:
                                page_contents[path] = text[:5000]
                    except Exception:
                        continue
            finally:
                browser.close()
    except ImportError:
        logger.debug("Playwright not available for Layer 4 deep crawl")
        return result
    except Exception as e:
        logger.debug(f"Deep crawl browser failed: {e}")

    if not page_contents:
        return result

    # Extract emails
    all_text = "\n".join(page_contents.values())
    emails = _extract_emails(all_text)
    if emails:
        result["email_source"] = f"deep_crawl:{','.join(page_contents.keys())}"

    # LLM synthesis
    if router_engine:
        combined = ""
        for path, content in page_contents.items():
            combined += f"\n--- Page: {path} ---\n{content[:2000]}\n"
        prompt = (
            f"Summarize this business ({domain}) based on these pages:\n"
            f"{combined[:6000]}\n\n"
            f"Provide: 1) What the business does 2) Key decision makers 3) Services 4) Pain points"
        )
        try:
            response = router_engine.route("summarize_webpage", prompt)
            if response and response.get("success"):
                result["deep_crawl_summary"] = (response.get("data", "") or response.get("result", ""))[:3000]
        except Exception as e:
            logger.debug(f"Layer 4 synthesis failed: {e}")

    result["data_sources"] = json.dumps([f"crawl:{p}" for p in page_contents.keys()])
    return result


async def enrich_layer4(domain: str, completeness_score: float,
                        browser_page=None, router_engine=None) -> dict:
    """Deep crawl key pages and synthesize with LLM.

    Args:
        domain: The domain to crawl
        completeness_score: Current enrichment completeness (0-100)
        browser_page: Playwright page object (optional, from enrichment_engine batch)
        router_engine: For LLM synthesis

    Returns:
        dict with deep_crawl_summary, potentially email_source, decision_maker_*
    """
    if completeness_score >= ENRICHMENT_COMPLETENESS_THRESHOLD:
        logger.debug(f"Skipping Layer 4: completeness {completeness_score} >= {ENRICHMENT_COMPLETENESS_THRESHOLD}")
        return {}

    if not browser_page:
        logger.debug("No browser page for Layer 4 deep crawl")
        return {}

    result = {}
    page_contents = {}

    base_url = f"https://{domain}"

    for path in _TARGET_PATHS:
        url = f"{base_url}{path}"
        content = await _crawl_page(browser_page, url)
        if content:
            page_contents[path] = content

    if not page_contents:
        return result

    # Extract emails from all crawled pages
    all_text = "\n".join(page_contents.values())
    emails = _extract_emails(all_text)
    if emails:
        result["email_source"] = f"deep_crawl:{','.join(page_contents.keys())}"

    # LLM synthesis
    if router_engine:
        summary = await _synthesize(page_contents, domain, router_engine)
        if summary:
            result["deep_crawl_summary"] = summary

    result["data_sources"] = json.dumps(
        [f"crawl:{p}" for p in page_contents.keys()]
    )

    return result


async def _crawl_page(page, url: str) -> str:
    """Navigate to URL and extract text content."""
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=10000)
        if response and response.status == 200:
            text = await page.evaluate("() => document.body.innerText")
            if text and len(text.strip()) > 50:
                return text[:5000]  # Cap per page
    except Exception as e:
        logger.debug(f"Deep crawl failed for {url}: {e}")
    return ""


def _extract_emails(text: str) -> list[str]:
    """Extract email addresses from text."""
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    found = re.findall(pattern, text)
    # Filter out common false positives
    filtered = [
        e for e in set(found)
        if not any(x in e.lower() for x in [
            "example.com", "test.com", "email.com", "domain.com",
            "sentry.io", "wixpress", "googleapis",
        ])
    ]
    return filtered[:5]


async def _synthesize(pages: dict, domain: str, router_engine) -> str:
    """Use LLM to synthesize multi-page content into a summary."""
    combined = ""
    for path, content in pages.items():
        combined += f"\n--- Page: {path} ---\n{content[:2000]}\n"

    prompt = (
        f"Summarize this business ({domain}) based on these pages:\n"
        f"{combined[:6000]}\n\n"
        f"Provide a 2-3 paragraph summary covering:\n"
        f"1. What the business does\n"
        f"2. Key decision makers (if found)\n"
        f"3. Services/products offered\n"
        f"4. Potential pain points or needs"
    )

    try:
        import asyncio
        response = await asyncio.to_thread(
            router_engine.route, "summarize_webpage", prompt
        )
        if response and response.get("success"):
            return (response.get("data", "") or response.get("result", ""))[:3000]
    except Exception as e:
        logger.debug(f"Layer 4 synthesis failed: {e}")

    return ""
