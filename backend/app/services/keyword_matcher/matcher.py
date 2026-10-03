import re
import difflib
from typing import List, Set, Optional, Tuple, Dict, Any
from app.schemas.candidate import CandidateProfile, CandidateSkill
from app.schemas.domain import JDRequirement, Evidence
from app.schemas.keyword_matching import KeywordMatchResult
from app.services.jd_analyzer.taxonomy import extract_all_technologies
from .normalization import normalize_text, clean_token, tokenize_words, extract_candidate_phrases
from .aliases import get_canonical_name, is_alias_match

# Aspirational patterns: Statements expressing intent to learn rather than current capability
ASPIRATIONAL_PATTERNS = [
    re.compile(r'\b(?:interested\s+in\s+(?:learning|exploring|gaining|studying))\b', re.IGNORECASE),
    re.compile(r'\b(?:plans?\s+to\s+learn|looking\s+to\s+learn|seeking\s+to\s+learn|want\s+to\s+learn|wants?\s+to\s+learn)\b', re.IGNORECASE),
    re.compile(r'\b(?:aspiring\s+to\s+learn|hopes?\s+to\s+learn|hoping\s+to\s+learn)\b', re.IGNORECASE),
    re.compile(r'\b(?:future\s+interest|basic\s+theoretical\s+knowledge)\b', re.IGNORECASE),
]

# Negation patterns: Statements explicitly stating lack of experience
NEGATION_PATTERNS = [
    re.compile(r'\b(?:no\s+experience\s+(?:with|in))\b', re.IGNORECASE),
    re.compile(r'\b(?:little\s+to\s+no\s+experience\s+(?:with|in)?)\b', re.IGNORECASE),
    re.compile(r'\b(?:never\s+used|never\s+worked\s+with)\b', re.IGNORECASE),
    re.compile(r'\b(?:not\s+familiar\s+with|no\s+knowledge\s+of)\b', re.IGNORECASE),
    re.compile(r'\b(?:without\s+experience\s+(?:in|with))\b', re.IGNORECASE),
    re.compile(r'\b(?:haven[\'’]t\s+worked\s+with|have\s+not\s+worked\s+with)\b', re.IGNORECASE),
    re.compile(r'\b(?:lacks?\s+experience\s+(?:in|with))\b', re.IGNORECASE),
]

# Conservative fuzzy matching settings
FUZZY_MIN_TOKEN_LEN = 4  # Short tokens (R, C, Go, AWS, Git, SQL) must NEVER be fuzzy matched
FUZZY_MAX_LEN_DIFF = 2   # Maximum character length difference allowed between tokens
FUZZY_SIMILARITY_THRESHOLD = 0.85  # Conservative cutoff for spelling/format variation

