"""
Aura — AI Performance Analyst
Gathers real campaign stats from the DB and answers performance questions via LiteLLM.
"""

import json

from database.db_manager import DatabaseManager
from database.schema import Campaign, Lead, Skill, Settings
from config import DEFAULT_TIER3_MODEL
from utils.logger import get_logger

logger = get_logger("analyst_engine")


class AnalystEngine:
    """AI-powered performance analysis using real campaign data."""

    def __init__(self, db_manager: DatabaseManager, key_vault):
        self.db_manager = db_manager
        self.key_vault = key_vault

    def gather_context(self) -> dict:
        """
        Query the DB and return structured stats. Never fabricates — only real data.
        """
        try:
            with self.db_manager.session_scope() as session:
                campaigns = session.query(Campaign).all()
                leads = session.query(Lead).all()
                skills = session.query(Skill).all()

                campaign_data = []
                best_reply_rate = ("", 0.0)
                worst_reply_rate = ("", 1.0)

                for c in campaigns:
                    reply_rate = (
                        c.replies / c.emails_sent if c.emails_sent and c.emails_sent > 0 else 0
                    )
                    campaign_data.append({
                        "name": c.name,
                        "status": c.status,
                        "total_leads": c.total_leads,
                        "qualified_leads": c.qualified_leads,
                        "emails_sent": c.emails_sent,
                        "replies": c.replies,
                        "reply_rate": round(reply_rate, 3),
                        "total_token_cost": round(c.total_token_cost or 0, 4),
                        "niche": c.target_niche,
                        "city": c.target_city,
                    })

                    if c.emails_sent and c.emails_sent > 0:
                        if reply_rate > best_reply_rate[1]:
                            best_reply_rate = (c.name, reply_rate)
                        if reply_rate < worst_reply_rate[1]:
                            worst_reply_rate = (c.name, reply_rate)

                total_spent = sum(
                    (l.tier2_cost_usd or 0) + (l.tier3_cost_usd or 0) for l in leads
                )
                total_emails = sum(c.emails_sent or 0 for c in campaigns)
                total_replies = sum(c.replies or 0 for c in campaigns)
                overall_reply_rate = (
                    total_replies / total_emails if total_emails > 0 else 0
                )

                # Top niches and cities by reply rate
                niche_stats = {}
                city_stats = {}
                for c in campaigns:
                    if c.emails_sent and c.emails_sent > 0:
                        rr = c.replies / c.emails_sent
                        if c.target_niche:
                            if c.target_niche not in niche_stats or rr > niche_stats[c.target_niche]:
                                niche_stats[c.target_niche] = rr
                        if c.target_city:
                            if c.target_city not in city_stats or rr > city_stats[c.target_city]:
                                city_stats[c.target_city] = rr

                context = {
                    "campaigns": campaign_data,
                    "total_spent_usd": round(total_spent, 4),
                    "best_reply_rate_campaign": best_reply_rate[0],
                    "worst_reply_rate_campaign": worst_reply_rate[0],
                    "best_performing_skill": "",
                    "total_leads_all_time": len(leads),
                    "total_emails_sent": total_emails,
                    "overall_reply_rate": round(overall_reply_rate, 3),
                    "top_niches_by_reply_rate": sorted(
                        niche_stats.items(), key=lambda x: x[1], reverse=True
                    )[:5],
                    "top_cities_by_reply_rate": sorted(
                        city_stats.items(), key=lambda x: x[1], reverse=True
                    )[:5],
                }

                # Find best performing skill
                skill_replies = {}
                for c in campaigns:
                    if c.skill_id and c.replies:
                        skill = session.query(Skill).filter_by(id=c.skill_id).first()
                        if skill:
                            skill_replies[skill.name] = (
                                skill_replies.get(skill.name, 0) + c.replies
                            )
                if skill_replies:
                    context["best_performing_skill"] = max(
                        skill_replies, key=skill_replies.get
                    )

                return context
        except Exception as e:
            logger.error(f"Error gathering context: {e}")
            return {"campaigns": [], "error": str(e)}

    def ask(self, question: str, context: dict = None) -> str:
        """
        Answer a performance question using real campaign data via LiteLLM.
        """
        try:
            if context is None:
                context = self.gather_context()

            # Get model from settings
            settings = self.db_manager.get_settings()
            model = DEFAULT_TIER3_MODEL
            if settings and settings.chat_model:
                model = settings.chat_model

            # Configure API keys
            api_keys = self._get_api_keys(settings)

            system_prompt = (
                "You are a data analyst for an AI sales outreach tool called Aura. "
                "You have access to the following real campaign data. "
                "Answer the user's question using only this data — never invent numbers. "
                "Be concise and actionable. Use specific numbers from the data.\n\n"
                f"DATA:\n{json.dumps(context, indent=2, default=str)}"
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ]

            # Subscription modes route through provider CLIs (no API key)
            from core.cli_llm import try_subscription_route
            handled, text = try_subscription_route(settings, model, messages)
            if handled:
                if text:
                    return text
                return (
                    "I couldn't analyze that right now: the provider CLI "
                    "call failed — is it installed and logged in?"
                )

            import litellm
            for provider, key in api_keys.items():
                if provider == "gemini":
                    import os
                    os.environ["GEMINI_API_KEY"] = key
                elif provider == "anthropic":
                    import os
                    os.environ["ANTHROPIC_API_KEY"] = key
                elif provider == "openai":
                    import os
                    os.environ["OPENAI_API_KEY"] = key

            response = litellm.completion(
                model=model,
                messages=messages,
                max_tokens=500,
                temperature=0.3,
            )

            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Analyst ask failed: {e}")
            return f"I couldn't analyze that right now: {str(e)}"

    def _get_api_keys(self, settings) -> dict:
        """Decrypt API keys from settings."""
        keys = {}
        if not settings:
            return keys
        for provider, field in [
            ("gemini", "gemini_key_enc"),
            ("anthropic", "anthropic_key_enc"),
            ("openai", "openai_key_enc"),
        ]:
            enc = getattr(settings, field, "")
            if enc:
                try:
                    keys[provider] = self.key_vault.decrypt(enc)
                except Exception:
                    pass
        return keys
