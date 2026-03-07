"""
Aura — Dashboard Controller
Aggregates stats from campaigns and leads for the dashboard display.
"""

from PySide6.QtCore import QObject, Signal

from database.db_manager import DatabaseManager
from database.schema import Campaign, Lead, Settings, ApiUsageLog
from sqlalchemy import func, extract
from datetime import datetime
from utils.logger import get_logger

logger = get_logger("dashboard_controller")


class DashboardController(QObject):
    """Provides aggregated statistics for the Dashboard page."""

    stats_ready = Signal(dict)  # Emitted with full stats dict

    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager

    def refresh_stats(self):
        """Calculate all dashboard statistics and emit them."""
        try:
            with self.db_manager.session_scope() as session:
                total_campaigns = session.query(func.count(Campaign.id)).scalar() or 0
                active_campaigns = session.query(func.count(Campaign.id)).filter(
                    Campaign.status == "active"
                ).scalar() or 0

                total_leads = session.query(func.count(Lead.id)).scalar() or 0
                qualified_leads = session.query(func.count(Lead.id)).filter(
                    Lead.status == "qualified"
                ).scalar() or 0
                emailed_leads = session.query(func.count(Lead.id)).filter(
                    Lead.status == "emailed"
                ).scalar() or 0
                new_leads = session.query(func.count(Lead.id)).filter(
                    Lead.status == "new"
                ).scalar() or 0

                # Recent campaigns
                recent = session.query(Campaign).order_by(
                    Campaign.created_at.desc()
                ).limit(5).all()
                recent_campaigns = [
                    {
                        "id": c.id,
                        "name": c.name,
                        "total_leads": c.total_leads,
                        "qualified_leads": c.qualified_leads,
                        "status": c.status,
                        "created_at": str(c.created_at) if c.created_at else "",
                    }
                    for c in recent
                ]

                # Pipeline funnel
                conversion_rate = 0
                if total_leads > 0:
                    conversion_rate = round((qualified_leads / total_leads) * 100, 1)

            stats = {
                "total_campaigns": total_campaigns,
                "active_campaigns": active_campaigns,
                "total_leads": total_leads,
                "new_leads": new_leads,
                "qualified_leads": qualified_leads,
                "emailed_leads": emailed_leads,
                "conversion_rate": conversion_rate,
                "recent_campaigns": recent_campaigns,
            }

            # ─── API usage stats (current month) ──────────────
            api_usage = self._get_api_usage_stats()
            stats["api_usage"] = api_usage

            self.stats_ready.emit(stats)
            return stats

        except Exception as e:
            logger.error(f"Dashboard stats error: {e}")
            return {}

    def _get_api_usage_stats(self) -> dict:
        """Query ApiUsageLog for current-month tier breakdown."""
        now = datetime.utcnow()
        try:
            with self.db_manager.session_scope() as session:
                rows = (
                    session.query(
                        ApiUsageLog.service,
                        func.count(ApiUsageLog.id).label("calls"),
                        func.coalesce(func.sum(ApiUsageLog.tokens_used), 0).label("tokens"),
                        func.coalesce(func.sum(ApiUsageLog.cost_usd), 0.0).label("cost"),
                    )
                    .filter(
                        extract("year", ApiUsageLog.timestamp) == now.year,
                        extract("month", ApiUsageLog.timestamp) == now.month,
                    )
                    .group_by(ApiUsageLog.service)
                    .all()
                )

                breakdown = {}
                total_cost = 0.0
                total_calls = 0
                for service, calls, tokens, cost in rows:
                    calls = calls or 0
                    tokens = tokens or 0
                    cost = cost or 0.0
                    breakdown[service] = {"calls": calls, "tokens": tokens, "cost_usd": round(cost, 4)}
                    total_cost += cost
                    total_calls += calls

                return {
                    "breakdown": breakdown,
                    "total_cost_usd": round(total_cost, 4),
                    "total_calls": total_calls,
                    "month": now.strftime("%Y-%m"),
                }
        except Exception as e:
            logger.warning(f"API usage stats error: {e}")
            return {"breakdown": {}, "total_cost_usd": 0.0, "total_calls": 0, "month": ""}
