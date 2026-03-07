"""
Aura — Suppression Engine
Global email/domain suppression with in-memory cache and CSV bulk import.
"""

import csv
import time
from datetime import datetime
from typing import Optional

from database.db_manager import DatabaseManager
from database.schema import SuppressionEntry
from utils.logger import get_logger

logger = get_logger("suppression_engine")

# Cache refresh interval (seconds)
CACHE_TTL = 600  # 10 minutes


class SuppressionEngine:
    """Manages the suppression list: check, add, import, cache."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self._cache_emails: set = set()
        self._cache_domains: set = set()
        self._cache_loaded_at: float = 0

    def _refresh_cache(self):
        """Reload the suppression list into memory if stale."""
        if time.time() - self._cache_loaded_at < CACHE_TTL:
            return

        try:
            with self.db_manager.session_scope() as session:
                entries = session.query(SuppressionEntry).all()
                self._cache_emails = {
                    e.email.lower() for e in entries if e.email
                }
                self._cache_domains = {
                    e.domain.lower() for e in entries if e.domain
                }
                self._cache_loaded_at = time.time()
                logger.debug(
                    f"Suppression cache refreshed: {len(self._cache_emails)} emails, "
                    f"{len(self._cache_domains)} domains"
                )
        except Exception as e:
            logger.error(f"Error refreshing suppression cache: {e}")

    def is_suppressed(self, email: str = "", domain: str = "") -> bool:
        """
        Check if an email or domain is on the suppression list.
        Uses in-memory cache for performance.
        """
        self._refresh_cache()

        if email and email.lower() in self._cache_emails:
            return True

        # Extract domain from email if not provided
        if not domain and email and "@" in email:
            domain = email.split("@")[1]

        if domain and domain.lower() in self._cache_domains:
            return True

        return False

    def add_suppression(self, email: str = None, domain: str = None,
                        reason: str = "manual") -> dict:
        """Add an email or domain to the suppression list."""
        try:
            if not email and not domain:
                return {"success": False, "error": "Email or domain required"}

            with self.db_manager.session_scope() as session:
                # Check for duplicates
                if email:
                    existing = session.query(SuppressionEntry).filter_by(
                        email=email.lower()
                    ).first()
                    if existing:
                        return {"success": True, "data": {"duplicate": True}}

                if domain:
                    existing = session.query(SuppressionEntry).filter_by(
                        domain=domain.lower()
                    ).first()
                    if existing:
                        return {"success": True, "data": {"duplicate": True}}

                entry = SuppressionEntry(
                    email=email.lower() if email else None,
                    domain=domain.lower() if domain else None,
                    reason=reason,
                    added_at=datetime.utcnow(),
                )
                session.add(entry)

            # Clear cache
            self._cache_loaded_at = 0
            return {"success": True, "data": {"email": email, "domain": domain}}
        except Exception as e:
            logger.error(f"Error adding suppression: {e}")
            return {"success": False, "error": str(e)}

    def remove_suppression(self, entry_id: int) -> dict:
        """Remove a suppression entry by ID."""
        try:
            with self.db_manager.session_scope() as session:
                entry = session.query(SuppressionEntry).filter_by(id=entry_id).first()
                if entry:
                    session.delete(entry)
                    self._cache_loaded_at = 0
                    return {"success": True}
                return {"success": False, "error": "Entry not found"}
        except Exception as e:
            logger.error(f"Error removing suppression: {e}")
            return {"success": False, "error": str(e)}

    def bulk_import_from_csv(self, file_path: str) -> dict:
        """
        Import suppression entries from a CSV file.
        Expected columns: email, domain (at least one required per row).
        """
        imported = 0
        skipped = 0
        errors = []

        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader, 1):
                    email_val = (row.get("email") or "").strip()
                    domain_val = (row.get("domain") or "").strip()

                    if not email_val and not domain_val:
                        errors.append(f"Row {i}: no email or domain")
                        skipped += 1
                        continue

                    result = self.add_suppression(
                        email=email_val if email_val else None,
                        domain=domain_val if domain_val else None,
                        reason="csv_import",
                    )

                    if result.get("success"):
                        if result.get("data", {}).get("duplicate"):
                            skipped += 1
                        else:
                            imported += 1
                    else:
                        errors.append(f"Row {i}: {result.get('error', 'unknown')}")
                        skipped += 1

            return {
                "success": True,
                "data": {
                    "imported": imported,
                    "skipped": skipped,
                    "errors": errors[:20],  # Limit error list
                },
            }
        except Exception as e:
            logger.error(f"CSV import failed: {e}")
            return {"success": False, "error": str(e)}

    def get_all_entries(self) -> list:
        """Get all suppression list entries."""
        try:
            with self.db_manager.session_scope() as session:
                entries = (
                    session.query(SuppressionEntry)
                    .order_by(SuppressionEntry.added_at.desc())
                    .all()
                )
                return [
                    {
                        "id": e.id,
                        "email": e.email,
                        "domain": e.domain,
                        "reason": e.reason,
                        "added_at": e.added_at.isoformat() if e.added_at else "",
                    }
                    for e in entries
                ]
        except Exception as e:
            logger.error(f"Error getting suppression entries: {e}")
            return []
