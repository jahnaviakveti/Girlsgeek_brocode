import re
from typing import Optional, Tuple
from app.schemas.domain import RequirementCategory, RequirementPriority
from app.services.jd_analyzer.patterns import (
    NEGATION_PATTERNS,
    REQUIRED_SIGNALS,
    PREFERRED_SIGNALS,
    SOFT_WORDING_SIGNALS,
    EXPERIENCE_YEARS_RANGE,
    EXPERIENCE_YEARS_SINGLE,
    EXPERIENCE_MONTHS,
    EDUCATION_DEGREES,
    CERTIFICATION_SIGNALS,
    REQUIRED_SECTION_NAMES,
    PREFERRED_SECTION_NAMES,
)
from app.services.jd_analyzer.taxonomy import extract_technologies

def is_negated(text: str) -> bool:
    """
    Returns True if the requirement text expresses negation
    (e.g., 'Java is not required', 'No prior experience needed').
    """
    for pattern in NEGATION_PATTERNS:
        if pattern.search(text):
            return True
    return False

def determine_priority(
    text: str, 
    section_name: Optional[str] = None
) -> Tuple[RequirementPriority, bool, float]:
    """
    Determines requirement priority (REQUIRED vs PREFERRED), whether it is negated,
    and a confidence score [0.0 - 1.0].
    """
    neg = is_negated(text)
    if neg:
        # Negated requirements are never marked as REQUIRED
        return RequirementPriority.PREFERRED, True, 1.0

    # 1. Sentence-level explicit preferred indicators (override section default)
    for pattern in PREFERRED_SIGNALS:
        if pattern.search(text):
            return RequirementPriority.PREFERRED, False, 1.0

    # 2. Sentence-level explicit required indicators
    for pattern in REQUIRED_SIGNALS:
        if pattern.search(text):
            return RequirementPriority.REQUIRED, False, 1.0

    # 3. Contextual section-level indicators
    if section_name:
        sec_clean = section_name.lower().strip()
        if sec_clean in PREFERRED_SECTION_NAMES:
            return RequirementPriority.PREFERRED, False, 0.95
        if sec_clean in REQUIRED_SECTION_NAMES:
            return RequirementPriority.REQUIRED, False, 0.95

    # 4. Soft phrasing signals (e.g. 'familiarity with')
    for pattern in SOFT_WORDING_SIGNALS:
        if pattern.search(text):
            return RequirementPriority.PREFERRED, False, 0.80

    # 5. Default fallback
    return RequirementPriority.REQUIRED, False, 0.70

def extract_experience_details(text: str) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    Extracts minimum years, maximum years, and experience domain if present.
    Example: '3-5 years of backend experience' -> (3.0, 5.0, 'backend')
    """
    min_years: Optional[float] = None
    max_years: Optional[float] = None
    domain: Optional[str] = None

    # Check for range: '3-5 years'
    range_match = EXPERIENCE_YEARS_RANGE.search(text)
    if range_match:
        min_years = float(range_match.group(1))
        max_years = float(range_match.group(2))
    else:
        # Check for single year: '2+ years'
        single_match = EXPERIENCE_YEARS_SINGLE.search(text)
        if single_match:
            min_years = float(single_match.group(1))
        else:
            # Check for months: '6 months'
            month_match = EXPERIENCE_MONTHS.search(text)
            if month_match:
                min_years = float(month_match.group(1)) / 12.0

    # Domain extraction heuristic
    domain_match = re.search(
        r'(?:years?(?:\s+of)?\s+([A-Za-z\s]+?)\s+experience)|(?:experience\s+(?:in|with)\s+([A-Za-z\s]+?)(?:,|\.|$))',
        text,
        re.IGNORECASE
    )
    if domain_match:
        extracted = domain_match.group(1) or domain_match.group(2)
        if extracted:
            cleaned_domain = extracted.strip()
            # Omit generic stop words
            if len(cleaned_domain) > 2 and cleaned_domain.lower() not in {"professional", "relevant", "prior", "hands-on"}:
                domain = cleaned_domain

    return min_years, max_years, domain

def determine_category(text: str) -> RequirementCategory:
    """
    Determines the requirement category based on linguistic cues and taxonomy hits.
    CATEGORY != PRIORITY.
    """
    # 1. Education
    for pattern in EDUCATION_DEGREES:
        if pattern.search(text):
            return RequirementCategory.EDUCATION

    # 2. Certification
    for pattern in CERTIFICATION_SIGNALS:
        if pattern.search(text):
            return RequirementCategory.CERTIFICATION

    # 3. Experience / Tenure
    min_y, max_y, _ = extract_experience_details(text)
    if min_y is not None or re.search(r'\b(years?\s+of\s+experience|prior\s+experience)\b', text, re.IGNORECASE):
        return RequirementCategory.EXPERIENCE

    # 4. Technical Skill / Technology
    techs = extract_technologies(text)
    if techs:
        return RequirementCategory.SKILL

    # 5. Domain Knowledge (e.g. distributed systems, microservices, cloud security)
    domain_indicators = [
        "distributed systems", "microservices", "cloud architecture", "embedded",
        "fintech", "ecommerce", "system design", "scalable systems", "security"
    ]
    if any(d in text.lower() for d in domain_indicators):
        return RequirementCategory.DOMAIN

    # 6. Fallback
    return RequirementCategory.OTHER
