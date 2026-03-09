"""
Aura — Pricing Engine
Evaluates lead value via LLM analysis, creates invoices with auto-incrementing
numbers, generates PDF invoices with reportlab, and manages invoice lifecycle.
"""

from datetime import datetime, timedelta

from database.db_manager import DatabaseManager
from database.schema import (
    Lead, EnrichmentData, Service, Invoice, InvoiceLineItem, FinanceNote, Settings,
)
from config import INVOICE_STATUSES
from utils.logger import get_logger

logger = get_logger("pricing_engine")


class PricingEngine:
    """Handles pricing evaluation, invoice creation, PDF generation, and status management."""

    def __init__(self, db_manager: DatabaseManager, router_engine=None):
        self.db_manager = db_manager
        self.router_engine = router_engine

    # ─── Pricing Evaluation ───────────────────────────────────────

    def evaluate_pricing(self, lead_id: int) -> dict:
        """
        Analyze lead enrichment data + services catalog via LLM to propose
        invoice line items with rationale. Falls back to rule-based if no LLM.
        """
        try:
            with self.db_manager.session_scope() as session:
                lead = session.query(Lead).get(lead_id)
                if not lead:
                    return {"success": False, "error": f"Lead {lead_id} not found"}

                enrichment = session.query(EnrichmentData).filter_by(
                    lead_id=lead_id
                ).first()

                services = session.query(Service).filter_by(is_active=True).all()

                # Build context for evaluation
                lead_context = {
                    "business_name": lead.business_name or "",
                    "category": lead.category or "",
                    "city": lead.city or "",
                    "website_score": lead.website_score or 0,
                    "tier2_cost_usd": lead.tier2_cost_usd or 0,
                }

                if enrichment:
                    lead_context.update({
                        "company_size": enrichment.company_size_estimate or "",
                        "industry": enrichment.industry_tag or "",
                        "tech_stack": enrichment.tech_stack or "",
                        "pain_points": enrichment.pain_points or "",
                        "icp_fit_score": enrichment.icp_fit_score or 0,
                    })

                service_catalog = [
                    {
                        "id": s.id, "name": s.name, "description": s.description,
                        "base_price": s.base_price, "max_price": s.max_price,
                        "unit": s.unit, "category": s.category,
                    }
                    for s in services
                ]

                # Try LLM evaluation
                if self.router_engine and service_catalog:
                    line_items, rationale = self._llm_evaluate(
                        lead_context, service_catalog
                    )
                else:
                    line_items, rationale = self._rule_based_evaluate(
                        lead_context, service_catalog
                    )

                return {
                    "success": True,
                    "data": {
                        "lead_id": lead_id,
                        "line_items": line_items,
                        "rationale": rationale,
                        "subtotal": sum(li["total"] for li in line_items),
                    },
                }

        except Exception as e:
            logger.error(f"Pricing evaluation failed: {e}")
            return {"success": False, "error": str(e)}

    def _llm_evaluate(self, lead_context: dict, service_catalog: list) -> tuple:
        """Use LLM to propose line items. Returns (line_items, rationale)."""
        prompt = (
            f"Evaluate this lead for pricing:\n{lead_context}\n\n"
            f"Available services:\n{service_catalog}\n\n"
            "Propose 1-5 relevant services with quantities and prices within "
            "the base_price to max_price range. Consider the lead's industry, "
            "pain points, and company size. Return JSON with 'line_items' "
            "(list of {{service_id, description, quantity, unit_price}}) and 'rationale'."
        )

        try:
            response = self.router_engine.route_and_call(
                task_type="evaluate_pricing",
                system_prompt="You are a pricing analyst. Respond with valid JSON only.",
                user_prompt=prompt,
            )
            import json
            text = response.get("response", "{}")
            # Try to extract JSON from response
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            data = json.loads(text.strip())
            items = data.get("line_items", [])
            rationale = data.get("rationale", "LLM-generated pricing proposal")

            line_items = []
            for item in items:
                total = float(item.get("quantity", 1)) * float(item.get("unit_price", 0))
                line_items.append({
                    "service_id": item.get("service_id"),
                    "description": item.get("description", ""),
                    "quantity": float(item.get("quantity", 1)),
                    "unit_price": float(item.get("unit_price", 0)),
                    "total": total,
                })

            return line_items, rationale

        except Exception as e:
            logger.warning(f"LLM pricing failed, falling back to rules: {e}")
            return self._rule_based_evaluate(lead_context, service_catalog)

    def _rule_based_evaluate(self, lead_context: dict, service_catalog: list) -> tuple:
        """Simple rule-based pricing fallback."""
        line_items = []
        for svc in service_catalog[:3]:  # Propose up to 3 services
            price = svc["base_price"]
            # Adjust by ICP score
            icp = lead_context.get("icp_fit_score", 50)
            if icp > 70:
                price = min(svc["max_price"], price * 1.2)
            line_items.append({
                "service_id": svc["id"],
                "description": svc["name"],
                "quantity": 1,
                "unit_price": price,
                "total": price,
            })

        rationale = "Rule-based pricing: base prices adjusted by ICP fit score."
        return line_items, rationale

    # ─── Invoice Creation ─────────────────────────────────────────

    def create_invoice(self, lead_id: int = None, line_items: list = None,
                       rationale: str = "", client_name: str = "",
                       client_email: str = "", client_address: str = "",
                       campaign_id: int = None, notes: str = "") -> dict:
        """
        Create a new invoice with auto-incrementing invoice number.
        line_items: list of dicts with service_id, description, quantity, unit_price.
        """
        try:
            with self.db_manager.session_scope() as session:
                settings = session.query(Settings).first()
                if not settings:
                    settings = Settings(id=1)
                    session.add(settings)
                    session.flush()

                # Auto-fill from lead if available
                if lead_id and not client_name:
                    lead = session.query(Lead).get(lead_id)
                    if lead:
                        client_name = client_name or lead.business_name or ""
                        client_email = client_email or lead.email or ""

                # Generate invoice number
                prefix = settings.invoice_prefix or "INV-"
                next_num = settings.invoice_next_number or 1
                invoice_number = f"{prefix}{next_num:04d}"
                settings.invoice_next_number = next_num + 1

                # Calculate totals
                tax_rate = settings.company_tax_id and 0.21 or 0.0  # Default 21% if tax ID set
                subtotal = 0.0
                db_line_items = []

                for item in (line_items or []):
                    qty = float(item.get("quantity", 1))
                    price = float(item.get("unit_price", 0))
                    item_total = qty * price
                    subtotal += item_total

                    li = InvoiceLineItem(
                        service_id=item.get("service_id"),
                        description=item.get("description", ""),
                        quantity=qty,
                        unit_price=price,
                        total=item_total,
                    )
                    db_line_items.append(li)

                tax_amount = round(subtotal * tax_rate, 2)
                total = round(subtotal + tax_amount, 2)

                # Due date
                payment_days = settings.payment_terms_days or 30
                due_date = datetime.utcnow() + timedelta(days=payment_days)

                invoice = Invoice(
                    invoice_number=invoice_number,
                    lead_id=lead_id,
                    campaign_id=campaign_id,
                    client_name=client_name,
                    client_email=client_email,
                    client_address=client_address,
                    subtotal=round(subtotal, 2),
                    tax_rate=tax_rate,
                    tax_amount=tax_amount,
                    total=total,
                    currency=settings.invoice_currency or "EUR",
                    status="draft",
                    approval_status="pending",
                    due_date=due_date,
                    pricing_rationale=rationale,
                    notes=notes,
                )
                session.add(invoice)
                session.flush()

                # Attach line items
                for li in db_line_items:
                    li.invoice_id = invoice.id
                    session.add(li)

                invoice_id = invoice.id
                inv_number = invoice.invoice_number

                logger.info(f"Created invoice {inv_number} (total={total})")

                return {
                    "success": True,
                    "data": {
                        "id": invoice_id,
                        "invoice_number": inv_number,
                        "subtotal": round(subtotal, 2),
                        "tax_amount": tax_amount,
                        "total": total,
                        "status": "draft",
                        "due_date": due_date.isoformat(),
                    },
                }

        except Exception as e:
            logger.error(f"Invoice creation failed: {e}")
            return {"success": False, "error": str(e)}

    # ─── Invoice Queries ──────────────────────────────────────────

    def get_invoices(self, status: str = None) -> dict:
        """List invoices, optionally filtered by status."""
        try:
            with self.db_manager.session_scope() as session:
                q = session.query(Invoice)
                if status:
                    q = q.filter_by(status=status)
                invoices = q.order_by(Invoice.created_at.desc()).all()

                data = []
                for inv in invoices:
                    data.append({
                        "id": inv.id,
                        "invoice_number": inv.invoice_number,
                        "client_name": inv.client_name,
                        "client_email": inv.client_email,
                        "subtotal": inv.subtotal,
                        "tax_amount": inv.tax_amount,
                        "total": inv.total,
                        "currency": inv.currency,
                        "status": inv.status,
                        "approval_status": inv.approval_status,
                        "due_date": inv.due_date.isoformat() if inv.due_date else None,
                        "created_at": inv.created_at.isoformat() if inv.created_at else None,
                    })

                return {"success": True, "data": data}

        except Exception as e:
            logger.error(f"Get invoices failed: {e}")
            return {"success": False, "error": str(e)}

    def get_invoice(self, invoice_id: int) -> dict:
        """Get a single invoice with line items."""
        try:
            with self.db_manager.session_scope() as session:
                inv = session.query(Invoice).get(invoice_id)
                if not inv:
                    return {"success": False, "error": f"Invoice {invoice_id} not found"}

                items = []
                for li in inv.line_items:
                    items.append({
                        "id": li.id,
                        "description": li.description,
                        "quantity": li.quantity,
                        "unit_price": li.unit_price,
                        "total": li.total,
                    })

                return {
                    "success": True,
                    "data": {
                        "id": inv.id,
                        "invoice_number": inv.invoice_number,
                        "client_name": inv.client_name,
                        "client_email": inv.client_email,
                        "client_address": inv.client_address,
                        "subtotal": inv.subtotal,
                        "tax_rate": inv.tax_rate,
                        "tax_amount": inv.tax_amount,
                        "total": inv.total,
                        "currency": inv.currency,
                        "status": inv.status,
                        "approval_status": inv.approval_status,
                        "due_date": inv.due_date.isoformat() if inv.due_date else None,
                        "pricing_rationale": inv.pricing_rationale,
                        "notes": inv.notes,
                        "line_items": items,
                        "created_at": inv.created_at.isoformat() if inv.created_at else None,
                    },
                }

        except Exception as e:
            logger.error(f"Get invoice failed: {e}")
            return {"success": False, "error": str(e)}

    # ─── Status Management ────────────────────────────────────────

    def update_status(self, invoice_id: int, status: str) -> dict:
        """Update invoice status (draft/sent/paid/overdue/cancelled)."""
        if status not in INVOICE_STATUSES:
            return {"success": False, "error": f"Invalid status: {status}. Valid: {INVOICE_STATUSES}"}

        try:
            with self.db_manager.session_scope() as session:
                inv = session.query(Invoice).get(invoice_id)
                if not inv:
                    return {"success": False, "error": f"Invoice {invoice_id} not found"}

                old_status = inv.status
                inv.status = status

                # Log finance note
                note = FinanceNote(
                    invoice_id=invoice_id,
                    lead_id=inv.lead_id,
                    note_type="payment" if status == "paid" else "general",
                    content=f"Status changed: {old_status} → {status}",
                    created_by="system",
                )
                session.add(note)

                logger.info(f"Invoice {inv.invoice_number}: {old_status} → {status}")

                return {
                    "success": True,
                    "data": {
                        "id": inv.id,
                        "invoice_number": inv.invoice_number,
                        "old_status": old_status,
                        "new_status": status,
                    },
                }

        except Exception as e:
            logger.error(f"Status update failed: {e}")
            return {"success": False, "error": str(e)}

    # ─── PDF Generation ───────────────────────────────────────────

    def generate_invoice_pdf(self, invoice_id: int, output_path: str = None) -> dict:
        """
        Generate a professional PDF invoice using reportlab.
        Falls back to a simple text-based PDF if reportlab isn't available.
        """
        try:
            with self.db_manager.session_scope() as session:
                inv = session.query(Invoice).get(invoice_id)
                if not inv:
                    return {"success": False, "error": f"Invoice {invoice_id} not found"}

                settings = session.query(Settings).first()

                if not output_path:
                    import tempfile
                    output_path = tempfile.mktemp(
                        suffix=".pdf", prefix=f"{inv.invoice_number}_"
                    )

                items = [
                    {
                        "description": li.description,
                        "quantity": li.quantity,
                        "unit_price": li.unit_price,
                        "total": li.total,
                    }
                    for li in inv.line_items
                ]

                inv_data = {
                    "invoice_number": inv.invoice_number,
                    "client_name": inv.client_name,
                    "client_email": inv.client_email,
                    "client_address": inv.client_address,
                    "subtotal": inv.subtotal,
                    "tax_rate": inv.tax_rate,
                    "tax_amount": inv.tax_amount,
                    "total": inv.total,
                    "currency": inv.currency,
                    "due_date": inv.due_date.strftime("%Y-%m-%d") if inv.due_date else "N/A",
                    "notes": inv.notes,
                    "line_items": items,
                }

                company_data = {}
                if settings:
                    company_data = {
                        "name": settings.company_legal_name or "Aura AI",
                        "address": settings.company_address or "",
                        "tax_id": settings.company_tax_id or "",
                        "iban": settings.company_iban or "",
                        "swift": settings.company_swift or "",
                        "bank": settings.company_bank_name or "",
                        "email": settings.company_email or "",
                        "phone": settings.company_phone or "",
                        "website": settings.company_website or "",
                    }

                self._write_pdf(output_path, inv_data, company_data)

                # Save path to invoice
                inv.pdf_path = output_path

                logger.info(f"Generated PDF for {inv.invoice_number}: {output_path}")

                return {
                    "success": True,
                    "data": {
                        "invoice_number": inv.invoice_number,
                        "path": output_path,
                    },
                }

        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            return {"success": False, "error": str(e)}

    def _write_pdf(self, path: str, inv_data: dict, company_data: dict):
        """Write invoice PDF. Uses reportlab if available, else plaintext fallback."""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
            )
            from reportlab.lib.styles import getSampleStyleSheet

            doc = SimpleDocTemplate(path, pagesize=A4)
            styles = getSampleStyleSheet()
            elements = []

            # Header
            elements.append(Paragraph(
                f"<b>{company_data.get('name', 'Aura AI')}</b>",
                styles["Title"],
            ))
            if company_data.get("address"):
                elements.append(Paragraph(company_data["address"], styles["Normal"]))
            elements.append(Spacer(1, 10 * mm))

            # Invoice info
            elements.append(Paragraph(
                f"<b>Invoice {inv_data['invoice_number']}</b>", styles["Heading2"],
            ))
            elements.append(Paragraph(
                f"Client: {inv_data['client_name']}", styles["Normal"],
            ))
            if inv_data.get("client_address"):
                elements.append(Paragraph(inv_data["client_address"], styles["Normal"]))
            elements.append(Paragraph(
                f"Due: {inv_data['due_date']} | Currency: {inv_data['currency']}",
                styles["Normal"],
            ))
            elements.append(Spacer(1, 8 * mm))

            # Line items table
            table_data = [["Description", "Qty", "Unit Price", "Total"]]
            for item in inv_data["line_items"]:
                table_data.append([
                    item["description"],
                    str(item["quantity"]),
                    f"{inv_data['currency']} {item['unit_price']:.2f}",
                    f"{inv_data['currency']} {item['total']:.2f}",
                ])

            table_data.append(["", "", "Subtotal:", f"{inv_data['currency']} {inv_data['subtotal']:.2f}"])
            tax_pct = int(inv_data['tax_rate'] * 100) if inv_data['tax_rate'] else 0
            table_data.append(["", "", f"Tax ({tax_pct}%):", f"{inv_data['currency']} {inv_data['tax_amount']:.2f}"])
            table_data.append(["", "", "TOTAL:", f"{inv_data['currency']} {inv_data['total']:.2f}"])

            table = Table(table_data, colWidths=[200, 50, 100, 100])
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -4), 0.5, colors.grey),
                ("FONTNAME", (2, -1), (3, -1), "Helvetica-Bold"),
                ("LINEABOVE", (2, -3), (-1, -3), 0.5, colors.grey),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 10 * mm))

            # Payment details
            if company_data.get("iban"):
                elements.append(Paragraph("<b>Payment Details</b>", styles["Heading3"]))
                elements.append(Paragraph(
                    f"IBAN: {company_data['iban']}", styles["Normal"],
                ))
                if company_data.get("swift"):
                    elements.append(Paragraph(
                        f"SWIFT: {company_data['swift']}", styles["Normal"],
                    ))
                if company_data.get("bank"):
                    elements.append(Paragraph(
                        f"Bank: {company_data['bank']}", styles["Normal"],
                    ))

            # Notes
            if inv_data.get("notes"):
                elements.append(Spacer(1, 5 * mm))
                elements.append(Paragraph(f"Notes: {inv_data['notes']}", styles["Normal"]))

            doc.build(elements)

        except ImportError:
            # Fallback: simple text file with .pdf extension
            with open(path, "w") as f:
                f.write(f"INVOICE {inv_data['invoice_number']}\n")
                f.write(f"{'=' * 50}\n")
                f.write(f"From: {company_data.get('name', 'Aura AI')}\n")
                f.write(f"To: {inv_data['client_name']}\n")
                f.write(f"Due: {inv_data['due_date']}\n\n")
                for item in inv_data["line_items"]:
                    f.write(
                        f"  {item['description']}: "
                        f"{item['quantity']} x {inv_data['currency']} {item['unit_price']:.2f} = "
                        f"{inv_data['currency']} {item['total']:.2f}\n"
                    )
                f.write(f"\nSubtotal: {inv_data['currency']} {inv_data['subtotal']:.2f}\n")
                f.write(f"Tax: {inv_data['currency']} {inv_data['tax_amount']:.2f}\n")
                f.write(f"TOTAL: {inv_data['currency']} {inv_data['total']:.2f}\n")

    # ─── Revenue Summary ──────────────────────────────────────────

    def get_revenue_summary(self) -> dict:
        """Aggregate revenue stats across all invoices."""
        try:
            with self.db_manager.session_scope() as session:
                invoices = session.query(Invoice).all()

                total_revenue = sum(inv.total for inv in invoices if inv.status == "paid")
                total_pending = sum(inv.total for inv in invoices if inv.status in ("sent", "draft"))
                total_overdue = sum(inv.total for inv in invoices if inv.status == "overdue")
                invoice_count = len(invoices)
                paid_count = sum(1 for inv in invoices if inv.status == "paid")

                return {
                    "success": True,
                    "data": {
                        "total_revenue": round(total_revenue, 2),
                        "total_pending": round(total_pending, 2),
                        "total_overdue": round(total_overdue, 2),
                        "invoice_count": invoice_count,
                        "paid_count": paid_count,
                        "avg_invoice": round(total_revenue / paid_count, 2) if paid_count else 0,
                    },
                }

        except Exception as e:
            logger.error(f"Revenue summary failed: {e}")
            return {"success": False, "error": str(e)}
