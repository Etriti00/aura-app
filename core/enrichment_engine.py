"""
Aura — Lead Enrichment Engine
Enriches leads with Google Maps data, domain age, social presence,
and website screenshots using Playwright + httpx.
"""

import json
import os
import re
import hashlib
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

import httpx

from config import ASSETS_DIR, DATA_DIR
from database.db_manager import DatabaseManager
from database.schema import EnrichmentData, Lead
from utils.logger import get_logger

logger = get_logger("enrichment_engine")

# Screenshot directory
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


class EnrichmentEngine:
    """Enriches leads with external data: GMaps, WHOIS, social, screenshots."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.apollo_engine = None
        self.hunter_engine = None
        self.lead_lifecycle_engine = None  # injected by main_window
        self.knowledge_graph_engine = None  # injected by main_window
        self.router_engine = None  # injected by main_window
        self.case_engine = None    # injected by main_window
        self.key_vault = None      # injected by main_window
        # Persistent browser for batch operations
        self._batch_playwright = None
        self._batch_browser = None

    # ─── Browser lifecycle management ──────────────────────────────

    @contextmanager
    def _browser_context(self):
        """Context manager that yields a Playwright browser page.
        Uses the batch browser if available, otherwise launches a one-shot browser
        with guaranteed cleanup."""
        if self._batch_browser:
            page = self._batch_browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                from playwright_stealth import stealth_sync
                stealth_sync(page)
            except ImportError:
                pass
            try:
                yield page
            finally:
                page.close()
            return

        from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
        browser = None
        try:
            browser = pw.chromium.launch(headless=True)
            # Apply stealth if available
            try:
                from playwright_stealth import stealth_sync
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                stealth_sync(page)
            except ImportError:
                page = browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                yield page
            finally:
                page.close()
        finally:
            if browser:
                browser.close()
            pw.stop()

    def start_batch(self):
        """Start a persistent browser for batch screenshot operations."""
        if self._batch_browser:
            return
        from playwright.sync_api import sync_playwright
        self._batch_playwright = sync_playwright().start()
        self._batch_browser = self._batch_playwright.chromium.launch(headless=True)
        logger.info("Batch browser started")

    def end_batch(self):
        """Close the persistent batch browser."""
        if self._batch_browser:
            try:
                self._batch_browser.close()
            except Exception:
                pass
            self._batch_browser = None
        if self._batch_playwright:
            try:
                self._batch_playwright.stop()
            except Exception:
                pass
            self._batch_playwright = None
        logger.debug("Batch browser closed")

    def enrich_lead(self, lead_dict: dict) -> dict:
        """
        Orchestrate all enrichment checks for a lead.
        Returns a combined enrichment result dict.
        """
        result = {
            "google_maps_rating": None,
            "google_maps_review_count": None,
            "domain_age_years": None,
            "has_facebook": False,
            "has_instagram": False,
            "has_linkedin": False,
            "website_screenshot_path": None,
        }

        business_name = lead_dict.get("business_name", "")
        city = lead_dict.get("city", "")
        website_url = lead_dict.get("website_url", "")

        # Google Maps presence
        try:
            gmaps = self._check_google_maps_presence(business_name, city)
            result["google_maps_rating"] = gmaps.get("rating")
            result["google_maps_review_count"] = gmaps.get("review_count")
        except Exception as e:
            logger.warning(f"Google Maps enrichment failed: {e}")

        # Domain age
        if website_url:
            try:
                domain_info = self._check_domain_age(website_url)
                result["domain_age_years"] = domain_info.get("domain_age_years")
            except Exception as e:
                logger.warning(f"Domain age check failed: {e}")

        # Social presence
        try:
            social = self._check_social_presence(business_name, city)
            result["has_facebook"] = social.get("has_facebook", False)
            result["has_instagram"] = social.get("has_instagram", False)
            result["has_linkedin"] = social.get("has_linkedin", False)
        except Exception as e:
            logger.warning(f"Social presence check failed: {e}")

        # Website screenshot
        if website_url:
            try:
                lead_id = lead_dict.get("id", 0)
                path = self._capture_website_screenshot(website_url, lead_id)
                result["website_screenshot_path"] = path
            except Exception as e:
                logger.warning(f"Screenshot capture failed: {e}")

        return result

    def _check_google_maps_presence(self, business_name: str, city: str) -> dict:
        """
        Check Google Maps for business rating and review count.
        Uses httpx to query a Maps search page.
        """
        try:
            query = f"{business_name} {city}"
            url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"

            with httpx.Client(timeout=15, follow_redirects=True) as client:
                resp = client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })

            # Parse rating from response text
            text = resp.text
            rating_match = re.search(r'(\d\.\d)\s*stars?', text)
            review_match = re.search(r'(\d[\d,]*)\s*reviews?', text)

            rating = float(rating_match.group(1)) if rating_match else None
            reviews = int(review_match.group(1).replace(",", "")) if review_match else None

            return {
                "rating": rating,
                "review_count": reviews,
                "claimed": rating is not None,
            }
        except Exception as e:
            logger.warning(f"Google Maps check failed for {business_name}: {e}")
            return {"rating": None, "review_count": None, "claimed": False}

    def _check_domain_age(self, website_url: str) -> dict:
        """
        Check domain age using WHOIS API.
        Falls back gracefully if API is unavailable.
        """
        try:
            # Extract domain from URL
            domain = re.sub(r'^https?://', '', website_url).split('/')[0].strip()
            if not domain:
                return {"domain_age_years": None}

            url = f"https://whoisjson.com/api/v1/whois?domain={domain}"
            with httpx.Client(timeout=10) as client:
                resp = client.get(url)

            if resp.status_code == 200:
                data = resp.json()
                created = data.get("created", "") or data.get("creation_date", "")
                if created:
                    # Parse creation date
                    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d-%b-%Y"):
                        try:
                            dt = datetime.strptime(created[:19], fmt)
                            age = (datetime.utcnow() - dt).days / 365.25
                            return {"domain_age_years": round(age, 1)}
                        except ValueError:
                            continue

            return {"domain_age_years": None}
        except Exception as e:
            logger.warning(f"Domain age check failed: {e}")
            return {"domain_age_years": None}

    def _check_social_presence(self, business_name: str, city: str) -> dict:
        """
        Check for social media presence using DuckDuckGo search.
        """
        result = {"has_facebook": False, "has_instagram": False, "has_linkedin": False}

        try:
            query = f"{business_name} {city}"
            url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"

            with httpx.Client(timeout=10, follow_redirects=True) as client:
                resp = client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })

            text = resp.text.lower()
            result["has_facebook"] = "facebook.com" in text
            result["has_instagram"] = "instagram.com" in text
            result["has_linkedin"] = "linkedin.com" in text

        except Exception as e:
            logger.warning(f"Social presence check failed: {e}")

        return result

    def _capture_website_screenshot(self, url: str, lead_id: int) -> Optional[str]:
        """
        Capture a screenshot of the lead's website using Playwright.
        Browser cleanup guaranteed via _browser_context.
        Returns the file path or None.
        """
        try:
            filename = f"{lead_id}.png"
            filepath = str(SCREENSHOTS_DIR / filename)

            # Check cache
            if os.path.exists(filepath):
                return filepath

            with self._browser_context() as page:
                page.goto(url, timeout=15000, wait_until="domcontentloaded")
                page.screenshot(path=filepath, full_page=False)

            logger.info(f"Screenshot saved: {filepath}")
            return filepath
        except Exception as e:
            logger.warning(f"Screenshot capture failed for {url}: {e}")
            return None

    def get_competitor_screenshot(self, niche: str, city: str) -> Optional[str]:
        """
        Get a screenshot of a competitor website for leads without their own site.
        Caches by niche+city to avoid re-scraping.
        """
        try:
            cache_key = hashlib.md5(f"{niche}_{city}".encode()).hexdigest()[:12]
            filename = f"competitor_{cache_key}.png"
            filepath = str(SCREENSHOTS_DIR / filename)

            # Check cache
            if os.path.exists(filepath):
                return filepath

            # Search DuckDuckGo for a competitor site
            query = f"{niche} website {city}"
            url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"

            with httpx.Client(timeout=10, follow_redirects=True) as client:
                resp = client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })

            # Extract first non-directory result URL
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "lxml")
            skip_domains = {"yelp.com", "yellowpages.com", "facebook.com", "tripadvisor.com"}

            target_url = None
            for link in soup.select("a.result__url"):
                href = link.get("href", "")
                if any(d in href for d in skip_domains):
                    continue
                if href.startswith("http"):
                    target_url = href
                    break

            if not target_url:
                return None

            # Screenshot the competitor site
            with self._browser_context() as page:
                page.goto(target_url, timeout=15000, wait_until="domcontentloaded")
                page.screenshot(path=filepath, full_page=False)

            logger.info(f"Competitor screenshot saved: {filepath}")
            return filepath
        except Exception as e:
            logger.warning(f"Competitor screenshot failed: {e}")
            return None

    def save_enrichment(self, lead_id: int, enrichment_data: dict) -> dict:
        """Save or update enrichment data for a lead."""
        try:
            with self.db_manager.session_scope() as session:
                existing = session.query(EnrichmentData).filter_by(lead_id=lead_id).first()
                if existing:
                    for key, val in enrichment_data.items():
                        if hasattr(existing, key) and val is not None:
                            setattr(existing, key, val)
                    existing.enriched_at = datetime.utcnow()
                else:
                    record = EnrichmentData(
                        lead_id=lead_id,
                        google_maps_rating=enrichment_data.get("google_maps_rating"),
                        google_maps_review_count=enrichment_data.get("google_maps_review_count"),
                        domain_age_years=enrichment_data.get("domain_age_years"),
                        has_facebook=enrichment_data.get("has_facebook", False),
                        has_instagram=enrichment_data.get("has_instagram", False),
                        has_linkedin=enrichment_data.get("has_linkedin", False),
                        website_screenshot_path=enrichment_data.get("website_screenshot_path"),
                        enriched_at=datetime.utcnow(),
                    )
                    session.add(record)

                return {"success": True, "data": {"lead_id": lead_id}}
        except Exception as e:
            logger.error(f"Error saving enrichment: {e}")
            return {"success": False, "error": str(e)}

    def format_enrichment_summary(self, enrichment: dict) -> str:
        """Format enrichment data as a human-readable summary for AI prompts."""
        parts = []

        rating = enrichment.get("google_maps_rating")
        reviews = enrichment.get("google_maps_review_count")
        if rating:
            parts.append(f"This business has {reviews or 0} Google reviews ({rating} stars)")

        age = enrichment.get("domain_age_years")
        if age:
            parts.append(f"a {age}-year-old domain")

        social = []
        if enrichment.get("has_facebook"):
            social.append("Facebook")
        if enrichment.get("has_instagram"):
            social.append("Instagram")
        if enrichment.get("has_linkedin"):
            social.append("LinkedIn")

        if social:
            parts.append(f"presence on {', '.join(social)}")
        else:
            parts.append("no social media presence found")

        return ". ".join(parts) + "." if parts else ""

    # ─── Waterfall Enrichment ──────────────────────────────────────

    def waterfall_enrich_lead(self, lead_id: int) -> dict:
        """5-layer waterfall enrichment. Each layer fills gaps left by previous ones."""
        try:
            with self.db_manager.session_scope() as session:
                lead = session.query(Lead).filter_by(id=lead_id).first()
                if not lead:
                    return {"success": False, "error": "Lead not found"}
                lead_dict = {
                    "id": lead.id,
                    "business_name": lead.business_name or "",
                    "city": lead.city or "",
                    "website_url": lead.website_url or "",
                    "email": lead.email or "",
                    "phone": lead.phone or "",
                    "category": lead.category or "",
                }

            sources_tried = []
            enrichment_data = {}
            email_found = bool(lead_dict.get("email"))
            domain = ""
            if lead_dict.get("website_url"):
                domain = re.sub(r'^https?://', '', lead_dict["website_url"]).split('/')[0].strip()

            # ── Layer 0: DNS/WHOIS/SSL/Tech Stack (free, instant) ──
            if domain:
                try:
                    from core.enrichment_layers.layer0_dns import enrich_layer0
                    homepage_html = ""
                    try:
                        with httpx.Client(timeout=10, follow_redirects=True) as client:
                            resp = client.get(f"https://{domain}", headers={"User-Agent": "Mozilla/5.0"})
                            if resp.status_code == 200:
                                homepage_html = resp.text
                    except Exception:
                        pass
                    layer0 = enrich_layer0(domain, homepage_html)
                    enrichment_data.update(layer0)
                    enrichment_data["_homepage_html"] = homepage_html
                    sources_tried.append("layer0_dns")
                    self._log_case_event(lead_id, "enrichment", f"Layer 0 completed: {list(layer0.keys())}")
                except Exception as e:
                    logger.warning(f"Layer 0 failed for lead {lead_id}: {e}")

            # ── Layer 1: Ollama LLM extraction (free, local) ──
            if domain and self.router_engine:
                try:
                    from core.enrichment_layers.layer1_ollama import enrich_layer1_sync
                    homepage_html = enrichment_data.get("_homepage_html", "")
                    if not homepage_html:
                        try:
                            with httpx.Client(timeout=10, follow_redirects=True) as client:
                                resp = client.get(f"https://{domain}", headers={"User-Agent": "Mozilla/5.0"})
                                if resp.status_code == 200:
                                    homepage_html = resp.text
                        except Exception:
                            pass
                    if homepage_html:
                        layer1 = enrich_layer1_sync(homepage_html, lead_dict["business_name"], self.router_engine)
                        enrichment_data.update(layer1)
                        sources_tried.append("layer1_ollama")
                        self._log_case_event(lead_id, "enrichment", f"Layer 1 completed: {list(layer1.keys())}")
                except Exception as e:
                    logger.warning(f"Layer 1 failed for lead {lead_id}: {e}")

            # ── Layer 2: Free APIs (Google Maps, Clearbit) ──
            if domain or lead_dict.get("business_name"):
                try:
                    from core.enrichment_layers.layer2_free_apis import enrich_layer2_sync
                    gmaps_key = ""
                    try:
                        from database.schema import Settings
                        with self.db_manager.session_scope() as session:
                            settings = session.query(Settings).first()
                            if settings and settings.gmaps_api_key_enc and self.key_vault:
                                gmaps_key = self.key_vault.decrypt(settings.gmaps_api_key_enc) or ""
                    except Exception:
                        pass
                    layer2 = enrich_layer2_sync(
                        domain, lead_dict["business_name"], lead_dict.get("city", ""),
                        gmaps_api_key=gmaps_key, db_manager=self.db_manager,
                    )
                    enrichment_data.update(layer2)
                    sources_tried.append("layer2_free_apis")
                    if layer2.get("gmaps_phone") and not lead_dict.get("phone"):
                        with self.db_manager.session_scope() as session:
                            db_lead = session.query(Lead).filter_by(id=lead_id).first()
                            if db_lead:
                                db_lead.phone = layer2["gmaps_phone"]
                    self._log_case_event(lead_id, "enrichment", f"Layer 2 completed: {list(layer2.keys())}")
                except Exception as e:
                    logger.warning(f"Layer 2 failed for lead {lead_id}: {e}")

            # ── Local enrichment (GMaps scrape, domain age, social, screenshot) ──
            local_result = self.enrich_lead(lead_dict)
            enrichment_data.update({k: v for k, v in local_result.items() if v is not None})
            sources_tried.append("local")

            # Remove internal keys before saving
            enrichment_data.pop("_homepage_html", None)

            # Save enrichment data so far
            self.save_enrichment(lead_id, enrichment_data)

            # ── Layer 3: Paid APIs — Apollo then Hunter (only if no email) ──
            if not email_found and self.apollo_engine:
                try:
                    apollo_result = self.apollo_engine.search_people(
                        niche=lead_dict["business_name"], city=lead_dict["city"], limit=1,
                    )
                    sources_tried.append("apollo")
                    if apollo_result.get("success") and apollo_result.get("data"):
                        people = apollo_result["data"]
                        if people and people[0].get("email"):
                            with self.db_manager.session_scope() as session:
                                db_lead = session.query(Lead).filter_by(id=lead_id).first()
                                if db_lead:
                                    db_lead.email = people[0]["email"]
                                    if people[0].get("phone") and not db_lead.phone:
                                        db_lead.phone = people[0]["phone"]
                            email_found = True
                            enrichment_data["email_source"] = "apollo"
                            self._log_case_event(lead_id, "enrichment", "Layer 3: Apollo found email")
                except Exception as e:
                    logger.warning(f"Layer 3 Apollo failed for lead {lead_id}: {e}")

            if not email_found and self.hunter_engine and domain:
                try:
                    hunter_result = self.hunter_engine.domain_search(domain)
                    sources_tried.append("hunter")
                    if hunter_result.get("success") and hunter_result.get("data"):
                        emails = hunter_result["data"]
                        if emails:
                            with self.db_manager.session_scope() as session:
                                db_lead = session.query(Lead).filter_by(id=lead_id).first()
                                if db_lead:
                                    db_lead.email = emails[0].get("email", "")
                            email_found = True
                            enrichment_data["email_source"] = "hunter"
                            self._log_case_event(lead_id, "enrichment", "Layer 3: Hunter found email")
                except Exception as e:
                    logger.warning(f"Layer 3 Hunter failed for lead {lead_id}: {e}")

            # ── Calculate completeness score ──
            from core.enrichment_scoring import calculate_completeness
            score_input = dict(enrichment_data)
            with self.db_manager.session_scope() as session:
                db_lead = session.query(Lead).filter_by(id=lead_id).first()
                if db_lead:
                    score_input["email"] = db_lead.email or ""
                    score_input["phone"] = db_lead.phone or ""
            completeness = calculate_completeness(score_input)

            # ── Layer 4: Deep crawl (only if score < threshold) ──
            from config import ENRICHMENT_COMPLETENESS_THRESHOLD
            if completeness < ENRICHMENT_COMPLETENESS_THRESHOLD and domain:
                try:
                    from core.enrichment_layers.layer4_deep_crawl import enrich_layer4_sync
                    layer4 = enrich_layer4_sync(domain, completeness, self.router_engine)
                    enrichment_data.update(layer4)
                    sources_tried.append("layer4_deep_crawl")
                    score_input.update(layer4)
                    completeness = calculate_completeness(score_input)
                    self._log_case_event(lead_id, "enrichment", f"Layer 4 deep crawl completed, score now {completeness}")
                except Exception as e:
                    logger.warning(f"Layer 4 failed for lead {lead_id}: {e}")

            # ── Persist completeness score ──
            with self.db_manager.session_scope() as session:
                db_lead = session.query(Lead).filter_by(id=lead_id).first()
                if db_lead:
                    db_lead.data_completeness_score = completeness

            # Save final enrichment data with data_sources
            enrichment_data["data_sources"] = json.dumps(sources_tried)
            self.save_enrichment(lead_id, enrichment_data)

            # ─── Post-enrichment hooks ───
            if self.lead_lifecycle_engine:
                try:
                    self.lead_lifecycle_engine.transition(
                        lead_id=lead_id, to_state="researched",
                        triggered_by="enrichment_engine",
                        metadata={"sources": sources_tried, "email_found": email_found, "completeness": completeness},
                    )
                except Exception:
                    pass

            if self.knowledge_graph_engine:
                try:
                    node_key = lead_dict.get("business_name", "").lower().replace(" ", "_")
                    if node_key:
                        self.knowledge_graph_engine.upsert_node(
                            node_type="company", node_key=node_key,
                            display_name=lead_dict.get("business_name", ""),
                            properties={
                                "city": lead_dict.get("city", ""),
                                "rating": enrichment_data.get("google_maps_rating"),
                                "reviews": enrichment_data.get("google_maps_review_count"),
                                "domain_age": enrichment_data.get("domain_age_years"),
                                "completeness": completeness,
                            },
                        )
                except Exception:
                    pass

            return {
                "success": True, "lead_id": lead_id, "email_found": email_found,
                "sources_tried": sources_tried, "completeness_score": completeness,
            }

        except Exception as e:
            logger.error(f"Waterfall enrichment failed for lead {lead_id}: {e}")
            return {"success": False, "error": str(e)}

    def _log_case_event(self, lead_id: int, event_type: str, description: str):
        """Log an enrichment event to case notes if case_engine is available."""
        if self.case_engine:
            try:
                self.case_engine.add_note(lead_id=lead_id, note_type=event_type, content=description, created_by="Enricher")
            except Exception:
                pass

    def waterfall_enrich_campaign(self, campaign_id: int) -> dict:
        """
        Run waterfall enrichment on all leads in a campaign that lack email.
        Returns summary stats.
        """
        try:
            with self.db_manager.session_scope() as session:
                leads = session.query(Lead).filter_by(
                    campaign_id=campaign_id
                ).filter(
                    (Lead.email == None) | (Lead.email == "")
                ).all()
                lead_ids = [l.id for l in leads]

            if not lead_ids:
                return {"success": True, "enriched": 0, "emails_found": 0, "message": "All leads already have emails"}

            enriched = 0
            emails_found = 0
            for lid in lead_ids:
                result = self.waterfall_enrich_lead(lid)
                if result.get("success"):
                    enriched += 1
                    if result.get("email_found"):
                        emails_found += 1

            return {
                "success": True,
                "enriched": enriched,
                "emails_found": emails_found,
                "total_attempted": len(lead_ids),
            }

        except Exception as e:
            logger.error(f"Campaign waterfall enrichment failed: {e}")
            return {"success": False, "error": str(e)}
