import re
import uuid
from typing import List, Optional
from app.schemas.domain import JDRequirement, RequirementCategory, RequirementPriority
from app.services.jd_analyzer.classifier import (
    determine_category,
    determine_priority,
    extract_experience_details,
    is_negated,
)
from app.services.jd_analyzer.taxonomy import (
    extract_technologies,
    extract_all_technologies,
    extract_unfamiliar_terms,
)

def decompose_requirement(
    text: str,
    source_text: str,
    page_number: int,
    source_section: Optional[str] = None
) -> List[JDRequirement]:
    """
    Decomposes a candidate requirement text into one or more structured JDRequirements.
    Preserves logical relationships (OR/AND) and contextual integrity.
    The taxonomy provides normalization assistance but is NOT an exhaustive source of truth;
    unfamiliar or proprietary technical terms are preserved.
    """
    clean_text = text.strip()
    if not clean_text:
        return []

    priority, neg, confidence = determine_priority(clean_text, source_section)
    category = determine_category(clean_text)
    known_techs = extract_technologies(clean_text)
    techs = extract_all_technologies(clean_text)

    # 1. Check for explicit OR / Alternative relationship
    # Example: 'Experience with React or Angular'
    has_or = bool(re.search(r'\b(?:or|either\s+.*?or)\b', clean_text, re.IGNORECASE))
    if has_or and len(techs) >= 2:
        req_id = f"req_{uuid.uuid4().hex[:8]}"
        return [
            JDRequirement(
                id=req_id,
                requirement_text=clean_text,
                category=category,
                priority=priority,
                extracted_keywords=techs,
                source_text=source_text,
                page_number=page_number,
                source_section=source_section,
                logical_operator="OR",
                alternatives=techs,
                is_alternative=True,
                is_negated=neg,
                extraction_confidence=confidence,
            )
        ]

    # 2. Check for Experience requirement
    if category == RequirementCategory.EXPERIENCE:
        min_y, max_y, domain = extract_experience_details(clean_text)
        req_id = f"req_{uuid.uuid4().hex[:8]}"
        return [
            JDRequirement(
                id=req_id,
                requirement_text=clean_text,
                category=category,
                priority=priority,
                extracted_keywords=techs,
                source_text=source_text,
                page_number=page_number,
                source_section=source_section,
                min_years=min_y,
                max_years=max_y,
                experience_domain=domain,
                is_negated=neg,
                extraction_confidence=confidence,
            )
        ]

    # 3. Check for Education requirement (may have alternative majors)
    if category == RequirementCategory.EDUCATION:
        req_id = f"req_{uuid.uuid4().hex[:8]}"
        is_alt = bool(re.search(r'\b(?:or\s+(?:related|equivalent|similar))\b', clean_text, re.IGNORECASE))
        return [
            JDRequirement(
                id=req_id,
                requirement_text=clean_text,
                category=category,
                priority=priority,
                extracted_keywords=techs,
                source_text=source_text,
                page_number=page_number,
                source_section=source_section,
                is_alternative=is_alt,
                logical_operator="OR" if is_alt else None,
                is_negated=neg,
                extraction_confidence=confidence,
            )
        ]

    # 4. Check for Contextual / Conceptual requirements that should NOT be split
    # Example: 'Experience designing scalable distributed systems.'
    is_conceptual = bool(
        re.search(
            r'\b(designing|architecting|building|implementing|scaling|optimizing)\s+[a-z\s]+(systems|infrastructure|pipelines|solutions)\b',
            clean_text,
            re.IGNORECASE
        )
    )
    if is_conceptual:
        req_id = f"req_{uuid.uuid4().hex[:8]}"
        return [
            JDRequirement(
                id=req_id,
                requirement_text=clean_text,
                category=RequirementCategory.DOMAIN if category == RequirementCategory.SKILL else category,
                priority=priority,
                extracted_keywords=techs,
                source_text=source_text,
                page_number=page_number,
                source_section=source_section,
                is_negated=neg,
                extraction_confidence=confidence,
            )
        ]

    # 5. Check for compound list of 3+ distinct technologies:
    # Example: 'Experience with Python, Django, PostgreSQL and Docker.'
    # Split into atomic requirements for modular matching.
    has_list_format = ("," in clean_text or " and " in clean_text.lower())
    if has_list_format and len(techs) >= 3 and not is_conceptual:
        atomic_requirements: List[JDRequirement] = []
        for tech in techs:
            req_id = f"req_{uuid.uuid4().hex[:8]}"
            atomic_requirements.append(
                JDRequirement(
                    id=req_id,
                    requirement_text=f"Proficiency in {tech}",
                    category=RequirementCategory.SKILL if tech in known_techs else category,
                    priority=priority,
                    extracted_keywords=[tech],
                    source_text=source_text,
                    page_number=page_number,
                    source_section=source_section,
                    logical_operator="AND",
                    is_negated=neg,
                    extraction_confidence=confidence,
                )
            )
        return atomic_requirements

    # 6. Default: Single unified requirement
    # Preserves unfamiliar technical terms/requirements instead of discarding them
    req_id = f"req_{uuid.uuid4().hex[:8]}"
    logical_op = "AND" if (len(techs) > 1 and " and " in clean_text.lower()) else None
    return [
        JDRequirement(
            id=req_id,
            requirement_text=clean_text,
            category=category,
            priority=priority,
            extracted_keywords=techs,
            source_text=source_text,
            page_number=page_number,
            source_section=source_section,
            logical_operator=logical_op,
            is_negated=neg,
            extraction_confidence=confidence,
        )
    ]
