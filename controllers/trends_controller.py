"""
Aura — Trends Controller
UI-facing controller for Google Trends: keyword analysis, opportunity discovery,
campaign monitoring, and alert management.
"""

from PySide6.QtCore import QObject, Signal

from database.db_manager import DatabaseManager
from core.trends_engine import TrendsEngine
from utils.logger import get_logger

logger = get_logger("trends_controller")


class TrendsController(QObject):
    """Bridges the TrendsEngine to the UI layer."""

    interest_ready = Signal(dict)
    related_ready = Signal(dict)
    topics_ready = Signal(dict)
    regions_ready = Signal(dict)
    opportunities_ready = Signal(dict)
    campaign_monitor_ready = Signal(dict)
    alerts_ready = Signal(dict)
    error = Signal(str)

    def __init__(self, db_manager: DatabaseManager, trends_engine: TrendsEngine):
        super().__init__()
        self.db_manager = db_manager
        self.trends = trends_engine

    # ─── Keyword analysis ─────────────────────────────────────────────

    def fetch_interest(self, keywords: list, region: str = "US",
                       timeframe: str = None):
        """Fetch interest-over-time data for keywords."""
        try:
            result = self.trends.fetch_interest_over_time(
                keywords, region, timeframe
            )
            self.interest_ready.emit(result)
        except Exception as e:
            logger.error(f"Fetch interest error: {e}")
            self.error.emit(str(e))

    def fetch_related_queries(self, keyword: str, region: str = "US"):
        """Fetch related queries for a keyword."""
        try:
            result = self.trends.fetch_related_queries(keyword, region)
            self.related_ready.emit(result)
        except Exception as e:
            logger.error(f"Fetch related queries error: {e}")
            self.error.emit(str(e))

    def fetch_related_topics(self, keyword: str, region: str = "US"):
        """Fetch related topics for a keyword."""
        try:
            result = self.trends.fetch_related_topics(keyword, region)
            self.topics_ready.emit(result)
        except Exception as e:
            logger.error(f"Fetch topics error: {e}")
            self.error.emit(str(e))

    def fetch_regions(self, keyword: str, region: str = "",
                      resolution: str = "COUNTRY"):
        """Fetch interest by region."""
        try:
            result = self.trends.fetch_interest_by_region(
                keyword, region, resolution
            )
            self.regions_ready.emit(result)
        except Exception as e:
            logger.error(f"Fetch regions error: {e}")
            self.error.emit(str(e))

    def compare_keywords(self, keywords: list, region: str = "US",
                         timeframe: str = None):
        """Compare multiple keywords."""
        try:
            result = self.trends.compare_keywords(keywords, region, timeframe)
            self.interest_ready.emit(result)
        except Exception as e:
            logger.error(f"Compare keywords error: {e}")
            self.error.emit(str(e))

    def detect_direction(self, keyword: str, region: str = "US"):
        """Analyze trend direction for a keyword."""
        try:
            result = self.trends.detect_trend_direction(keyword, region)
            self.interest_ready.emit(result)
        except Exception as e:
            logger.error(f"Detect direction error: {e}")
            self.error.emit(str(e))

    # ─── Opportunity discovery ────────────────────────────────────────

    def find_opportunities(self, seed_keywords: list, region: str = "US"):
        """Discover rising niches not yet targeted."""
        try:
            result = self.trends.find_opportunity_niches(seed_keywords, region)
            self.opportunities_ready.emit(result)
        except Exception as e:
            logger.error(f"Opportunity discovery error: {e}")
            self.error.emit(str(e))

    # ─── Campaign monitoring ──────────────────────────────────────────

    def monitor_campaign(self, campaign_id: int):
        """Monitor trends for a specific campaign."""
        try:
            result = self.trends.monitor_campaign_keywords(campaign_id)
            self.campaign_monitor_ready.emit(result)
        except Exception as e:
            logger.error(f"Campaign monitor error: {e}")
            self.error.emit(str(e))

    def run_scheduled_checks(self):
        """Run trend checks for all active campaigns."""
        try:
            result = self.trends.schedule_trend_checks()
            self.campaign_monitor_ready.emit(result)
        except Exception as e:
            logger.error(f"Scheduled checks error: {e}")
            self.error.emit(str(e))

    # ─── Alerts ───────────────────────────────────────────────────────

    def refresh_alerts(self, unread_only: bool = True):
        """Load trend alerts."""
        try:
            result = self.trends.get_alerts(unread_only)
            self.alerts_ready.emit(result)
        except Exception as e:
            logger.error(f"Refresh alerts error: {e}")
            self.error.emit(str(e))

    def acknowledge_alert(self, alert_id: int):
        """Acknowledge a trend alert."""
        try:
            self.trends.acknowledge_alert(alert_id)
            self.refresh_alerts()
        except Exception as e:
            logger.error(f"Acknowledge alert error: {e}")
            self.error.emit(str(e))
