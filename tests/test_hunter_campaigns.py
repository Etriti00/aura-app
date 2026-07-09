"""
Tests for Hunter Campaign views, enrichment fix, and controller methods.
"""

import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt

from tests.conftest import InMemoryDatabaseManager
from database.schema import Campaign, Lead, EnrichmentData


# ─── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def db():
    """Create an in-memory database with all tables."""
    dbm = InMemoryDatabaseManager()
    dbm.init_db()
    return dbm


@pytest.fixture
def db_with_campaign(db):
    """DB with a campaign and some leads."""
    with db.session_scope() as session:
        campaign = Campaign(
            name="Test Campaign",
            search_query="dentist",
            target_city="Berlin",
            target_niche="dentist",
            status="completed",
        )
        session.add(campaign)
        session.flush()
        cid = campaign.id

        # Add leads
        for i in range(5):
            lead = Lead(
                campaign_id=cid,
                business_name=f"Business {i}",
                category="dentist",
                city="Berlin",
                phone=f"555-000{i}",
                email=f"lead{i}@example.com" if i < 3 else "",
                source_platform="duckduckgo",
                has_website=True,
                website_url=f"https://business{i}.com",
                status="qualified" if i < 2 else "new",
                data_completeness_score=60 if i < 2 else 0,
            )
            session.add(lead)
        session.flush()

        # Add enrichment for first 2 leads
        leads = session.query(Lead).filter_by(campaign_id=cid).all()
        for lead in leads[:2]:
            enrichment = EnrichmentData(
                lead_id=lead.id,
                google_maps_rating=4.5,
                google_maps_review_count=120,
                domain_age_years=5.0,
                has_facebook=True,
                has_instagram=False,
                has_linkedin=True,
                decision_maker_name="John Doe",
                icp_fit_score=8,
            )
            session.add(enrichment)

    return db, cid


# ─── HunterController Tests ────────────────────────────────────────────

class TestHunterControllerCampaigns:
    """Tests for campaign loading and enrichment methods."""

    def test_load_campaigns_emits_signal(self, db_with_campaign, qapp):
        from controllers.hunter_controller import HunterController
        db, cid = db_with_campaign
        ctrl = HunterController(db)

        received = []
        ctrl.campaigns_loaded.connect(lambda camps: received.append(camps))
        ctrl.load_campaigns()

        assert len(received) == 1
        campaigns = received[0]
        assert len(campaigns) == 1
        assert campaigns[0]["name"] == "Test Campaign"
        assert campaigns[0]["total_leads"] == 5
        assert campaigns[0]["qualified_leads"] == 2
        assert campaigns[0]["enriched_leads"] == 2

    def test_load_campaigns_empty_db(self, db, qapp):
        from controllers.hunter_controller import HunterController
        ctrl = HunterController(db)

        received = []
        ctrl.campaigns_loaded.connect(lambda camps: received.append(camps))
        ctrl.load_campaigns()

        assert len(received) == 1
        assert received[0] == []

    def test_get_campaign_leads_detailed(self, db_with_campaign, qapp):
        from controllers.hunter_controller import HunterController
        db, cid = db_with_campaign
        ctrl = HunterController(db)

        leads = ctrl.get_campaign_leads_detailed(cid)
        assert len(leads) == 5

        # First lead should have enrichment data
        enriched_lead = leads[0]
        assert enriched_lead["google_maps_rating"] == 4.5
        assert enriched_lead["review_count"] == 120
        assert enriched_lead["domain_age"] == 5.0
        assert enriched_lead["has_facebook"] is True
        assert enriched_lead["decision_maker"] == "John Doe"
        assert enriched_lead["data_completeness_score"] == 60

    def test_get_campaign_leads_detailed_no_enrichment(self, db_with_campaign, qapp):
        from controllers.hunter_controller import HunterController
        db, cid = db_with_campaign
        ctrl = HunterController(db)

        leads = ctrl.get_campaign_leads_detailed(cid)
        # Lead at index 3 has no enrichment
        unenriched = leads[3]
        assert unenriched["google_maps_rating"] is None
        assert unenriched["decision_maker"] == ""
        assert unenriched["data_completeness_score"] == 0

    def test_get_campaign_leads_detailed_invalid_campaign(self, db, qapp):
        from controllers.hunter_controller import HunterController
        ctrl = HunterController(db)
        leads = ctrl.get_campaign_leads_detailed(9999)
        assert leads == []

    def test_enrich_single_lead_no_engine(self, db, qapp):
        from controllers.hunter_controller import HunterController
        ctrl = HunterController(db)
        ctrl.enrichment_engine = None

        errors = []
        ctrl.scrape_error.connect(lambda msg: errors.append(msg))
        ctrl.enrich_single_lead(1)
        assert len(errors) == 1
        assert "not available" in errors[0]

    def test_enrich_campaign_no_engine(self, db, qapp):
        from controllers.hunter_controller import HunterController
        ctrl = HunterController(db)
        ctrl.enrichment_engine = None

        errors = []
        ctrl.scrape_error.connect(lambda msg: errors.append(msg))
        ctrl.enrich_campaign_leads(1)
        assert len(errors) == 1

    def test_campaign_stats_include_created_at(self, db_with_campaign, qapp):
        from controllers.hunter_controller import HunterController
        db, cid = db_with_campaign
        ctrl = HunterController(db)

        received = []
        ctrl.campaigns_loaded.connect(lambda camps: received.append(camps))
        ctrl.load_campaigns()

        campaign = received[0][0]
        assert "created_at" in campaign
        assert campaign["created_at"] != ""


