"""
Aura — Lead Lifecycle Engine
Rich multi-path state machine for lead progression through the sales funnel.
Validates transitions, fires callbacks, and maintains an audit trail.
"""

import json
from datetime import datetime
from collections import defaultdict

from database.db_manager import DatabaseManager
from database.schema import Lead, LeadStateTransition, Agent
from config import LEAD_STATE_TRANSITIONS, LEAD_TERMINAL_STATES
from utils.logger import get_logger

logger = get_logger("lead_lifecycle_engine")


class LeadLifecycleEngine:
    """Manages lead state transitions with validation, callbacks, and audit trail."""

    def __init__(self, db_manager: DatabaseManager, fleet_orchestrator=None):
        self.db_manager = db_manager
        self.fleet_orchestrator = fleet_orchestrator
        self.command_history = None  # Injected from main_window
        self.case_engine = None  # Injected from main_window
        self._on_enter_callbacks = defaultdict(list)
        self._on_exit_callbacks = defaultdict(list)
        self._on_transition_callbacks = defaultdict(list)

    # ─── State Transitions ─────────────────────────────────────────

    def transition(self, lead_id: int, to_state: str, triggered_by: str = "system",
                   agent_id: int = None, metadata: dict = None) -> dict:
        """
        Move a lead to a new state if the transition is valid.
        Fires on_exit → records transition → updates lead → fires on_enter callbacks.
        """
        try:
            with self.db_manager.session_scope() as session:
                lead = session.query(Lead).get(lead_id)
                if not lead:
                    return {"success": False, "error": f"Lead {lead_id} not found"}

                from_state = lead.lifecycle_state or "new"

                # Validate transition
                if from_state in LEAD_TERMINAL_STATES:
                    return {
                        "success": False,
                        "error": f"Lead is in terminal state '{from_state}', no transitions allowed",
                    }

                valid_targets = LEAD_STATE_TRANSITIONS.get(from_state, [])
                if to_state not in valid_targets:
                    return {
                        "success": False,
                        "error": (
                            f"Invalid transition: '{from_state}' → '{to_state}'. "
                            f"Valid targets: {valid_targets}"
                        ),
                    }

                # Fire on_exit callbacks
                self._fire_callbacks(self._on_exit_callbacks, from_state,
                                     lead_id, from_state, to_state)

                # Record transition
                transition_record = LeadStateTransition(
                    lead_id=lead_id,
                    from_state=from_state,
                    to_state=to_state,
                    triggered_by=triggered_by,
                    agent_id=agent_id,
                    metadata_json=json.dumps(metadata or {}),
                )
                session.add(transition_record)

                # Update lead state
                lead.lifecycle_state = to_state

                # Also update legacy status for backward compat
                lead.status = to_state

            # Fire on_enter callbacks (after commit)
            self._fire_callbacks(self._on_enter_callbacks, to_state,
                                 lead_id, from_state, to_state)

            # Fire transition-specific callbacks
            key = f"{from_state}→{to_state}"
            self._fire_callbacks(self._on_transition_callbacks, key,
                                 lead_id, from_state, to_state)

            logger.info(
                f"Lifecycle transition: lead={lead_id} "
                f"'{from_state}'→'{to_state}' by={triggered_by}"
            )

            if self.command_history:
                try:
                    self.command_history.log_command(
                        source="system",
                        command_type="lifecycle_transition",
                        command_text=f"Lead {lead_id}: {from_state} → {to_state}",
                        actor_type="system",
                        agent_id=agent_id,
                        status="completed",
                        parameters={
                            "lead_id": lead_id,
                            "from_state": from_state,
                            "to_state": to_state,
                            "triggered_by": triggered_by,
                        },
                    )
                except Exception:
                    pass

            # Log case note for lifecycle transition
            if self.case_engine:
                try:
                    self.case_engine.add_note(
                        lead_id=lead_id,
                        note_type="lifecycle",
                        content=f"State: {from_state} -> {to_state} (by: {triggered_by})",
                        agent_id=agent_id,
                        metadata=metadata,
                    )
                except Exception:
                    pass

            return {
                "success": True,
                "data": {
                    "lead_id": lead_id,
                    "from_state": from_state,
                    "to_state": to_state,
                    "triggered_by": triggered_by,
                },
            }

        except Exception as e:
            logger.error(f"Transition failed: {e}")
            return {"success": False, "error": str(e)}

    # ─── Callback Registration ─────────────────────────────────────

    def register_on_enter(self, state: str, callback):
        """Register a callback fired when a lead enters the given state."""
        self._on_enter_callbacks[state].append(callback)

    def register_on_exit(self, state: str, callback):
        """Register a callback fired when a lead exits the given state."""
        self._on_exit_callbacks[state].append(callback)

    def register_on_transition(self, from_state: str, to_state: str, callback):
        """Register a callback fired on a specific transition."""
        key = f"{from_state}→{to_state}"
        self._on_transition_callbacks[key].append(callback)

    # ─── Queries ───────────────────────────────────────────────────

    def get_valid_transitions(self, lead_id: int) -> dict:
        """Return the list of valid next states for a lead."""
        try:
            with self.db_manager.session_scope() as session:
                lead = session.query(Lead).get(lead_id)
                if not lead:
                    return {"success": False, "error": f"Lead {lead_id} not found"}

                current = lead.lifecycle_state or "new"
                if current in LEAD_TERMINAL_STATES:
                    valid = []
                else:
                    valid = LEAD_STATE_TRANSITIONS.get(current, [])

            return {
                "success": True,
                "data": {
                    "lead_id": lead_id,
                    "current_state": current,
                    "valid_transitions": valid,
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_transition_history(self, lead_id: int, limit: int = 50) -> dict:
        """Return audit trail of state transitions for a lead."""
        try:
            with self.db_manager.session_scope() as session:
                transitions = (
                    session.query(LeadStateTransition)
                    .filter_by(lead_id=lead_id)
                    .order_by(LeadStateTransition.created_at.desc())
                    .limit(limit)
                    .all()
                )

                items = [
                    {
                        "id": t.id,
                        "from_state": t.from_state,
                        "to_state": t.to_state,
                        "triggered_by": t.triggered_by,
                        "agent_id": t.agent_id,
                        "metadata": json.loads(t.metadata_json) if t.metadata_json else {},
                        "created_at": t.created_at.isoformat() if t.created_at else None,
                    }
                    for t in transitions
                ]

            return {"success": True, "data": items}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_leads_in_state(self, state: str, campaign_id: int = None) -> dict:
        """Return all leads currently in the given lifecycle state."""
        try:
            with self.db_manager.session_scope() as session:
                query = session.query(Lead).filter(Lead.lifecycle_state == state)
                if campaign_id is not None:
                    query = query.filter(Lead.campaign_id == campaign_id)

                leads = query.all()
                items = [
                    {
                        "id": l.id,
                        "business_name": l.business_name,
                        "lifecycle_state": l.lifecycle_state,
                        "campaign_id": l.campaign_id,
                    }
                    for l in leads
                ]

            return {"success": True, "data": items}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_lifecycle_stats(self, campaign_id: int = None) -> dict:
        """Return counts of leads per lifecycle state, optionally filtered by campaign."""
        try:
            from sqlalchemy import func

            with self.db_manager.session_scope() as session:
                query = session.query(
                    Lead.lifecycle_state, func.count(Lead.id)
                ).group_by(Lead.lifecycle_state)

                if campaign_id is not None:
                    query = query.filter(Lead.campaign_id == campaign_id)

                rows = query.all()
                stats = {state: count for state, count in rows}

            return {"success": True, "data": stats}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─── Private ───────────────────────────────────────────────────

    def _fire_callbacks(self, registry, key, lead_id, from_state, to_state):
        """Fire all callbacks registered under the given key."""
        for cb in registry.get(key, []):
            try:
                cb(lead_id, from_state, to_state)
            except Exception as e:
                logger.warning(f"Callback error for '{key}': {e}")
