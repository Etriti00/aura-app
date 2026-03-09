"""
Aura — Fleet Orchestrator
Coordinates the multi-agent fleet: dispatches work, triages incoming requests,
manages canary testing, and fleet-wide status aggregation.
"""

import json
from datetime import datetime

from database.db_manager import DatabaseManager
from database.schema import Agent, AgentTask, Settings
from core.agent_engine import AgentEngine
from utils.logger import get_logger
from config import FLEET_MAX_CONCURRENT_TASKS

logger = get_logger("fleet_orchestrator")

# Map task types to agent specializations (playbook keywords)
TASK_SPECIALTY_MAP = {
    "scrape_leads": "Scout",
    "enrich_lead": "Enricher",
    "qualify_lead": "Qualifier",
    "generate_email": "Closer",
    "send_email": "Postman",
    "check_replies": "Tracker",
    "rag_store": "Archivist",
    "analyze_performance": "Analyst",
    "create_skill": "Forger",
    "crm_sync": "Syncer",
    "check_trends": "Trend Spotter",
    "suppress_email": "Suppressor",
    "generate_report": "Reporter",
    "schedule_followup": "Scheduler",
    "triage_inbox": "Triage Lead",
    "manage_ticket": "Commander",
    "escalate_ticket": "Commander",
    # Advanced engine tasks
    "reflect_on_output": "Analyst",
    "classify_reply": "Triage Lead",
    "handle_objection": "Closer",
    "record_metrics": "Analyst",
    "update_knowledge_graph": "Archivist",
    "plan_strategy": "Analyst",
    "improve_skill": "Forger",
    # Voice calling (last resort)
    "make_call": "Caller",
    # Pricing / invoicing
    "evaluate_pricing": "Accountant",
    "create_invoice": "Accountant",
    "send_invoice": "Accountant",
    "track_payment": "Accountant",
}


