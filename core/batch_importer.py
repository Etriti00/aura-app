"""
Aura — Batch Campaign Importer
Validates CSV files and creates multiple campaigns for sequential execution.
"""

import csv
import json
import random
import time
from typing import Callable, Optional

from database.db_manager import DatabaseManager
from database.schema import Campaign, Skill
from utils.logger import get_logger

logger = get_logger("batch_importer")


class BatchImporter:
    """Handles CSV-based batch campaign creation and sequential execution."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def validate_csv(self, file_path: str) -> dict:
        """
        Validate a CSV file for batch import.
        Required columns: niche, city.
        Optional columns: limit (int), skill_name (must match existing Skill).
        """
        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                columns = reader.fieldnames or []

                errors = []
                if "niche" not in columns:
                    errors.append("Missing required column: 'niche'")
                if "city" not in columns:
                    errors.append("Missing required column: 'city'")

                if errors:
                    return {"valid": False, "row_count": 0, "errors": errors}

                rows = list(reader)
                row_count = len(rows)

                # Validate each row
                for i, row in enumerate(rows, 1):
                    niche = (row.get("niche") or "").strip()
                    city = (row.get("city") or "").strip()

                    if not niche:
                        errors.append(f"Row {i}: empty niche")
                    if not city:
                        errors.append(f"Row {i}: empty city")

                    # Validate limit if present
                    limit_str = (row.get("limit") or "").strip()
                    if limit_str:
                        try:
                            limit = int(limit_str)
                            if limit < 1 or limit > 500:
                                errors.append(f"Row {i}: limit must be 1–500, got {limit}")
                        except ValueError:
                            errors.append(f"Row {i}: invalid limit '{limit_str}'")

                    # Validate skill_name if present
                    skill_name = (row.get("skill_name") or "").strip()
                    if skill_name:
                        with self.db_manager.session_scope() as session:
                            skill = session.query(Skill).filter_by(name=skill_name).first()
                            if not skill:
                                errors.append(f"Row {i}: skill '{skill_name}' not found")

                return {
                    "valid": len(errors) == 0,
                    "row_count": row_count,
                    "errors": errors[:50],
                }
        except Exception as e:
            logger.error(f"CSV validation failed: {e}")
            return {"valid": False, "row_count": 0, "errors": [str(e)]}

    def create_campaigns_from_csv(self, file_path: str,
                                   default_skill_id: int) -> dict:
        """
        Create campaigns from each row in the CSV.
        Returns {created, skipped, campaign_ids}.
        """
        created = 0
        skipped = 0
        campaign_ids = []

        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)

                for i, row in enumerate(reader, 1):
                    niche = (row.get("niche") or "").strip()
                    city = (row.get("city") or "").strip()
                    limit_str = (row.get("limit") or "50").strip()
                    skill_name = (row.get("skill_name") or "").strip()

                    if not niche or not city:
                        skipped += 1
                        continue

                    try:
                        limit = int(limit_str)
                    except ValueError:
                        limit = 50

                    # Resolve skill
                    skill_id = default_skill_id
                    if skill_name:
                        with self.db_manager.session_scope() as session:
                            skill = session.query(Skill).filter_by(name=skill_name).first()
                            if skill:
                                skill_id = skill.id

                    # Create campaign
                    with self.db_manager.session_scope() as session:
                        campaign = Campaign(
                            name=f"{niche.title()} in {city.title()}",
                            search_query=f"{niche} in {city}",
                            target_city=city,
                            target_niche=niche,
                            status="draft",
                            skill_id=skill_id,
                        )
                        session.add(campaign)
                        session.flush()
                        campaign_ids.append(campaign.id)
                        created += 1

            return {
                "success": True,
                "data": {
                    "created": created,
                    "skipped": skipped,
                    "campaign_ids": campaign_ids,
                },
            }
        except Exception as e:
            logger.error(f"Campaign creation from CSV failed: {e}")
            return {"success": False, "error": str(e)}

    def preview_csv(self, file_path: str) -> list:
        """Preview parsed CSV rows for the UI table."""
        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                return [
                    {
                        "niche": (row.get("niche") or "").strip(),
                        "city": (row.get("city") or "").strip(),
                        "limit": (row.get("limit") or "50").strip(),
                        "skill_name": (row.get("skill_name") or "").strip(),
                    }
                    for row in reader
                ]
        except Exception as e:
            logger.error(f"CSV preview failed: {e}")
            return []

    def run_campaigns_sequentially(
        self,
        campaign_ids: list,
        run_single_campaign: Callable,
        progress_callback: Optional[Callable] = None,
    ) -> dict:
        """
        Run campaigns one at a time with inter-campaign jitter.
        run_single_campaign: callable(campaign_id) -> dict
        """
        completed = 0
        failed = 0

        for i, campaign_id in enumerate(campaign_ids):
            try:
                if progress_callback:
                    progress_callback(i, len(campaign_ids))

                result = run_single_campaign(campaign_id)
                if result.get("success"):
                    completed += 1
                else:
                    failed += 1

                # Inter-campaign jitter (skip for last campaign)
                if i < len(campaign_ids) - 1:
                    delay = random.uniform(120, 300)
                    logger.info(f"Inter-campaign delay: {delay:.0f}s before next campaign")
                    time.sleep(delay)

            except Exception as e:
                logger.error(f"Campaign {campaign_id} failed: {e}")
                failed += 1

        if progress_callback:
            progress_callback(len(campaign_ids), len(campaign_ids))

        return {
            "success": True,
            "data": {
                "completed": completed,
                "failed": failed,
                "total": len(campaign_ids),
            },
        }
