"""
Aura — Invoice Approval Engine
Manages the approval workflow for invoices: starts approval flow, handles
approve/reject decisions, escalates urgent invoices, and notifies channels.
"""

from datetime import datetime

from database.db_manager import DatabaseManager
from database.schema import Invoice, FinanceNote, Settings
from config import INVOICE_APPROVAL_STATUSES
from utils.logger import get_logger

logger = get_logger("invoice_approval")


class InvoiceApprovalEngine:
    """Orchestrates invoice approval workflow across channels."""

    def __init__(self, db_manager: DatabaseManager, gateway_engine=None,
                 pricing_engine=None):
        self.db_manager = db_manager
        self.gateway_engine = gateway_engine
        self.pricing_engine = pricing_engine
        self.voice_call_engine = None  # injected by main_window

    # ─── Approval Flow ────────────────────────────────────────────

    def start_approval_flow(self, invoice_id: int) -> dict:
        """
        Initiate approval for an invoice: set pending_approval status,
        send notifications to configured channels.
        """
        try:
            with self.db_manager.session_scope() as session:
                inv = session.query(Invoice).get(invoice_id)
                if not inv:
                    return {"success": False, "error": f"Invoice {invoice_id} not found"}

                if inv.approval_status == "approved":
                    return {"success": False, "error": "Invoice already approved"}

                inv.approval_status = "pending"
                inv.approval_requested_at = datetime.utcnow()

                # Log note
                session.add(FinanceNote(
                    invoice_id=invoice_id,
                    lead_id=inv.lead_id,
                    note_type="general",
                    content="Approval flow started — awaiting review.",
                    created_by="system",
                ))

                inv_number = inv.invoice_number
                total = inv.total
                currency = inv.currency
                client = inv.client_name

            # Notify channels (outside session)
            notification = {
                "type": "invoice_approval_needed",
                "invoice_id": invoice_id,
                "invoice_number": inv_number,
                "total": total,
                "currency": currency,
                "client_name": client,
            }

            if self.gateway_engine:
                try:
                    self.gateway_engine.notify_event(
                        "invoice_approval_needed", notification
                    )
                except Exception as e:
                    logger.warning(f"Gateway notification failed: {e}")

            logger.info(f"Approval flow started for {inv_number}")

            return {
                "success": True,
                "data": {
                    "invoice_id": invoice_id,
                    "invoice_number": inv_number,
                    "approval_status": "pending",
                },
            }

        except Exception as e:
            logger.error(f"Start approval failed: {e}")
            return {"success": False, "error": str(e)}

    # ─── Approve / Reject ─────────────────────────────────────────

    def approve(self, invoice_id: int, approved_by: str = "user") -> dict:
        """Approve an invoice — update status, optionally trigger PDF generation."""
        try:
            with self.db_manager.session_scope() as session:
                inv = session.query(Invoice).get(invoice_id)
                if not inv:
                    return {"success": False, "error": f"Invoice {invoice_id} not found"}

                if inv.approval_status == "approved":
                    return {"success": False, "error": "Already approved"}

                inv.approval_status = "approved"
                inv.approved_at = datetime.utcnow()

                session.add(FinanceNote(
                    invoice_id=invoice_id,
                    lead_id=inv.lead_id,
                    note_type="general",
                    content=f"Invoice approved by {approved_by}.",
                    created_by=approved_by,
                ))

                inv_number = inv.invoice_number

            # Trigger PDF generation if pricing engine available
            pdf_result = None
            if self.pricing_engine:
                pdf_result = self.pricing_engine.generate_invoice_pdf(invoice_id)

            # Notify channels
            if self.gateway_engine:
                try:
                    self.gateway_engine.notify_event("invoice_approved", {
                        "invoice_id": invoice_id,
                        "invoice_number": inv_number,
                        "approved_by": approved_by,
                    })
                except Exception as e:
                    logger.warning(f"Approval notification failed: {e}")

            logger.info(f"Invoice {inv_number} approved by {approved_by}")

            result = {
                "success": True,
                "data": {
                    "invoice_id": invoice_id,
                    "invoice_number": inv_number,
                    "approval_status": "approved",
                },
            }
            if pdf_result and pdf_result.get("success"):
                result["data"]["pdf_path"] = pdf_result["data"]["path"]

            return result

        except Exception as e:
            logger.error(f"Approve failed: {e}")
            return {"success": False, "error": str(e)}

    def reject(self, invoice_id: int, reason: str = "",
               rejected_by: str = "user") -> dict:
        """Reject an invoice with reason."""
        try:
            with self.db_manager.session_scope() as session:
                inv = session.query(Invoice).get(invoice_id)
                if not inv:
                    return {"success": False, "error": f"Invoice {invoice_id} not found"}

                if inv.approval_status == "rejected":
                    return {"success": False, "error": "Already rejected"}

                inv.approval_status = "rejected"

                session.add(FinanceNote(
                    invoice_id=invoice_id,
                    lead_id=inv.lead_id,
                    note_type="general",
                    content=f"Invoice rejected by {rejected_by}. Reason: {reason or 'No reason given.'}",
                    created_by=rejected_by,
                ))

                inv_number = inv.invoice_number

            # Notify
            if self.gateway_engine:
                try:
                    self.gateway_engine.notify_event("invoice_rejected", {
                        "invoice_id": invoice_id,
                        "invoice_number": inv_number,
                        "rejected_by": rejected_by,
                        "reason": reason,
                    })
                except Exception as e:
                    logger.warning(f"Rejection notification failed: {e}")

            logger.info(f"Invoice {inv_number} rejected by {rejected_by}: {reason}")

            return {
                "success": True,
                "data": {
                    "invoice_id": invoice_id,
                    "invoice_number": inv_number,
                    "approval_status": "rejected",
                    "reason": reason,
                },
            }

        except Exception as e:
            logger.error(f"Reject failed: {e}")
            return {"success": False, "error": str(e)}

    # ─── Escalation ───────────────────────────────────────────────

    def escalate(self, invoice_id: int) -> dict:
        """Full escalation: urgent notification -> voice calls (3 attempts) -> passive wait."""
        try:
            with self.db_manager.session_scope() as session:
                inv = session.query(Invoice).get(invoice_id)
                if not inv:
                    return {"success": False, "error": f"Invoice {invoice_id} not found"}

                if inv.approval_status == "approved":
                    return {"success": False, "error": "Already approved, no need to escalate"}

                call_count = inv.approval_call_count or 0
                inv_number = inv.invoice_number
                total = inv.total
                currency = inv.currency
                lead_id = inv.lead_id

            # Step 1: Urgent text notification
            if self.gateway_engine:
                try:
                    self.gateway_engine.notify_event("invoice_escalated", {
                        "invoice_id": invoice_id,
                        "invoice_number": inv_number,
                        "total": total,
                        "currency": currency,
                        "urgent": True,
                    })
                except Exception as e:
                    logger.warning(f"Escalation notification failed: {e}")

            # Step 2: Voice calls (up to 3 attempts)
            called = False
            if call_count < 3:
                # Try high-priority Discord notification
                if self.gateway_engine:
                    try:
                        self.gateway_engine.notify_event("invoice_voice_ring", {
                            "invoice_id": invoice_id,
                            "invoice_number": inv_number,
                            "total": total,
                            "currency": currency,
                            "message": f"URGENT: Invoice {inv_number} for {currency} {total:.2f} needs your approval!",
                            "force_notification": True,
                        })
                        called = True
                    except Exception as e:
                        logger.warning(f"Voice ring notification failed: {e}")

                # Update call count
                with self.db_manager.session_scope() as session:
                    inv = session.query(Invoice).get(invoice_id)
                    if inv:
                        inv.approval_call_count = call_count + 1

                    session.add(FinanceNote(
                        invoice_id=invoice_id,
                        lead_id=lead_id,
                        note_type="follow_up",
                        content=f"Escalation attempt {call_count + 1}/3. Notification {'sent' if called else 'failed'}.",
                        created_by="system",
                    ))
            else:
                # After 3 failed calls: passive wait
                with self.db_manager.session_scope() as session:
                    session.add(FinanceNote(
                        invoice_id=invoice_id,
                        lead_id=lead_id,
                        note_type="follow_up",
                        content="Max escalation attempts reached. Waiting for manual user approval.",
                        created_by="system",
                    ))
                logger.info(f"Invoice {inv_number}: max escalation attempts reached")

            logger.info(f"Invoice {inv_number} escalated (attempt {call_count + 1})")

            return {
                "success": True,
                "data": {
                    "invoice_id": invoice_id,
                    "invoice_number": inv_number,
                    "escalated": True,
                    "call_count": min(call_count + 1, 3),
                },
            }

        except Exception as e:
            logger.error(f"Escalation failed: {e}")
            return {"success": False, "error": str(e)}

    # ─── Queries ──────────────────────────────────────────────────

    def get_pending_approvals(self) -> dict:
        """Get all invoices pending approval."""
        try:
            with self.db_manager.session_scope() as session:
                invoices = session.query(Invoice).filter_by(
                    approval_status="pending"
                ).order_by(Invoice.created_at.desc()).all()

                data = [
                    {
                        "id": inv.id,
                        "invoice_number": inv.invoice_number,
                        "client_name": inv.client_name,
                        "total": inv.total,
                        "currency": inv.currency,
                        "created_at": inv.created_at.isoformat() if inv.created_at else None,
                    }
                    for inv in invoices
                ]

                return {"success": True, "data": data, "count": len(data)}

        except Exception as e:
            logger.error(f"Get pending approvals failed: {e}")
            return {"success": False, "error": str(e)}
