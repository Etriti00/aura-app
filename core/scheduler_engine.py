"""
Aura — Scheduler Engine
Timezone-aware email scheduling. Detects lead timezone from city,
calculates optimal 9am send time, and manages the scheduled send queue.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import ASSETS_DIR
from database.db_manager import DatabaseManager
from database.schema import Lead
from utils.logger import get_logger

logger = get_logger("scheduler_engine")

# Path to bundled timezone data
TIMEZONE_FILE = ASSETS_DIR / "city_timezones.json"


class SchedulerEngine:
    """Handles timezone detection and scheduled sending."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self._tz_data = self._load_timezone_data()

    def _load_timezone_data(self) -> dict:
        """Load the bundled city timezone JSON."""
        try:
            if TIMEZONE_FILE.exists():
                with open(TIMEZONE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            logger.warning(f"Timezone file not found at {TIMEZONE_FILE}")
            return {}
        except Exception as e:
            logger.error(f"Error loading timezone data: {e}")
            return {}

    def detect_timezone_offset(self, city: str, country: str = "") -> int:
        """
        Detect UTC offset for a city using local lookup.
        Falls back to 0 (UTC) if city not found.
        Returns integer UTC offset in hours.
        """
        if not city:
            return 0

        # Try various key formats
        city_lower = city.lower().strip()
        country_lower = (country or "").lower().strip()

        keys_to_try = [
            f"{city_lower}_{country_lower}" if country_lower else None,
            city_lower,
            f"{city_lower}_",  # Partial match
        ]

        for key in keys_to_try:
            if key and key in self._tz_data:
                return self._tz_data[key]

        # Fuzzy match: check if city appears in any key
        for key, offset in self._tz_data.items():
            if city_lower in key:
                return offset

        logger.info(f"No timezone data for {city}, {country} — defaulting to UTC")
        return 0

    def calculate_optimal_send_time(self, timezone_offset: int) -> datetime:
        """
        Calculate the next occurrence of 9:00am in the lead's local timezone.
        Returns a UTC datetime.
        """
        now_utc = datetime.utcnow()

        # Convert current UTC time to lead's local time
        local_now = now_utc + timedelta(hours=timezone_offset)

        # Target: 9:00am local
        target_local = local_now.replace(hour=9, minute=0, second=0, microsecond=0)

        # If 9am has already passed today in their timezone, schedule for tomorrow
        if local_now.hour >= 9:
            target_local += timedelta(days=1)

        # Convert back to UTC
        target_utc = target_local - timedelta(hours=timezone_offset)

        return target_utc

    def get_leads_ready_to_send(self) -> list:
        """
        Get leads whose scheduled_send_at has passed and status is 'scheduled'.
        Returns list of lead IDs.
        """
        try:
            with self.db_manager.session_scope() as session:
                now = datetime.utcnow()
                leads = (
                    session.query(Lead)
                    .filter(
                        Lead.scheduled_send_at <= now,
                        Lead.status == "scheduled",
                    )
                    .all()
                )
                return [lead.id for lead in leads]
        except Exception as e:
            logger.error(f"Error getting scheduled leads: {e}")
            return []

    def schedule_lead(self, lead_id: int, send_at: datetime) -> dict:
        """Set a lead's scheduled send time and update status."""
        try:
            with self.db_manager.session_scope() as session:
                lead = session.query(Lead).filter_by(id=lead_id).first()
                if not lead:
                    return {"success": False, "error": "Lead not found"}

                lead.scheduled_send_at = send_at
                lead.status = "scheduled"

                return {
                    "success": True,
                    "data": {
                        "lead_id": lead_id,
                        "scheduled_for": send_at.isoformat(),
                    },
                }
        except Exception as e:
            logger.error(f"Error scheduling lead: {e}")
            return {"success": False, "error": str(e)}
