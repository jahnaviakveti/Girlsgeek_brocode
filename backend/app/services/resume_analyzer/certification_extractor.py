import re
from typing import List, Optional
from app.schemas.candidate import CandidateCertification
from app.schemas.domain import Evidence
from app.services.resume_analyzer.date_parser import parse_date_range

COMMON_ISSUERS = {
    "aws": "Amazon Web Services (AWS)",
    "amazon": "Amazon Web Services (AWS)",
    "microsoft": "Microsoft",
    "azure": "Microsoft Azure",
    "google": "Google Cloud (GCP)",
    "gcp": "Google Cloud (GCP)",
    "pmi": "Project Management Institute (PMI)",
    "cisco": "Cisco",
    "comptia": "CompTIA",
    "oracle": "Oracle",
    "scrum alliance": "Scrum Alliance",
    "linux foundation": "Linux Foundation",
    "coursera": "Coursera",
    "udacity": "Udacity",
}

class CertificationExtractor:
    """
    Extracts professional certifications, issuing organizations, and dates.
    """

    @classmethod
    def extract_certifications(
        cls,
        cert_text: str,
        section_name: str = "Certifications",
        page_number: int = 1
    ) -> List[CandidateCertification]:
        if not cert_text.strip():
            return []

        entries: List[CandidateCertification] = []
        lines = [l.strip() for l in cert_text.split("\n") if l.strip()]

        for line in lines:
            clean = re.sub(r'^[•\-\*0-9\.]+', '', line).strip()
            if not clean or len(clean) < 3:
                continue

            s_date, e_date, _, _ = parse_date_range(clean)
            cert_date = s_date or e_date

            # Check if this line is an issue date or metadata line for the previous certification
            if entries and (
                re.match(r'^(?:issued|issue\s+date|date|expires|valid\s+until)\s*:', clean, re.IGNORECASE)
                or (cert_date and len(clean.split()) <= 3 and not any(k in clean.lower() for k in ["certified", "certificate", "aws", "gcp", "azure", "foundation", "institute"]))
            ):
                if cert_date:
                    entries[-1].date = cert_date
                continue

            # Check if this line is a wrapped continuation of the previous certification title
            if entries and len(clean.split()) <= 2 and not re.match(r'^[•\-\*0-9\.]+', line) and not any(k in clean.lower() for k in ["certified", "certificate", "license", "aws", "azure", "gcp", "comptia"]):
                entries[-1].name = f"{entries[-1].name} {clean}".strip()
                continue

            # Clean line of date segments
            line_no_date = clean
            if cert_date:
                line_no_date = re.sub(
                    r'\(?(?:[A-Za-z]{3,9}\.?\s+)?(?:\d{1,2}[/.-])?\d{4}\)?',
                    '',
                    clean,
                    flags=re.IGNORECASE
                ).strip().strip("|-,")

            # Extract issuer
            issuer: Optional[str] = None
            for key, val in COMMON_ISSUERS.items():
                if re.search(r'\b' + re.escape(key) + r'\b', clean, re.IGNORECASE):
                    issuer = val
                    break

            # If separated by by / from / - / |
            cert_name = line_no_date
            if " - " in line_no_date:
                parts = line_no_date.split(" - ", 1)
                cert_name = parts[0].strip()
                if not issuer and len(parts) > 1:
                    issuer = parts[1].strip()
            elif " | " in line_no_date:
                parts = line_no_date.split(" | ", 1)
                cert_name = parts[0].strip()
                if not issuer and len(parts) > 1:
                    issuer = parts[1].strip()
            elif re.search(r'\b(?:from|by)\s+([A-Za-z\s]+)', line_no_date, re.IGNORECASE):
                m_iss = re.search(r'\b(?:from|by)\s+([A-Za-z\s]+)', line_no_date, re.IGNORECASE)
                if m_iss:
                    issuer = m_iss.group(1).strip()
                    cert_name = re.sub(r'\b(?:from|by)\s+[A-Za-z\s]+', '', line_no_date, flags=re.IGNORECASE).strip()

            ev = Evidence(
                source_text=clean,
                source_section=section_name,
                confidence_score=0.90,
                page_number=page_number,
                evidence_type="certification_entry"
            )
            entries.append(
                CandidateCertification(
                    name=cert_name or clean,
                    issuer=issuer,
                    date=cert_date,
                    evidence=ev
                )
            )

        return entries
