"""
Aura — Orchestrator Engine
Natural language command interpreter. Parses user intent, routes to correct
controller/engine, and maintains rolling conversation history.
"""

import json
import os
from typing import Optional

from database.db_manager import DatabaseManager
from database.schema import Campaign, Lead, Skill, Settings
from config import DEFAULT_TIER3_MODEL
from utils.logger import get_logger

logger = get_logger("orchestrator_engine")

# Defined intents
INTENTS = [
    "start_campaign", "show_stats", "generate_drafts", "send_emails",
    "create_skill", "analyze_performance", "export_report",
    "add_suppression", "schedule_followups", "show_replies",
    "pause_campaign", "general_question",
    "crm_sync", "inbox_triage", "enrich_list",
    "set_budget", "show_budget", "set_gateway",
    "fleet_dispatch", "fleet_status", "fleet_boot", "fleet_shutdown",
    # Advanced engine intents
    "set_goal", "show_goals", "show_reflections", "set_autonomy",
    "show_conversations", "show_approvals", "approve_action", "deny_action",
]

SYSTEM_PROMPT = """You are the AI assistant for Aura, an AI-powered sales outreach tool.
You interpret user commands and return structured JSON.

Available actions and their parameter schemas:
- "start_campaign": {"niche": str, "city": str, "limit": int (default 50), "skill_name": str|null}
- "show_stats": {"campaign_name": str|null, "time_range": str|null}
- "generate_drafts": {"campaign_name": str}
- "send_emails": {"campaign_name": str, "count": int|null}
- "create_skill": {"name": str, "description": str, "tone": str}
- "analyze_performance": {"question": str}
- "export_report": {"campaign_name": str, "format": str}  // format: "pdf" or "csv"
- "add_suppression": {"email": str|null, "domain": str|null}
- "schedule_followups": {"campaign_name": str, "sequence_name": str|null}
- "show_replies": {}
- "pause_campaign": {"campaign_name": str}
- "crm_sync": {"campaign_name": str|null, "crm_platform": str|null}
- "inbox_triage": {}
- "enrich_list": {"campaign_name": str}
- "set_budget": {"budget_usd": float, "time_window_hours": float, "eco_mode": bool|null, "action": str|null}  // action: "activate", "deactivate", "pause", "resume"
- "show_budget": {}
- "set_gateway": {"platform": str|null, "action": str|null}  // action: "enable", "disable", "status"
- "fleet_dispatch": {"command": str}  // natural language command for the agent fleet
- "fleet_status": {}  // get current fleet status
- "fleet_boot": {}  // boot all fleet agents
- "fleet_shutdown": {}  // shutdown all fleet agents
- "general_question": {"question": str}
- "set_goal": {"goal_text": str, "target_metric": str|null, "target_value": int, "budget": float|null, "niche": str|null, "city": str|null}  // target_metric: "conversions", "meetings", "replies"
- "show_goals": {"status": str|null}  // status: "active", "planning", "completed", null for all
- "show_reflections": {"agent_name": str|null, "task_type": str|null, "limit": int|null}
- "set_autonomy": {"level": str}  // level: "observer", "supervised", "autonomous", "full_trust"
- "show_conversations": {"lead_id": int|null, "status": str|null}
- "show_approvals": {}  // show pending approval requests
- "approve_action": {"approval_id": int}  // approve a pending action
- "deny_action": {"approval_id": int}  // deny a pending action

Current app context will be provided. Use it to resolve ambiguous references like "this campaign" or "run it again".

ALWAYS respond with ONLY valid JSON in this exact format:
{
  "intent": "<one of the intent names above>",
  "confidence": <0.0-1.0>,
  "parameters": {<extracted params>},
  "clarification_needed": <true|false>,
  "clarification_question": "<question to ask if clarification needed>",
  "response_text": "<what to say back to the user>"
}
"""