class KeywordMatcher:
    """
    Deterministic local keyword/lexical matching engine.
    Compares JDRequirements against structured candidate evidence from CandidateProfile.
    """

    @classmethod
    def is_negated_or_aspirational(cls, text: str, keyword: Optional[str] = None) -> bool:
        """
        Detects if text contains negative or aspirational phrasing regarding candidate qualifications.
        If keyword is provided, checks if the negative/aspirational phrasing relates to that keyword.
        """
        if not text:
            return False
        
        # Check aspirational
        for pattern in ASPIRATIONAL_PATTERNS:
            if pattern.search(text):
                return True

        # Check negation
        for pattern in NEGATION_PATTERNS:
            if pattern.search(text):
                return True

        return False

    @classmethod
    def build_boundary_pattern(cls, term: str) -> re.Pattern:
        """
        Creates a regex pattern that safely matches a term on token boundaries,
        protecting against substring false positives (e.g. Java vs JavaScript, C vs C++, R vs Rust).
        """
        escaped = re.escape(term.strip())
        # (?<![a-zA-Z0-9+#]) and (?![a-zA-Z0-9+#]) ensure proper tech token boundaries
        pattern_str = rf'(?<![a-zA-Z0-9+#]){escaped}(?![a-zA-Z0-9+#])'
        return re.compile(pattern_str, re.IGNORECASE)

    def extract_requirement_keywords(self, requirement: JDRequirement) -> List[str]:
        """
        Extracts actionable search keywords from a JDRequirement.
        Prioritizes extracted_keywords, taxonomy-identified tech terms, or normalized requirement text.
        """
        keywords: List[str] = []
        seen: Set[str] = set()

        def add_kw(kw: str):
            clean_kw = kw.strip()
            norm = normalize_text(clean_kw)
            if norm and norm not in seen:
                seen.add(norm)
                keywords.append(clean_kw)

        # 1. Extracted keywords from Phase 3 if present
        if requirement.extracted_keywords:
            for kw in requirement.extracted_keywords:
                add_kw(kw)
        elif requirement.requirement_text:
            # 2. Otherwise identify technologies in requirement text
            techs = extract_all_technologies(requirement.requirement_text)
            for t in techs:
                add_kw(t)

        # 3. Fallback: if no keywords found, use requirement_text directly
        if not keywords and requirement.requirement_text and requirement.requirement_text.strip():
            clean_req = requirement.requirement_text.strip()
            # If short phrase (<= 4 words), use whole text
            if len(clean_req.split()) <= 4:
                add_kw(clean_req)
            else:
                # Tokenize significant words (> 2 chars)
                for w in tokenize_words(clean_req):
                    if len(w) > 2:
                        add_kw(w)

        return keywords

    def evaluate_requirement(
        self,
        requirement: JDRequirement,
        profile: CandidateProfile
    ) -> List[KeywordMatchResult]:
        """
        Evaluates a JDRequirement against a CandidateProfile.
        Returns all valid lexical matches sorted by evidence strength and score.
        """
        if not requirement or not requirement.requirement_text or not requirement.requirement_text.strip():
            return []

        keywords = self.extract_requirement_keywords(requirement)
        if not keywords:
            return []

        candidate_evidence = self._gather_candidate_evidence(profile)
        if not candidate_evidence:
            return []

        # Map from (norm_ev, ev_type) -> KeywordMatchResult to keep strongest match per evidence item
        best_matches: Dict[Tuple[str, str], KeywordMatchResult] = {}
        type_priority = {"EXACT": 0, "ALIAS": 1, "FUZZY": 2}

        def record_match(res: KeywordMatchResult):
            key = (normalize_text(res.evidence_text), res.evidence_type or "")
            if key not in best_matches:
                best_matches[key] = res
            else:
                existing = best_matches[key]
                existing_prio = type_priority.get(existing.match_type, 9)
                new_prio = type_priority.get(res.match_type, 9)
                # Lower prio number is stronger match
                if new_prio < existing_prio or (new_prio == existing_prio and res.lexical_score > existing.lexical_score):
                    best_matches[key] = res

        for kw in keywords:
            norm_kw = normalize_text(kw)
            canonical_kw = get_canonical_name(kw)
            kw_pattern = self.build_boundary_pattern(kw)

            for ev_text, ev_type, provenance in candidate_evidence:
                if not ev_text or not ev_text.strip():
                    continue

                # False positive protection: Skip aspirational or negated evidence
                if self.is_negated_or_aspirational(ev_text, kw):
                    continue

                norm_ev = normalize_text(ev_text)

                # --- 1. EXACT MATCH ---
                is_exact = False
                matched_token = kw

                if ev_type == "skill" and norm_kw == norm_ev:
                    is_exact = True
                    matched_token = ev_text
                elif kw_pattern.search(ev_text):
                    is_exact = True
                    matched_token = kw

                if is_exact:
                    record_match(
                        self._build_result(
                            requirement, kw, ev_text, "EXACT", 1.0, ev_type, provenance
                        )
                    )
                    continue  # Exact match found for this evidence item

                # --- 2. ALIAS MATCH ---
                is_alias = False
                if canonical_kw:
                    candidate_phrases = extract_candidate_phrases(ev_text, max_words=3)
                    for phrase in candidate_phrases:
                        if is_alias_match(kw, phrase):
                            is_alias = True
                            matched_token = phrase
                            break

                if is_alias:
                    record_match(
                        self._build_result(
                            requirement, kw, ev_text, "ALIAS", 1.0, ev_type, provenance
                        )
                    )
                    continue

                # --- 3. FUZZY MATCH ---
                if len(norm_kw) >= FUZZY_MIN_TOKEN_LEN:
                    is_fuzzy = False
                    best_ratio = 0.0
                    fuzzy_matched_phrase = ""

                    candidate_phrases = extract_candidate_phrases(ev_text, max_words=len(norm_kw.split()) + 1)
                    for phrase in candidate_phrases:
                        norm_phrase = normalize_text(phrase)
                        if len(norm_phrase) < FUZZY_MIN_TOKEN_LEN:
                            continue
                        if abs(len(norm_kw) - len(norm_phrase)) > FUZZY_MAX_LEN_DIFF:
                            continue

                        ratio = difflib.SequenceMatcher(None, norm_kw, norm_phrase).ratio()
                        if ratio >= FUZZY_SIMILARITY_THRESHOLD and ratio > best_ratio:
                            best_ratio = ratio
                            fuzzy_matched_phrase = phrase
                            is_fuzzy = True

                    if is_fuzzy:
                        record_match(
                            self._build_result(
                                requirement,
                                kw,
                                ev_text,
                                "FUZZY",
                                round(best_ratio, 3),
                                ev_type,
                                provenance
                            )
                        )

        results = list(best_matches.values())

        # Deterministic sorting:
        # 1. Match type priority: EXACT (0) > ALIAS (1) > FUZZY (2)
        # 2. Lexical score descending
        # 3. Evidence type priority: skill (0) > experience (1) > project (2) > education (3) > certification (4) > summary (5)
        # 4. Evidence text alphabetical
        type_priority = {"EXACT": 0, "ALIAS": 1, "FUZZY": 2}
        ev_type_priority = {"skill": 0, "experience": 1, "project": 2, "education": 3, "certification": 4, "summary": 5}

        results.sort(
            key=lambda r: (
                type_priority.get(r.match_type, 9),
                -r.lexical_score,
                ev_type_priority.get(r.evidence_type or "", 9),
                r.evidence_text
            )
        )

        return results

    def _build_result(
        self,
        requirement: JDRequirement,
        matched_keyword: str,
        evidence_text: str,
        match_type: str,
        lexical_score: float,
        evidence_type: str,
        provenance: Optional[Evidence]
    ) -> KeywordMatchResult:
        """
        Constructs a KeywordMatchResult with provenance faithfully preserved from domain Evidence.
        Does NOT fabricate evidence IDs or final verdicts.
        """
        page_num = provenance.page_number if provenance else None
        sec_name = provenance.source_section if provenance else None
        src_text = provenance.source_text if provenance and hasattr(provenance, 'source_text') else None

        return KeywordMatchResult(
            requirement_id=str(requirement.id) if hasattr(requirement, 'id') else "req",
            evidence_id=None,  # Domain Evidence has no ID; keep None
            requirement_text=requirement.requirement_text.strip(),
            matched_keyword=matched_keyword,
            evidence_text=evidence_text,
            match_type=match_type,
            lexical_score=lexical_score,
            page_number=page_num,
            source_section=sec_name,
            source_text=src_text,
            evidence_type=evidence_type,
            evidence=provenance
        )

    def _gather_candidate_evidence(
        self,
        profile: CandidateProfile
    ) -> List[Tuple[str, str, Optional[Evidence]]]:
        """
        Gathers candidate evidence units from CandidateProfile with domain Evidence provenance.
        Distinguishes explicit skills, experience, projects, education, certifications, and summary.
        """
        evidence_list: List[Tuple[str, str, Optional[Evidence]]] = []

        # 1. Explicit Skills
        for skill in profile.skill_details:
            name = skill.name or skill.raw_name
            if name:
                evidence_list.append((name, "skill", skill.evidence))

        # 2. Experience entries
        for exp in profile.experience:
            text_parts = []
            if exp.role:
                text_parts.append(exp.role)
            if exp.company:
                text_parts.append(f"at {exp.company}")
            if exp.description:
                text_parts.append(exp.description)
            combined = " ".join(text_parts).strip()
            if combined:
                evidence_list.append((combined, "experience", exp.evidence))

        # 3. Projects
        for proj in profile.projects:
            text_parts = []
            if proj.name:
                text_parts.append(proj.name)
            if proj.description:
                text_parts.append(proj.description)
            combined = " ".join(text_parts).strip()
            if combined:
                evidence_list.append((combined, "project", proj.evidence))

        # 4. Education
        for edu in profile.education:
            text_parts = []
            if edu.degree:
                text_parts.append(edu.degree)
            if edu.field_of_study:
                text_parts.append(edu.field_of_study)
            if edu.institution:
                text_parts.append(f"at {edu.institution}")
            combined = " ".join(text_parts).strip()
            if combined:
                evidence_list.append((combined, "education", edu.evidence))

        # 5. Certifications
        for cert in profile.certifications:
            text_parts = []
            if cert.name:
                text_parts.append(cert.name)
            if cert.issuer:
                text_parts.append(f"by {cert.issuer}")
            combined = " ".join(text_parts).strip()
            if combined:
                evidence_list.append((combined, "certification", cert.evidence))

        # 6. Professional Summary
        if profile.summary and profile.summary.strip():
            evidence_list.append((profile.summary.strip(), "summary", None))

        return evidence_list
