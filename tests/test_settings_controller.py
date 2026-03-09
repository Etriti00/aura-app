"""
Tests for SettingsController — business fields, get/save, and regression checks.
"""

import pytest
from unittest.mock import MagicMock
from PySide6.QtCore import QObject

from controllers.settings_controller import SettingsController
from database.schema import Settings


# ─── Fixtures ─────────────────────────────────────────────────────────


class FakeVault:
    """Minimal key vault that does not encrypt."""

    def encrypt(self, value):
        return f"enc:{value}"

    def decrypt(self, value):
        return value.replace("enc:", "")

    def mask(self, value):
        if len(value) <= 4:
            return "****"
        return value[:2] + "***" + value[-2:]


@pytest.fixture
def vault():
    return FakeVault()


@pytest.fixture
def ctrl(db, qapp, vault):
    """SettingsController backed by in-memory DB."""
    # Seed a Settings row
    with db.session_scope() as session:
        session.add(Settings())
    return SettingsController(db, vault)


# ─── get_settings: business fields present ────────────────────────────


class TestGetSettingsBusinessFields:

    def test_business_keys_present(self, ctrl):
        """All 16 business/invoice keys should be in the returned dict."""
        settings = ctrl.get_settings()
        expected_keys = [
            "company_legal_name", "company_address", "company_tax_id",
            "company_email", "company_phone", "company_website",
            "company_logo_path", "company_iban", "company_swift",
            "company_bank_name", "invoice_prefix", "invoice_next_number",
            "invoice_currency", "payment_terms_days", "invoice_notes",
            "telegram_owner_chat_id",
        ]
        for key in expected_keys:
            assert key in settings, f"Missing key: {key}"

    def test_business_defaults(self, ctrl):
        """Business fields should return sensible defaults on a fresh DB."""
        settings = ctrl.get_settings()
        assert settings["company_legal_name"] == ""
        assert settings["company_address"] == ""
        assert settings["invoice_prefix"] == "INV-"
        assert settings["invoice_next_number"] == 1
        assert settings["invoice_currency"] == "EUR"
        assert settings["payment_terms_days"] == 30
        assert settings["invoice_notes"] == ""

    def test_existing_keys_still_present(self, ctrl):
        """Regression: existing settings keys must still be returned."""
        settings = ctrl.get_settings()
        for key in ["sender_name", "sender_email", "theme", "tier2_model",
                     "has_gemini", "autonomy_level", "reflection_enabled"]:
            assert key in settings, f"Missing existing key: {key}"


# ─── save_business_settings ───────────────────────────────────────────


class TestSaveBusinessSettings:

    def test_save_company_info(self, ctrl, db):
        """Save company info and verify round-trip."""
        ctrl.save_business_settings({
            "company_legal_name": "Acme Corp GmbH",
            "company_tax_id": "DE123456789",
            "company_email": "billing@acme.com",
            "company_phone": "+49 30 12345678",
        })
        settings = ctrl.get_settings()
        assert settings["company_legal_name"] == "Acme Corp GmbH"
        assert settings["company_tax_id"] == "DE123456789"
        assert settings["company_email"] == "billing@acme.com"
        assert settings["company_phone"] == "+49 30 12345678"

    def test_save_banking(self, ctrl, db):
        """Save banking details and verify round-trip."""
        ctrl.save_business_settings({
            "company_bank_name": "Deutsche Bank",
            "company_swift": "DEUTDEDB",
            "company_iban": "DE89370400440532013000",
        })
        settings = ctrl.get_settings()
        assert settings["company_bank_name"] == "Deutsche Bank"
        assert settings["company_swift"] == "DEUTDEDB"
        assert settings["company_iban"] == "DE89370400440532013000"

    def test_save_invoice_config(self, ctrl, db):
        """Save invoice configuration and verify round-trip."""
        ctrl.save_business_settings({
            "invoice_prefix": "AURA-",
            "invoice_next_number": 42,
            "invoice_currency": "USD",
            "payment_terms_days": 14,
            "invoice_notes": "Thank you for your business.",
        })
        settings = ctrl.get_settings()
        assert settings["invoice_prefix"] == "AURA-"
        assert settings["invoice_next_number"] == 42
        assert settings["invoice_currency"] == "USD"
        assert settings["payment_terms_days"] == 14
        assert settings["invoice_notes"] == "Thank you for your business."

    def test_unknown_fields_ignored(self, ctrl, db):
        """Fields not on the Settings model should be silently ignored."""
        ctrl.save_business_settings({
            "company_legal_name": "Test Corp",
            "nonexistent_field": "should be ignored",
        })
        settings = ctrl.get_settings()
        assert settings["company_legal_name"] == "Test Corp"
        assert "nonexistent_field" not in settings

    def test_emits_settings_saved(self, ctrl, db):
        """save_business_settings should emit settings_saved signal."""
        saved = []
        ctrl.settings_saved.connect(lambda: saved.append(True))
        ctrl.save_business_settings({"company_legal_name": "Test"})
        assert len(saved) == 1

    def test_error_signal_on_failure(self, ctrl, db):
        """Simulate error and verify settings_error is emitted."""
        errors = []
        ctrl.settings_error.connect(lambda msg: errors.append(msg))
        # Force an error by making session_scope raise
        original = ctrl.db_manager.session_scope
        def bad_scope():
            raise RuntimeError("DB exploded")
        ctrl.db_manager.session_scope = bad_scope
        ctrl.save_business_settings({"company_legal_name": "Boom"})
        assert len(errors) == 1
        assert "DB exploded" in errors[0]
        ctrl.db_manager.session_scope = original


# ─── Existing methods regression ──────────────────────────────────────


class TestExistingMethods:

    def test_save_sender_info(self, ctrl, db):
        """Regression: save_sender_info still works."""
        ctrl.save_sender_info("Alice", "alice@co.com", "AliceCo")
        settings = ctrl.get_settings()
        assert settings["sender_name"] == "Alice"
        assert settings["sender_email"] == "alice@co.com"
        assert settings["sender_company"] == "AliceCo"

    def test_save_toggles(self, ctrl, db):
        """Regression: save_toggles still works."""
        ctrl.save_toggles({"ab_test_enabled": True, "enrichment_enabled": False})
        settings = ctrl.get_settings()
        assert settings["ab_test_enabled"] is True
        assert settings["enrichment_enabled"] is False

    def test_set_theme(self, ctrl, db):
        """Regression: set_theme still works."""
        changed = []
        ctrl.theme_changed.connect(lambda t: changed.append(t))
        ctrl.set_theme("dark")
        assert changed == ["dark"]
        settings = ctrl.get_settings()
        assert settings["theme"] == "dark"

    def test_save_models(self, ctrl, db):
        """Regression: save_models still works."""
        ctrl.save_models("gemini/gemini-2.0-flash", "anthropic/claude-sonnet-4-6")
        settings = ctrl.get_settings()
        assert settings["tier2_model"] == "gemini/gemini-2.0-flash"
        assert settings["tier3_model"] == "anthropic/claude-sonnet-4-6"