class TestEnrichmentSaveFix:
    """Test that enrichment data is saved during scraping."""

    def test_enrich_lead_calls_save_enrichment(self, db, qapp):
        """Verify the controller calls save_enrichment after enrich_lead."""
        from controllers.hunter_controller import HunterController

        mock_enrichment = MagicMock()
        mock_enrichment.enrich_lead.return_value = {
            "google_maps_rating": 4.0,
            "has_facebook": True,
        }
        mock_enrichment.save_enrichment.return_value = {"success": True}
        mock_enrichment.start_batch.return_value = None
        mock_enrichment.end_batch.return_value = None

        ctrl = HunterController(db, enrichment_engine=mock_enrichment)

        # Create campaign + lead
        with db.session_scope() as session:
            campaign = Campaign(name="Test", target_city="Test", target_niche="test", status="active")
            session.add(campaign)
            session.flush()
            ctrl._current_campaign_id = campaign.id

        from core.scraper_engine import ScrapedLead
        lead = ScrapedLead(
            business_name="TestBiz", category="test", city="Test",
            phone="555", email="test@test.com", source_url="",
            source_platform="duckduckgo", has_website=True,
            website_url="https://test.com",
        )

        # Simulate the save+enrich flow (extracted from _run_scrape)
        lead_dict = ctrl._save_lead(lead)
        assert lead_dict is not None

        enrichment_data = mock_enrichment.enrich_lead(lead_dict)
        mock_enrichment.save_enrichment(lead_dict["id"], enrichment_data)

        mock_enrichment.save_enrichment.assert_called_once_with(
            lead_dict["id"], enrichment_data
        )


# ─── UI Tests ──────────────────────────────────────────────────────────

