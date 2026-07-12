"""
Aura — Agent Engine
Individual agent lifecycle: boot, run tasks, send messages, maintain memory.
"""

import json
from datetime import datetime, timedelta

from database.db_manager import DatabaseManager
from database.schema import Agent, AgentTask, AgentMessage, AgentMemoryLog, Skill, Settings
from config import AGENT_MAX_MESSAGES_PER_HOUR
from utils.logger import get_logger

logger = get_logger("agent_engine")

# Legacy task-to-skill name map (kept for backwards compatibility)
TASK_SKILL_MAP = {
    "generate_email": ["Closer", "Consultant", "Cold Outreach"],
    "qualify_lead": ["Qualifier", "Lead Scoring"],
    "qualify_lead_complex": ["Qualifier", "Deep Qualifier"],
    "rag_style_matching": ["RAG", "Style Matching"],
    "write_followup": ["Closer", "Follow-up"],
    "summarize": ["Summarizer", "Analyst"],
    "research": ["Researcher", "Analyst"],
    "enrich_lead": ["Enrichment", "Data"],
}

# Tasks that require a skill — if none found, delegate to Forger
SKILL_REQUIRING_TASKS = {"generate_email", "qualify_lead_complex", "rag_style_matching"}

# Import capability-based matching from skill_registry
try:
    from core.skill_registry import find_best_skill_for_task, build_skill_context
except ImportError:
    find_best_skill_for_task = None
    build_skill_context = None

# Maximum delegation depth to prevent infinite loops
AGENT_MAX_DELEGATION_DEPTH = 3


