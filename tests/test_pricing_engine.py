"""Tests for the Pricing Engine and Invoice Approval Engine."""

import os
import tempfile

import pytest

from database.schema import (
    Campaign, Lead, Service, Invoice, InvoiceLineItem, FinanceNote, Settings,
)


# ═══════════════════════════════════════════════════════════════════
# Pricing Engine Tests
# ═══════════════════════════════════════════════════════════════════

class TestEvaluatePricing:
    """Test rule-based pricing evaluation."""

    def test_evaluate_with_services(self, db):
        from core.pricing_engine import PricingEngine

        with db.session_scope() as session:
            camp = Campaign(name="Price Test")
            session.add(camp)
            session.flush()
            lead = Lead(
                campaign_id=camp.id, business_name="Acme Corp",
                city="Austin", email="acme@test.com",
                website_score=80,
            )
            session.add(lead)
            session.flush()
            lead_id = lead.id

            session.add(Service(
                name="Web Design", base_price=500, max_price=2000,
                unit="project", category="development",
            ))
            session.add(Service(
                name="SEO Audit", base_price=200, max_price=800,
                unit="project", category="marketing",
            ))

        engine = PricingEngine(db)
        result = engine.evaluate_pricing(lead_id)
        assert result["success"]
        assert len(result["data"]["line_items"]) == 2
        assert result["data"]["subtotal"] > 0
        assert "rationale" in result["data"]

    def test_evaluate_no_services(self, db):
        from core.pricing_engine import PricingEngine

        with db.session_scope() as session:
            camp = Campaign(name="Empty")
            session.add(camp)
            session.flush()
            lead = Lead(campaign_id=camp.id, business_name="X")
            session.add(lead)
            session.flush()
            lead_id = lead.id

        engine = PricingEngine(db)
        result = engine.evaluate_pricing(lead_id)
        assert result["success"]
        assert result["data"]["line_items"] == []

    def test_evaluate_nonexistent_lead(self, db):
        from core.pricing_engine import PricingEngine

        engine = PricingEngine(db)
        result = engine.evaluate_pricing(9999)
        assert not result["success"]
        assert "not found" in result["error"]


class TestRuleBasedPricing:
    """Test rule-based pricing logic."""

    def test_high_icp_increases_price(self, db):
        from core.pricing_engine import PricingEngine

        engine = PricingEngine(db)
        catalog = [
            {"id": 1, "name": "Svc", "description": "", "base_price": 100,
             "max_price": 500, "unit": "project", "category": "dev"},
        ]
        items, _ = engine._rule_based_evaluate({"icp_fit_score": 90}, catalog)
        assert items[0]["unit_price"] == 120  # 100 * 1.2

    def test_low_icp_keeps_base(self, db):
        from core.pricing_engine import PricingEngine

        engine = PricingEngine(db)
        catalog = [
            {"id": 1, "name": "Svc", "description": "", "base_price": 100,
             "max_price": 500, "unit": "project", "category": "dev"},
        ]
        items, _ = engine._rule_based_evaluate({"icp_fit_score": 50}, catalog)
        assert items[0]["unit_price"] == 100

    def test_max_three_services(self, db):
        from core.pricing_engine import PricingEngine

        engine = PricingEngine(db)
        catalog = [
            {"id": i, "name": f"Svc{i}", "description": "", "base_price": 100,
             "max_price": 500, "unit": "project", "category": "dev"}
            for i in range(5)
        ]
        items, _ = engine._rule_based_evaluate({}, catalog)
        assert len(items) == 3


# ═══════════════════════════════════════════════════════════════════
# Invoice Creation Tests
# ═══════════════════════════════════════════════════════════════════