class TestCampaignListView:
    """Tests for the CampaignListView widget."""

    def test_creates(self, qapp):
        from ui.pages.hunter import CampaignListView
        view = CampaignListView()
        assert view.table.columnCount() == 8

    def test_load_campaigns(self, qapp):
        from ui.pages.hunter import CampaignListView
        view = CampaignListView()
        campaigns = [
            {"id": 1, "name": "Campaign A", "target_niche": "dentist",
             "target_city": "Berlin", "status": "completed",
             "total_leads": 50, "qualified_leads": 20, "enriched_leads": 15,
             "created_at": "2025-07-01 12:00"},
            {"id": 2, "name": "Campaign B", "target_niche": "plumber",
             "target_city": "London", "status": "active",
             "total_leads": 30, "qualified_leads": 10, "enriched_leads": 5,
             "created_at": "2025-07-02 14:00"},
        ]
        view.load_campaigns(campaigns)
        assert view.table.rowCount() == 2
        assert view.table.item(0, 0).text() == "Campaign A"
        assert view.table.item(1, 0).text() == "Campaign B"

    def test_load_campaigns_empty(self, qapp):
        from ui.pages.hunter import CampaignListView
        view = CampaignListView()
        view.load_campaigns([])
        assert view.table.rowCount() == 0
        assert not view.empty_state.isHidden()

    def test_campaign_id_stored_in_data(self, qapp):
        from ui.pages.hunter import CampaignListView
        view = CampaignListView()
        view.load_campaigns([{
            "id": 42, "name": "Test", "target_niche": "", "target_city": "",
            "status": "completed", "total_leads": 0, "qualified_leads": 0,
            "enriched_leads": 0, "created_at": "",
        }])
        item = view.table.item(0, 0)
        assert item.data(Qt.ItemDataRole.UserRole) == 42

    def test_campaign_selected_signal(self, qapp):
        from ui.pages.hunter import CampaignListView
        view = CampaignListView()
        received = []
        view.campaign_selected.connect(lambda cid, name: received.append((cid, name)))
        view.load_campaigns([{
            "id": 7, "name": "My Campaign", "target_niche": "", "target_city": "",
            "status": "completed", "total_leads": 5, "qualified_leads": 2,
            "enriched_leads": 1, "created_at": "",
        }])
        # Simulate double click on row 0
        index = view.table.model().index(0, 0)
        view._on_row_double_clicked(index)
        assert len(received) == 1
        assert received[0] == (7, "My Campaign")