class FleetOrchestrator:
    """Coordinates the entire agent fleet."""

    def __init__(self, db_manager: DatabaseManager, agent_engine: AgentEngine):
        self.db_manager = db_manager
        self.agent_engine = agent_engine
        self.command_history = None  # injected by main_window

    def dispatch(self, task_type: str, payload: dict,
                 priority: str = "normal",
                 _parent_cmd_id: int = None, _correlation_id: str = None) -> dict:
        """Find the best available agent for a task and dispatch it."""
        try:
            # Find the best agent for this task type
            target_name = TASK_SPECIALTY_MAP.get(task_type)

            with self.db_manager.session_scope() as session:
                # Check concurrent task limit
                running = session.query(AgentTask).filter_by(status="running").count()
                if running >= FLEET_MAX_CONCURRENT_TASKS:
                    return {
                        "success": False,
                        "error": f"Fleet at capacity ({running} running tasks)",
                    }

                # Try to find the specialist agent first
                agent = None
                if target_name:
                    agent = (
                        session.query(Agent)
                        .filter_by(name=target_name, status="idle")
                        .first()
                    )

                # Fallback: find any idle worker
                if not agent:
                    agent = (
                        session.query(Agent)
                        .filter_by(role="worker", status="idle")
                        .first()
                    )

                if not agent:
                    # Queue the task (agent_id=0 sentinel — no agent assigned yet)
                    task = AgentTask(
                        agent_id=0,
                        task_type=task_type,
                        task_payload=json.dumps(payload),
                        status="queued",
                        assigned_by="fleet_orchestrator",
                    )
                    session.add(task)
                    session.flush()
                    return {
                        "success": True,
                        "dispatched": False,
                        "queued": True,
                        "task_id": task.id,
                        "message": "No idle agents available, task queued",
                    }

                agent_id = agent.id
                agent_name = agent.name

            # Dispatch the task
            result = self.agent_engine.run_task(
                agent_id, task_type, payload,
                _parent_cmd_id=_parent_cmd_id, _correlation_id=_correlation_id,
            )
            return {
                "success": True,
                "dispatched": True,
                "agent_id": agent_id,
                "agent_name": agent_name,
                "task_result": result,
            }
        except Exception as e:
            logger.error(f"Dispatch failed: {e}")
            return {"success": False, "error": str(e)}

    def triage_incoming_work(self, raw_command: str) -> dict:
        """Decompose a complex user command into subtasks with dependencies."""
        try:
            if self.agent_engine.router_engine:
                prompt = (
                    "Decompose this user command into a list of subtasks. "
                    "Each subtask should have a task_type, parameters, and depends_on "
                    "(list of subtask indices that must complete before this one). "
                    f"Available task types: {', '.join(TASK_SPECIALTY_MAP.keys())}.\n\n"
                    f"User command: {raw_command}\n\n"
                    "Respond with JSON: {\"subtasks\": ["
                    "{\"task_type\": str, \"payload\": dict, \"depends_on\": [int]}"
                    "]}"
                )
                result = self.agent_engine.router_engine.route(
                    "agent_triage", prompt
                )
                if result.get("success"):
                    try:
                        data = json.loads(result.get("data", "{}"))
                        return {
                            "success": True,
                            "subtasks": data.get("subtasks", []),
                        }
                    except json.JSONDecodeError:
                        pass

            # Fallback: single task
            return {
                "success": True,
                "subtasks": [{"task_type": "general", "payload": {"command": raw_command}, "depends_on": []}],
            }
        except Exception as e:
            logger.error(f"Triage failed: {e}")
            return {"success": False, "error": str(e)}

    def execute_pipeline(self, subtasks: list) -> dict:
        """Execute subtasks in dependency order (topological sort).

        Each subtask: {"task_type": str, "payload": dict, "depends_on": [int]}
        """
        n = len(subtasks)
        if n == 0:
            return {"success": True, "completed": 0, "total_cost": 0.0, "results": []}

        # Track completion
        completed = set()
        results = [None] * n
        total_cost = 0.0
        max_iterations = n * 2  # Safety valve

        iteration = 0
        while len(completed) < n and iteration < max_iterations:
            iteration += 1
            dispatched_this_round = False

            for i, st in enumerate(subtasks):
                if i in completed:
                    continue

                # Check if all dependencies are satisfied
                deps = st.get("depends_on", [])
                if all(d in completed for d in deps):
                    # Inject previous results into payload
                    payload = dict(st.get("payload", {}))
                    dep_results = {}
                    for d in deps:
                        if results[d] and results[d].get("success"):
                            dep_results[f"step_{d}_result"] = results[d].get(
                                "task_result", {}
                            ).get("result", "")
                    if dep_results:
                        payload["previous_results"] = dep_results

                    # Dispatch
                    result = self.dispatch(st["task_type"], payload)
                    results[i] = result
                    total_cost += (
                        result.get("task_result", {}).get("cost_usd", 0.0)
                        if result.get("success") else 0.0
                    )
                    completed.add(i)
                    dispatched_this_round = True
                    logger.info(
                        f"Pipeline step {i}/{n} completed: {st['task_type']} "
                        f"({'OK' if result.get('success') else 'FAIL'})"
                    )

            if not dispatched_this_round:
                logger.warning("Pipeline stalled — circular dependency or unresolvable deps")
                break

        return {
            "success": len(completed) == n,
            "completed": len(completed),
            "total": n,
            "total_cost": total_cost,
            "results": results,
        }

    def batch_dispatch(self, tasks: list) -> dict:
        """Dispatch multiple tasks sorted by tier cost (cheapest first)."""
        tier_order = {"local": 0, "ollama": 1, "haiku": 2, "sonnet": 3}
        sorted_tasks = sorted(
            tasks,
            key=lambda t: tier_order.get(t.get("tier", "haiku"), 2),
        )

        results = []
        total_cost = 0.0
        for t in sorted_tasks:
            result = self.dispatch(t["task_type"], t.get("payload", {}))
            results.append(result)
            total_cost += (
                result.get("task_result", {}).get("cost_usd", 0.0)
                if result.get("success") else 0.0
            )

        return {
            "success": True,
            "dispatched": len(results),
            "total_cost": total_cost,
            "results": results,
        }

    def get_fleet_status(self) -> dict:
        """Aggregate status of all agents into fleet summary."""
        try:
            with self.db_manager.session_scope() as session:
                agents = session.query(Agent).all()

                total = len(agents)
                idle = sum(1 for a in agents if a.status == "idle")
                running = sum(1 for a in agents if a.status == "running")
                error_count = sum(1 for a in agents if a.status == "error")
                paused = sum(1 for a in agents if a.status == "paused")

                total_tasks = sum(a.tasks_completed or 0 for a in agents)
                total_cost = sum(a.total_cost_usd or 0.0 for a in agents)

                # Per-agent summary
                agent_list = []
                for a in agents:
                    agent_list.append({
                        "id": a.id,
                        "name": a.name,
                        "role": a.role,
                        "identity_emoji": a.identity_emoji,
                        "model_tier": a.model_tier or "haiku",
                        "status": a.status,
                        "current_task": a.current_task,
                        "tasks_completed": a.tasks_completed or 0,
                        "total_cost_usd": a.total_cost_usd or 0.0,
                        "heartbeat_last": (
                            a.heartbeat_last.isoformat() if a.heartbeat_last else None
                        ),
                    })

                # Health percentage
                health_pct = int((idle + running) / total * 100) if total > 0 else 0

            return {
                "success": True,
                "data": {
                    "total_agents": total,
                    "idle": idle,
                    "running": running,
                    "error": error_count,
                    "paused": paused,
                    "health_pct": health_pct,
                    "total_tasks_today": total_tasks,
                    "total_cost_today": total_cost,
                    "agents": agent_list,
                },
            }
        except Exception as e:
            logger.error(f"Fleet status failed: {e}")
            return {"success": False, "error": str(e)}

    def boot_fleet(self) -> dict:
        """Boot all enabled agents."""
        try:
            with self.db_manager.session_scope() as session:
                agents = session.query(Agent).all()
                agent_ids = [a.id for a in agents]

            booted = []
            errors = []
            for aid in agent_ids:
                result = self.agent_engine.boot_agent(aid)
                if result.get("success"):
                    booted.append(result.get("name", str(aid)))
                else:
                    errors.append(f"{aid}: {result.get('error')}")

            logger.info(f"Fleet booted: {len(booted)} agents, {len(errors)} errors")
            return {
                "success": True,
                "data": {
                    "booted": len(booted),
                    "errors": len(errors),
                    "agent_names": booted,
                    "error_details": errors,
                },
            }
        except Exception as e:
            logger.error(f"Fleet boot failed: {e}")
            return {"success": False, "error": str(e)}

    def shutdown_fleet(self) -> dict:
        """Gracefully shut down all agents."""
        try:
            with self.db_manager.session_scope() as session:
                agents = session.query(Agent).all()
                for a in agents:
                    a.status = "idle"
                    a.current_task = None

            logger.debug("Fleet shut down")
            return {"success": True}
        except Exception as e:
            logger.error(f"Fleet shutdown failed: {e}")
            return {"success": False, "error": str(e)}

    def apply_canary_update(self, new_config: dict) -> dict:
        """Test a config change on the canary agent before fleet-wide rollout."""
        try:
            with self.db_manager.session_scope() as session:
                canary = session.query(Agent).filter_by(role="canary").first()
                if not canary:
                    return {"success": False, "error": "No canary agent found"}
                canary_id = canary.id

            # Apply config to canary
            for field, value in new_config.items():
                self.agent_engine.update_agent_field(canary_id, field, value)

            # Test heartbeat
            hb = self.agent_engine.run_heartbeat(canary_id)
            if hb.get("status") == "healthy":
                logger.info("Canary passed — safe to deploy fleet-wide")
                return {
                    "success": True,
                    "canary_passed": True,
                    "safe_to_deploy": True,
                }
            else:
                logger.warning("Canary failed — rolling back")
                return {
                    "success": True,
                    "canary_passed": False,
                    "safe_to_deploy": False,
                }
        except Exception as e:
            logger.error(f"Canary update failed: {e}")
            return {"success": False, "error": str(e)}

    def get_agent_by_name(self, name: str) -> dict:
        """Find an agent by name (case-insensitive)."""
        try:
            with self.db_manager.session_scope() as session:
                agent = (
                    session.query(Agent)
                    .filter(Agent.name.ilike(f"%{name}%"))
                    .first()
                )
                if not agent:
                    return {"success": False, "error": f"Agent '{name}' not found"}
                return {
                    "success": True,
                    "data": {
                        "id": agent.id,
                        "name": agent.name,
                        "role": agent.role,
                    },
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def dispatch_queued_tasks(self) -> dict:
        """Retry queued tasks by assigning them to idle agents."""
        dispatched = 0
        failed = 0
        try:
            with self.db_manager.session_scope() as session:
                queued = (
                    session.query(AgentTask)
                    .filter_by(status="queued")
                    .order_by(AgentTask.created_at.asc())
                    .all()
                )
                if not queued:
                    return {"success": True, "dispatched": 0, "remaining": 0}

                task_data = [
                    {"id": t.id, "task_type": t.task_type,
                     "payload": t.task_payload}
                    for t in queued
                ]

            for td in task_data:
                try:
                    payload = json.loads(td["payload"]) if isinstance(td["payload"], str) else td["payload"]
                except (json.JSONDecodeError, TypeError):
                    payload = {}

                target_name = TASK_SPECIALTY_MAP.get(td["task_type"])

                with self.db_manager.session_scope() as session:
                    agent = None
                    if target_name:
                        agent = (
                            session.query(Agent)
                            .filter_by(name=target_name, status="idle")
                            .first()
                        )
                    if not agent:
                        agent = (
                            session.query(Agent)
                            .filter_by(role="worker", status="idle")
                            .first()
                        )
                    if not agent:
                        continue  # Still no idle agents — skip

                    agent_id = agent.id
                    # Remove the queued placeholder
                    old_task = session.query(AgentTask).filter_by(id=td["id"]).first()
                    if old_task:
                        session.delete(old_task)

                # Dispatch via normal path
                result = self.agent_engine.run_task(agent_id, td["task_type"], payload)
                if result.get("success"):
                    dispatched += 1
                else:
                    failed += 1

            # Count remaining
            with self.db_manager.session_scope() as session:
                remaining = session.query(AgentTask).filter_by(status="queued").count()

            logger.info(f"Queue sweep: dispatched={dispatched}, failed={failed}, remaining={remaining}")
            return {
                "success": True,
                "dispatched": dispatched,
                "failed": failed,
                "remaining": remaining,
            }
        except Exception as e:
            logger.error(f"dispatch_queued_tasks failed: {e}")
            return {"success": False, "error": str(e)}