class OrchestratorEngine:
    """Brain of the chat system. Parses intent and routes to actions."""

    def __init__(self, db_manager: DatabaseManager, key_vault):
        self.db_manager = db_manager
        self.key_vault = key_vault
        self._history: list = []
        self._max_history = 20

    def parse_intent(self, message: str, context: dict = None) -> dict:
        """
        Send user message to AI for intent parsing.
        Returns structured intent dict.
        """
        try:
            settings = self.db_manager.get_settings()
            model = DEFAULT_TIER3_MODEL
            if settings and settings.chat_model:
                model = settings.chat_model

            # Configure API keys
            api_keys = self._get_api_keys(settings)
            for provider, key in api_keys.items():
                if provider == "gemini":
                    os.environ["GEMINI_API_KEY"] = key
                elif provider == "anthropic":
                    os.environ["ANTHROPIC_API_KEY"] = key
                elif provider == "openai":
                    os.environ["OPENAI_API_KEY"] = key
                elif provider == "openrouter":
                    os.environ["OPENROUTER_API_KEY"] = key

            # Build messages with context
            system = SYSTEM_PROMPT
            if context:
                system += f"\n\nCurrent app context:\n{json.dumps(context, indent=2, default=str)}"

            messages = [{"role": "system", "content": system}]

            # Add rolling history for context
            for h in self._history[-self._max_history:]:
                messages.append(h)

            messages.append({"role": "user", "content": message})

            import litellm
            response = litellm.completion(
                model=model,
                messages=messages,
                max_tokens=500,
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            raw = response.choices[0].message.content.strip()

            # Parse JSON response
            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                # Try to extract JSON from the response
                import re
                json_match = re.search(r'\{.*\}', raw, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    result = {
                        "intent": "general_question",
                        "confidence": 0.3,
                        "parameters": {"question": message},
                        "clarification_needed": False,
                        "clarification_question": None,
                        "response_text": raw,
                    }

            # Update history
            self._history.append({"role": "user", "content": message})
            self._history.append({
                "role": "assistant",
                "content": json.dumps(result),
            })

            # Trim history
            if len(self._history) > self._max_history * 2:
                self._history = self._history[-self._max_history * 2:]

            return result

        except Exception as e:
            logger.error(f"Intent parsing failed: {e}")
            return {
                "intent": "general_question",
                "confidence": 0.0,
                "parameters": {"question": message},
                "clarification_needed": False,
                "clarification_question": None,
                "response_text": f"I had trouble understanding that: {str(e)}",
            }

    def execute_intent(self, intent_dict: dict, engines: dict) -> dict:
        """
        Route the parsed intent to the correct engine/controller.
        engines: dict of engine/controller instances keyed by name.
        Returns result dict.
        """
        intent = intent_dict.get("intent", "general_question")
        params = intent_dict.get("parameters", {})

        try:
            if intent == "start_campaign":
                return self._exec_start_campaign(params, engines)
            elif intent == "show_stats":
                return self._exec_show_stats(params, engines)
            elif intent == "generate_drafts":
                return self._exec_generate_drafts(params, engines)
            elif intent == "send_emails":
                return self._exec_send_emails(params, engines)
            elif intent == "create_skill":
                return self._exec_create_skill(params, engines)
            elif intent == "analyze_performance":
                return self._exec_analyze(params, engines)
            elif intent == "export_report":
                return self._exec_export(params, engines)
            elif intent == "add_suppression":
                return self._exec_add_suppression(params, engines)
            elif intent == "pause_campaign":
                return self._exec_pause_campaign(params, engines)
            elif intent == "show_replies":
                return self._exec_show_replies(params, engines)
            elif intent == "schedule_followups":
                return self._exec_schedule_followups(params, engines)
            elif intent == "crm_sync":
                return self._exec_crm_sync(params, engines)
            elif intent == "inbox_triage":
                return self._exec_inbox_triage(params, engines)
            elif intent == "enrich_list":
                return self._exec_enrich_list(params, engines)
            elif intent == "set_budget":
                return self._exec_set_budget(params, engines)
            elif intent == "show_budget":
                return self._exec_show_budget(params, engines)
            elif intent == "set_gateway":
                return self._exec_set_gateway(params, engines)
            elif intent == "fleet_dispatch":
                return self._exec_fleet_dispatch(params, engines)
            elif intent == "fleet_status":
                return self._exec_fleet_status(params, engines)
            elif intent == "fleet_boot":
                return self._exec_fleet_boot(params, engines)
            elif intent == "fleet_shutdown":
                return self._exec_fleet_shutdown(params, engines)
            elif intent == "set_goal":
                return self._exec_set_goal(params, engines)
            elif intent == "show_goals":
                return self._exec_show_goals(params, engines)
            elif intent == "show_reflections":
                return self._exec_show_reflections(params, engines)
            elif intent == "set_autonomy":
                return self._exec_set_autonomy(params, engines)
            elif intent == "show_conversations":
                return self._exec_show_conversations(params, engines)
            elif intent == "show_approvals":
                return self._exec_show_approvals(params, engines)
            elif intent == "approve_action":
                return self._exec_approve_action(params, engines)
            elif intent == "deny_action":
                return self._exec_deny_action(params, engines)
            elif intent == "create_invoice":
                return self._exec_create_invoice(params, engines)
            elif intent == "show_invoices":
                return self._exec_show_invoices(params, engines)
            elif intent == "general_question":
                return self._exec_general_question(params, engines)
            else:
                return {"success": False, "error": f"Unknown intent: {intent}"}
        except Exception as e:
            logger.error(f"Intent execution failed: {e}")
            return {"success": False, "error": str(e)}

    # ─── Intent Executors ──────────────────────────────────────────────

    def _exec_start_campaign(self, params: dict, engines: dict) -> dict:
        """Create a campaign and prepare for scraping."""
        blocked = self._check_autonomy(
            "start_campaign", engines,
            f"Start campaign: {params.get('niche', '')} in {params.get('city', '')}",
        )
        if blocked:
            return blocked

        niche = params.get("niche", "")
        city = params.get("city", "")
        limit = params.get("limit", 50)

        if not niche or not city:
            return {"success": False, "error": "Niche and city are required"}

        with self.db_manager.session_scope() as session:
            # Resolve skill
            skill_name = params.get("skill_name")
            skill_id = None
            if skill_name:
                skill = session.query(Skill).filter_by(name=skill_name).first()
                if skill:
                    skill_id = skill.id

            if not skill_id:
                # Use default skill
                default_skill = session.query(Skill).filter_by(is_default=True).first()
                if default_skill:
                    skill_id = default_skill.id

            campaign = Campaign(
                name=f"{niche.title()} in {city.title()}",
                search_query=f"{niche} in {city}",
                target_city=city,
                target_niche=niche,
                status="active",
                skill_id=skill_id,
            )
            session.add(campaign)
            session.flush()
            campaign_id = campaign.id
            campaign_name = campaign.name

        # Trigger lead hunting via hunter controller
        hunter_ctrl = engines.get("hunter_ctrl")
        if hunter_ctrl:
            try:
                query = f"{niche} in {city}"
                hunter_ctrl.start_scrape(
                    query=query, city=city, niche=niche,
                    campaign_name=campaign_name, limit=limit,
                )
                logger.info(f"Scraping triggered for campaign #{campaign_id}")
            except Exception as e:
                logger.error(f"Failed to trigger scraping: {e}")

        return {
            "success": True,
            "action": "start_campaign",
            "data": {
                "campaign_id": campaign_id,
                "niche": niche,
                "city": city,
                "limit": limit,
            },
        }

    def _exec_show_stats(self, params: dict, engines: dict) -> dict:
        """Get campaign stats."""
        analyst = engines.get("analyst")
        if analyst:
            context = analyst.gather_context()
            campaign_name = params.get("campaign_name")
            if campaign_name:
                # Filter to specific campaign
                for c in context.get("campaigns", []):
                    if campaign_name.lower() in c.get("name", "").lower():
                        return {"success": True, "data": c}
            return {"success": True, "data": context}
        return {"success": False, "error": "Analyst engine not available"}

    def _exec_generate_drafts(self, params: dict, engines: dict) -> dict:
        """Generate drafts for a campaign."""
        blocked = self._check_autonomy(
            "generate_email", engines,
            f"Generate drafts for: {params.get('campaign_name', '')}",
        )
        if blocked:
            return blocked

        campaign_name = params.get("campaign_name", "")
        with self.db_manager.session_scope() as session:
            campaign = (
                session.query(Campaign)
                .filter(Campaign.name.ilike(f"%{campaign_name}%"))
                .first()
            )
            if not campaign:
                return {"success": False, "error": f"Campaign '{campaign_name}' not found"}

            return {
                "success": True,
                "action": "generate_drafts",
                "data": {"campaign_id": campaign.id, "campaign_name": campaign.name},
            }

    def _exec_send_emails(self, params: dict, engines: dict) -> dict:
        """Prepare email sending (requires confirmation)."""
        blocked = self._check_autonomy(
            "send_email", engines,
            f"Send emails for: {params.get('campaign_name', '')}",
        )
        if blocked:
            return blocked

        campaign_name = params.get("campaign_name", "")
        with self.db_manager.session_scope() as session:
            campaign = (
                session.query(Campaign)
                .filter(Campaign.name.ilike(f"%{campaign_name}%"))
                .first()
            )
            if not campaign:
                return {"success": False, "error": f"Campaign '{campaign_name}' not found"}

            ready_count = session.query(Lead).filter_by(
                campaign_id=campaign.id,
                status="email_drafted",
            ).count()

            return {
                "success": True,
                "action": "send_emails",
                "requires_confirmation": True,
                "data": {
                    "campaign_id": campaign.id,
                    "campaign_name": campaign.name,
                    "ready_count": ready_count,
                },
            }

    def _exec_create_skill(self, params: dict, engines: dict) -> dict:
        """Create a new skill."""
        name = params.get("name", "New Skill")
        desc = params.get("description", "")
        tone = params.get("tone", "professional")

        with self.db_manager.session_scope() as session:
            skill = Skill(
                name=name,
                system_prompt=desc,
                tone=tone,
            )
            session.add(skill)
            session.flush()
            skill_id = skill.id

        return {
            "success": True,
            "action": "create_skill",
            "data": {"skill_id": skill_id, "name": name},
        }

    def _exec_analyze(self, params: dict, engines: dict) -> dict:
        """Run performance analysis."""
        analyst = engines.get("analyst")
        if analyst:
            question = params.get("question", "How are my campaigns doing?")
            answer = analyst.ask(question)
            return {"success": True, "data": {"answer": answer}}
        return {"success": False, "error": "Analyst engine not available"}

    def _exec_export(self, params: dict, engines: dict) -> dict:
        """Export a report."""
        report = engines.get("report")
        campaign_name = params.get("campaign_name", "")
        fmt = params.get("format", "pdf")

        with self.db_manager.session_scope() as session:
            campaign = (
                session.query(Campaign)
                .filter(Campaign.name.ilike(f"%{campaign_name}%"))
                .first()
            )
            if not campaign:
                return {"success": False, "error": f"Campaign '{campaign_name}' not found"}

            return {
                "success": True,
                "action": "export_report",
                "data": {
                    "campaign_id": campaign.id,
                    "campaign_name": campaign.name,
                    "format": fmt,
                },
            }

    def _exec_add_suppression(self, params: dict, engines: dict) -> dict:
        """Add to suppression list."""
        suppression = engines.get("suppression")
        if suppression:
            result = suppression.add_suppression(
                email=params.get("email"),
                domain=params.get("domain"),
            )
            return result
        return {"success": False, "error": "Suppression engine not available"}

    def _exec_pause_campaign(self, params: dict, engines: dict) -> dict:
        """Pause a campaign."""
        campaign_name = params.get("campaign_name", "")
        with self.db_manager.session_scope() as session:
            campaign = (
                session.query(Campaign)
                .filter(Campaign.name.ilike(f"%{campaign_name}%"))
                .first()
            )
            if not campaign:
                return {"success": False, "error": f"Campaign '{campaign_name}' not found"}

            campaign.status = "paused"
            return {
                "success": True,
                "action": "pause_campaign",
                "data": {"campaign_name": campaign.name},
            }

    def _exec_show_replies(self, params: dict, engines: dict) -> dict:
        """Show recent replies / conversation threads with leads."""
        conversation = engines.get("conversation")
        if not conversation:
            return {"success": False, "error": "Conversation engine not available"}

        campaign_id = params.get("campaign_id")
        lead_id = params.get("lead_id")

        # If a specific lead is requested, return that thread
        if lead_id:
            result = conversation.get_thread(lead_id)
            return {"success": True, "action": "show_replies", "data": result.get("data", {})}

        # Otherwise return thread stats and any active/re_engage threads
        stats = conversation.get_thread_stats(campaign_id=campaign_id)
        pending = conversation.get_pending_re_engagements()

        # Query recent replied threads
        replied_threads = []
        try:
            from database.schema import ConversationThread, Lead
            with self.db_manager.session_scope() as session:
                query = (
                    session.query(ConversationThread, Lead.business_name, Lead.email)
                    .join(Lead, Lead.id == ConversationThread.lead_id)
                    .filter(ConversationThread.reply_intent.isnot(None))
                    .order_by(ConversationThread.last_activity.desc())
                    .limit(20)
                )
                for thread, lead_name, lead_email in query:
                    replied_threads.append({
                        "lead_id": thread.lead_id,
                        "lead_name": lead_name,
                        "lead_email": lead_email,
                        "intent": thread.reply_intent,
                        "status": thread.thread_status,
                        "message_count": thread.message_count,
                        "last_activity": thread.last_activity.isoformat() if thread.last_activity else None,
                    })
        except Exception as e:
            logger.debug(f"Failed to query replied threads: {e}")

        return {
            "success": True,
            "action": "show_replies",
            "data": {
                "stats": stats.get("data", {}),
                "replied_threads": replied_threads,
                "pending_re_engagements": pending.get("data", []),
            },
        }

    def _exec_schedule_followups(self, params: dict, engines: dict) -> dict:
        """Schedule follow-up re-engagements for leads."""
        conversation = engines.get("conversation")
        if not conversation:
            return {"success": False, "error": "Conversation engine not available"}

        lead_id = params.get("lead_id")
        delay_days = params.get("delay_days", 14)

        if lead_id:
            # Schedule for a specific lead
            result = conversation.schedule_re_engagement(lead_id, delay_days=delay_days)
            return {
                "success": result.get("success", False),
                "action": "schedule_followups",
                "data": result.get("data", {}),
                "error": result.get("error"),
            }

        # Bulk: find all "not_now" / "objection" threads without a re-engage date
        scheduled = []
        try:
            from database.schema import ConversationThread
            with self.db_manager.session_scope() as session:
                threads = (
                    session.query(ConversationThread)
                    .filter(
                        ConversationThread.reply_intent.in_(["not_now", "objection"]),
                        ConversationThread.thread_status != "re_engage",
                        ConversationThread.thread_status != "closed",
                    )
                    .all()
                )
                lead_ids = [t.lead_id for t in threads]

            for lid in lead_ids:
                r = conversation.schedule_re_engagement(lid, delay_days=delay_days)
                if r.get("success"):
                    scheduled.append(lid)
        except Exception as e:
            logger.debug(f"Bulk follow-up scheduling error: {e}")

        return {
            "success": True,
            "action": "schedule_followups",
            "data": {
                "scheduled_count": len(scheduled),
                "delay_days": delay_days,
                "lead_ids": scheduled,
            },
        }

    def _exec_crm_sync(self, params: dict, engines: dict) -> dict:
        """Sync leads to CRM."""
        crm = engines.get("crm")
        if not crm:
            return {"success": False, "error": "CRM engine not available"}

        campaign_name = params.get("campaign_name", "")
        if campaign_name:
            with self.db_manager.session_scope() as session:
                campaign = (
                    session.query(Campaign)
                    .filter(Campaign.name.ilike(f"%{campaign_name}%"))
                    .first()
                )
                if not campaign:
                    return {"success": False, "error": f"Campaign '{campaign_name}' not found"}
                result = crm.sync_campaign_to_crm(campaign.id)
                return {
                    "success": True,
                    "action": "crm_sync",
                    "data": {
                        "campaign_name": campaign.name,
                        "synced": result.get("synced", 0),
                        "failed": result.get("failed", 0),
                    },
                }
        return {"success": False, "error": "Campaign name required for CRM sync"}

    def _exec_inbox_triage(self, params: dict, engines: dict) -> dict:
        """Run morning inbox triage."""
        triage = engines.get("triage")
        if not triage:
            return {"success": False, "error": "Triage engine not available"}

        result = triage.run_morning_triage()
        return {
            "success": True,
            "action": "inbox_triage",
            "data": result,
        }

    def _exec_enrich_list(self, params: dict, engines: dict) -> dict:
        """Enrich leads in a campaign using waterfall enrichment."""
        enrichment = engines.get("enrichment")
        if not enrichment:
            return {"success": False, "error": "Enrichment engine not available"}

        campaign_name = params.get("campaign_name", "")
        with self.db_manager.session_scope() as session:
            campaign = (
                session.query(Campaign)
                .filter(Campaign.name.ilike(f"%{campaign_name}%"))
                .first()
            )
            if not campaign:
                return {"success": False, "error": f"Campaign '{campaign_name}' not found"}
            campaign_id = campaign.id
            campaign_name_resolved = campaign.name

        # Run waterfall enrichment
        result = enrichment.waterfall_enrich_campaign(campaign_id)
        return {
            "success": True,
            "action": "enrich_list",
            "data": {
                "campaign_id": campaign_id,
                "campaign_name": campaign_name_resolved,
                "enriched": result.get("enriched", 0),
                "emails_found": result.get("emails_found", 0),
                "total_attempted": result.get("total_attempted", 0),
            },
        }

    def _exec_set_budget(self, params: dict, engines: dict) -> dict:
        """Set or modify budget pacing."""
        pacing = engines.get("pacing")
        if not pacing:
            return {"success": False, "error": "Pacing engine not available"}

        action = params.get("action", "activate")

        if action == "deactivate":
            result = pacing.deactivate()
            return {
                "success": result.get("success", False),
                "action": "set_budget",
                "data": {"action": "deactivated"},
            }

        if action == "pause":
            result = pacing.pause()
            return {"success": result.get("success", False), "action": "set_budget", "data": {"action": "paused"}}

        if action == "resume":
            result = pacing.resume()
            return {"success": result.get("success", False), "action": "set_budget", "data": {"action": "resumed"}}

        # Default: activate
        budget = params.get("budget_usd", 20.0)
        hours = params.get("time_window_hours", 24.0)
        eco = params.get("eco_mode", True)
        if eco is None:
            eco = True

        result = pacing.activate(budget, hours, eco)
        if result.get("success"):
            return {
                "success": True,
                "action": "set_budget",
                "data": {
                    "budget_usd": budget,
                    "time_window_hours": hours,
                    "eco_mode": eco,
                    "budget_id": result.get("budget_id"),
                },
            }
        return {"success": False, "error": result.get("error", "Failed to activate budget")}

    def _exec_show_budget(self, params: dict, engines: dict) -> dict:
        """Show current budget pacing status."""
        pacing = engines.get("pacing")
        if not pacing:
            return {"success": False, "error": "Pacing engine not available"}

        status = pacing.get_status()
        return {"success": True, "action": "show_budget", "data": status}

    def _exec_set_gateway(self, params: dict, engines: dict) -> dict:
        """Show gateway connection status."""
        gateway = engines.get("gateway")
        if not gateway:
            return {"success": False, "error": "Gateway engine not available"}

        users = gateway.get_authorized_users()
        return {
            "success": True,
            "action": "set_gateway",
            "data": {
                "authorized_users": len(users),
                "users": users,
            },
        }

    def _exec_fleet_dispatch(self, params: dict, engines: dict) -> dict:
        """Dispatch a command to the agent fleet via triage."""
        fleet = engines.get("fleet")
        if not fleet:
            return {"success": False, "error": "Fleet orchestrator not available"}

        command = params.get("command", "")
        if not command:
            return {"success": False, "error": "No command provided for fleet dispatch"}

        triage_result = fleet.triage_incoming_work(command)
        if not triage_result.get("success"):
            return triage_result

        subtasks = triage_result.get("subtasks", [])
        has_deps = any(st.get("depends_on") for st in subtasks)

        if has_deps:
            pipeline_result = fleet.execute_pipeline(subtasks)
            return {
                "success": True,
                "action": "fleet_dispatch",
                "data": {
                    "mode": "pipeline",
                    "subtasks": len(subtasks),
                    "completed": pipeline_result.get("completed", 0),
                    "total_cost": pipeline_result.get("total_cost", 0.0),
                },
            }
        else:
            results = []
            for st in subtasks:
                r = fleet.dispatch(st["task_type"], st.get("payload", {}))
                results.append(r)
            return {
                "success": True,
                "action": "fleet_dispatch",
                "data": {
                    "mode": "parallel",
                    "dispatched": len(results),
                },
            }

    def _exec_fleet_status(self, params: dict, engines: dict) -> dict:
        """Get fleet status."""
        fleet = engines.get("fleet")
        if not fleet:
            return {"success": False, "error": "Fleet orchestrator not available"}

        status = fleet.get_fleet_status()
        return {"success": True, "action": "fleet_status", "data": status.get("data", {})}

    def _exec_fleet_boot(self, params: dict, engines: dict) -> dict:
        """Boot the entire fleet."""
        fleet = engines.get("fleet")
        if not fleet:
            return {"success": False, "error": "Fleet orchestrator not available"}

        result = fleet.boot_fleet()
        return {"success": True, "action": "fleet_boot", "data": result.get("data", {})}

    def _exec_fleet_shutdown(self, params: dict, engines: dict) -> dict:
        """Shut down the entire fleet."""
        fleet = engines.get("fleet")
        if not fleet:
            return {"success": False, "error": "Fleet orchestrator not available"}

        result = fleet.shutdown_fleet()
        return {"success": True, "action": "fleet_shutdown", "data": {}}

    def _exec_general_question(self, params: dict, engines: dict) -> dict:
        """Route general questions to analyst."""
        analyst = engines.get("analyst")
        if analyst:
            question = params.get("question", "")
            answer = analyst.ask(question)
            return {"success": True, "data": {"answer": answer}}
        return {"success": True, "data": {"answer": "I can help with campaign management. Try asking about stats, creating campaigns, or managing skills."}}

    # ─── Advanced Engine Handlers ─────────────────────────────────────

    def _exec_set_goal(self, params: dict, engines: dict) -> dict:
        """Create a strategic goal."""
        strategy = engines.get("strategy")
        if not strategy:
            return {"success": False, "error": "Strategy engine not available"}

        result = strategy.create_goal(
            goal_text=params.get("goal_text", ""),
            target_metric=params.get("target_metric", "conversions"),
            target_value=params.get("target_value", 10),
            budget=params.get("budget"),
            niche=params.get("niche"),
            city=params.get("city"),
        )
        if result.get("success"):
            strategy.activate_goal(result["data"]["goal_id"])
        return {"success": True, "action": "set_goal", "data": result.get("data", {})}

    def _exec_show_goals(self, params: dict, engines: dict) -> dict:
        """Show strategic goals."""
        strategy = engines.get("strategy")
        if not strategy:
            return {"success": False, "error": "Strategy engine not available"}

        status = params.get("status")
        result = strategy.get_all_goals(status=status)
        return {"success": True, "action": "show_goals", "data": result.get("data", [])}

    def _exec_show_reflections(self, params: dict, engines: dict) -> dict:
        """Show task reflections/quality scores."""
        reflection = engines.get("reflection")
        if not reflection:
            return {"success": False, "error": "Reflection engine not available"}

        agent_id = params.get("agent_id")
        task_type = params.get("task_type")
        limit = params.get("limit", 10)
        result = reflection.get_reflections(
            agent_id=agent_id, task_type=task_type, limit=limit,
        )
        return {"success": True, "action": "show_reflections", "data": result.get("data", [])}

    def _exec_set_autonomy(self, params: dict, engines: dict) -> dict:
        """Set the autonomy level."""
        autonomy = engines.get("autonomy")
        if not autonomy:
            return {"success": False, "error": "Autonomy controller not available"}

        level = params.get("level", "supervised")
        result = autonomy.set_autonomy_level(level)
        return {"success": result.get("success", False), "action": "set_autonomy", "data": result.get("data", {}), "error": result.get("error")}

    def _exec_show_conversations(self, params: dict, engines: dict) -> dict:
        """Show conversation threads."""
        conversation = engines.get("conversation")
        if not conversation:
            return {"success": False, "error": "Conversation engine not available"}

        lead_id = params.get("lead_id")
        if lead_id:
            result = conversation.get_thread(lead_id)
        else:
            result = conversation.get_thread_stats()
        return {"success": True, "action": "show_conversations", "data": result.get("data", {})}

    def _exec_show_approvals(self, params: dict, engines: dict) -> dict:
        """Show pending approval requests."""
        autonomy = engines.get("autonomy")
        if not autonomy:
            return {"success": False, "error": "Autonomy controller not available"}

        result = autonomy.get_pending_approvals()
        return {"success": True, "action": "show_approvals", "data": result.get("data", [])}

    def _exec_approve_action(self, params: dict, engines: dict) -> dict:
        """Approve a pending action and execute it if applicable."""
        autonomy = engines.get("autonomy")
        if not autonomy:
            return {"success": False, "error": "Autonomy controller not available"}

        approval_id = params.get("approval_id")
        if not approval_id:
            return {"success": False, "error": "approval_id is required"}

        # Fetch approval details before resolving (for post-approval execution)
        approval_data = self._get_approval_details(autonomy, approval_id)

        result = autonomy.approve_action(approval_id)
        if result.get("success") and approval_data:
            self._execute_approved_action(approval_data, engines)

        return {"success": result.get("success", False), "action": "approve_action", "data": result.get("data", {}), "error": result.get("error")}

    def _get_approval_details(self, autonomy, approval_id: int) -> dict | None:
        """Fetch full approval details including payload."""
        try:
            pending = autonomy.get_pending_approvals()
            if pending.get("success"):
                for item in pending.get("data", []):
                    if item.get("id") == approval_id:
                        return item
        except Exception:
            pass
        return None

    def _execute_approved_action(self, approval_data: dict, engines: dict):
        """Execute an action after it has been approved."""
        action_type = approval_data.get("action_type")
        payload = approval_data.get("payload", {})

        if action_type == "make_call":
            voice_engine = engines.get("voice")
            if voice_engine and payload.get("lead_id"):
                try:
                    voice_engine.initiate_call(payload["lead_id"])
                    logger.info(f"Voice call initiated for lead #{payload['lead_id']} after approval")
                except Exception as e:
                    logger.error(f"Failed to initiate approved call: {e}")

    def _exec_deny_action(self, params: dict, engines: dict) -> dict:
        """Deny a pending action."""
        autonomy = engines.get("autonomy")
        if not autonomy:
            return {"success": False, "error": "Autonomy controller not available"}

        approval_id = params.get("approval_id")
        if not approval_id:
            return {"success": False, "error": "approval_id is required"}
        result = autonomy.deny_action(approval_id)
        return {"success": result.get("success", False), "action": "deny_action", "data": result.get("data", {}), "error": result.get("error")}

    # ─── Invoice Intents ─────────────────────────────────────────────

    def _exec_create_invoice(self, params: dict, engines: dict) -> dict:
        """Create an invoice via pricing engine."""
        pricing = engines.get("pricing")
        if not pricing:
            return {"success": False, "error": "Pricing engine not available"}

        lead_id = params.get("lead_id")
        line_items = params.get("line_items", [])
        client_name = params.get("client_name", "")
        client_email = params.get("client_email", "")
        notes = params.get("notes", "")

        result = pricing.create_invoice(
            lead_id=lead_id,
            line_items=line_items,
            client_name=client_name,
            client_email=client_email,
            notes=notes,
        )
        return result

    def _exec_show_invoices(self, params: dict, engines: dict) -> dict:
        """List invoices, optionally filtered by status."""
        pricing = engines.get("pricing")
        if not pricing:
            return {"success": False, "error": "Pricing engine not available"}

        status = params.get("status")
        return pricing.get_invoices(status=status)

    # ─── Helpers ───────────────────────────────────────────────────────

    def _check_autonomy(self, action_type: str, engines: dict,
                        description: str = "") -> dict | None:
        """Check autonomy permission. Returns None if allowed, or a blocked result dict."""
        autonomy = engines.get("autonomy")
        if not autonomy:
            return None  # No autonomy controller → allow
        try:
            check = autonomy.check_permission(action_type)
            if check.get("data", {}).get("allowed"):
                return None  # Allowed
            if check.get("data", {}).get("needs_approval"):
                q = autonomy.queue_for_approval(action_type, description=description)
                return {
                    "success": False,
                    "error": f"Action '{action_type}' requires approval at current autonomy level",
                    "approval_queued": True,
                    "approval_id": q.get("data", {}).get("approval_id"),
                }
            return {
                "success": False,
                "error": f"Action '{action_type}' is blocked at current autonomy level",
            }
        except Exception as e:
            logger.debug(f"Autonomy check failed: {e}")
            return None  # Fail open on error

    def _get_api_keys(self, settings) -> dict:
        """Decrypt API keys from settings, falling back to subscription tokens."""
        keys = {}
        if not settings:
            return keys
        for provider, field in [
            ("gemini", "gemini_key_enc"),
            ("anthropic", "anthropic_key_enc"),
            ("openai", "openai_key_enc"),
            ("openrouter", "openrouter_key_enc"),
        ]:
            enc = getattr(settings, field, "")
            if enc:
                try:
                    keys[provider] = self.key_vault.decrypt(enc)
                except Exception:
                    pass
        # Fall back to subscription tokens when API keys are missing
        if "anthropic" not in keys:
            enc = getattr(settings, "anthropic_sub_token_enc", "")
            if enc:
                try:
                    keys["anthropic"] = self.key_vault.decrypt(enc)
                except Exception:
                    pass
        if "openai" not in keys:
            enc = getattr(settings, "openai_sub_token_enc", "")
            if enc:
                try:
                    keys["openai"] = self.key_vault.decrypt(enc)
                except Exception:
                    pass
        return keys

    def get_history(self) -> list:
        """Return conversation history for display."""
        return [
            {"role": h["role"], "content": h["content"]}
            for h in self._history
        ]

    def clear_history(self):
        """Clear conversation history."""
        self._history.clear()