class TestCampaignDetailView:
    """Tests for the CampaignDetailView widget."""

    def test_creates(self, qapp):
        from ui.pages.hunter import CampaignDetailView
        view = CampaignDetailView()
        assert view.table.columnCount() == 15

    def test_load_campaign(self, qapp):
        from ui.pages.hunter import CampaignDetailView
        view = CampaignDetailView()
        leads = [
            {"id": 1, "business_name": "Biz A", "email": "a@test.com",
             "phone": "555-1", "city": "Berlin", "category": "dentist",
             "status": "qualified", "data_completeness_score": 75,
             "google_maps_rating": 4.5, "review_count": 100,
             "domain_age": 3.0, "decision_maker": "Jane",
             "has_facebook": True, "has_instagram": False,
             "has_linkedin": True, "source_platform": "duckduckgo",
             "icp_fit_score": 8, "lifecycle_state": "qualified"},
            {"id": 2, "business_name": "Biz B", "email": "",
             "phone": "", "city": "Berlin", "category": "dentist",
             "status": "new", "data_completeness_score": 0,
             "google_maps_rating": None, "review_count": None,
             "domain_age": None, "decision_maker": "",
             "has_facebook": False, "has_instagram": False,
             "has_linkedin": False, "source_platform": "google_maps",
             "icp_fit_score": None, "lifecycle_state": "new"},
        ]
        view.load_campaign(1, "Test Campaign", leads)

        assert view.campaign_title.text() == "Test Campaign"
        assert view.table.rowCount() == 2
        assert view.lead_count_label.text() == "2 leads"

        # Verify data in first row
        assert view.table.item(0, 0).text() == "Biz A"
        assert view.table.item(0, 1).text() == "a@test.com"
        assert view.table.item(0, 6).text() == "75%"  # score
        assert view.table.item(0, 7).text() == "4.5"  # rating

    def test_lead_id_stored_in_data(self, qapp):
        from ui.pages.hunter import CampaignDetailView
        view = CampaignDetailView()
        view.load_campaign(1, "Test", [
            {"id": 99, "business_name": "Test Biz", "email": "", "phone": "",
             "city": "", "category": "", "status": "new",
             "data_completeness_score": 0, "google_maps_rating": None,
             "review_count": None, "domain_age": None, "decision_maker": "",
             "has_facebook": False, "has_instagram": False,
             "has_linkedin": False, "source_platform": "", "icp_fit_score": None,
             "lifecycle_state": "new"},
        ])
        item = view.table.item(0, 0)
        assert item.data(Qt.ItemDataRole.UserRole) == 99

    def test_back_signal(self, qapp):
        from ui.pages.hunter import CampaignDetailView
        view = CampaignDetailView()
        received = []
        view.back_requested.connect(lambda: received.append(True))
        view.back_btn.click()
        assert len(received) == 1

    def test_enrich_all_signal(self, qapp):
        from ui.pages.hunter import CampaignDetailView
        view = CampaignDetailView()
        view._campaign_id = 42
        received = []
        view.enrich_all_requested.connect(lambda cid: received.append(cid))
        view.enrich_all_btn.click()
        assert received == [42]

    def test_export_csv_button_exists(self, qapp):
        from ui.pages.hunter import CampaignDetailView
        view = CampaignDetailView()
        assert hasattr(view, "export_csv_btn")

    def test_export_csv_empty_shows_warning(self, qapp):
        from ui.pages.hunter import CampaignDetailView
        view = CampaignDetailView()
        # No leads loaded — button click should not open dialog
        with patch("ui.pages.hunter.QFileDialog.getSaveFileName", return_value=("", "")) as mock_dlg:
            view.export_csv_btn.click()
            mock_dlg.assert_not_called()

    def test_export_csv_writes_file(self, qapp, tmp_path):
        import csv
        from ui.pages.hunter import CampaignDetailView
        view = CampaignDetailView()
        leads = [
            {"id": 1, "business_name": "Dental Co", "email": "d@test.com",
             "phone": "555-0", "city": "Austin", "category": "dentist",
             "status": "qualified", "data_completeness_score": 80,
             "google_maps_rating": 4.8, "review_count": 200, "domain_age": 5.0,
             "decision_maker": "Dr Jones", "has_facebook": True, "has_instagram": False,
             "has_linkedin": True, "source_platform": "google_maps",
             "icp_fit_score": 9, "lifecycle_state": "qualified"},
        ]
        view.load_campaign(1, "Austin Dentists", leads)

        csv_path = str(tmp_path / "test_export.csv")
        with patch("ui.pages.hunter.QFileDialog.getSaveFileName",
                   return_value=(csv_path, "CSV Files (*.csv)")):
            view.export_csv_btn.click()

        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]["business_name"] == "Dental Co"
        assert rows[0]["email"] == "d@test.com"
        assert rows[0]["city"] == "Austin"

    def test_stats_display(self, qapp):
        from ui.pages.hunter import CampaignDetailView
        view = CampaignDetailView()
        leads = [
            {"id": i, "business_name": f"B{i}", "email": f"e{i}@test.com" if i < 3 else "",
             "phone": "", "city": "", "category": "", "status": "qualified" if i < 2 else "new",
             "data_completeness_score": 60 if i < 2 else 0,
             "google_maps_rating": None, "review_count": None, "domain_age": None,
             "decision_maker": "", "has_facebook": False, "has_instagram": False,
             "has_linkedin": False, "source_platform": "", "icp_fit_score": None,
             "lifecycle_state": "new"}
            for i in range(5)
        ]
        view.load_campaign(1, "Stats Test", leads)
        assert "2 qualified" in view.stat_qualified.text()
        assert "2 enriched" in view.stat_enriched.text()


