#!/usr/bin/env python3
"""
Aura CLI — Headless AI Sales Agent
Run Aura without a graphical interface.
"""

import sys
import os
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import APP_NAME, APP_VERSION
from database.db_manager import DatabaseManager
from database.schema import Settings, Campaign, Lead, Skill
from core.key_vault import KeyVault
from core.ai_engine import AIEngine
from core.scraper_engine import ScraperEngine
from core.safety_guard import SafetyGuard
from core.enrichment_engine import EnrichmentEngine
from core.delivery_engine import DeliveryEngine
from core.reply_detector import ReplyDetector
from core.report_engine import ReportEngine
from core.suppression_engine import SuppressionEngine
from utils.logger import get_logger

logger = get_logger("cli")


class AuraCLI:
    """Headless CLI interface for Aura."""

    def __init__(self):
        self.db = DatabaseManager()
        self.db.init_db()
        self.db.migrate_schema()
        self.db.seed_defaults()
        self.db.seed_default_agents()

        self.key_vault = KeyVault()
        self.safety = SafetyGuard()
        self.ai_engine = AIEngine(safety_guard=self.safety)
        self.suppression = SuppressionEngine(self.db)
        self.scraper = ScraperEngine(suppression_engine=self.suppression)
        self.enrichment = EnrichmentEngine(self.db)
        self.delivery = DeliveryEngine()
        self.reply_detector = ReplyDetector(self.db, self.key_vault)
        self.report_engine = ReportEngine(self.db)

        self._configure_engines()

    def _configure_engines(self):
        """Load API keys from the database and configure engines."""
        settings = self.db.get_settings()
        if not settings:
            return

        api_keys = {}
        for provider in ["gemini", "anthropic", "openai", "openrouter"]:
            enc_field = f"{provider}_key_enc"
            enc_val = getattr(settings, enc_field, None)
            if enc_val:
                decrypted = self.key_vault.decrypt(enc_val)
                if decrypted:
                    api_keys[provider] = decrypted

        models = {}
        if settings.tier2_model:
            models["tier2"] = settings.tier2_model
        if settings.tier3_model:
            models["tier3"] = settings.tier3_model

        if api_keys:
            self.ai_engine.configure(api_keys, models)

        # Configure delivery
        if settings.resend_key_enc:
            key = self.key_vault.decrypt(settings.resend_key_enc)
            if key:
                self.delivery.configure_resend(key)
        if settings.smtp_host:
            smtp_pass = ""
            if settings.smtp_password_enc:
                smtp_pass = self.key_vault.decrypt(settings.smtp_password_enc) or ""
            self.delivery.configure_smtp(
                settings.smtp_host, settings.smtp_port or 587,
                settings.smtp_user or "", smtp_pass,
            )

    # ─── Commands ─────────────────────────────────────────

    def cmd_hunt(self, niche: str, city: str, limit: int = 50):
        """Run the lead scraping pipeline."""
        print(f"Hunting for {limit} leads: '{niche}' in '{city}'...")

        def on_progress(pct):
            print(f"  Progress: {pct}%", end="\r")

        leads = self.scraper.run(
            query=f"{niche} {city}",
            city=city,
            niche=niche,
            limit=limit,
            _progress_callback=on_progress,
        )
        print(f"\nFound {len(leads)} leads.")

        # Save to campaign
        with self.db.session_scope() as session:
            campaign = Campaign(
                name=f"{niche} — {city}",
                target_niche=niche,
                target_city=city,
                status="active",
            )
            session.add(campaign)
            session.flush()
            campaign_id = campaign.id

        saved = 0
        for lead_data in leads:
            with self.db.session_scope() as session:
                lead = Lead(
                    campaign_id=campaign_id,
                    business_name=lead_data.business_name,
                    category=lead_data.category,
                    city=lead_data.city,
                    phone=lead_data.phone,
                    email=lead_data.email,
                    source_url=lead_data.source_url,
                    source_platform=lead_data.source_platform,
                    has_website=lead_data.has_website,
                    website_url=lead_data.website_url,
                    status="new",
                )
                session.add(lead)
            saved += 1
        print(f"Saved {saved} leads to campaign '{niche} — {city}' (ID: {campaign_id})")
        return campaign_id

    def cmd_qualify(self, campaign_id: int):
        """Qualify all new leads in a campaign using AI."""
        with self.db.session_scope() as session:
            leads = session.query(Lead).filter_by(campaign_id=campaign_id, status="new").all()
            lead_dicts = [{"id": l.id, "business_name": l.business_name, "category": l.category,
                           "city": l.city, "phone": l.phone, "website_url": l.website_url,
                           "snippet": l.notes or ""} for l in leads]

        if not lead_dicts:
            print("No new leads to qualify in this campaign.")
            return

        with self.db.session_scope() as session:
            campaign = session.query(Campaign).filter_by(id=campaign_id).first()
            niche = campaign.target_niche if campaign else ""

        print(f"Qualifying {len(lead_dicts)} leads...")
        qualified = 0
        for ld in lead_dicts:
            result = self.ai_engine.qualify_lead(ld, niche)
            status = "qualified" if result.get("qualified") else "disqualified"
            with self.db.session_scope() as session:
                lead = session.query(Lead).filter_by(id=ld["id"]).first()
                if lead:
                    lead.status = status
                    lead.notes = (lead.notes or "") + f"\n[{status.title()}] Score: {result.get('score', 0)}/10"
            if result.get("qualified"):
                qualified += 1
            print(f"  {ld['business_name']}: {status} (score: {result.get('score', 0)}/10)")

        print(f"\nQualified: {qualified}/{len(lead_dicts)}")

    def cmd_draft(self, campaign_id: int):
        """Generate email drafts for qualified leads."""
        with self.db.session_scope() as session:
            leads = session.query(Lead).filter_by(campaign_id=campaign_id, status="qualified").all()
            lead_dicts = [{"id": l.id, "business_name": l.business_name, "email": l.email,
                           "city": l.city, "category": l.category, "website_url": l.website_url}
                          for l in leads]
            campaign = session.query(Campaign).filter_by(id=campaign_id).first()
            niche = campaign.target_niche if campaign else ""

            # Get the campaign's skill or default
            skill_dict = {}
            if campaign and campaign.skill_id:
                skill = session.query(Skill).filter_by(id=campaign.skill_id).first()
                if skill:
                    skill_dict = {"name": skill.name, "tone": skill.tone,
                                  "template": skill.template, "niche": niche}
            if not skill_dict:
                skill_dict = {"name": "Default", "tone": "professional", "template": "", "niche": niche}

        if not lead_dicts:
            print("No qualified leads to draft emails for.")
            return

        settings = self.db.get_settings()
        sender_name = settings.sender_name if settings else APP_NAME

        print(f"Drafting emails for {len(lead_dicts)} qualified leads...")
        for ld in lead_dicts:
            result = self.ai_engine.generate_email(ld, skill_dict, sender_name=sender_name)
            if result.get("subject") and result.get("body"):
                with self.db.session_scope() as session:
                    lead = session.query(Lead).filter_by(id=ld["id"]).first()
                    if lead:
                        lead.email_subject = result["subject"]
                        lead.email_body = result["body"]
                        lead.status = "email_drafted"
                print(f"  + {ld['business_name']}: {result['subject'][:60]}...")
            else:
                print(f"  x {ld['business_name']}: draft failed")

    def cmd_send(self, campaign_id: int, count: int = None):
        """Send drafted emails."""
        with self.db.session_scope() as session:
            query = session.query(Lead).filter_by(campaign_id=campaign_id, status="email_drafted")
            leads = query.limit(count).all() if count else query.all()
            lead_dicts = [{"id": l.id, "business_name": l.business_name, "email": l.email,
                           "email_subject": l.email_subject, "email_body": l.email_body}
                          for l in leads if l.email]

        settings = self.db.get_settings()
        from_email = settings.sender_email if settings else ""
        from_name = settings.sender_name if settings else APP_NAME

        if not from_email:
            print("Error: No sender email configured. Run 'aura config' first.")
            return

        if not lead_dicts:
            print("No drafted emails to send.")
            return

        print(f"Sending {len(lead_dicts)} emails from {from_email}...")
        sent = 0
        for ld in lead_dicts:
            result = self.delivery.send_email(
                to_email=ld["email"],
                from_email=from_email,
                subject=ld["email_subject"],
                body=ld["email_body"],
                from_name=from_name,
            )
            if result.get("success"):
                with self.db.session_scope() as session:
                    lead = session.query(Lead).filter_by(id=ld["id"]).first()
                    if lead:
                        lead.status = "emailed"
                        lead.email_sent_at = datetime.utcnow()
                sent += 1
                print(f"  + {ld['business_name']} ({ld['email']})")
            else:
                print(f"  x {ld['business_name']}: {result.get('error', 'unknown')}")

        print(f"\nSent: {sent}/{len(lead_dicts)}")

    def cmd_stats(self, campaign_id: int = None):
        """Show campaign statistics."""
        with self.db.session_scope() as session:
            if campaign_id:
                campaigns = [session.query(Campaign).filter_by(id=campaign_id).first()]
            else:
                campaigns = session.query(Campaign).all()

            if not campaigns or not campaigns[0]:
                print("No campaigns found.")
                return

            for c in campaigns:
                if not c:
                    continue
                total = session.query(Lead).filter_by(campaign_id=c.id).count()
                qualified = session.query(Lead).filter_by(campaign_id=c.id, status="qualified").count()
                drafted = session.query(Lead).filter_by(campaign_id=c.id, status="email_drafted").count()
                sent = session.query(Lead).filter_by(campaign_id=c.id, status="emailed").count()
                replied = session.query(Lead).filter_by(campaign_id=c.id, status="replied").count()

                print(f"\n{'=' * 50}")
                print(f"Campaign: {c.name} (ID: {c.id})")
                print(f"  Status:    {c.status}")
                print(f"  Leads:     {total}")
                print(f"  Qualified: {qualified}")
                print(f"  Drafted:   {drafted}")
                print(f"  Sent:      {sent}")
                print(f"  Replied:   {replied}")

    def cmd_replies(self):
        """Check for email replies via IMAP."""
        print("Checking inbox for replies...")
        results = self.reply_detector.check_inbox()
        if results:
            print(f"Found {len(results)} new replies:")
            for r in results:
                print(f"  - Lead #{r.get('lead_id', '?')}: {r.get('subject', 'No subject')}")
        else:
            print("No new replies found.")

    def cmd_campaigns(self):
        """List all campaigns."""
        with self.db.session_scope() as session:
            campaigns = session.query(Campaign).all()
            if not campaigns:
                print("No campaigns yet. Run 'aura hunt' to create one.")
                return
            print(f"\n{'ID':<6} {'Status':<12} {'Name'}")
            print("-" * 50)
            for c in campaigns:
                print(f"{c.id:<6} {c.status:<12} {c.name}")

    def cmd_interactive(self):
        """Interactive command loop using the orchestrator."""
        print(f"\n{APP_NAME} v{APP_VERSION} -- Interactive Mode")
        print("Type commands in natural language. Type 'quit' to exit.\n")

        from core.orchestrator_engine import OrchestratorEngine
        orchestrator = OrchestratorEngine(self.db, self.key_vault)
        orchestrator.ai_engine = self.ai_engine

        while True:
            try:
                user_input = input("aura> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break

            result = orchestrator.parse_intent(user_input)
            if result.get("success"):
                intent = result.get("intent", "")
                params = result.get("params", {})
                print(f"[Intent: {intent}] {params}")
                exec_result = orchestrator.execute_intent(result, {})
                if exec_result.get("success"):
                    print(exec_result.get("message", "Done."))
                    if exec_result.get("data"):
                        import json
                        print(json.dumps(exec_result["data"], indent=2, default=str))
                else:
                    print(f"Error: {exec_result.get('error', 'Unknown error')}")
            else:
                print(f"Could not parse: {result.get('error', 'Unknown')}")

    def cmd_config_interactive(self):
        """Interactive configuration for API keys and email settings."""
        print(f"\n{APP_NAME} -- Configuration\n")
        settings = self.db.get_settings()

        # API Keys
        print("--- API Keys ---")
        providers = [
            ("gemini", "Gemini (Google)"),
            ("anthropic", "Anthropic (Claude)"),
            ("openai", "OpenAI"),
            ("openrouter", "OpenRouter"),
        ]
        for key_name, label in providers:
            enc_field = f"{key_name}_key_enc"
            current = getattr(settings, enc_field, None) if settings else None
            status = "[configured]" if current else "[not set]"
            print(f"  {label}: {status}")
            new_key = input(f"  Enter new {label} API key (or press Enter to skip): ").strip()
            if new_key:
                encrypted = self.key_vault.encrypt(new_key)
                with self.db.session_scope() as session:
                    s = session.query(Settings).first()
                    setattr(s, enc_field, encrypted)
                print(f"  -> {label} key saved.\n")

        # SMTP
        print("\n--- Email Delivery (SMTP) ---")
        current_host = getattr(settings, "smtp_host", "") or ""
        smtp_host = input(f"  SMTP host [{current_host}]: ").strip()
        if smtp_host:
            smtp_port = input("  SMTP port [587]: ").strip() or "587"
            smtp_user = input("  SMTP username: ").strip()
            smtp_pass = input("  SMTP password: ").strip()
            sender_email = input("  Sender email: ").strip()
            sender_name = input(f"  Sender name [{APP_NAME}]: ").strip() or APP_NAME

            with self.db.session_scope() as session:
                s = session.query(Settings).first()
                s.smtp_host = smtp_host
                s.smtp_port = int(smtp_port)
                s.smtp_user = smtp_user
                s.smtp_password_enc = self.key_vault.encrypt(smtp_pass) if smtp_pass else ""
                s.sender_email = sender_email
                s.sender_name = sender_name
            print("  -> SMTP settings saved.")

        # Model selection
        print("\n--- AI Model Selection ---")
        current_t2 = getattr(settings, "tier2_model", "default") if settings else "default"
        current_t3 = getattr(settings, "tier3_model", "default") if settings else "default"
        print(f"  Current Tier 2 (fast): {current_t2}")
        print(f"  Current Tier 3 (smart): {current_t3}")
        tier2 = input("  Tier 2 model (or Enter to skip): ").strip()
        tier3 = input("  Tier 3 model (or Enter to skip): ").strip()
        if tier2 or tier3:
            with self.db.session_scope() as session:
                s = session.query(Settings).first()
                if tier2:
                    s.tier2_model = tier2
                if tier3:
                    s.tier3_model = tier3
            print("  -> Model settings saved.")

        print("\nConfiguration complete! Restart to apply changes.")


def main():
    parser = argparse.ArgumentParser(
        prog="aura",
        description=f"{APP_NAME} v{APP_VERSION} -- AI Sales Agent (CLI)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # hunt
    hunt_p = subparsers.add_parser("hunt", help="Scrape leads for a niche in a city")
    hunt_p.add_argument("niche", help="Business niche (e.g., 'plumber')")
    hunt_p.add_argument("city", help="Target city (e.g., 'Austin TX')")
    hunt_p.add_argument("-n", "--limit", type=int, default=50, help="Max leads (default: 50)")

    # qualify
    qual_p = subparsers.add_parser("qualify", help="AI-qualify leads in a campaign")
    qual_p.add_argument("campaign_id", type=int, help="Campaign ID")

    # draft
    draft_p = subparsers.add_parser("draft", help="Generate email drafts for qualified leads")
    draft_p.add_argument("campaign_id", type=int, help="Campaign ID")

    # send
    send_p = subparsers.add_parser("send", help="Send drafted emails")
    send_p.add_argument("campaign_id", type=int, help="Campaign ID")
    send_p.add_argument("-n", "--count", type=int, help="Max emails to send")

    # stats
    stats_p = subparsers.add_parser("stats", help="Show campaign statistics")
    stats_p.add_argument("campaign_id", type=int, nargs="?", help="Campaign ID (omit for all)")

    # replies
    subparsers.add_parser("replies", help="Check inbox for email replies")

    # campaigns
    subparsers.add_parser("campaigns", help="List all campaigns")

    # interactive
    subparsers.add_parser("interactive", aliases=["i", "shell"],
                          help="Interactive natural-language mode")

    # config
    subparsers.add_parser("config", help="Interactive settings (API keys, SMTP, models)")

    # version
    subparsers.add_parser("version", help="Show version")

    args = parser.parse_args()

    if args.command == "version":
        print(f"{APP_NAME} v{APP_VERSION}")
        return

    if args.command is None:
        parser.print_help()
        return

    cli = AuraCLI()

    if args.command == "hunt":
        cli.cmd_hunt(args.niche, args.city, args.limit)
    elif args.command == "qualify":
        cli.cmd_qualify(args.campaign_id)
    elif args.command == "draft":
        cli.cmd_draft(args.campaign_id)
    elif args.command == "send":
        cli.cmd_send(args.campaign_id, args.count)
    elif args.command == "stats":
        cli.cmd_stats(args.campaign_id)
    elif args.command == "replies":
        cli.cmd_replies()
    elif args.command == "campaigns":
        cli.cmd_campaigns()
    elif args.command in ("interactive", "i", "shell"):
        cli.cmd_interactive()
    elif args.command == "config":
        cli.cmd_config_interactive()


if __name__ == "__main__":
    main()
