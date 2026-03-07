"""
Tests for LinkedIn Engine — CSV import for lead hunting (no API).
"""
import pytest
from pathlib import Path

from core.linkedin_engine import LinkedInEngine


@pytest.fixture
def linkedin_engine():
    """Fresh LinkedInEngine instance."""
    return LinkedInEngine()


@pytest.fixture
def sales_nav_csv(tmp_path):
    """Create a sample Sales Navigator CSV export."""
    csv_content = (
        "First Name,Last Name,Title,Company,Email,LinkedIn URL,City,State\n"
        "John,Doe,Owner,Doe Plumbing,john@doeplumbing.com,https://linkedin.com/in/johndoe,Denver,CO\n"
        "Jane,Smith,CEO,Smith HVAC,jane@smithhvac.com,https://linkedin.com/in/janesmith,Boulder,CO\n"
        "Bob,Jones,Manager,Jones Electric,,https://linkedin.com/in/bobjones,Aurora,CO\n"
    )
    csv_file = tmp_path / "sales_nav_export.csv"
    csv_file.write_text(csv_content, encoding="utf-8")
    return str(csv_file)


@pytest.fixture
def generic_csv(tmp_path):
    """Create a generic LinkedIn CSV export."""
    csv_content = (
        "first_name,last_name,position,company_name,email_address,profile_url,location\n"
        "Alice,Brown,Founder,Brown Consulting,alice@brown.com,https://linkedin.com/in/alicebrown,Seattle WA\n"
        "Charlie,White,VP Sales,White Corp,charlie@white.com,https://linkedin.com/in/charliewhite,Portland OR\n"
    )
    csv_file = tmp_path / "generic_export.csv"
    csv_file.write_text(csv_content, encoding="utf-8")
    return str(csv_file)


@pytest.fixture
def empty_csv(tmp_path):
    """Create an empty CSV file (headers only, no data rows)."""
    csv_file = tmp_path / "empty.csv"
    csv_file.write_text("First Name,Last Name,Title,Company,Email\n", encoding="utf-8")
    return str(csv_file)


@pytest.fixture
def bad_csv(tmp_path):
    """Create a malformed CSV file with no recognized LinkedIn columns."""
    csv_file = tmp_path / "bad.csv"
    csv_file.write_text("not,a,valid,linkedin,format\nfoo,bar,baz,qux,quux\n", encoding="utf-8")
    return str(csv_file)


class TestLinkedInEngineInit:
    """Test engine initialization."""

    def test_init(self, linkedin_engine):
        assert linkedin_engine is not None

    def test_has_required_methods(self, linkedin_engine):
        assert hasattr(linkedin_engine, "validate_csv")
        assert hasattr(linkedin_engine, "import_from_csv")
        assert hasattr(linkedin_engine, "map_to_lead")


class TestValidateCSV:
    """Test CSV validation."""

    def test_validate_sales_nav_csv(self, linkedin_engine, sales_nav_csv):
        """Should validate Sales Navigator export format."""
        result = linkedin_engine.validate_csv(sales_nav_csv)
        assert result["valid"] is True
        assert result["row_count"] == 3

    def test_validate_generic_csv(self, linkedin_engine, generic_csv):
        """Should validate generic LinkedIn export format."""
        result = linkedin_engine.validate_csv(generic_csv)
        assert "valid" in result
        assert "row_count" in result

    def test_validate_empty_csv_invalid(self, linkedin_engine, empty_csv):
        """Empty CSV (0 data rows) should be flagged as invalid."""
        result = linkedin_engine.validate_csv(empty_csv)
        assert result["valid"] is False
        assert result["row_count"] == 0

    def test_validate_nonexistent_file(self, linkedin_engine):
        """Should report missing file as invalid."""
        result = linkedin_engine.validate_csv("/nonexistent/file.csv")
        assert result["valid"] is False

    def test_validate_bad_csv(self, linkedin_engine, bad_csv):
        """Should reject CSV without recognized LinkedIn columns."""
        result = linkedin_engine.validate_csv(bad_csv)
        assert result["valid"] is False

    def test_validate_returns_columns_found(self, linkedin_engine, sales_nav_csv):
        """Should report which LinkedIn columns were detected."""
        result = linkedin_engine.validate_csv(sales_nav_csv)
        assert isinstance(result.get("columns_found"), list)
        assert len(result["columns_found"]) > 0