class TestCreateInvoice:
    def test_create_basic_invoice(self, db):
        from core.pricing_engine import PricingEngine

        engine = PricingEngine(db)
        result = engine.create_invoice(
            client_name="Test Client",
            client_email="test@client.com",
            line_items=[
                {"description": "Service A", "quantity": 2, "unit_price": 100},
                {"description": "Service B", "quantity": 1, "unit_price": 50},
            ],
        )

        assert result["success"]
        assert result["data"]["invoice_number"].startswith("INV-")
        assert result["data"]["subtotal"] == 250.0
        assert result["data"]["status"] == "draft"

    def test_auto_increment_number(self, db):
        from core.pricing_engine import PricingEngine

        engine = PricingEngine(db)
        r1 = engine.create_invoice(
            client_name="A",
            line_items=[{"description": "X", "quantity": 1, "unit_price": 10}],
        )
        r2 = engine.create_invoice(
            client_name="B",
            line_items=[{"description": "Y", "quantity": 1, "unit_price": 20}],
        )

        assert r1["data"]["invoice_number"] == "INV-0001"
        assert r2["data"]["invoice_number"] == "INV-0002"

    def test_create_with_lead_auto_fills(self, db):
        from core.pricing_engine import PricingEngine

        with db.session_scope() as session:
            camp = Campaign(name="Test")
            session.add(camp)
            session.flush()
            lead = Lead(
                campaign_id=camp.id, business_name="Auto Co",
                email="auto@co.com",
            )
            session.add(lead)
            session.flush()
            lead_id = lead.id

        engine = PricingEngine(db)
        result = engine.create_invoice(
            lead_id=lead_id,
            line_items=[{"description": "Svc", "quantity": 1, "unit_price": 100}],
        )

        assert result["success"]
        # Verify auto-filled from lead
        inv = engine.get_invoice(result["data"]["id"])
        assert inv["data"]["client_name"] == "Auto Co"
        assert inv["data"]["client_email"] == "auto@co.com"

    def test_tax_calculation_with_tax_id(self, db):
        from core.pricing_engine import PricingEngine

        # Set a tax ID so tax rate is applied
        with db.session_scope() as session:
            settings = session.query(Settings).first()
            if not settings:
                settings = Settings(id=1)
                session.add(settings)
            settings.company_tax_id = "NL123456789B01"

        engine = PricingEngine(db)
        result = engine.create_invoice(
            client_name="Taxed Client",
            line_items=[{"description": "Svc", "quantity": 1, "unit_price": 1000}],
        )

        assert result["success"]
        assert result["data"]["tax_amount"] == 210.0  # 21% of 1000
        assert result["data"]["total"] == 1210.0

    def test_empty_line_items(self, db):
        from core.pricing_engine import PricingEngine

        engine = PricingEngine(db)
        result = engine.create_invoice(client_name="Empty", line_items=[])
        assert result["success"]
        assert result["data"]["subtotal"] == 0.0
        assert result["data"]["total"] == 0.0


# ═══════════════════════════════════════════════════════════════════
# Invoice Queries
# ═══════════════════════════════════════════════════════════════════

class TestInvoiceQueries:
    def test_get_invoices_all(self, db):
        from core.pricing_engine import PricingEngine

        engine = PricingEngine(db)
        engine.create_invoice(client_name="A", line_items=[])
        engine.create_invoice(client_name="B", line_items=[])

        result = engine.get_invoices()
        assert result["success"]
        assert len(result["data"]) == 2

    def test_get_invoices_by_status(self, db):
        from core.pricing_engine import PricingEngine

        engine = PricingEngine(db)
        engine.create_invoice(client_name="Draft", line_items=[])

        result = engine.get_invoices(status="draft")
        assert len(result["data"]) == 1
        result2 = engine.get_invoices(status="paid")
        assert len(result2["data"]) == 0

    def test_get_invoice_detail(self, db):
        from core.pricing_engine import PricingEngine

        engine = PricingEngine(db)
        created = engine.create_invoice(
            client_name="Detail",
            line_items=[
                {"description": "A", "quantity": 1, "unit_price": 100},
                {"description": "B", "quantity": 2, "unit_price": 50},
            ],
        )
        result = engine.get_invoice(created["data"]["id"])
        assert result["success"]
        assert result["data"]["client_name"] == "Detail"
        assert len(result["data"]["line_items"]) == 2
        assert result["data"]["subtotal"] == 200.0

    def test_get_nonexistent_invoice(self, db):
        from core.pricing_engine import PricingEngine

        engine = PricingEngine(db)
        result = engine.get_invoice(9999)
        assert not result["success"]
        assert "not found" in result["error"]


# ═══════════════════════════════════════════════════════════════════
# Status Management
# ═══════════════════════════════════════════════════════════════════

class TestStatusManagement:
    def test_update_status(self, db):
        from core.pricing_engine import PricingEngine

        engine = PricingEngine(db)
        created = engine.create_invoice(client_name="S", line_items=[])
        inv_id = created["data"]["id"]

        result = engine.update_status(inv_id, "sent")
        assert result["success"]
        assert result["data"]["old_status"] == "draft"
        assert result["data"]["new_status"] == "sent"

    def test_invalid_status(self, db):
        from core.pricing_engine import PricingEngine

        engine = PricingEngine(db)
        created = engine.create_invoice(client_name="X", line_items=[])
        result = engine.update_status(created["data"]["id"], "invalid")
        assert not result["success"]
        assert "Invalid status" in result["error"]

    def test_status_creates_finance_note(self, db):
        from core.pricing_engine import PricingEngine

        engine = PricingEngine(db)
        created = engine.create_invoice(client_name="N", line_items=[])
        engine.update_status(created["data"]["id"], "paid")

        with db.session_scope() as session:
            notes = session.query(FinanceNote).filter_by(
                invoice_id=created["data"]["id"]
            ).all()
            assert any("paid" in n.content for n in notes)

    def test_update_nonexistent(self, db):
        from core.pricing_engine import PricingEngine

        engine = PricingEngine(db)
        result = engine.update_status(9999, "paid")
        assert not result["success"]


