"""
Aura — Scraper Engine
Multi-source scraper with DuckDuckGo → Google Maps → Yelp fallback chain.
Uses httpx + BeautifulSoup4 for lightweight scraping, Playwright for JS-heavy pages.
Browser fingerprint rotation on every launch.
"""

import re
import json
import random
import urllib.parse
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Callable

import httpx
from bs4 import BeautifulSoup

from core.safety_guard import SafetyGuard
from config import USER_AGENTS, SCRAPER_MIN_RESULTS_THRESHOLD, AGGREGATOR_KEYWORDS
from utils.logger import get_logger

logger = get_logger("scraper")


@dataclass
class ScrapedLead:
    """A single business lead discovered by the scraper."""
    business_name: str = ""
    category: str = ""
    address: str = ""
    city: str = ""
    country: str = ""
    phone: str = ""
    email: str = ""
    source_url: str = ""
    source_platform: str = ""
    has_website: bool = False
    website_url: str = ""
    snippet: str = ""  # Raw snippet text for Tier 2 analysis


class ScraperEngine:
    """
    Multi-source web scraper with fallback chain.
    Priority: DuckDuckGo → Google Maps → Yelp
    """

    def __init__(self, suppression_engine=None):
        self.safety = SafetyGuard()
        self._user_agent = random.choice(USER_AGENTS)
        self._session = None
        self._playwright_browser = None
        self._suppression = suppression_engine
        self._viewport_width = random.randint(1200, 1920)
        self._viewport_height = random.randint(768, 1080)

    def _get_headers(self) -> dict:
        """Generate realistic browser headers."""
        # Only advertise brotli when we can actually decode it — otherwise
        # servers that prefer br (e.g. DuckDuckGo) send bytes httpx cannot
        # decompress and every page parses as empty.
        try:
            import brotli  # noqa: F401
            accept_encoding = "gzip, deflate, br"
        except ImportError:
            accept_encoding = "gzip, deflate"
        return {
            "User-Agent": self._user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": accept_encoding,
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def run(
        self,
        query: str,
        city: str,
        niche: str,
        limit: int = 50,
        sources: List[str] = None,
        _progress_callback: Callable = None,
        _cancel_checker: Callable = None,
    ) -> List[ScrapedLead]:
        """
        Execute the scraping pipeline with fallback chain.

        Args:
            query: Search query string
            city: Target city
            niche: Business niche/category
            limit: Maximum number of leads to find
            sources: Ordered list of sources to try
            _progress_callback: Callback for progress updates (0-100)
            _cancel_checker: Callable returning True if cancelled

        Returns:
            List of ScrapedLead objects
        """
        if sources is None:
            sources = ["duckduckgo", "google_maps", "yelp"]

        self.safety.reset()
        all_leads = []
        search_query = f"{niche} {city}" if not query else query

        if _progress_callback:
            _progress_callback(0)

        for source_idx, source in enumerate(sources):
            if _cancel_checker and _cancel_checker():
                logger.info("Scraping cancelled by user.")
                break

            if self.safety.is_killed:
                logger.warning("Kill switch active. Stopping scrape.")
                break

            logger.info(f"Trying source: {source} (query: '{search_query}')")

            try:
                if source == "duckduckgo":
                    leads = self._scrape_duckduckgo(
                        search_query, city, niche, limit, _progress_callback, _cancel_checker
                    )
                elif source == "google_maps":
                    leads = self._scrape_google_maps(
                        search_query, city, niche, limit, _progress_callback, _cancel_checker
                    )
                elif source == "yelp":
                    leads = self._scrape_yelp(
                        search_query, city, niche, limit, _progress_callback, _cancel_checker
                    )
                else:
                    logger.warning(f"Unknown source: {source}")
                    continue

                all_leads.extend(leads)
                logger.info(f"Source '{source}' returned {len(leads)} leads.")

                # If we have enough results, stop
                if len(all_leads) >= limit:
                    all_leads = all_leads[:limit]
                    break

                # If this source gave decent results, don't fall back
                if len(leads) >= SCRAPER_MIN_RESULTS_THRESHOLD:
                    continue  # Still try other sources for variety

            except Exception as e:
                logger.error(f"Source '{source}' failed: {e}")
                # Fall through to next source

        if _progress_callback:
            _progress_callback(100)

        # Deduplicate by business name + city
        all_leads = self._deduplicate(all_leads)

        # Suppression list filter
        if self._suppression:
            before = len(all_leads)
            all_leads = [
                lead for lead in all_leads
                if not self._suppression.is_suppressed(email=lead.email)
            ]
            suppressed = before - len(all_leads)
            if suppressed:
                logger.info(f"Suppression filter removed {suppressed} leads")

        logger.info(f"Scraping complete. Total unique leads: {len(all_leads)}")
        return all_leads

    def _scrape_duckduckgo(
        self, query: str, city: str, niche: str, limit: int,
        progress_cb: Callable = None, cancel_checker: Callable = None,
    ) -> List[ScrapedLead]:
        """Scrape DuckDuckGo search results for business leads."""
        leads = []
        page = 0
        max_pages = min(limit // 5 + 1, 10)  # ~5 results per page

        with httpx.Client(headers=self._get_headers(), timeout=30, follow_redirects=True) as client:
            while len(leads) < limit and page < max_pages:
                if cancel_checker and cancel_checker():
                    break
                if self.safety.is_killed:
                    break

                # Human jitter before each request
                self.safety.human_jitter(cancel_checker)

                url = "https://html.duckduckgo.com/html/"
                params = {"q": query, "s": str(page * 30), "dc": str(page * 30 + 1)}

                try:
                    resp = client.post(url, data=params)

                    if resp.status_code in (403, 429):
                        killed = self.safety.report_failure(resp.status_code, "Rate limited")
                        if killed:
                            break
                        continue

                    if resp.status_code != 200:
                        self.safety.report_failure(resp.status_code, f"HTTP {resp.status_code}")
                        continue

                    self.safety.report_success()
                    soup = BeautifulSoup(resp.text, "html.parser")

                    results = soup.select(".result")
                    if not results:
                        logger.info(f"DuckDuckGo page {page}: no results found.")
                        break

                    for result in results:
                        if len(leads) >= limit:
                            break

                        lead = self._parse_ddg_result(result, city, niche)
                        if lead and self._passes_tier1(lead):
                            leads.append(lead)

                            if progress_cb:
                                pct = min(90, int((len(leads) / limit) * 90))
                                progress_cb(pct)

                except httpx.TimeoutException:
                    self.safety.report_failure(0, "Timeout")
                    logger.warning(f"DuckDuckGo timeout on page {page}")
                except Exception as e:
                    logger.error(f"DuckDuckGo error: {e}")
                    self.safety.report_failure(0, str(e))

                page += 1

        return leads

    def _parse_ddg_result(self, result, city: str, niche: str) -> Optional[ScrapedLead]:
        """Parse a single DuckDuckGo search result into a ScrapedLead."""
        try:
            title_elem = result.select_one(".result__title a, .result__a")
            snippet_elem = result.select_one(".result__snippet")
            url_elem = result.select_one(".result__url")

            if not title_elem:
                return None

            name = title_elem.get_text(strip=True)
            url = title_elem.get("href", "")
            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
            display_url = url_elem.get_text(strip=True) if url_elem else ""

            if not name or len(name) < 3:
                return None

            # Try to extract data from snippet
            phone = self._extract_phone(snippet)
            email = self._extract_email(snippet)

            # Determine if the URL is the business's own website
            has_website = bool(url) and not any(
                agg in url.lower() for agg in AGGREGATOR_KEYWORDS
            )

            lead = ScrapedLead(
                business_name=name,
                category=niche,
                city=city,
                phone=phone,
                email=email,
                source_url=url,
                source_platform="duckduckgo",
                has_website=has_website,
                website_url=url if has_website else "",
                snippet=snippet,
            )
            return lead

        except Exception as e:
            logger.debug(f"Failed to parse DDG result: {e}")
            return None

    def _scrape_google_maps(
        self, query: str, city: str, niche: str, limit: int,
        progress_cb: Callable = None, cancel_checker: Callable = None,
    ) -> List[ScrapedLead]:
        """
        Scrape Google Maps search results via the standard web interface.
        Falls back from DuckDuckGo when that source is insufficient.
        """
        leads = []

        with httpx.Client(headers=self._get_headers(), timeout=30, follow_redirects=True) as client:
            # Use Google search with Maps intent
            search_url = "https://www.google.com/search"
            params = {"q": f"{query} near {city}", "tbm": "lcl", "num": str(min(limit, 20))}

            if cancel_checker and cancel_checker():
                return leads
            if self.safety.is_killed:
                return leads

            self.safety.human_jitter(cancel_checker)

            try:
                resp = client.get(search_url, params=params)

                if resp.status_code in (403, 429):
                    self.safety.report_failure(resp.status_code, "Google blocked")
                    return leads

                if resp.status_code != 200:
                    self.safety.report_failure(resp.status_code, f"HTTP {resp.status_code}")
                    return leads

                self.safety.report_success()
                soup = BeautifulSoup(resp.text, "html.parser")

                # Parse local business results
                # Google local results appear in various div structures
                for div in soup.select("div.VkpGBb, div[data-hveid], div.rlfl__tls"):
                    if len(leads) >= limit:
                        break

                    name_elem = div.select_one("div.dbg0pd, span.OSrXXb, div.BNeawe")
                    if not name_elem:
                        continue

                    name = name_elem.get_text(strip=True)
                    if not name or len(name) < 3:
                        continue

                    # Extract address and other details from the text
                    full_text = div.get_text(" ", strip=True)
                    phone = self._extract_phone(full_text)

                    lead = ScrapedLead(
                        business_name=name,
                        category=niche,
                        city=city,
                        phone=phone,
                        source_platform="google_maps",
                        snippet=full_text,
                    )

                    if self._passes_tier1(lead):
                        leads.append(lead)

                        if progress_cb:
                            pct = min(90, int((len(leads) / limit) * 90))
                            progress_cb(pct)

            except httpx.TimeoutException:
                self.safety.report_failure(0, "Timeout")
            except Exception as e:
                logger.error(f"Google Maps error: {e}")
                self.safety.report_failure(0, str(e))

        return leads

    def _scrape_yelp(
        self, query: str, city: str, niche: str, limit: int,
        progress_cb: Callable = None, cancel_checker: Callable = None,
    ) -> List[ScrapedLead]:
        """Scrape Yelp search results for business leads."""
        leads = []
        page = 0
        max_pages = min(limit // 10 + 1, 5)

        city_slug = city.lower().replace(" ", "+")

        with httpx.Client(headers=self._get_headers(), timeout=30, follow_redirects=True) as client:
            while len(leads) < limit and page < max_pages:
                if cancel_checker and cancel_checker():
                    break
                if self.safety.is_killed:
                    break

                self.safety.human_jitter(cancel_checker)

                url = f"https://www.yelp.com/search"
                params = {
                    "find_desc": niche,
                    "find_loc": city,
                    "start": str(page * 10),
                }

                try:
                    resp = client.get(url, params=params)

                    if resp.status_code in (403, 429):
                        killed = self.safety.report_failure(resp.status_code, "Yelp blocked")
                        if killed:
                            break
                        continue

                    if resp.status_code != 200:
                        self.safety.report_failure(resp.status_code, f"HTTP {resp.status_code}")
                        continue

                    self.safety.report_success()
                    soup = BeautifulSoup(resp.text, "html.parser")

                    # Parse Yelp business results
                    results = soup.select('[data-testid="serp-ia-card"], div[class*="container__"] a[href*="/biz/"]')

                    if not results:
                        # Try alternative selectors
                        results = soup.select("li h3 a, div.businessName__ a")

                    if not results:
                        logger.info(f"Yelp page {page}: no results found.")
                        break

                    for result in results:
                        if len(leads) >= limit:
                            break

                        # Extract business name
                        if result.name == "a":
                            name = result.get_text(strip=True)
                            biz_url = result.get("href", "")
                        else:
                            name_elem = result.select_one("a[href*='/biz/'], h3, span")
                            if not name_elem:
                                continue
                            name = name_elem.get_text(strip=True)
                            biz_url = name_elem.get("href", "") if name_elem.name == "a" else ""

                        if not name or len(name) < 3:
                            continue

                        # Clean up Yelp relative URLs
                        if biz_url.startswith("/"):
                            biz_url = f"https://www.yelp.com{biz_url}"

                        # Get surrounding text for data
                        parent_text = result.parent.get_text(" ", strip=True) if result.parent else ""
                        phone = self._extract_phone(parent_text)

                        lead = ScrapedLead(
                            business_name=self._clean_business_name(name),
                            category=niche,
                            city=city,
                            phone=phone,
                            source_url=biz_url,
                            source_platform="yelp",
                            snippet=parent_text[:500],
                        )

                        if self._passes_tier1(lead):
                            leads.append(lead)

                            if progress_cb:
                                pct = min(90, int((len(leads) / limit) * 90))
                                progress_cb(pct)

                except httpx.TimeoutException:
                    self.safety.report_failure(0, "Timeout")
                except Exception as e:
                    logger.error(f"Yelp error: {e}")
                    self.safety.report_failure(0, str(e))

                page += 1

        return leads

    # ─── Tier 1: The Doorman (pure Python, zero AI) ───────────────────

    def _passes_tier1(self, lead: ScrapedLead) -> bool:
        """
        Tier 1 — The Doorman. Zero-cost Python check.
        Returns True if lead passes all basic filters.
        """
        name_lower = lead.business_name.lower()

        # Check against aggregator keywords
        for keyword in AGGREGATOR_KEYWORDS:
            if keyword in name_lower:
                logger.debug(f"Tier 1 REJECT (aggregator): {lead.business_name}")
                return False

        # Check if name is too short or too generic
        if len(lead.business_name.strip()) < 3:
            return False

        # Check if it's just a number
        if lead.business_name.strip().isdigit():
            return False

        # If email is present, validate format
        if lead.email and not self._is_valid_email(lead.email):
            lead.email = ""  # Clear invalid email, but don't reject the lead

        return True

    # ─── Utility Methods ──────────────────────────────────────────────

    @staticmethod
    def _extract_phone(text: str) -> str:
        """Extract phone number from text using regex."""
        patterns = [
            r'\+?1?\s*\(?(\d{3})\)?[\s.-]*(\d{3})[\s.-]*(\d{4})',  # US: (555) 123-4567
            r'\+?\d{1,4}[\s.-]?\(?\d{1,5}\)?[\s.-]?\d{2,4}[\s.-]?\d{2,4}[\s.-]?\d{0,4}',  # International
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0).strip()
        return ""

    @staticmethod
    def _extract_email(text: str) -> str:
        """Extract email address from text using regex."""
        match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        return match.group(0) if match else ""

    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """Validate basic email format."""
        return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))

    @staticmethod
    def _clean_business_name(name: str) -> str:
        """Clean up business name — remove numbering, extra whitespace."""
        # Remove leading numbers like "1. " or "1 - "
        name = re.sub(r'^\d+[\s.)-]+', '', name)
        # Remove extra whitespace
        name = ' '.join(name.split())
        return name.strip()

    @staticmethod
    def _deduplicate(leads: List[ScrapedLead]) -> List[ScrapedLead]:
        """Remove duplicate leads based on business name similarity."""
        seen = set()
        unique = []
        for lead in leads:
            key = lead.business_name.lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(lead)
        return unique
