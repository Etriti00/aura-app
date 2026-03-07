"""
Aura — Fleet Controller
UI-facing controller for the multi-agent fleet: boot, shutdown, dispatch,
health checks, and per-agent management.
"""

from PySide6.QtCore import QObject, Signal, QTimer

from database.db_manager import DatabaseManager
from core.agent_engine import AgentEngine
from core.fleet_orchestrator import FleetOrchestrator
from core.observer_engine import ObserverEngine
from utils.logger import get_logger
from config import (
    AGENT_HEARTBEAT_CHECK_MS, OBSERVER_CHECK_INTERVAL_MS,
    ESCALATION_CHECK_INTERVAL_MS, SELF_IMPROVEMENT_INTERVAL_MS,
    CALLER_CHECK_INTERVAL_MS, CALLER_FAILED_EMAIL_THRESHOLD,
    CALLER_STALLED_DAYS,
)

logger = get_logger("fleet_controller")


class FleetController(QObject):
    """Bridges the fleet engines to the UI layer."""

    fleet_status_ready = Signal(dict)
    health_check_ready = Signal(dict)
    agent_status_ready = Signal(dict)
    anomalies_ready = Signal(dict)
    daily_report_ready = Signal(dict)
    fleet_booted = Signal(dict)
    fleet_shutdown = Signal()
    dispatch_result = Signal(dict)
    pipeline_complete = Signal(dict)
    triage_result = Signal(dict)
    agent_updated = Signal(int)  # agent_id
    escalation_triggered = Signal(dict)
    ticket_request_processed = Signal(dict)
    error = Signal(str)

    def __init__(self, db_manager: DatabaseManager,
                 agent_engine: AgentEngine,
                 fleet_orchestrator: FleetOrchestrator,
                 observer_engine: ObserverEngine,
                 escalation_engine=None,
                 kanban_ctrl=None):
        super().__init__()
        self.db_manager = db_manager
        self.agent_engine = agent_engine
        self.fleet = fleet_orchestrator
        self.observer = observer_engine
        self.escalation_engine = escalation_engine
        self.kanban_ctrl = kanban_ctrl

        # Heartbeat timer
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.timeout.connect(self._run_heartbeats)

        # Observer timer
        self._observer_timer = QTimer(self)
        self._observer_timer.timeout.connect(self.run_health_check)

        # Escalation timer
        self._escalation_timer = QTimer(self)
        self._escalation_timer.timeout.connect(self.run_escalation_check)

        # Self-improvement timer
        self._improvement_timer = QTimer(self)
        self._improvement_timer.timeout.connect(self._run_improvement_cycle)
        self.self_improvement_engine = None  # injected by main_window

        # Pipeline automation controllers — injected by main_window
        self.reply_ctrl = None
        self.sequence_ctrl = None
        self.outreach_ctrl = None

        # Caller agent timer — last-resort voice calling
        self._caller_timer = QTimer(self)
        self._caller_timer.timeout.connect(self._check_stalled_leads)
        self.voice_ctrl = None       # injected by main_window
        self.autonomy_ctrl = None    # injected by main_window
        self.voice_engine = None     # injected by main_window

        self._fleet_running = False

    # ─── Fleet lifecycle ──────────────────────────────────────────────

    def boot_fleet(self):
        """Boot all agents and start timers."""
        try:
            result = self.fleet.boot_fleet()
            if result.get("success"):
                self._fleet_running = True
                self._heartbeat_timer.start(AGENT_HEARTBEAT_CHECK_MS)
                self._observer_timer.start(OBSERVER_CHECK_INTERVAL_MS)
                self._escalation_timer.start(ESCALATION_CHECK_INTERVAL_MS)
                self._improvement_timer.start(SELF_IMPROVEMENT_INTERVAL_MS)
                # Start pipeline automation timers
                if self.reply_ctrl:
                    self.reply_ctrl.start()
                if self.sequence_ctrl:
                    self.sequence_ctrl.start()
                if self.outreach_ctrl:
                    self.outreach_ctrl.start_schedule_timer()
                # Start caller agent timer (voice call last resort)
                self._caller_timer.start(CALLER_CHECK_INTERVAL_MS)
                logger.info("Fleet booted — all timers started")
            self.fleet_booted.emit(result)
        except Exception as e:
            logger.error(f"Fleet boot error: {e}")
            self.error.emit(str(e))

    def shutdown_fleet(self):
        """Shut down all agents and stop timers."""
        try:
            self._heartbeat_timer.stop()
            self._observer_timer.stop()
            self._escalation_timer.stop()
            self._improvement_timer.stop()
            self._caller_timer.stop()
            # Stop pipeline automation timers
            if self.reply_ctrl:
                self.reply_ctrl.stop()
            if self.sequence_ctrl:
                self.sequence_ctrl.stop()
            if self.outreach_ctrl:
                self.outreach_ctrl.stop_schedule_timer()
            self._fleet_running = False
            self.fleet.shutdown_fleet()
            logger.info("Fleet shut down — all timers stopped")
            self.fleet_shutdown.emit()
        except Exception as e:
            logger.error(f"Fleet shutdown error: {e}")
            self.error.emit(str(e))

    @property
    def is_running(self) -> bool:
        return self._fleet_running

    # ─── Status queries ───────────────────────────────────────────────

    def refresh_fleet_status(self):
        """Get fleet-wide status and emit to UI."""
        try:
            result = self.fleet.get_fleet_status()
            self.fleet_status_ready.emit(result)
        except Exception as e:
            self.error.emit(str(e))

    def run_health_check(self):
        """Run observer health check and emit results."""
        try:
            result = self.observer.run_fleet_health_check()
            self.health_check_ready.emit(result)
        except Exception as e:
            self.error.emit(str(e))

    def run_anomaly_detection(self):
        """Run anomaly detection and emit results."""
        try:
            result = self.observer.detect_anomalies()
            self.anomalies_ready.emit(result)
        except Exception as e:
            self.error.emit(str(e))

    def get_daily_report(self):
        """Generate daily report and emit."""
        try:
            result = self.observer.aggregate_daily_report()
            self.daily_report_ready.emit(result)
        except Exception as e:
            self.error.emit(str(e))

    # ─── Per-agent actions ────────────────────────────────────────────

    def get_agent_status(self, agent_id: int):
        """Get detailed status for one agent."""
        try:
            result = self.agent_engine.get_agent_status(agent_id)
            self.agent_status_ready.emit(result)
        except Exception as e:
            self.error.emit(str(e))

    def boot_agent(self, agent_id: int):
        """Boot a single agent."""
        try:
            self.agent_engine.boot_agent(agent_id)
            self.agent_updated.emit(agent_id)
        except Exception as e:
            self.error.emit(str(e))

    def shutdown_agent(self, agent_id: int):
        """Shut down a single agent."""
        try:
            self.agent_engine.shutdown_agent(agent_id)
            self.agent_updated.emit(agent_id)
        except Exception as e:
            self.error.emit(str(e))

    def update_agent_field(self, agent_id: int, field: str, value: str):
        """Update an agent configuration field."""
        try:
            result = self.agent_engine.update_agent_field(agent_id, field, value)
            if result.get("success"):
                self.agent_updated.emit(agent_id)
            else:
                self.error.emit(result.get("error", "Unknown error"))
        except Exception as e:
            self.error.emit(str(e))

    # ─── Dispatch ─────────────────────────────────────────────────────

    def dispatch_task(self, task_type: str, payload: dict):
        """Dispatch a task to the fleet."""
        try:
            result = self.fleet.dispatch(task_type, payload)
            self.dispatch_result.emit(result)
        except Exception as e:
            self.error.emit(str(e))

    def triage_command(self, raw_command: str):
        """Triage a natural language command into fleet subtasks with pipeline support."""
        try:
            result = self.fleet.triage_incoming_work(raw_command)
            self.triage_result.emit(result)

            if result.get("success"):
                subtasks = result.get("subtasks", [])

                # Check if any subtask has dependencies → pipeline mode
                has_deps = any(st.get("depends_on") for st in subtasks)

                if has_deps:
                    pipeline_result = self.fleet.execute_pipeline(subtasks)
                    self.pipeline_complete.emit(pipeline_result)
                else:
                    for st in subtasks:
                        self.fleet.dispatch(st["task_type"], st.get("payload", {}))
        except Exception as e:
            self.error.emit(str(e))

    # ─── Canary ───────────────────────────────────────────────────────

    def test_canary_update(self, config: dict):
        """Test a config change on the canary first."""
        try:
            result = self.fleet.apply_canary_update(config)
            self.dispatch_result.emit(result)
        except Exception as e:
            self.error.emit(str(e))

    # ─── Escalation ──────────────────────────────────────────────────

    def run_escalation_check(self):
        """Run escalation check for blocked tickets (called by timer).
        Also triggers due-date check via kanban_ctrl."""
        if not self.escalation_engine:
            return
        try:
            result = self.escalation_engine.check_and_escalate()
            if result.get("success") and result.get("count", 0) > 0:
                self.escalation_triggered.emit(result)
        except Exception as e:
            logger.error(f"Escalation check error: {e}")

        # Piggyback due-date check on the same timer interval
        if self.kanban_ctrl:
            try:
                self.kanban_ctrl.check_due_dates()
            except Exception as e:
                logger.error(f"Due-date check error: {e}")

    def process_ticket_requests(self):
        """Process pending agent ticket requests."""
        if not self.escalation_engine:
            return
        try:
            result = self.escalation_engine.get_pending_requests()
            if result.get("success"):
                self.ticket_request_processed.emit(result)
        except Exception as e:
            logger.error(f"Ticket request processing error: {e}")

    def _run_improvement_cycle(self):
        """Run daily self-improvement cycle (called by timer)."""
        if not self.self_improvement_engine:
            return
        try:
            result = self.self_improvement_engine.run_improvement_cycle()
            if result.get("success"):
                logger.info(f"Self-improvement cycle: {result.get('data', {})}")
        except Exception as e:
            logger.debug(f"Self-improvement cycle error: {e}")

    # ─── Internal ─────────────────────────────────────────────────────

    def _run_heartbeats(self):
        """Run heartbeats for all agents (called by timer)."""
        try:
            agents_result = self.agent_engine.get_all_agents()
            if not agents_result.get("success"):
                return
            for agent in agents_result["data"]:
                if agent["status"] in ("idle", "running"):
                    self.agent_engine.run_heartbeat(agent["id"])
        except Exception as e:
            logger.error(f"Heartbeat cycle error: {e}")

    # ─── Caller Agent (Last-Resort Voice) ─────────────────────────────

    def _check_stalled_leads(self):
        """Find leads eligible for voice call (last resort) and queue for approval."""
        if not self.voice_engine or not self.autonomy_ctrl:
            return
        try:
            from database.schema import Settings
            with self.db_manager.session_scope() as session:
                settings = session.query(Settings).first()
                if not settings or not getattr(settings, 'voice_call_enabled', False):
                    return  # Voice calling disabled by user

            stalled = self._find_call_eligible_leads()
            for lead_info in stalled:
                self.autonomy_ctrl.queue_for_approval(
                    action_type="make_call",
                    description=f"Call {lead_info['name']} — {lead_info['reason']}",
                    payload={"lead_id": lead_info["lead_id"]},
                    lead_id=lead_info["lead_id"],
                )
            if stalled:
                logger.info(f"Queued {len(stalled)} leads for voice call approval")
        except Exception as e:
            logger.error(f"Stalled lead check error: {e}")

    def _find_call_eligible_leads(self) -> list:
        """Find leads with 3+ failed emails OR interested-but-stalled 7+ days."""
        from datetime import datetime, timedelta
        from sqlalchemy import func
        from database.schema import (
            Lead, FollowUpSend, ConversationThread, VoiceCall, PendingApproval,
        )

        results = []
        cutoff = datetime.utcnow() - timedelta(days=CALLER_STALLED_DAYS)

        with self.db_manager.session_scope() as session:
            # Skip leads with existing calls or pending call approvals
            existing_calls = session.query(VoiceCall.lead_id).filter(
                VoiceCall.status.in_(["queued", "ringing", "in_progress", "completed"])
            ).all()
            already_called = {c[0] for c in existing_calls}

            pending = session.query(PendingApproval.lead_id).filter(
                PendingApproval.action_type == "make_call",
                PendingApproval.status == "pending",
            ).all()
            already_queued = {p[0] for p in pending if p[0]}
            skip_ids = already_called | already_queued

            # Condition 1: 3+ failed/bounced follow-up sends
            failed_query = (
                session.query(Lead.id, Lead.business_name, func.count(FollowUpSend.id))
                .join(FollowUpSend, FollowUpSend.lead_id == Lead.id)
                .filter(FollowUpSend.status == "failed")
                .filter(Lead.phone.isnot(None), Lead.phone != "")
                .group_by(Lead.id, Lead.business_name)
                .having(func.count(FollowUpSend.id) >= CALLER_FAILED_EMAIL_THRESHOLD)
            )
            if skip_ids:
                failed_query = failed_query.filter(Lead.id.notin_(skip_ids))
            for lead_id, name, count in failed_query.all():
                results.append({
                    "lead_id": lead_id,
                    "name": name or "Unknown",
                    "reason": f"{count} failed emails",
                })

            # Condition 2: Interested but stalled (reply_intent="interested", last_activity > 7 days ago)
            stalled_query = (
                session.query(Lead.id, Lead.business_name)
                .join(ConversationThread, ConversationThread.lead_id == Lead.id)
                .filter(ConversationThread.reply_intent == "interested")
                .filter(ConversationThread.last_activity < cutoff)
                .filter(Lead.phone.isnot(None), Lead.phone != "")
            )
            if skip_ids:
                stalled_query = stalled_query.filter(Lead.id.notin_(skip_ids))
            found_ids = {r["lead_id"] for r in results}
            for lead_id, name in stalled_query.all():
                if lead_id not in found_ids:
                    results.append({
                        "lead_id": lead_id,
                        "name": name or "Unknown",
                        "reason": "interested but stalled 7+ days",
                    })

        return results
