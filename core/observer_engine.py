"""
Aura — Observer Engine
Fleet-wide health monitoring, anomaly detection, and daily reporting.
"""

from datetime import datetime, timedelta

from database.db_manager import DatabaseManager
from database.schema import Agent, AgentTask, AgentMessage, AgentMemoryLog
from core.agent_engine import AgentEngine
from utils.logger import get_logger

logger = get_logger("observer_engine")


class ObserverEngine:
    """Monitors fleet health and generates reports."""

    def __init__(self, db_manager: DatabaseManager, agent_engine: AgentEngine):
        self.db_manager = db_manager
        self.agent_engine = agent_engine

    def run_fleet_health_check(self) -> dict:
        """Check all agents for heartbeat staleness, error rates, task queues."""
        try:
            now = datetime.utcnow()
            with self.db_manager.session_scope() as session:
                agents = session.query(Agent).all()

                healthy = []
                warning = []
                critical = []

                for a in agents:
                    status = "healthy"
                    issues = []

                    # Check heartbeat staleness
                    if a.heartbeat_last:
                        stale_threshold = timedelta(
                            minutes=(a.heartbeat_interval_mins or 30) * 2
                        )
                        if now - a.heartbeat_last > stale_threshold:
                            status = "warning"
                            issues.append("stale heartbeat")
                    else:
                        if a.status != "idle":
                            issues.append("never heartbeated")

                    # Check error state
                    if a.status == "error":
                        status = "critical"
                        issues.append("in error state")

                    # Check high failure rate
                    completed = a.tasks_completed or 0
                    failed = a.tasks_failed or 0
                    if completed + failed > 5 and failed > completed * 0.5:
                        status = "warning" if status != "critical" else status
                        issues.append(f"high failure rate ({failed}/{completed + failed})")

                    entry = {
                        "id": a.id,
                        "name": a.name,
                        "role": a.role,
                        "identity_emoji": a.identity_emoji,
                        "status": status,
                        "issues": issues,
                        "agent_status": a.status,
                        "heartbeat_last": (
                            a.heartbeat_last.isoformat() if a.heartbeat_last else None
                        ),
                    }

                    if status == "critical":
                        critical.append(entry)
                    elif status == "warning":
                        warning.append(entry)
                    else:
                        healthy.append(entry)

                total = len(agents)
                health_pct = int(len(healthy) / total * 100) if total > 0 else 0

                # Mark stale agents as error
                for c in critical:
                    agent = session.query(Agent).filter_by(id=c["id"]).first()
                    if agent and agent.status not in ("idle", "error"):
                        agent.status = "error"

            result = {
                "success": True,
                "data": {
                    "health_pct": health_pct,
                    "total": total,
                    "healthy_count": len(healthy),
                    "warning_count": len(warning),
                    "critical_count": len(critical),
                    "healthy": healthy,
                    "warning": warning,
                    "critical": critical,
                },
            }

            if len(critical) > 0:
                logger.warning(
                    f"Fleet health: {health_pct}% — {len(critical)} critical agents"
                )
            else:
                logger.debug(f"Fleet health: {health_pct}%")

            return result
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"success": False, "error": str(e)}

    def aggregate_daily_report(self) -> dict:
        """Generate end-of-day fleet performance summary."""
        try:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            with self.db_manager.session_scope() as session:
                agents = session.query(Agent).all()

                report_lines = []
                total_tasks = 0
                total_cost = 0.0

                for a in agents:
                    completed = a.tasks_completed or 0
                    failed = a.tasks_failed or 0
                    cost = a.total_cost_usd or 0.0

                    total_tasks += completed
                    total_cost += cost

                    if completed > 0 or failed > 0:
                        report_lines.append(
                            f"{a.identity_emoji} {a.name}: "
                            f"{completed} completed, {failed} failed, "
                            f"${cost:.4f}"
                        )

                # Get today's memory logs count
                log_count = (
                    session.query(AgentMemoryLog)
                    .filter_by(log_date=today)
                    .count()
                )

            summary = (
                f"Fleet Daily Report ({today})\n"
                f"{'=' * 40}\n"
                f"Total tasks: {total_tasks}\n"
                f"Total cost: ${total_cost:.4f}\n"
                f"Memory logs today: {log_count}\n\n"
                + "\n".join(report_lines) if report_lines
                else "No agent activity today."
            )

            return {
                "success": True,
                "data": {
                    "date": today,
                    "total_tasks": total_tasks,
                    "total_cost": total_cost,
                    "log_count": log_count,
                    "summary": summary,
                    "agent_details": report_lines,
                },
            }
        except Exception as e:
            logger.error(f"Daily report failed: {e}")
            return {"success": False, "error": str(e)}

    def detect_anomalies(self) -> dict:
        """Detect fleet anomalies: stuck tasks, high errors, silent agents."""
        try:
            now = datetime.utcnow()
            anomalies = []

            with self.db_manager.session_scope() as session:
                # Stuck tasks (running > 30 minutes)
                stuck_threshold = now - timedelta(minutes=30)
                stuck = (
                    session.query(AgentTask)
                    .filter(
                        AgentTask.status == "running",
                        AgentTask.started_at < stuck_threshold,
                    )
                    .all()
                )
                for t in stuck:
                    anomalies.append({
                        "type": "stuck_task",
                        "severity": "warning",
                        "message": f"Task #{t.id} ({t.task_type}) stuck running for >30min",
                        "agent_id": t.agent_id,
                        "task_id": t.id,
                    })

                # Silent agents (no heartbeat in 2 hours, but status is active/running)
                silent_threshold = now - timedelta(hours=2)
                silent = (
                    session.query(Agent)
                    .filter(
                        Agent.status.in_(["running", "idle"]),
                        Agent.heartbeat_last < silent_threshold,
                    )
                    .all()
                )
                for a in silent:
                    if a.heartbeat_last:  # Only flag if they had heartbeated before
                        anomalies.append({
                            "type": "silent_agent",
                            "severity": "warning",
                            "message": f"Agent '{a.name}' has been silent for >2 hours",
                            "agent_id": a.id,
                        })

                # High error rate agents
                agents = session.query(Agent).all()
                for a in agents:
                    completed = a.tasks_completed or 0
                    failed = a.tasks_failed or 0
                    total = completed + failed
                    if total >= 10 and failed > completed * 0.5:
                        anomalies.append({
                            "type": "high_error_rate",
                            "severity": "critical",
                            "message": (
                                f"Agent '{a.name}' failing {failed}/{total} tasks "
                                f"({int(failed / total * 100)}%)"
                            ),
                            "agent_id": a.id,
                        })

            severity = "info"
            if any(a["severity"] == "critical" for a in anomalies):
                severity = "critical"
            elif any(a["severity"] == "warning" for a in anomalies):
                severity = "warning"

            return {
                "success": True,
                "data": {
                    "anomalies": anomalies,
                    "count": len(anomalies),
                    "severity": severity,
                },
            }
        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
            return {"success": False, "error": str(e)}
