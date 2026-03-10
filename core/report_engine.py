"""
Aura — Report Engine
Generates PDF reports and CSV exports for campaigns.
"""

import csv
import os
from datetime import datetime

from database.db_manager import DatabaseManager
from database.schema import Campaign, Lead
from config import APP_NAME
from utils.logger import get_logger

logger = get_logger("report_engine")


class ReportEngine:
    """Generates campaign reports in PDF and CSV formats."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def export_campaign_pdf(self, campaign_id: int, output_path: str) -> dict:
        """
        Generate a clean PDF report for a campaign using reportlab.
        """
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
            )

            with self.db_manager.session_scope() as session:
                campaign = session.query(Campaign).filter_by(id=campaign_id).first()
                if not campaign:
                    return {"success": False, "error": "Campaign not found"}

                leads = session.query(Lead).filter_by(campaign_id=campaign_id).all()

                # Stats
                total = len(leads)
                qualified = sum(1 for l in leads if l.status not in ("new", "disqualified", "qualifying"))
                sent = sum(1 for l in leads if l.status in ("emailed", "email_sent", "replied", "converted"))
                replied = sum(1 for l in leads if l.status in ("replied", "converted"))
                total_cost = sum((l.tier2_cost_usd or 0) + (l.tier3_cost_usd or 0) for l in leads)
                qual_rate = (qualified / total * 100) if total > 0 else 0
                reply_rate = (replied / sent * 100) if sent > 0 else 0
                cost_per_qual = (total_cost / qualified) if qualified > 0 else 0
                cost_per_reply = (total_cost / replied) if replied > 0 else 0

                # Build PDF
                doc = SimpleDocTemplate(output_path, pagesize=A4)
                styles = getSampleStyleSheet()
                story = []

                # Title style
                title_style = ParagraphStyle(
                    "AuraTitle", parent=styles["Title"],
                    fontSize=28, textColor=colors.HexColor("#007AFF"),
                )
                subtitle_style = ParagraphStyle(
                    "AuraSubtitle", parent=styles["Normal"],
                    fontSize=14, textColor=colors.HexColor("#86868B"),
                )
                heading_style = ParagraphStyle(
                    "AuraHeading", parent=styles["Heading2"],
                    textColor=colors.HexColor("#1D1D1F"),
                )

                # ─── Cover Page ────────────────────────────────────────
                story.append(Spacer(1, 2 * inch))
                story.append(Paragraph(APP_NAME, title_style))
                story.append(Spacer(1, 0.3 * inch))
                story.append(Paragraph(f"Campaign Report: {campaign.name}", subtitle_style))
                story.append(Spacer(1, 0.2 * inch))
                story.append(Paragraph(
                    f"Generated: {datetime.utcnow().strftime('%B %d, %Y at %H:%M UTC')}",
                    subtitle_style,
                ))
                story.append(PageBreak())

                # ─── Summary Page ──────────────────────────────────────
                story.append(Paragraph("Campaign Summary", heading_style))
                story.append(Spacer(1, 0.2 * inch))

                summary_data = [
                    ["Metric", "Value"],
                    ["Total Leads Scraped", str(total)],
                    ["Qualified Rate", f"{qual_rate:.1f}%"],
                    ["Emails Sent", str(sent)],
                    ["Reply Rate", f"{reply_rate:.1f}%"],
                    ["Total AI Cost", f"${total_cost:.4f}"],
                    ["Cost per Qualified Lead", f"${cost_per_qual:.4f}"],
                    ["Cost per Reply", f"${cost_per_reply:.4f}"],
                ]

                t = Table(summary_data, colWidths=[3 * inch, 2.5 * inch])
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#007AFF")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F7")]),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E5EA")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]))
                story.append(t)
                story.append(PageBreak())

                # ─── Lead List Page ────────────────────────────────────
                story.append(Paragraph("Lead Details", heading_style))
                story.append(Spacer(1, 0.2 * inch))

                sent_leads = [l for l in leads if l.status in (
                    "emailed", "email_sent", "replied", "converted", "email_drafted"
                )]

                if sent_leads:
                    lead_data = [["Business", "City", "Status", "Sent At"]]
                    for lead in sent_leads[:100]:  # Cap at 100 for PDF
                        lead_data.append([
                            lead.business_name[:30],
                            lead.city[:20],
                            lead.status,
                            lead.email_sent_at.strftime("%Y-%m-%d") if lead.email_sent_at else "—",
                        ])

                    lt = Table(lead_data, colWidths=[2.2 * inch, 1.5 * inch, 1.2 * inch, 1.2 * inch])
                    lt.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#007AFF")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F7")]),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E5EA")),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]))
                    story.append(lt)
                else:
                    story.append(Paragraph("No sent leads to display.", styles["Normal"]))

                doc.build(story)

            return {"success": True, "path": output_path}
        except Exception as e:
            logger.error(f"PDF export failed: {e}")
            return {"success": False, "error": str(e)}

    def export_leads_csv(self, campaign_id: int, output_path: str,
                         status_filter: str = None) -> dict:
        """Export lead data to CSV for a campaign."""
        try:
            with self.db_manager.session_scope() as session:
                query = session.query(Lead).filter_by(campaign_id=campaign_id)
                if status_filter:
                    query = query.filter_by(status=status_filter)
                leads = query.all()

                columns = [
                    "business_name", "category", "city", "country", "email",
                    "phone", "website_url", "website_score", "status",
                    "email_subject", "email_sent_at", "notes",
                    "tier2_cost_usd", "tier3_cost_usd",
                ]

                with open(output_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=columns)
                    writer.writeheader()
                    for lead in leads:
                        writer.writerow({
                            col: getattr(lead, col, "") for col in columns
                        })

                return {
                    "success": True,
                    "data": {"count": len(leads), "path": output_path},
                }
        except Exception as e:
            logger.error(f"CSV export failed: {e}")
            return {"success": False, "error": str(e)}

    def export_all_campaigns_summary_csv(self, output_path: str) -> dict:
        """Export a summary CSV with one row per campaign."""
        try:
            with self.db_manager.session_scope() as session:
                campaigns = session.query(Campaign).order_by(Campaign.created_at.desc()).all()

                columns = [
                    "name", "status", "total_leads", "qualified_leads",
                    "emails_sent", "replies", "reply_rate", "total_token_cost",
                ]

                with open(output_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=columns)
                    writer.writeheader()
                    for c in campaigns:
                        reply_rate = (
                            (c.replies / c.emails_sent * 100)
                            if c.emails_sent and c.emails_sent > 0 else 0
                        )
                        writer.writerow({
                            "name": c.name,
                            "status": c.status,
                            "total_leads": c.total_leads,
                            "qualified_leads": c.qualified_leads,
                            "emails_sent": c.emails_sent,
                            "replies": c.replies,
                            "reply_rate": f"{reply_rate:.1f}%",
                            "total_token_cost": f"${c.total_token_cost:.4f}",
                        })

                return {
                    "success": True,
                    "data": {"count": len(campaigns), "path": output_path},
                }
        except Exception as e:
            logger.error(f"All-campaigns CSV export failed: {e}")
            return {"success": False, "error": str(e)}

    def export_all_campaigns_csv(self, output_path: str) -> dict:
        """Alias for export_all_campaigns_summary_csv."""
        return self.export_all_campaigns_summary_csv(output_path)

    def export_all_campaigns_pdf(self, output_path: str) -> dict:
        """Export PDF for the most recent campaign (dashboard shortcut)."""
        try:
            with self.db_manager.session_scope() as session:
                campaign = session.query(Campaign).order_by(Campaign.created_at.desc()).first()
                if not campaign:
                    return {"success": False, "error": "No campaigns found"}
                campaign_id = campaign.id
            return self.export_campaign_pdf(campaign_id, output_path)
        except Exception as e:
            logger.error(f"All-campaigns PDF export failed: {e}")
            return {"success": False, "error": str(e)}

    def export_campaign_xlsx(self, campaign_id: int, output_path: str) -> dict:
        """Export campaign to Excel via ExcelExportEngine."""
        try:
            from core.excel_export_engine import ExcelExportEngine
            engine = ExcelExportEngine(self.db_manager)
            result_path = engine.export_campaign_xlsx(campaign_id, output_path)
            return {"success": True, "data": {"path": result_path}}
        except Exception as e:
            logger.error(f"Campaign XLSX export failed: {e}")
            return {"success": False, "error": str(e)}