# ═══════════════════════════════════════════════════════════════════
# PDF Generation
# ═══════════════════════════════════════════════════════════════════

class TestPDFGeneration:
    def test_generate_pdf(self, db):
        """Test PDF generation (reportlab or text fallback)."""
        from core.pricing_engine import PricingEngine

        engine = PricingEngine(db)
        created = engine.create_invoice(
            client_name="PDF Client",
            line_items=[{"description": "Svc", "quantity": 1, "unit_price": 100}],
        )
        inv_id = created["data"]["id"]

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name

        try:
            result = engine.generate_invoice_pdf(inv_id, path)
            assert result["success"]
            assert os.path.exists(path)
            assert result["data"]["path"] == path
            assert os.path.getsize(path) > 0
        finally:
            os.unlink(path)

    def test_generate_pdf_nonexistent(self, db):
        from core.pricing_engine import PricingEngine

        engine = PricingEngine(db)
        result = engine.generate_invoice_pdf(9999)
        assert not result["success"]
        assert "not found" in result["error"]


# ═══════════════════════════════════════════════════════════════════
# Revenue Summary
# ═══════════════════════════════════════════════════════════════════

class TestRevenueSummary:
    def test_empty_revenue(self, db):
        from core.pricing_engine import PricingEngine

        engine = PricingEngine(db)
        result = engine.get_revenue_summary()
        assert result["success"]
        assert result["data"]["total_revenue"] == 0
        assert result["data"]["invoice_count"] == 0

    def test_revenue_with_invoices(self, db):
        from core.pricing_engine import PricingEngine

        engine = PricingEngine(db)
        inv1 = engine.create_invoice(
            client_name="A",
            line_items=[{"description": "X", "quantity": 1, "unit_price": 1000}],
        )
        inv2 = engine.create_invoice(
            client_name="B",
            line_items=[{"description": "Y", "quantity": 1, "unit_price": 500}],
        )
        engine.update_status(inv1["data"]["id"], "paid")

        result = engine.get_revenue_summary()
        assert result["success"]
        assert result["data"]["paid_count"] == 1
        assert result["data"]["total_revenue"] == 1000.0
        assert result["data"]["total_pending"] == 500.0


# ═══════════════════════════════════════════════════════════════════
# Invoice Approval Engine Tests
# ═══════════════════════════════════════════════════════════════════

class TestApprovalFlow:
    def test_start_approval(self, db):
        from core.pricing_engine import PricingEngine
        from core.invoice_approval_engine import InvoiceApprovalEngine

        pe = PricingEngine(db)
        iae = InvoiceApprovalEngine(db, pricing_engine=pe)

        created = pe.create_invoice(
            client_name="Approval Test",
            line_items=[{"description": "Svc", "quantity": 1, "unit_price": 500}],
        )
        result = iae.start_approval_flow(created["data"]["id"])
        assert result["success"]
        assert result["data"]["approval_status"] == "pending"

    def test_start_already_approved(self, db):
        from core.pricing_engine import PricingEngine
        from core.invoice_approval_engine import InvoiceApprovalEngine

        pe = PricingEngine(db)
        iae = InvoiceApprovalEngine(db, pricing_engine=pe)

        created = pe.create_invoice(client_name="X", line_items=[])
        iae.approve(created["data"]["id"])

        result = iae.start_approval_flow(created["data"]["id"])
        assert not result["success"]
        assert "already approved" in result["error"].lower()

    def test_start_nonexistent(self, db):
        from core.invoice_approval_engine import InvoiceApprovalEngine

        iae = InvoiceApprovalEngine(db)
        result = iae.start_approval_flow(9999)
        assert not result["success"]


