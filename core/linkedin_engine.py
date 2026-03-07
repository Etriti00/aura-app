"""
Aura — LinkedIn Engine
CSV-based LinkedIn data import for Sales Navigator exports.
No direct API scraping (LinkedIn TOS compliance).
Accepts Sales Navigator CSV exports and generic LinkedIn data exports.
"""

import csv
import io
from typing import List, Dict, Optional
from utils.logger import get_logger

logger = get_logger("linkedin_engine")

# Standard Sales Navigator export columns
SALES_NAV_COLUMNS = {
    "first_name": ["First Name", "first_name", "firstName"],
    "last_name": ["Last Name", "last_name", "lastName"],
    "title": ["Title", "Job Title", "title", "jobTitle"],
    "company": ["Company", "Company Name", "company", "companyName"],
    "email": ["Email", "Email Address", "email", "emailAddress"],
    "phone": ["Phone", "Phone Number", "phone", "phoneNumber"],
    "linkedin_url": ["LinkedIn URL", "Profile URL", "linkedinUrl", "profileUrl", "LinkedIn Profile"],
    "city": ["City", "Location", "city", "geography"],
    "country": ["Country", "country"],
    "industry": ["Industry", "industry"],
    "company_size": ["Company Size", "# Employees", "companySize", "employees"],
    "website": ["Website", "Company Website", "website"],
}


class LinkedInEngine:
    """LinkedIn data import engine — CSV-only, no API scraping."""

    def __init__(self):
        pass

    def _detect_column_mapping(self, headers: List[str]) -> Dict[str, str]:
        """
        Auto-detect column mapping from CSV headers.
        Returns: {standard_field: actual_header_name}
        """
        mapping = {}
        headers_lower = {h.strip().lower(): h.strip() for h in headers}

        for standard_field, candidates in SALES_NAV_COLUMNS.items():
            for candidate in candidates:
                if candidate.lower() in headers_lower:
                    mapping[standard_field] = headers_lower[candidate.lower()]
                    break

        return mapping

    def validate_csv(self, file_path: str) -> dict:
        """
        Validate a LinkedIn CSV export file.
        Returns: {"valid": bool, "row_count": int, "columns_found": list, "errors": list}
        """
        errors = []
        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []

                if not headers:
                    return {"valid": False, "row_count": 0, "columns_found": [], "errors": ["CSV file has no headers"]}

                mapping = self._detect_column_mapping(headers)
                columns_found = list(mapping.keys())

                # Must have at least a name or email
                has_identity = any(k in mapping for k in ("first_name", "last_name", "email", "company"))
                if not has_identity:
                    errors.append("CSV must contain at least one of: First Name, Last Name, Email, or Company")

                rows = list(reader)
                row_count = len(rows)

                if row_count == 0:
                    errors.append("CSV file has no data rows")

                return {
                    "valid": len(errors) == 0,
                    "row_count": row_count,
                    "columns_found": columns_found,
                    "errors": errors,
                }

        except UnicodeDecodeError:
            return {"valid": False, "row_count": 0, "columns_found": [], "errors": ["File encoding not supported. Please save as UTF-8."]}
        except Exception as e:
            return {"valid": False, "row_count": 0, "columns_found": [], "errors": [str(e)]}

    def import_from_csv(self, file_path: str) -> dict:
        """
        Parse a LinkedIn CSV export and return lead-formatted records.
        Returns: {"success": bool, "leads": [lead_dicts], "skipped": int, "error": str|None}
        """
        try:
            validation = self.validate_csv(file_path)
            if not validation["valid"]:
                return {
                    "success": False,
                    "leads": [],
                    "skipped": 0,
                    "error": "; ".join(validation["errors"]),
                }

            with open(file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []
                mapping = self._detect_column_mapping(headers)

                leads = []
                skipped = 0

                for row in reader:
                    lead = self._row_to_lead(row, mapping)
                    if lead:
                        leads.append(lead)
                    else:
                        skipped += 1

            logger.info(f"LinkedIn CSV import: {len(leads)} leads, {skipped} skipped from {file_path}")
            return {
                "success": True,
                "leads": leads,
                "skipped": skipped,
                "error": None,
            }

        except Exception as e:
            logger.error(f"LinkedIn CSV import failed: {e}")
            return {"success": False, "leads": [], "skipped": 0, "error": str(e)}

    def parse_sales_nav_export(self, csv_text: str) -> dict:
        """
        Parse Sales Navigator CSV data from a string (clipboard paste).
        Returns same format as import_from_csv.
        """
        try:
            reader = csv.DictReader(io.StringIO(csv_text))
            headers = reader.fieldnames or []
            mapping = self._detect_column_mapping(headers)

            if not mapping:
                return {"success": False, "leads": [], "skipped": 0,
                        "error": "Could not detect LinkedIn CSV columns"}

            leads = []
            skipped = 0

            for row in reader:
                lead = self._row_to_lead(row, mapping)
                if lead:
                    leads.append(lead)
                else:
                    skipped += 1

            return {"success": True, "leads": leads, "skipped": skipped, "error": None}

        except Exception as e:
            logger.error(f"LinkedIn paste parse failed: {e}")
            return {"success": False, "leads": [], "skipped": 0, "error": str(e)}

    def _row_to_lead(self, row: dict, mapping: Dict[str, str]) -> Optional[dict]:
        """Convert a single CSV row to an Aura lead dict using the detected mapping."""
        def get(field: str) -> str:
            col = mapping.get(field)
            if col and col in row:
                return (row[col] or "").strip()
            return ""

        first = get("first_name")
        last = get("last_name")
        company = get("company")
        email = get("email")

        # Skip rows with no useful identity data
        if not any([first, last, company, email]):
            return None

        name = f"{first} {last}".strip()
        title = get("title")

        return {
            "business_name": company or name,
            "category": get("industry"),
            "address": "",
            "city": get("city"),
            "country": get("country"),
            "phone": get("phone"),
            "email": email,
            "source_url": get("linkedin_url"),
            "source_platform": "linkedin",
            "has_website": bool(get("website")),
            "website_url": get("website"),
            "snippet": f"{name} — {title} at {company}".strip(" —"),
        }

    def map_to_lead(self, record: dict) -> dict:
        """
        Pass-through for consistency with other engines.
        LinkedIn records from import_from_csv are already in lead format.
        """
        return record
