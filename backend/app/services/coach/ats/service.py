from typing import Dict, Any, List
from app.schemas.document import GenericDocument
from app.schemas.candidate import CandidateProfile
from app.services.document_parser.section_detector import KNOWN_SECTION_ALIASES

class ATSStressTestService:
    """
    Simulates ATS parser behavior and audits document structure, header compatibility,
    and text extractability.
    """

    def audit_resume(self, document: GenericDocument, profile: CandidateProfile) -> Dict[str, Any]:
        """
        Executes structural ATS compliance audit.
        """
        checks: List[Dict[str, Any]] = []
        overall_score = 100.0

        # Check 1: Contact Information Extractability
        has_name = bool(profile.name)
        has_email = bool(profile.email)
        has_phone = bool(profile.phone)
        contact_score = (has_name * 40) + (has_email * 30) + (has_phone * 30)
        checks.append({
            "check": "Contact Details Parseability",
            "passed": bool(has_name and has_email),
            "score": contact_score,
            "details": f"Detected Name: {profile.name or 'Missing'}, Email: {profile.email or 'Missing'}, Phone: {profile.phone or 'Missing'}"
        })
        if not has_email:
            overall_score -= 15

        # Check 2: Core Section Headings Standard Compliance
        found_sections = set(profile.sections.keys())
        essential_sections = {"skills", "experience", "education"}
        missing_sections = essential_sections - found_sections

        checks.append({
            "check": "Standard Heading Conformance",
            "passed": len(missing_sections) == 0,
            "score": 100 if not missing_sections else (100 - len(missing_sections) * 25),
            "details": f"Found canonical sections: {', '.join(sorted(found_sections))}. Missing critical: {', '.join(missing_sections) or 'None'}"
        })
        overall_score -= len(missing_sections) * 15

        # Check 3: Digital Text Extractability & Density
        word_count = len((document.raw_text or "").split())
        text_healthy = word_count >= 150
        checks.append({
            "check": "Text Density & Digital Extractability",
            "passed": text_healthy,
            "score": 100 if text_healthy else 40,
            "details": f"Extracted {word_count} total words across {document.page_count} page(s)."
        })
        if not text_healthy:
            overall_score -= 30

        # Check 4: Experience Structure & Dates
        exp_has_dates = all(bool(exp.start_date) for exp in profile.experience) if profile.experience else False
        checks.append({
            "check": "Tenure & Date Normalization",
            "passed": exp_has_dates,
            "score": 100 if exp_has_dates else 60,
            "details": f"Extracted {len(profile.experience)} employment entry/entries with chronological dates."
        })
        if not exp_has_dates and profile.experience:
            overall_score -= 10

        overall_score = max(20.0, min(100.0, overall_score))

        return {
            "ats_readability_score": overall_score,
            "ats_grade": "A" if overall_score >= 85 else ("B" if overall_score >= 70 else "C"),
            "checks": checks,
            "recommendations": [
                "Ensure your name and email are in standard header text rather than floating textboxes." if not has_email else None,
                f"Add standard headings for: {', '.join(missing_sections)}" if missing_sections else None,
                "Avoid graphic charts or multi-column layouts that may scramble reading order in older ATS engines."
            ]
        }