class TestApproveInvoice:
    def test_approve_success(self, db):
        from core.pricing_engine import PricingEngine
        from core.invoice_approval_engine import InvoiceApprovalEngine

        pe = PricingEngine(db)
        iae = InvoiceApprovalEngine(db, pricing_engine=pe)

        created = pe.create_invoice(
            client_name="Approve Me",
            line_items=[{"description": "Svc", "quantity": 1, "unit_price": 100}],
        )
        result = iae.approve(created["data"]["id"], approved_by="admin")
        assert result["success"]
        assert result["data"]["approval_status"] == "approved"

        # Verify in DB
        inv = pe.get_invoice(created["data"]["id"])
        assert inv["data"]["approval_status"] == "approved"

    def test_approve_already_approved(self, db):
        from core.pricing_engine import PricingEngine
        from core.invoice_approval_engine import InvoiceApprovalEngine

        pe = PricingEngine(db)
        iae = InvoiceApprovalEngine(db, pricing_engine=pe)

        created = pe.create_invoice(client_name="X", line_items=[])
        iae.approve(created["data"]["id"])
        result = iae.approve(created["data"]["id"])
        assert not result["success"]

    def test_approve_creates_finance_note(self, db):
        from core.pricing_engine import PricingEngine
        from core.invoice_approval_engine import InvoiceApprovalEngine

        pe = PricingEngine(db)
        iae = InvoiceApprovalEngine(db, pricing_engine=pe)

        created = pe.create_invoice(client_name="Note Test", line_items=[])
        iae.approve(created["data"]["id"], approved_by="admin")

        with db.session_scope() as session:
            notes = session.query(FinanceNote).filter_by(
                invoice_id=created["data"]["id"],
            ).all()
            assert any("approved" in n.content.lower() for n in notes)


class TestRejectInvoice:
    def test_reject_success(self, db):
        from core.pricing_engine import PricingEngine
        from core.invoice_approval_engine import InvoiceApprovalEngine

        pe = PricingEngine(db)
        iae = InvoiceApprovalEngine(db, pricing_engine=pe)

        created = pe.create_invoice(client_name="Reject Me", line_items=[])
        result = iae.reject(created["data"]["id"], reason="Too expensive")
        assert result["success"]
        assert result["data"]["approval_status"] == "rejected"
        assert result["data"]["reason"] == "Too expensive"

    def test_reject_already_rejected(self, db):
        from core.pricing_engine import PricingEngine
        from core.invoice_approval_engine import InvoiceApprovalEngine

        pe = PricingEngine(db)
        iae = InvoiceApprovalEngine(db, pricing_engine=pe)

        created = pe.create_invoice(client_name="X", line_items=[])
        iae.reject(created["data"]["id"])
        result = iae.reject(created["data"]["id"])
        assert not result["success"]


class TestEscalation:
    def test_escalate_pending(self, db):
        from core.pricing_engine import PricingEngine
        from core.invoice_approval_engine import InvoiceApprovalEngine

        pe = PricingEngine(db)
        iae = InvoiceApprovalEngine(db)

        created = pe.create_invoice(client_name="Escalate", line_items=[])
        result = iae.escalate(created["data"]["id"])
        assert result["success"]
        assert result["data"]["escalated"] is True

    def test_escalate_already_approved(self, db):
        from core.pricing_engine import PricingEngine
        from core.invoice_approval_engine import InvoiceApprovalEngine

        pe = PricingEngine(db)
        iae = InvoiceApprovalEngine(db, pricing_engine=pe)

        created = pe.create_invoice(client_name="X", line_items=[])
        iae.approve(created["data"]["id"])
        result = iae.escalate(created["data"]["id"])
        assert not result["success"]

    def test_escalate_nonexistent(self, db):
        from core.invoice_approval_engine import InvoiceApprovalEngine

        iae = InvoiceApprovalEngine(db)
        result = iae.escalate(9999)
        assert not result["success"]


class TestPendingApprovals:
    def test_get_pending(self, db):
        from core.pricing_engine import PricingEngine
        from core.invoice_approval_engine import InvoiceApprovalEngine

        pe = PricingEngine(db)
        iae = InvoiceApprovalEngine(db)

        pe.create_invoice(client_name="Pending 1", line_items=[])
        pe.create_invoice(client_name="Pending 2", line_items=[])

        result = iae.get_pending_approvals()
        assert result["success"]
        assert result["count"] == 2

    def test_approved_not_in_pending(self, db):
        from core.pricing_engine import PricingEngine
        from core.invoice_approval_engine import InvoiceApprovalEngine

        pe = PricingEngine(db)
        iae = InvoiceApprovalEngine(db, pricing_engine=pe)

        c1 = pe.create_invoice(client_name="A", line_items=[])
        pe.create_invoice(client_name="B", line_items=[])
        iae.approve(c1["data"]["id"])

        result = iae.get_pending_approvals()
        assert result["count"] == 1
        assert result["data"][0]["client_name"] == "B"