class AgentEngine:
    """Manages individual agent lifecycle and task execution."""

    def __init__(self, db_manager: DatabaseManager, key_vault,
                 router_engine=None, forge_controller=None,
                 pacing_engine=None, escalation_engine=None):
        self.db_manager = db_manager
        self.key_vault = key_vault
        self.router_engine = router_engine
        self.forge_controller = forge_controller
        self.pacing_engine = pacing_engine
        self.escalation_engine = escalation_engine
        self.command_history = None  # injected by main_window
        self.reflection_engine = None  # injected by main_window
        self.knowledge_graph = None  # injected by main_window
        self.self_improvement_engine = None  # injected by main_window
        self.autonomy_controller = None  # injected by main_window
        self.token_manager = None  # injected by main_window
        self.case_engine = None  # injected by main_window
        self.subagent_engine = None  # injected by main_window
        self.correction_memory = None  # injected by main_window
        self.knowledge_base_engine = None  # injected by main_window
        # Per-agent hourly call counter: {agent_id: [(timestamp, ...)] }
        self._hourly_calls: dict[int, list] = {}

    def boot_agent(self, agent_id: int) -> dict:
        """Set agent status to idle, record heartbeat, log boot event."""
        try:
            with self.db_manager.session_scope() as session:
                agent = session.query(Agent).filter_by(id=agent_id).first()
                if not agent:
                    return {"success": False, "error": f"Agent {agent_id} not found"}

                agent.status = "idle"
                agent.heartbeat_last = datetime.utcnow()
                agent.current_task = None

                # Log boot event
                log = AgentMemoryLog(
                    agent_id=agent_id,
                    log_date=datetime.utcnow().strftime("%Y-%m-%d"),
                    content=f"Agent '{agent.name}' booted at {datetime.utcnow().isoformat()}",
                    memory_type="daily_notes",
                )
                session.add(log)

                name = agent.name
                emoji = agent.identity_emoji

            logger.info(f"Agent '{name}' ({emoji}) booted successfully")
            return {"success": True, "agent_id": agent_id, "name": name}
        except Exception as e:
            logger.error(f"Failed to boot agent {agent_id}: {e}")
            return {"success": False, "error": str(e)}

    def shutdown_agent(self, agent_id: int) -> dict:
        """Gracefully shut down an agent."""
        try:
            with self.db_manager.session_scope() as session:
                agent = session.query(Agent).filter_by(id=agent_id).first()
                if not agent:
                    return {"success": False, "error": f"Agent {agent_id} not found"}

                agent.status = "idle"
                agent.current_task = None
                name = agent.name

            logger.info(f"Agent '{name}' shut down")
            return {"success": True, "agent_id": agent_id}
        except Exception as e:
            logger.error(f"Failed to shutdown agent {agent_id}: {e}")
            return {"success": False, "error": str(e)}

    def _check_hourly_rate(self, agent_id: int) -> bool:
        """Return True if agent is within hourly rate limit."""
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=1)
        calls = self._hourly_calls.get(agent_id, [])
        # Prune old entries
        calls = [t for t in calls if t > cutoff]
        self._hourly_calls[agent_id] = calls
        return len(calls) < AGENT_MAX_MESSAGES_PER_HOUR

    def _record_call(self, agent_id: int):
        """Record a call timestamp for rate limiting."""
        if agent_id not in self._hourly_calls:
            self._hourly_calls[agent_id] = []
        self._hourly_calls[agent_id].append(datetime.utcnow())

    def run_task(self, agent_id: int, task_type: str, payload: dict,
                 _delegation_depth: int = 0,
                 _parent_cmd_id: int = None, _correlation_id: str = None) -> dict:
        """Create and execute a task for the specified agent."""
        try:
            # Enforce hourly rate limit
            if not self._check_hourly_rate(agent_id):
                logger.warning(
                    f"Agent {agent_id} throttled: {AGENT_MAX_MESSAGES_PER_HOUR} calls/hour limit reached"
                )
                return {
                    "success": False,
                    "error": f"Rate limit: agent {agent_id} exceeded {AGENT_MAX_MESSAGES_PER_HOUR} calls/hour",
                    "rate_limited": True,
                }

            # Create task record and find matching skill
            with self.db_manager.session_scope() as session:
                agent = session.query(Agent).filter_by(id=agent_id).first()
                if not agent:
                    return {"success": False, "error": f"Agent {agent_id} not found"}

                if agent.status == "error":
                    return {"success": False, "error": f"Agent '{agent.name}' is in error state"}

                # Skill matching
                skill_data = self._find_matching_skill(
                    session, task_type, payload, agent=agent
                )

                task = AgentTask(
                    agent_id=agent_id,
                    task_type=task_type,
                    task_payload=json.dumps(payload),
                    status="running",
                    started_at=datetime.utcnow(),
                    skill_id=skill_data["id"] if skill_data else None,
                )
                session.add(task)
                session.flush()
                task_id = task.id

                # Update agent state
                agent.status = "running"
                agent.current_task = f"{task_type} (#{task_id})"

                # Build context prompt (with skill injection)
                context = self._build_agent_context(
                    agent, task_type, payload, skill_data=skill_data
                )
                agent_name = agent.name
                model_tier = agent.model_tier
                model_override = getattr(agent, "model_override", None)

            # Record call for rate limiting
            self._record_call(agent_id)

            # Log task dispatch to command history
            cmd_id = None
            if self.command_history:
                try:
                    cmd_entry = self.command_history.log_command(
                        source="system",
                        command_type="task_dispatched",
                        actor_type="agent",
                        agent_id=agent_id,
                        parameters=payload,
                        status="running",
                        parent_command_id=_parent_cmd_id,
                        correlation_id=_correlation_id,
                        linked_task_id=task_id,
                    )
                    cmd_id = cmd_entry.get("data", {}).get("id") if cmd_entry.get("success") else None
                except Exception:
                    pass

            # Forger delegation: if skill required but not found
            if (not skill_data
                    and task_type in SKILL_REQUIRING_TASKS
                    and _delegation_depth < AGENT_MAX_DELEGATION_DEPTH
                    and self.forge_controller):
                forger_result = self._delegate_to_forger(
                    agent_id, task_type, payload, _delegation_depth
                )
                if forger_result and forger_result.get("skill_id"):
                    # Re-run with the newly created skill
                    payload["skill_id"] = forger_result["skill_id"]
                    logger.info(
                        f"Forger created skill #{forger_result['skill_id']} "
                        f"for task '{task_type}', re-running"
                    )
                    # Reset agent to idle before retry
                    with self.db_manager.session_scope() as session:
                        agent = session.query(Agent).filter_by(id=agent_id).first()
                        if agent:
                            agent.status = "idle"
                            agent.current_task = None
                    return self.run_task(
                        agent_id, task_type, payload,
                        _delegation_depth=_delegation_depth + 1,
                    )

            # Pacing-aware tier downgrade
            effective_tier = model_tier
            if self.pacing_engine and model_tier not in ("local", "ollama"):
                try:
                    pacing_status = self.pacing_engine.get_status()
                    if pacing_status.get("active"):
                        allowed_max = pacing_status.get("current_max_tier", "sonnet")
                        tier_rank = {"local": 0, "ollama": 1, "haiku": 2, "sonnet": 3}
                        if tier_rank.get(model_tier, 0) > tier_rank.get(allowed_max, 3):
                            logger.info(
                                f"Pacing downgrade: {model_tier} → {allowed_max} "
                                f"for agent '{agent_name}'"
                            )
                            effective_tier = allowed_max
                except Exception:
                    pass

            # ── Autonomy gate: check permission before executing ──
            if self.autonomy_controller:
                try:
                    perm = self.autonomy_controller.check_permission(task_type)
                    perm_data = perm.get("data", {})
                    if perm_data.get("needs_approval") and not perm_data.get("allowed"):
                        self.autonomy_controller.queue_for_approval(
                            action_type=task_type,
                            description=f"Agent '{agent_name}' wants to run '{task_type}'",
                            payload=payload,
                            agent_id=agent_id,
                            lead_id=payload.get("lead_id"),
                        )
                        # Return the task as pending approval
                        with self.db_manager.session_scope() as session:
                            task_obj = session.query(AgentTask).filter_by(id=task_id).first()
                            if task_obj:
                                task_obj.status = "pending_approval"
                            agent_obj = session.query(Agent).filter_by(id=agent_id).first()
                            if agent_obj:
                                agent_obj.status = "idle"
                                agent_obj.current_task = None
                        return {
                            "success": False,
                            "error": f"Requires approval at '{perm_data.get('level', 'supervised')}' level",
                            "needs_approval": True,
                            "task_id": task_id,
                        }
                except Exception as e:
                    logger.debug(f"Autonomy check failed, proceeding: {e}")

            # Execute via router if available
            result_data = None
            cost = 0.0
            tokens = 0
            prompt_hash = None
            used_cache = False

            if self.router_engine and effective_tier != "local":
                # Response cache check
                if self.token_manager:
                    prompt_hash = self.token_manager.hash_prompt(context)
                    cached = self.token_manager.get_cached_response(prompt_hash)
                    if cached:
                        logger.debug(f"Cache hit for task '{task_type}' — skipping LLM call")
                        result_data = cached.get("data", "")
                        cost = 0.0
                        tokens = 0
                        used_cache = True

                # Subagent decomposition check
                if (not used_cache and self.subagent_engine
                        and self.subagent_engine.should_decompose(task_type)):
                    try:
                        sub_result = self.subagent_engine.decompose_and_run(
                            parent_task_id=task_id,
                            task_type=task_type,
                            payload=payload,
                            lead_context=context,
                            skill_data=skill_data,
                        )
                        if sub_result.get("success") and sub_result.get("decomposed"):
                            result_data = sub_result["result"]
                            cost = sub_result.get("total_cost_usd", 0.0)
                            tokens = sub_result.get("total_tokens", 0)
                            used_cache = True  # skip normal router call
                    except Exception as e:
                        logger.debug(f"Subagent decomposition failed, falling back: {e}")

                # Normal router call (if not cached/decomposed)
                if not used_cache:
                    try:
                        route_result = self.router_engine.route(
                            task_type, context, tier_override=effective_tier,
                            model_override=model_override,
                        )
                        if route_result.get("success"):
                            result_data = route_result.get("data", "")
                            cost = route_result.get("cost_usd", 0.0)
                            tokens = route_result.get("tokens", 0)
                            # Cache the successful response
                            if prompt_hash and self.token_manager:
                                self.token_manager.cache_response(
                                    prompt_hash, route_result
                                )
                        else:
                            result_data = route_result.get("error", "Router returned failure")
                    except Exception as e:
                        result_data = f"Router error: {e}"
            else:
                result_data = f"Task '{task_type}' acknowledged by {agent_name} (local tier)"

            # Update task and agent
            with self.db_manager.session_scope() as session:
                task = session.query(AgentTask).filter_by(id=task_id).first()
                agent = session.query(Agent).filter_by(id=agent_id).first()

                if task:
                    task.status = "completed"
                    task.result = str(result_data)[:5000] if result_data else ""
                    task.completed_at = datetime.utcnow()
                    task.cost_usd = cost
                    task.tokens_used = tokens
                    if prompt_hash:
                        task.context_hash = prompt_hash

                if agent:
                    agent.status = "idle"
                    agent.current_task = None
                    agent.tasks_completed = (agent.tasks_completed or 0) + 1
                    agent.total_cost_usd = (agent.total_cost_usd or 0.0) + cost

                    # Append to daily memory
                    skill_note = f" (skill: {skill_data['name']})" if skill_data else ""
                    note = f"[{datetime.utcnow().strftime('%H:%M')}] Completed {task_type}{skill_note}"
                    agent.memory_today = (
                        f"{agent.memory_today}\n{note}" if agent.memory_today else note
                    )

            logger.info(f"Agent '{agent_name}' completed task '{task_type}' (${cost:.4f})")

            # Log completion to command history
            if self.command_history and cmd_id:
                try:
                    self.command_history.update_command_status(
                        cmd_id, "completed",
                        result={"result": str(result_data)[:1000], "skill_used": skill_data["name"] if skill_data else None},
                        cost_usd=cost, tokens_used=tokens,
                    )
                except Exception:
                    pass

            # ─── Post-task hooks: Reflection, Metrics, Knowledge Graph, Case Notes ─
            self._post_task_hooks(
                agent_id, task_id, task_type, agent_name,
                result_data, cost, skill_data, payload=payload,
            )

            return {
                "success": True,
                "task_id": task_id,
                "agent_name": agent_name,
                "result": result_data,
                "cost_usd": cost,
                "tokens": tokens,
                "skill_used": skill_data["name"] if skill_data else None,
            }
        except Exception as e:
            logger.error(f"Task execution failed for agent {agent_id}: {e}")
            # Log failure to command history
            if self.command_history and cmd_id:
                try:
                    self.command_history.update_command_status(
                        cmd_id, "failed", result={"error": str(e)[:500]},
                    )
                except Exception:
                    pass
            # Mark task as failed
            try:
                with self.db_manager.session_scope() as session:
                    agent = session.query(Agent).filter_by(id=agent_id).first()
                    if agent:
                        agent.status = "idle"
                        agent.current_task = None
                        agent.tasks_failed = (agent.tasks_failed or 0) + 1
            except Exception:
                pass
            return {"success": False, "error": str(e)}

    def delegate_task(self, from_agent_id: int, to_agent_id: int,
                      task_type: str, payload: dict) -> dict:
        """Delegate a task from one agent to another."""
        try:
            with self.db_manager.session_scope() as session:
                # Create delegation message
                msg = AgentMessage(
                    from_agent_id=from_agent_id,
                    to_agent_id=to_agent_id,
                    message_type="task_delegation",
                    content=json.dumps({
                        "task_type": task_type,
                        "payload": payload,
                    }),
                    sent_at=datetime.utcnow(),
                )
                session.add(msg)
                session.flush()
                msg_id = msg.id

            # Execute the task on the target agent
            result = self.run_task(to_agent_id, task_type, payload)
            return {
                "success": True,
                "message_id": msg_id,
                "delegation_result": result,
            }
        except Exception as e:
            logger.error(f"Delegation failed: {e}")
            return {"success": False, "error": str(e)}

    def send_message(self, from_id: int, to_id: int,
                     message_type: str, content: dict) -> dict:
        """Send a message between agents."""
        try:
            with self.db_manager.session_scope() as session:
                msg = AgentMessage(
                    from_agent_id=from_id,
                    to_agent_id=to_id,
                    message_type=message_type,
                    content=json.dumps(content),
                    sent_at=datetime.utcnow(),
                )
                session.add(msg)
                session.flush()
                msg_id = msg.id

            return {"success": True, "message_id": msg_id}
        except Exception as e:
            logger.error(f"Send message failed: {e}")
            return {"success": False, "error": str(e)}

    def get_messages(self, agent_id: int, unread_only: bool = True,
                     limit: int = 50) -> dict:
        """Retrieve messages for an agent."""
        try:
            with self.db_manager.session_scope() as session:
                q = session.query(AgentMessage).filter_by(to_agent_id=agent_id)
                if unread_only:
                    q = q.filter_by(acknowledged=False)
                messages = q.order_by(AgentMessage.sent_at.desc()).limit(limit).all()

                result = []
                for m in messages:
                    result.append({
                        "id": m.id,
                        "from_agent_id": m.from_agent_id,
                        "message_type": m.message_type,
                        "content": m.content,
                        "sent_at": m.sent_at.isoformat() if m.sent_at else None,
                    })

            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_heartbeat(self, agent_id: int) -> dict:
        """Record heartbeat and check pending work."""
        try:
            with self.db_manager.session_scope() as session:
                agent = session.query(Agent).filter_by(id=agent_id).first()
                if not agent:
                    return {"success": False, "error": f"Agent {agent_id} not found"}

                agent.heartbeat_last = datetime.utcnow()

                # Count unread messages
                unread = session.query(AgentMessage).filter_by(
                    to_agent_id=agent_id, acknowledged=False
                ).count()

                # Count pending tasks
                pending = session.query(AgentTask).filter_by(
                    agent_id=agent_id, status="queued"
                ).count()

                # Append heartbeat note
                note = f"[{datetime.utcnow().strftime('%H:%M')}] Heartbeat OK — {unread} unread, {pending} pending"
                agent.memory_today = (
                    f"{agent.memory_today}\n{note}" if agent.memory_today else note
                )

                # Log heartbeat
                log = AgentMemoryLog(
                    agent_id=agent_id,
                    log_date=datetime.utcnow().strftime("%Y-%m-%d"),
                    content=note,
                    memory_type="heartbeat_report",
                )
                session.add(log)

                status = "healthy" if agent.status != "error" else "failed"
                name = agent.name

            return {
                "success": True,
                "agent_id": agent_id,
                "agent_name": name,
                "status": status,
                "pending_tasks": pending,
                "unread_messages": unread,
            }
        except Exception as e:
            logger.error(f"Heartbeat failed for agent {agent_id}: {e}")
            return {"success": False, "error": str(e)}

    def update_agent_memory(self, agent_id: int, new_facts: str,
                            memory_type: str = "daily_notes") -> dict:
        """Add a memory entry for an agent."""
        try:
            with self.db_manager.session_scope() as session:
                agent = session.query(Agent).filter_by(id=agent_id).first()
                if not agent:
                    return {"success": False, "error": f"Agent {agent_id} not found"}

                timestamp = datetime.utcnow().strftime("%H:%M")
                entry = f"[{timestamp}] {new_facts}"

                if memory_type == "daily_notes":
                    agent.memory_today = (
                        f"{agent.memory_today}\n{entry}" if agent.memory_today else entry
                    )
                elif memory_type == "long_term":
                    agent.long_term_memory = (
                        f"{agent.long_term_memory}\n{entry}"
                        if agent.long_term_memory else entry
                    )

                log = AgentMemoryLog(
                    agent_id=agent_id,
                    log_date=datetime.utcnow().strftime("%Y-%m-%d"),
                    content=new_facts,
                    memory_type=memory_type,
                )
                session.add(log)

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def reset_daily_memory(self, agent_id: int) -> dict:
        """Save today's memory to log and reset."""
        try:
            with self.db_manager.session_scope() as session:
                agent = session.query(Agent).filter_by(id=agent_id).first()
                if not agent:
                    return {"success": False, "error": f"Agent {agent_id} not found"}

                if agent.memory_today:
                    log = AgentMemoryLog(
                        agent_id=agent_id,
                        log_date=datetime.utcnow().strftime("%Y-%m-%d"),
                        content=agent.memory_today,
                        memory_type="daily_notes",
                    )
                    session.add(log)

                agent.memory_today = ""

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_agent_status(self, agent_id: int) -> dict:
        """Get comprehensive status for a single agent."""
        try:
            with self.db_manager.session_scope() as session:
                agent = session.query(Agent).filter_by(id=agent_id).first()
                if not agent:
                    return {"success": False, "error": f"Agent {agent_id} not found"}

                # Recent tasks
                recent_tasks = (
                    session.query(AgentTask)
                    .filter_by(agent_id=agent_id)
                    .order_by(AgentTask.created_at.desc())
                    .limit(10)
                    .all()
                )
                tasks_list = []
                for t in recent_tasks:
                    skill_name = ""
                    if t.skill_id:
                        skill = session.query(Skill).filter_by(id=t.skill_id).first()
                        if skill:
                            skill_name = skill.name
                    tasks_list.append({
                        "id": t.id,
                        "task_type": t.task_type,
                        "status": t.status,
                        "cost_usd": t.cost_usd,
                        "skill_name": skill_name,
                        "created_at": t.created_at.isoformat() if t.created_at else None,
                    })

                return {
                    "success": True,
                    "data": {
                        "id": agent.id,
                        "name": agent.name,
                        "role": agent.role,
                        "identity_emoji": agent.identity_emoji,
                        "soul": agent.soul or "",
                        "mission": agent.mission or "",
                        "playbook": agent.playbook or "",
                        "boundaries": agent.boundaries or "",
                        "status": agent.status,
                        "current_task": agent.current_task,
                        "model_tier": agent.model_tier,
                        "model_override": getattr(agent, "model_override", None),
                        "heartbeat_last": agent.heartbeat_last.isoformat() if agent.heartbeat_last else None,
                        "heartbeat_interval_mins": agent.heartbeat_interval_mins,
                        "tasks_completed": agent.tasks_completed or 0,
                        "tasks_failed": agent.tasks_failed or 0,
                        "total_cost_usd": agent.total_cost_usd or 0.0,
                        "memory_today": agent.memory_today or "",
                        "long_term_memory": agent.long_term_memory or "",
                        "boot_script": agent.boot_script or "",
                        "skills": self._assigned_skills_list(agent),
                        "recent_tasks": tasks_list,
                    },
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_all_agents(self) -> dict:
        """Get all agents with their current status."""
        try:
            with self.db_manager.session_scope() as session:
                agents = session.query(Agent).order_by(Agent.role, Agent.name).all()
                result = []
                for a in agents:
                    result.append({
                        "id": a.id,
                        "name": a.name,
                        "role": a.role,
                        "identity_emoji": a.identity_emoji,
                        "status": a.status,
                        "current_task": a.current_task,
                        "model_tier": a.model_tier,
                        "model_override": getattr(a, "model_override", None),
                        "heartbeat_last": a.heartbeat_last.isoformat() if a.heartbeat_last else None,
                        "tasks_completed": a.tasks_completed or 0,
                        "tasks_failed": a.tasks_failed or 0,
                        "total_cost_usd": a.total_cost_usd or 0.0,
                    })

            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_agent_field(self, agent_id: int, field: str, value: str) -> dict:
        """Update a specific agent configuration field."""
        allowed = {
            "soul", "mission", "playbook", "boundaries", "boot_script",
            "long_term_memory", "model_tier", "model_override", "heartbeat_interval_mins",
            "name", "identity_emoji",
        }
        if field not in allowed:
            return {"success": False, "error": f"Field '{field}' not editable"}
        try:
            with self.db_manager.session_scope() as session:
                agent = session.query(Agent).filter_by(id=agent_id).first()
                if not agent:
                    return {"success": False, "error": f"Agent {agent_id} not found"}
                setattr(agent, field, value)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def request_ticket_creation(self, agent_id: int, ticket_data: dict) -> dict:
        """Agent requests to create a ticket. Routed through escalation engine."""
        if not self.escalation_engine:
            return {"success": False, "error": "Escalation engine not available"}
        return self.escalation_engine.process_ticket_request(agent_id, ticket_data)

    def _get_feature_toggles(self) -> dict:
        """Read feature toggles from Settings. Returns defaults on error."""
        try:
            with self.db_manager.session_scope() as session:
                settings = session.query(Settings).first()
                if settings:
                    return {
                        "reflection": getattr(settings, "reflection_enabled", True),
                        "self_improvement": getattr(settings, "self_improvement_enabled", False),
                        "knowledge_graph": getattr(settings, "knowledge_graph_enabled", False),
                    }
        except Exception:
            pass
        return {"reflection": True, "self_improvement": False, "knowledge_graph": False}

    def _post_task_hooks(self, agent_id, task_id, task_type, agent_name,
                         result_data, cost, skill_data, payload=None):
        """Run post-task hooks: reflection, metrics, knowledge graph, case notes."""
        toggles = self._get_feature_toggles()

        # Reflection: critique output and score
        if self.reflection_engine and toggles.get("reflection", True):
            try:
                self.reflection_engine.reflect_on_task(
                    agent_id=agent_id,
                    task_id=task_id,
                    task_type=task_type,
                    output_text=str(result_data)[:2000] if result_data else "",
                    context=f"Agent: {agent_name}, Skill: {skill_data['name'] if skill_data else 'None'}",
                )
            except Exception as e:
                logger.debug(f"Reflection hook failed: {e}")

        # Self-improvement: record performance metric
        if self.self_improvement_engine and toggles.get("self_improvement", False):
            try:
                self.self_improvement_engine.record_metric(
                    agent_id=agent_id,
                    metric_type="task_completion",
                    metric_key=task_type,
                    value=1.0,
                    sample_count=1,
                )
            except Exception as e:
                logger.debug(f"Metrics hook failed: {e}")

        # Knowledge graph: record agent→lead interaction edge
        if self.knowledge_graph and toggles.get("knowledge_graph", False):
            try:
                kg_lead_id = payload.get("lead_id") if payload else None
                if kg_lead_id is not None:
                    self.knowledge_graph.record_interaction(
                        lead_id=kg_lead_id, agent_id=agent_id,
                        interaction_type=task_type,
                        outcome="completed",
                    )
            except Exception as e:
                logger.debug(f"Knowledge graph hook failed: {e}")

        # Case notes: auto-log agent activity to the lead's case file
        if self.case_engine and payload and payload.get("lead_id"):
            note_type_map = {
                "generate_email": "outreach",
                "write_followup": "outreach",
                "qualify_lead": "qualification",
                "qualify_lead_complex": "qualification",
                "enrich_lead": "enrichment",
            }
            note_type = note_type_map.get(task_type, "observation")
            summary = str(result_data)[:500] if result_data else ""
            try:
                self.case_engine.add_note(
                    lead_id=payload["lead_id"],
                    note_type=note_type,
                    content=f"[{task_type}] {summary}",
                    agent_id=agent_id,
                    metadata={"task_id": task_id, "cost_usd": cost},
                )
            except Exception as e:
                logger.debug(f"Case note auto-log failed: {e}")

    def _find_matching_skill(self, session, task_type: str,
                             payload: dict, agent=None) -> dict | None:
        """Find the best matching skill for a task.

        Priority: payload skill_id → payload skill_name → capability match
                  → TASK_SKILL_MAP → is_default.

        Agents carry a least-privilege skill assignment (allowed_skills).
        Assigned skills are preferred; when the best match falls outside
        the assignment, the agent files a skill_request with the Commander
        (tier 1), the grant is logged, and the assignment is widened.
        """
        allowed = self._allowed_skill_names(agent)

        def _finish(skill_dict):
            if skill_dict is None:
                return None
            if allowed is not None and skill_dict.get("name") not in allowed:
                self._grant_skill(session, agent, skill_dict.get("name"))
            return skill_dict

        # Priority 1: Explicit skill_id in payload
        skill_id = payload.get("skill_id")
        if skill_id:
            skill = session.query(Skill).filter_by(id=skill_id).first()
            if skill:
                return _finish(self._skill_to_dict(skill))

        # Priority 2: Skill name in payload
        skill_name = payload.get("skill_name")
        if skill_name:
            skill = session.query(Skill).filter(
                Skill.name.ilike(f"%{skill_name}%")
            ).first()
            if skill:
                return _finish(self._skill_to_dict(skill))

        # Priority 3: Capability-based matching — assigned skills first
        if find_best_skill_for_task:
            all_skills = session.query(Skill).all()
            skill_dicts = [self._skill_to_dict(s) for s in all_skills]
            if allowed is not None:
                assigned = [s for s in skill_dicts if s.get("name") in allowed]
                match = find_best_skill_for_task(assigned, task_type, payload)
                if match:
                    return match
            match = find_best_skill_for_task(skill_dicts, task_type, payload)
            if match:
                return _finish(match)

        # Priority 4: Legacy TASK_SKILL_MAP patterns (fallback)
        patterns = TASK_SKILL_MAP.get(task_type, [])
        for pattern in patterns:
            query = session.query(Skill).filter(
                Skill.name.ilike(f"%{pattern}%")
            )
            skill = None
            if allowed:
                skill = query.filter(Skill.name.in_(allowed)).first()
            if not skill:
                skill = query.first()
            if skill:
                return _finish(self._skill_to_dict(skill))

        # Priority 5: Default skill
        skill = session.query(Skill).filter_by(is_default=True).first()
        if skill:
            return _finish(self._skill_to_dict(skill))

        return None

    @staticmethod
    def _allowed_skill_names(agent):
        """Parse an agent's skill assignment. None = unrestricted (legacy)."""
        if agent is None:
            return None
        raw = getattr(agent, "allowed_skills", None)
        if raw is None or raw == "":
            return None
        try:
            names = json.loads(raw)
            if isinstance(names, list):
                return set(names)
        except (ValueError, TypeError):
            pass
        return None

    def _grant_skill(self, session, agent, skill_name: str) -> None:
        """Widen an agent's assignment through the Commander (tier 1).

        The agent files a skill_request; Commander policy is to grant,
        log both sides of the exchange, and persist the wider assignment
        so the grant survives restarts.
        """
        if agent is None or not skill_name:
            return
        try:
            allowed = []
            raw = getattr(agent, "allowed_skills", None)
            if raw:
                try:
                    allowed = json.loads(raw) or []
                except (ValueError, TypeError):
                    allowed = []
            if skill_name in allowed:
                return
            allowed.append(skill_name)
            agent.allowed_skills = json.dumps(allowed)

            commander = session.query(Agent).filter_by(rank=1).first()
            if commander and commander.id != agent.id:
                session.add(AgentMessage(
                    from_agent_id=agent.id, to_agent_id=commander.id,
                    message_type="skill_request",
                    content=json.dumps({"skill_name": skill_name}),
                ))
                session.add(AgentMessage(
                    from_agent_id=commander.id, to_agent_id=agent.id,
                    message_type="skill_granted",
                    content=json.dumps({"skill_name": skill_name}),
                    acknowledged=True,
                ))
            logger.info(
                f"Skill '{skill_name}' granted to agent '{agent.name}' "
                f"by Commander policy"
            )
        except Exception as e:
            logger.debug(f"Skill grant failed: {e}")

    @staticmethod
    def _assigned_skills_list(agent) -> list:
        """Assigned skills as dicts for status consumers (fleet dialog)."""
        raw = getattr(agent, "allowed_skills", None)
        if not raw:
            return []
        try:
            return [{"name": n} for n in json.loads(raw)]
        except (ValueError, TypeError):
            return []

    @staticmethod
    def _skill_to_dict(skill: Skill) -> dict:
        """Convert a Skill ORM object to a dict with all fields."""
        result = {
            "id": skill.id,
            "name": skill.name,
            "system_prompt": skill.system_prompt,
            "temperature": skill.temperature,
            "max_tokens": skill.max_tokens,
            "tone": skill.tone,
            "preferred_tier": skill.preferred_tier,
        }
        # Include enhanced fields if available
        for field in ("description", "instructions", "input_schema",
                      "output_schema", "examples", "category", "version",
                      "capabilities", "tags"):
            val = getattr(skill, field, None)
            if val is not None:
                result[field] = val
        return result

    def _design_skill_with_llm(self, task_type: str, payload: dict) -> dict:
        """Have the Forger design a proper skill with an LLM pass.

        Model-agnostic: goes through the router, so any configured
        provider (API key or subscription CLI) can do the design work.
        Returns a dict of skill fields, or {} so callers fall back to the
        template stub when no model is reachable.
        """
        if not self.router_engine:
            return {}
        try:
            design_prompt = (
                "Design a reusable AI skill for a B2B sales automation agent.\n"
                f"Task type: {task_type}\n"
                f"Example payload: {json.dumps(payload)[:400]}\n\n"
                "Reply with ONLY a JSON object using exactly these keys:\n"
                '{"name": "short skill title",\n'
                ' "description": "one sentence",\n'
                ' "system_prompt": "persona and rules in 3 to 6 sentences",\n'
                ' "instructions": "numbered step by step procedure",\n'
                ' "tone": "professional|casual|direct|analytical",\n'
                ' "category": "prospecting|qualification|outreach|analysis|'
                'enrichment|research|conversation|management|general",\n'
                ' "capabilities": ["snake_case_capability"],\n'
                ' "temperature": 0.4,\n'
                ' "max_tokens": 800}'
            )
            result = self.router_engine.route(
                "forge_skill", design_prompt, tier_override="haiku",
            )
            if not result.get("success"):
                return {}
            text = result.get("data", "") or ""
            try:
                from core.cli_llm import strip_code_fences
                text = strip_code_fences(text)
            except ImportError:
                pass
            start = text.find("{")
            end = text.rfind("}")
            if start < 0 or end <= start:
                return {}
            designed = json.loads(text[start:end + 1])
            if not isinstance(designed, dict):
                return {}
            if not designed.get("system_prompt"):
                return {}
            return designed
        except Exception as e:
            logger.debug(f"LLM skill design failed, using template: {e}")
            return {}

    def _delegate_to_forger(self, requesting_agent_id: int, task_type: str,
                            payload: dict, depth: int) -> dict | None:
        """Delegate skill creation to the Forger agent.

        The Forger first tries to DESIGN the skill with an LLM pass
        (persona, instructions, sampling parameters). When no model is
        reachable the template stub still produces a working skill, so
        the pipeline never stalls on skill creation.
        """
        try:
            with self.db_manager.session_scope() as session:
                forger = session.query(Agent).filter(
                    Agent.name.ilike("%forger%")
                ).first()
                if not forger:
                    logger.warning("No Forger agent found for skill delegation")
                    return None
                forger_id = forger.id

            designed = self._design_skill_with_llm(task_type, payload)

            skill_name = (designed.get("name")
                          or f"Auto: {task_type.replace('_', ' ').title()}")
            system_prompt = designed.get("system_prompt") or (
                f"You are an AI specialist for the task '{task_type}'. "
                f"Generate high-quality, professional output. "
                f"Context: {json.dumps(payload)[:500]}"
            )
            capabilities = designed.get("capabilities")
            if not isinstance(capabilities, list):
                capabilities = None
            result = self.forge_controller.create_skill_from_agent(
                name=skill_name,
                system_prompt=system_prompt,
                tone=designed.get("tone", "professional"),
                preferred_tier="haiku",
                description=designed.get("description", ""),
                instructions=designed.get("instructions", ""),
                category=designed.get("category", "general"),
                capabilities=capabilities,
                temperature=designed.get("temperature"),
                max_tokens=designed.get("max_tokens"),
            )

            if result and result.get("success"):
                # Log delegation message
                self.send_message(
                    requesting_agent_id, forger_id, "skill_request",
                    {"task_type": task_type, "skill_id": result["skill_id"]},
                )
                logger.info(
                    f"Forger created skill '{skill_name}' (#{result['skill_id']}) "
                    f"for task '{task_type}'"
                )
                return result
            return None
        except Exception as e:
            logger.error(f"Forger delegation failed: {e}")
            return None

    def _build_agent_context(self, agent: Agent, task_type: str,
                             payload: dict, skill_data: dict | None = None) -> str:
        """Build the full context prompt for an agent task, token-aware."""
        parts_dict = {}

        if agent.soul:
            parts_dict["soul"] = f"SOUL: {agent.soul}"
        if agent.mission:
            parts_dict["mission"] = f"MISSION: {agent.mission}"

        # Enhanced skill injection: use structured context if available
        if skill_data:
            if build_skill_context and skill_data.get("instructions"):
                parts_dict["skill"] = build_skill_context(skill_data)
            elif skill_data.get("system_prompt"):
                parts_dict["skill"] = f"SKILL_PERSONA: {skill_data['system_prompt']}"

        if agent.playbook:
            parts_dict["playbook"] = f"PLAYBOOK: {agent.playbook}"
        if agent.boundaries:
            parts_dict["boundaries"] = f"BOUNDARIES: {agent.boundaries}"
        if agent.long_term_memory:
            parts_dict["long_term_memory"] = f"LONG_TERM_MEMORY: {agent.long_term_memory[:2000]}"
        if agent.memory_today:
            parts_dict["memory_today"] = f"TODAY_NOTES: {agent.memory_today[:1000]}"
        if self.command_history:
            try:
                recent = self.command_history.get_recent_for_agent_context(
                    agent_id=agent.id, limit=10,
                )
                if recent.get("success") and recent.get("data"):
                    parts_dict["history"] = f"RECENT_COMMAND_HISTORY:\n{recent['data']}"
            except Exception:
                pass

        # Case context injection: auto-inject case file when working on a lead
        if self.case_engine and payload.get("lead_id"):
            try:
                case_ctx = self.case_engine.build_case_context(payload["lead_id"])
                if case_ctx:
                    parts_dict["case_context"] = case_ctx
            except Exception as e:
                logger.debug(f"Case context injection failed: {e}")

        # Correction memory: inject learned rules
        if self.correction_memory:
            try:
                agent_name = getattr(agent, "name", None)
                rules_ctx = self.correction_memory.get_rules_for_context(agent_name)
                if rules_ctx:
                    parts_dict["learned_rules"] = rules_ctx
            except Exception:
                pass

        # Knowledge base: inject ICP, product, and approach context
        if self.knowledge_base_engine:
            try:
                kb_ctx = self.knowledge_base_engine.build_context()
                if kb_ctx:
                    parts_dict["knowledge_base"] = kb_ctx
            except Exception:
                pass

        parts_dict["payload"] = f"TASK: {task_type}\nPAYLOAD: {json.dumps(payload)}"

        # Token-aware compaction
        if self.token_manager:
            try:
                parts_dict = self.token_manager.compact_context(parts_dict, task_type)
            except Exception as e:
                logger.debug(f"Token compaction failed: {e}")

        return "\n\n".join(parts_dict.values())
