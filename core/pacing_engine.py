"""
Aura — Cost Pacing Engine
SLA-driven budget cruise-control. Calculates token burn rate,
dynamically constrains which LLM tiers are available, and
provides pre-flight feasibility checks.
"""

from datetime import datetime, timedelta
from typing import Optional

from database.db_manager import DatabaseManager
from database.schema import BudgetConfig, ApiUsageLog
from config import (
    PACING_MIN_BUDGET_USD,
    TIER_COST_PER_1K_TOKENS,
    ECO_MODE_FALLBACK_CHAIN,
)
from utils.logger import get_logger

logger = get_logger("pacing_engine")

# Tier cost ranking — higher index = more expensive
TIER_RANK = {"local": 0, "ollama": 0, "haiku": 1, "sonnet": 2}

# Estimated average tokens per LLM call by tier (for burn-rate projections)
AVG_TOKENS_PER_CALL = {"local": 0, "ollama": 300, "haiku": 400, "sonnet": 600}

# Average cost per single call (rough estimate for pacing math)
AVG_COST_PER_CALL = {
    tier: AVG_TOKENS_PER_CALL[tier] * TIER_COST_PER_1K_TOKENS[tier] / 1000.0
    for tier in TIER_COST_PER_1K_TOKENS
}


class PacingEngine:
    """
    Budget cruise-control for LLM usage.
    Sits between the AI layer and the RouterEngine, acting as a governor
    that dynamically constrains which tiers the router is allowed to use.
    """

    def __init__(self, db_manager: DatabaseManager, router_engine=None):
        self.db_manager = db_manager
        self.router_engine = router_engine
        self._cached_config: Optional[BudgetConfig] = None

    # ─── Budget lifecycle ──────────────────────────────────────────

    def activate(self, budget_usd: float, time_window_hours: float,
                 eco_mode: bool = True) -> dict:
        """Create or activate a budget pacing session."""
        if budget_usd < PACING_MIN_BUDGET_USD:
            return {
                "success": False,
                "error": f"Minimum budget is ${PACING_MIN_BUDGET_USD:.2f}",
            }
        if time_window_hours < 1:
            return {"success": False, "error": "Time window must be at least 1 hour"}

        now = datetime.utcnow()
        expires = now + timedelta(hours=time_window_hours)

        try:
            with self.db_manager.session_scope() as session:
                # Deactivate any existing active config
                active = session.query(BudgetConfig).filter_by(status="active").first()
                if active:
                    active.status = "expired"

                config = BudgetConfig(
                    budget_usd=budget_usd,
                    time_window_hours=time_window_hours,
                    started_at=now,
                    expires_at=expires,
                    spent_usd=0.0,
                    status="active",
                    eco_mode=eco_mode,
                    max_tier="sonnet",
                )
                session.add(config)
                session.flush()
                config_id = config.id

            self._cached_config = None  # Force reload
            logger.info(
                f"Pacing activated: ${budget_usd:.2f} over {time_window_hours}h "
                f"(eco_mode={eco_mode})"
            )
            return {"success": True, "budget_id": config_id}

        except Exception as e:
            logger.error(f"Failed to activate pacing: {e}")
            return {"success": False, "error": str(e)}

    def deactivate(self) -> dict:
        """Deactivate current pacing session."""
        try:
            with self.db_manager.session_scope() as session:
                active = session.query(BudgetConfig).filter_by(status="active").first()
                if active:
                    active.status = "inactive"
            self._cached_config = None
            logger.info("Pacing deactivated")
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def pause(self) -> dict:
        """Pause active pacing (budget timer pauses)."""
        try:
            with self.db_manager.session_scope() as session:
                active = session.query(BudgetConfig).filter_by(status="active").first()
                if active:
                    active.status = "paused"
                    self._cached_config = None
                    return {"success": True}
            return {"success": False, "error": "No active budget to pause"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def resume(self) -> dict:
        """Resume paused pacing."""
        try:
            with self.db_manager.session_scope() as session:
                paused = session.query(BudgetConfig).filter_by(status="paused").first()
                if paused:
                    # Extend expires_at by the paused duration
                    paused.status = "active"
                    self._cached_config = None
                    return {"success": True}
            return {"success": False, "error": "No paused budget to resume"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─── Status & analytics ────────────────────────────────────────

    def _get_active_config(self) -> Optional[BudgetConfig]:
        """Load the active BudgetConfig (cached)."""
        try:
            with self.db_manager.session_scope() as session:
                config = session.query(BudgetConfig).filter(
                    BudgetConfig.status.in_(["active", "paused"])
                ).first()
                if config:
                    session.expunge(config)
                return config
        except Exception:
            return None

    def is_active(self) -> bool:
        """Check if pacing is currently active."""
        config = self._get_active_config()
        return config is not None and config.status == "active"

    def sync_spend(self):
        """Sync spent_usd from ApiUsageLog since budget started."""
        config = self._get_active_config()
        if not config or not config.started_at:
            return

        try:
            from sqlalchemy import func
            with self.db_manager.session_scope() as session:
                total = session.query(
                    func.coalesce(func.sum(ApiUsageLog.cost_usd), 0.0)
                ).filter(
                    ApiUsageLog.timestamp >= config.started_at
                ).scalar()

                active = session.query(BudgetConfig).get(config.id)
                if active:
                    active.spent_usd = float(total)
        except Exception as e:
            logger.warning(f"Failed to sync spend: {e}")

    def get_status(self) -> dict:
        """Get comprehensive pacing status for UI display."""
        config = self._get_active_config()
        if not config:
            return {
                "active": False,
                "budget_usd": 0.0,
                "spent_usd": 0.0,
                "remaining_usd": 0.0,
                "elapsed_hours": 0.0,
                "remaining_hours": 0.0,
                "burn_rate_actual": 0.0,
                "burn_rate_target": 0.0,
                "current_max_tier": "sonnet",
                "eco_mode": True,
                "projected_runway_hours": 0.0,
                "on_track": True,
                "status": "inactive",
                "percent_spent": 0.0,
            }

        self.sync_spend()
        # Reload after sync
        config = self._get_active_config()
        if not config:
            return {"active": False, "status": "inactive"}

        now = datetime.utcnow()
        elapsed = max((now - config.started_at).total_seconds() / 3600.0, 0.001)
        remaining_hours = max(
            (config.expires_at - now).total_seconds() / 3600.0, 0.0
        ) if config.expires_at else 0.0

        remaining_usd = max(config.budget_usd - config.spent_usd, 0.0)
        burn_rate_actual = config.spent_usd / elapsed if elapsed > 0 else 0.0
        burn_rate_target = (
            config.budget_usd / config.time_window_hours
            if config.time_window_hours > 0 else 0.0
        )

        # Projected runway at current burn rate
        if burn_rate_actual > 0:
            projected_runway = remaining_usd / burn_rate_actual
        else:
            projected_runway = remaining_hours  # No spend yet

        on_track = burn_rate_actual <= burn_rate_target * 1.2  # 20% tolerance

        percent_spent = (
            (config.spent_usd / config.budget_usd * 100.0)
            if config.budget_usd > 0 else 0.0
        )

        # Check if expired
        if remaining_hours <= 0 or remaining_usd <= 0:
            self._expire_if_needed(config.id)

        max_tier = self.get_allowed_max_tier()

        return {
            "active": config.status == "active",
            "status": config.status,
            "budget_usd": config.budget_usd,
            "spent_usd": round(config.spent_usd, 4),
            "remaining_usd": round(remaining_usd, 4),
            "elapsed_hours": round(elapsed, 2),
            "remaining_hours": round(remaining_hours, 2),
            "burn_rate_actual": round(burn_rate_actual, 4),
            "burn_rate_target": round(burn_rate_target, 4),
            "current_max_tier": max_tier,
            "eco_mode": config.eco_mode,
            "projected_runway_hours": round(projected_runway, 2),
            "on_track": on_track,
            "percent_spent": round(percent_spent, 1),
        }

    def _expire_if_needed(self, config_id: int):
        """Mark budget as expired if time or money is exhausted."""
        try:
            with self.db_manager.session_scope() as session:
                config = session.query(BudgetConfig).get(config_id)
                if config and config.status == "active":
                    config.status = "expired"
                    logger.info(f"Budget #{config_id} expired")
        except Exception as e:
            logger.warning(f"Failed to expire budget: {e}")

    # ─── Core pacing algorithm ─────────────────────────────────────

    def get_allowed_max_tier(self) -> str:
        """
        Determine the highest tier allowed under current pacing constraints.
        This is the governor that constrains the RouterEngine.
        """
        config = self._get_active_config()
        if not config or config.status != "active":
            return "sonnet"  # No pacing active — all tiers available

        if not config.eco_mode:
            return "sonnet"  # Eco-mode off — no constraints

        now = datetime.utcnow()
        remaining_usd = max(config.budget_usd - config.spent_usd, 0.0)
        remaining_hours = max(
            (config.expires_at - now).total_seconds() / 3600.0, 0.01
        ) if config.expires_at else 0.01

        target_rate = remaining_usd / remaining_hours  # $/hr we can afford

        # Walk the fallback chain from most expensive to cheapest.
        # Allow the most expensive tier whose average hourly cost
        # fits within our target burn rate.
        # Assume ~60 calls/hour as a reasonable workload estimate.
        calls_per_hour = 60

        for tier in ECO_MODE_FALLBACK_CHAIN:
            tier_hourly_cost = AVG_COST_PER_CALL.get(tier, 0) * calls_per_hour
            if tier_hourly_cost <= target_rate:
                # Update stored max_tier
                self._update_max_tier(config.id, tier)
                return tier

        # Nothing fits — force local (free)
        self._update_max_tier(config.id, "local")
        return "local"

    def _update_max_tier(self, config_id: int, tier: str):
        """Persist the current max tier decision."""
        try:
            with self.db_manager.session_scope() as session:
                config = session.query(BudgetConfig).get(config_id)
                if config and config.max_tier != tier:
                    config.max_tier = tier
        except Exception:
            pass

    # ─── Pre-flight check ──────────────────────────────────────────

    def pre_flight_check(self, estimated_tasks: int,
                         avg_tokens_per_task: int = 500) -> dict:
        """
        Mathematical feasibility check before starting a paced run.
        Determines if the budget can support the estimated workload.
        """
        config = self._get_active_config()
        if not config:
            return {
                "feasible": False,
                "message": "No active budget configured. Set a budget first.",
            }

        remaining_usd = max(config.budget_usd - config.spent_usd, 0.0)

        # Cost at cheapest LLM tier (haiku)
        cheapest_llm_cost = (
            avg_tokens_per_task * TIER_COST_PER_1K_TOKENS["haiku"] / 1000.0
        )
        total_cheapest_cost = estimated_tasks * cheapest_llm_cost

        # Cost at most expensive tier (sonnet)
        expensive_cost = (
            avg_tokens_per_task * TIER_COST_PER_1K_TOKENS["sonnet"] / 1000.0
        )
        total_expensive_cost = estimated_tasks * expensive_cost

        if total_cheapest_cost > remaining_usd:
            shortfall = total_cheapest_cost - remaining_usd
            # Calculate what budget or task count would work
            max_feasible_tasks = int(remaining_usd / cheapest_llm_cost) if cheapest_llm_cost > 0 else 0
            min_budget_needed = total_cheapest_cost

            return {
                "feasible": False,
                "message": (
                    f"Budget insufficient even at cheapest model (Haiku). "
                    f"Need ${min_budget_needed:.2f} but only ${remaining_usd:.2f} remaining. "
                    f"Increase budget by ${shortfall:.2f} or reduce to {max_feasible_tasks} tasks."
                ),
                "min_budget_needed": round(min_budget_needed, 2),
                "max_feasible_tasks": max_feasible_tasks,
                "shortfall_usd": round(shortfall, 2),
            }

        # Feasible — determine at which tier quality
        if total_expensive_cost <= remaining_usd:
            quality = "premium"
            msg = (
                f"Budget sufficient for all {estimated_tasks} tasks at Sonnet quality. "
                f"Estimated cost: ${total_expensive_cost:.2f} of ${remaining_usd:.2f} remaining."
            )
        else:
            quality = "eco"
            msg = (
                f"Budget feasible with Eco-Mode. {estimated_tasks} tasks will use "
                f"dynamic tier switching. Estimated ${total_cheapest_cost:.2f}–"
                f"${total_expensive_cost:.2f} of ${remaining_usd:.2f} remaining."
            )

        return {
            "feasible": True,
            "quality": quality,
            "message": msg,
            "estimated_cost_min": round(total_cheapest_cost, 4),
            "estimated_cost_max": round(total_expensive_cost, 4),
            "remaining_budget": round(remaining_usd, 4),
        }

    def get_downgrade_recommendation(self) -> Optional[str]:
        """If actual burn rate exceeds 120% of target, recommend a lower tier."""
        status = self.get_status()
        if not status.get("active"):
            return None

        if status["burn_rate_actual"] > status["burn_rate_target"] * 1.2:
            current = status["current_max_tier"]
            idx = ECO_MODE_FALLBACK_CHAIN.index(current) if current in ECO_MODE_FALLBACK_CHAIN else 0
            if idx + 1 < len(ECO_MODE_FALLBACK_CHAIN):
                return ECO_MODE_FALLBACK_CHAIN[idx + 1]
        return None
