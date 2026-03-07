"""
Aura -- Command History Engine
Logs all commands, agent actions, and results into a single unified timeline.
Provides tree traversal, filtering, pagination, and agent context queries.
"""

import json
import math
import uuid
from datetime import datetime, timedelta
from typing import Optional

from database.db_manager import DatabaseManager
from database.schema import CommandLog, Agent
from config import (
    COMMAND_HISTORY_MAX_RETENTION_DAYS,
    COMMAND_HISTORY_PAGE_SIZE,
    COMMAND_HISTORY_AGENT_CONTEXT_LIMIT,
)
from utils.logger import get_logger

logger = get_logger("command_history")


class CommandHistoryEngine:
    """Records, queries, and prunes the unified command history."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    # ─── Logging ──────────────────────────────────────────────────────────────

    def log_command(
        self,
        source: str,
        command_type: str,
        command_text: str = "",
        actor_type: str = "user",
        agent_id: Optional[int] = None,
        intent: Optional[str] = None,
        parameters: Optional[dict] = None,
        result: Optional[dict] = None,
        status: str = "pending",
        parent_command_id: Optional[int] = None,
        correlation_id: Optional[str] = None,
        linked_task_id: Optional[int] = None,
        linked_ticket_id: Optional[int] = None,
        campaign_id: Optional[int] = None,
        cost_usd: float = 0.0,
        tokens_used: int = 0,
        source_sender_id: Optional[str] = None,
        source_display_name: Optional[str] = None,
    ) -> dict:
        """Log a single command/action entry."""
        try:
            with self.db_manager.session_scope() as session:
                # Resolve correlation_id
                if not correlation_id and parent_command_id:
                    parent = session.query(CommandLog).filter_by(
                        id=parent_command_id
                    ).first()
                    if parent:
                        correlation_id = parent.correlation_id
                if not correlation_id:
                    correlation_id = str(uuid.uuid4())

                entry = CommandLog(
                    parent_command_id=parent_command_id,
                    correlation_id=correlation_id,
                    source=source,
                    source_sender_id=source_sender_id,
                    source_display_name=source_display_name,
                    actor_type=actor_type,
                    agent_id=agent_id,
                    command_type=command_type,
                    command_text=command_text,
                    intent=intent,
                    parameters=json.dumps(parameters) if parameters else "{}",
                    result=json.dumps(result) if result else None,
                    status=status,
                    cost_usd=cost_usd,
                    tokens_used=tokens_used,
                    linked_task_id=linked_task_id,
                    linked_ticket_id=linked_ticket_id,
                    campaign_id=campaign_id,
                )
                if status in ("completed", "failed"):
                    entry.completed_at = datetime.utcnow()
                    entry.duration_ms = 0

                session.add(entry)
                session.flush()

                entry_id = entry.id
                entry_corr = entry.correlation_id

            logger.info(
                f"Logged command: type={command_type}, source={source}, id={entry_id}"
            )
            return {
                "success": True,
                "data": {
                    "id": entry_id,
                    "correlation_id": entry_corr,
                    "parent_command_id": parent_command_id,
                },
            }
        except Exception as e:
            logger.error(f"Failed to log command: {e}")
            return {"success": False, "error": str(e)}

    def update_command_status(
        self,
        command_id: int,
        status: str,
        result: Optional[dict] = None,
        cost_usd: float = 0.0,
        tokens_used: int = 0,
    ) -> dict:
        """Update an existing command's status and result. Computes duration_ms."""
        try:
            with self.db_manager.session_scope() as session:
                entry = session.query(CommandLog).filter_by(id=command_id).first()
                if not entry:
                    return {"success": False, "error": f"Command {command_id} not found"}

                entry.status = status
                if result is not None:
                    entry.result = json.dumps(result)
                if cost_usd:
                    entry.cost_usd = (entry.cost_usd or 0) + cost_usd
                if tokens_used:
                    entry.tokens_used = (entry.tokens_used or 0) + tokens_used

                now = datetime.utcnow()
                if status in ("completed", "failed"):
                    entry.completed_at = now
                    if entry.created_at:
                        delta = now - entry.created_at
                        entry.duration_ms = int(delta.total_seconds() * 1000)

                duration = entry.duration_ms

            return {
                "success": True,
                "data": {"id": command_id, "status": status, "duration_ms": duration},
            }
        except Exception as e:
            logger.error(f"Failed to update command {command_id}: {e}")
            return {"success": False, "error": str(e)}

    def log_user_command(
        self,
        source: str,
        text: str,
        sender_id: str = "",
        display_name: str = "",
    ) -> dict:
        """Convenience: log a root user command."""
        return self.log_command(
            source=source,
            command_type="user_command",
            command_text=text,
            actor_type="user",
            status="pending",
            source_sender_id=sender_id or None,
            source_display_name=display_name or None,
        )

    def log_agent_action(
        self,
        parent_command_id: int,
        agent_id: int,
        command_type: str,
        parameters: Optional[dict] = None,
        result: Optional[dict] = None,
        status: str = "completed",
        linked_task_id: Optional[int] = None,
        cost_usd: float = 0.0,
        tokens_used: int = 0,
    ) -> dict:
        """Convenience: log an agent's action as a child of a parent command."""
        return self.log_command(
            source="system",
            command_type=command_type,
            actor_type="agent",
            agent_id=agent_id,
            parameters=parameters,
            result=result,
            status=status,
            parent_command_id=parent_command_id,
            linked_task_id=linked_task_id,
            cost_usd=cost_usd,
            tokens_used=tokens_used,
        )

    # ─── Querying ─────────────────────────────────────────────────────────────

    def get_command(self, command_id: int) -> dict:
        """Get a single command entry by ID."""
        try:
            with self.db_manager.session_scope() as session:
                entry = session.query(CommandLog).filter_by(id=command_id).first()
                if not entry:
                    return {"success": False, "error": f"Command {command_id} not found"}
                return {"success": True, "data": self._command_to_dict(entry, session)}
        except Exception as e:
            logger.error(f"Failed to get command {command_id}: {e}")
            return {"success": False, "error": str(e)}

    def get_command_tree(self, command_id: int) -> dict:
        """Get a full command tree starting from a root command."""
        try:
            with self.db_manager.session_scope() as session:
                root = session.query(CommandLog).filter_by(id=command_id).first()
                if not root:
                    return {"success": False, "error": f"Command {command_id} not found"}

                # Get all entries with the same correlation_id
                all_entries = (
                    session.query(CommandLog)
                    .filter_by(correlation_id=root.correlation_id)
                    .order_by(CommandLog.created_at)
                    .all()
                )

                # Build lookup maps
                entries_dict = {}
                children_map = {}
                for entry in all_entries:
                    entries_dict[entry.id] = self._command_to_dict(entry, session)
                    pid = entry.parent_command_id
                    if pid not in children_map:
                        children_map[pid] = []
                    children_map[pid].append(entry.id)

                # Build tree recursively
                root_dict = entries_dict[command_id]
                root_dict["children"] = self._build_children(
                    command_id, entries_dict, children_map
                )

                return {"success": True, "data": root_dict}
        except Exception as e:
            logger.error(f"Failed to get command tree {command_id}: {e}")
            return {"success": False, "error": str(e)}

    def get_history(
        self,
        source: Optional[str] = None,
        agent_id: Optional[int] = None,
        command_type: Optional[str] = None,
        status: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        search_text: Optional[str] = None,
        root_only: bool = False,
        page: int = 1,
        page_size: int = COMMAND_HISTORY_PAGE_SIZE,
    ) -> dict:
        """Paginated, filterable history query."""
        try:
            with self.db_manager.session_scope() as session:
                query = session.query(CommandLog)

                if source:
                    query = query.filter(CommandLog.source == source)
                if agent_id:
                    query = query.filter(CommandLog.agent_id == agent_id)
                if command_type:
                    query = query.filter(CommandLog.command_type == command_type)
                if status:
                    query = query.filter(CommandLog.status == status)
                if since:
                    query = query.filter(CommandLog.created_at >= since)
                if until:
                    query = query.filter(CommandLog.created_at <= until)
                if search_text:
                    query = query.filter(
                        CommandLog.command_text.ilike(f"%{search_text}%")
                    )
                if root_only:
                    query = query.filter(CommandLog.parent_command_id.is_(None))

                total = query.count()
                pages = max(1, math.ceil(total / page_size))

                items = (
                    query.order_by(CommandLog.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                    .all()
                )

                return {
                    "success": True,
                    "data": {
                        "items": [self._command_to_dict(i, session) for i in items],
                        "total": total,
                        "page": page,
                        "pages": pages,
                    },
                }
        except Exception as e:
            logger.error(f"Failed to get history: {e}")
            return {"success": False, "error": str(e)}

    def get_recent_for_agent_context(
        self,
        agent_id: Optional[int] = None,
        limit: int = COMMAND_HISTORY_AGENT_CONTEXT_LIMIT,
    ) -> dict:
        """Get recent command summaries for agent context injection."""
        try:
            with self.db_manager.session_scope() as session:
                query = session.query(CommandLog).filter(
                    CommandLog.parent_command_id.is_(None)
                )
                if agent_id:
                    # Get commands involving this agent or root commands
                    sub = session.query(CommandLog.correlation_id).filter(
                        CommandLog.agent_id == agent_id
                    ).subquery()
                    query = session.query(CommandLog).filter(
                        CommandLog.parent_command_id.is_(None),
                        CommandLog.correlation_id.in_(sub),
                    )

                entries = (
                    query.order_by(CommandLog.created_at.desc())
                    .limit(limit)
                    .all()
                )

                lines = []
                for e in reversed(entries):
                    ts = e.created_at.strftime("%m/%d %H:%M") if e.created_at else "?"
                    src = e.source or "?"
                    text = (e.command_text or "")[:100]
                    st = e.status or "?"
                    intent_str = f" → {e.intent}" if e.intent else ""
                    lines.append(f"[{ts}] [{src}] {text}{intent_str} ({st})")

                return {"success": True, "data": "\n".join(lines)}
        except Exception as e:
            logger.error(f"Failed to get agent context: {e}")
            return {"success": False, "error": str(e)}

    def get_stats(self, since: Optional[datetime] = None) -> dict:
        """Get aggregate stats."""
        try:
            with self.db_manager.session_scope() as session:
                query = session.query(CommandLog)
                if since:
                    query = query.filter(CommandLog.created_at >= since)

                total = query.count()
                root_total = query.filter(
                    CommandLog.parent_command_id.is_(None)
                ).count()

                # By source
                by_source = {}
                for source_val in ["telegram", "discord", "chat", "system", "scheduled"]:
                    count = query.filter(CommandLog.source == source_val).count()
                    if count:
                        by_source[source_val] = count

                # By status
                by_status = {}
                for st in ["pending", "running", "completed", "failed"]:
                    count = query.filter(CommandLog.status == st).count()
                    if count:
                        by_status[st] = count

                # Today
                today_start = datetime.utcnow().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                today_count = (
                    query.filter(CommandLog.created_at >= today_start)
                    .filter(CommandLog.parent_command_id.is_(None))
                    .count()
                )

                # Success rate
                completed = by_status.get("completed", 0)
                failed = by_status.get("failed", 0)
                total_finished = completed + failed
                success_rate = (
                    round(completed / total_finished * 100, 1) if total_finished else 100.0
                )

                # Total cost
                from sqlalchemy import func
                total_cost = (
                    session.query(func.sum(CommandLog.cost_usd))
                    .scalar() or 0.0
                )

                return {
                    "success": True,
                    "data": {
                        "total": total,
                        "root_total": root_total,
                        "today": today_count,
                        "by_source": by_source,
                        "by_status": by_status,
                        "success_rate": success_rate,
                        "total_cost": round(total_cost, 4),
                    },
                }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"success": False, "error": str(e)}

    # ─── Maintenance ──────────────────────────────────────────────────────────

    def prune_old_entries(
        self, days: int = COMMAND_HISTORY_MAX_RETENTION_DAYS
    ) -> dict:
        """Delete command log entries older than N days."""
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            with self.db_manager.session_scope() as session:
                count = (
                    session.query(CommandLog)
                    .filter(CommandLog.created_at < cutoff)
                    .delete(synchronize_session="fetch")
                )
            logger.info(f"Pruned {count} command history entries older than {days} days")
            return {"success": True, "deleted": count}
        except Exception as e:
            logger.error(f"Failed to prune history: {e}")
            return {"success": False, "error": str(e)}

    # ─── Internal helpers ─────────────────────────────────────────────────────

    def _command_to_dict(self, cmd: CommandLog, session) -> dict:
        """Convert a CommandLog ORM instance to a dict."""
        agent_name = None
        agent_emoji = None
        if cmd.agent_id:
            agent = session.query(Agent).filter_by(id=cmd.agent_id).first()
            if agent:
                agent_name = agent.name
                agent_emoji = agent.identity_emoji

        return {
            "id": cmd.id,
            "parent_command_id": cmd.parent_command_id,
            "correlation_id": cmd.correlation_id,
            "source": cmd.source,
            "source_sender_id": cmd.source_sender_id,
            "source_display_name": cmd.source_display_name,
            "actor_type": cmd.actor_type,
            "agent_id": cmd.agent_id,
            "agent_name": agent_name,
            "agent_emoji": agent_emoji,
            "command_type": cmd.command_type,
            "command_text": cmd.command_text,
            "intent": cmd.intent,
            "parameters": json.loads(cmd.parameters) if cmd.parameters else {},
            "result": json.loads(cmd.result) if cmd.result else None,
            "status": cmd.status,
            "cost_usd": cmd.cost_usd or 0.0,
            "tokens_used": cmd.tokens_used or 0,
            "linked_task_id": cmd.linked_task_id,
            "linked_ticket_id": cmd.linked_ticket_id,
            "campaign_id": cmd.campaign_id,
            "created_at": cmd.created_at.isoformat() if cmd.created_at else None,
            "completed_at": cmd.completed_at.isoformat() if cmd.completed_at else None,
            "duration_ms": cmd.duration_ms,
        }

    def _build_children(self, parent_id: int, entries_dict: dict, children_map: dict) -> list:
        """Recursively build children list for tree structure."""
        child_ids = children_map.get(parent_id, [])
        children = []
        for cid in child_ids:
            child_dict = entries_dict.get(cid, {})
            child_dict["children"] = self._build_children(cid, entries_dict, children_map)
            children.append(child_dict)
        return children