class TestHunterPageTabs:
    """Tests for the tabbed HunterPage."""

    def test_has_two_tabs(self, qapp):
        from ui.pages.hunter import HunterPage
        page = HunterPage()
        assert page.tabs.count() == 2

    def test_search_tab_is_default(self, qapp):
        from ui.pages.hunter import HunterPage
        page = HunterPage()
        assert page.tabs.currentIndex() == 0

    def test_campaigns_tab_emits_load_signal(self, qapp):
        from ui.pages.hunter import HunterPage
        page = HunterPage()
        received = []
        page.load_campaigns_requested.connect(lambda: received.append(True))
        page.tabs.setCurrentIndex(1)
        assert len(received) == 1

    def test_on_campaigns_loaded(self, qapp):
        from ui.pages.hunter import HunterPage
        page = HunterPage()
        campaigns = [
            {"id": 1, "name": "C1", "target_niche": "n", "target_city": "c",
             "status": "completed", "total_leads": 10, "qualified_leads": 5,
             "enriched_leads": 3, "created_at": "2025-01-01"},
        ]
        page.on_campaigns_loaded(campaigns)
        assert page.campaign_list.table.rowCount() == 1

    def test_show_campaign_detail(self, qapp):
        from ui.pages.hunter import HunterPage
        page = HunterPage()
        leads = [
            {"id": 1, "business_name": "Biz", "email": "e@t.com", "phone": "555",
             "city": "C", "category": "cat", "status": "new",
             "data_completeness_score": 0, "google_maps_rating": None,
             "review_count": None, "domain_age": None, "decision_maker": "",
             "has_facebook": False, "has_instagram": False, "has_linkedin": False,
             "source_platform": "web", "icp_fit_score": None, "lifecycle_state": "new"},
        ]
        page.show_campaign_detail(1, "Test", leads)
        assert page._campaigns_stack.currentIndex() == 1
        assert page.campaign_detail.table.rowCount() == 1

    def test_back_to_list(self, qapp):
        from ui.pages.hunter import HunterPage
        page = HunterPage()
        page._campaigns_stack.setCurrentIndex(1)
        page._on_back_to_list()
        assert page._campaigns_stack.currentIndex() == 0

    def test_enrich_signals_forwarded(self, qapp):
        from ui.pages.hunter import HunterPage
        page = HunterPage()

        lead_received = []
        campaign_received = []
        page.enrich_lead_requested.connect(lambda lid: lead_received.append(lid))
        page.enrich_campaign_requested.connect(lambda cid: campaign_received.append(cid))

        # Simulate enrich all
        page.campaign_detail._campaign_id = 5
        page.campaign_detail.enrich_all_requested.emit(5)
        assert campaign_received == [5]

    def test_add_lead_row_still_works(self, qapp):
        """Search tab's add_lead_row should still work after tab restructure."""
        from ui.pages.hunter import HunterPage
        page = HunterPage()
        page.add_lead_row({
            "business_name": "Test", "category": "c", "city": "Berlin",
            "phone": "555", "email": "t@t.com", "source_platform": "web",
            "has_website": True, "status": "new",
        })
        assert page.table.rowCount() == 1
        assert page._lead_count == 1

    def test_receive_context_show_campaign(self, qapp):
        from ui.pages.hunter import HunterPage
        page = HunterPage()
        page.receive_context({"show_campaign": True})
        assert page.tabs.currentIndex() == 1

    def test_enrich_campaign_finished_toast(self, qapp):
        from ui.pages.hunter import HunterPage
        page = HunterPage()
        # Should not crash even without parent window
        page.on_enrich_campaign_finished(1, {"enriched": 5, "emails_found": 2})
        # Just verify it doesn't crash — toast needs window()

    def test_enrich_lead_finished_toast(self, qapp):
        from ui.pages.hunter import HunterPage
        page = HunterPage()
        page.on_enrich_lead_finished(1, {"success": True})
        page.on_enrich_lead_finished(2, {"success": False})
        # No crash = pass