class TestImportFromCSV:
    """Test CSV import functionality."""

    def test_import_sales_nav(self, linkedin_engine, sales_nav_csv):
        """Should import all rows from Sales Navigator export."""
        result = linkedin_engine.import_from_csv(sales_nav_csv)
        assert result["success"] is True
        leads = result["leads"]
        assert len(leads) == 3

    def test_import_preserves_email(self, linkedin_engine, sales_nav_csv):
        """Should preserve email field from import."""
        result = linkedin_engine.import_from_csv(sales_nav_csv)
        leads = result["leads"]
        emails = [l.get("email") for l in leads]
        assert "john@doeplumbing.com" in emails

    def test_import_preserves_source_platform(self, linkedin_engine, sales_nav_csv):
        """Should tag source as linkedin."""
        result = linkedin_engine.import_from_csv(sales_nav_csv)
        leads = result["leads"]
        for lead in leads:
            assert lead.get("source_platform") == "linkedin"

    def test_import_handles_missing_email(self, linkedin_engine, sales_nav_csv):
        """Bob Jones has no email — should still import (has name + company)."""
        result = linkedin_engine.import_from_csv(sales_nav_csv)
        leads = result["leads"]
        bob = next(
            (l for l in leads if "jones" in l.get("business_name", "").lower()
             or "jones" in l.get("snippet", "").lower()),
            None,
        )
        assert bob is not None
        assert bob.get("email") == ""

    def test_import_empty_csv_fails(self, linkedin_engine, empty_csv):
        """Empty CSV should fail because validation rejects 0 rows."""
        result = linkedin_engine.import_from_csv(empty_csv)
        assert result["success"] is False

    def test_import_nonexistent_file(self, linkedin_engine):
        """Should return error for missing file."""
        result = linkedin_engine.import_from_csv("/nonexistent/file.csv")
        assert result["success"] is False

    def test_import_returns_skipped_count(self, linkedin_engine, sales_nav_csv):
        """Should report number of skipped rows."""
        result = linkedin_engine.import_from_csv(sales_nav_csv)
        assert "skipped" in result
        assert isinstance(result["skipped"], int)


class TestMapToLead:
    """Test lead mapping. map_to_lead is a pass-through for LinkedIn."""

    def test_map_passes_through(self, linkedin_engine):
        """map_to_lead should return the record as-is (already in lead format)."""
        record = {
            "business_name": "Doe Plumbing",
            "email": "john@doeplumbing.com",
            "source_platform": "linkedin",
        }
        result = linkedin_engine.map_to_lead(record)
        assert result == record

    def test_map_empty(self, linkedin_engine):
        """Should handle empty dict."""
        result = linkedin_engine.map_to_lead({})
        assert result == {}


class TestParseSalesNavExport:
    """Test clipboard paste parsing."""

    def test_parse_from_string(self, linkedin_engine):
        """Should parse CSV text (like from clipboard)."""
        csv_text = (
            "First Name,Last Name,Title,Company,Email\n"
            "Alice,Brown,CEO,Brown Inc,alice@brown.com\n"
        )
        result = linkedin_engine.parse_sales_nav_export(csv_text)
        assert result["success"] is True
        assert len(result["leads"]) == 1
        assert result["leads"][0]["email"] == "alice@brown.com"

    def test_parse_empty_string(self, linkedin_engine):
        """Should handle empty CSV text."""
        result = linkedin_engine.parse_sales_nav_export("")
        assert isinstance(result, dict)
