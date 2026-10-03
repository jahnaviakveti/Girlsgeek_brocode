import re
from typing import List, Optional, Tuple, Set
from app.schemas.candidate import CandidateProfile
from app.schemas.domain import (
    JDRequirement,
    RequirementCategory,
    RequirementPriority,
    MatchVerdict,
    Evidence
)
from app.schemas.keyword_matching import KeywordMatchResult
from app.schemas.semantic_matching import SemanticMatchResult
from app.schemas.scoring import RequirementEvaluationResult
from app.services.keyword_matcher import KeywordMatcher
from app.services.keyword_matcher.matcher import NEGATION_PATTERNS, ASPIRATIONAL_PATTERNS
from app.services.semantic_matcher import SemanticMatcher
from app.services.jd_analyzer.taxonomy import extract_all_technologies
from .constants import (
    WEIGHT_LEXICAL_EXACT,
    WEIGHT_SEMANTIC_WITH_LEX,
    WEIGHT_LEXICAL_FUZZY,
    WEIGHT_SEMANTIC_FUZZY,
    WEIGHT_SEMANTIC_ONLY,
    SEMANTIC_MIN_THRESHOLD,
    VERDICT_MATCHED_THRESHOLD,
    VERDICT_PARTIAL_THRESHOLD,
    EXPERIENCE_UNVERIFIED_DURATION_MULTIPLIER,
    EXPERIENCE_UNVERIFIED_MAX_SCORE,
)

GENERIC_EXPERIENCE_STOPWORDS = {
    "experience", "years", "year", "months", "month", "work", "working",
    "job", "required", "preferred", "minimum", "demonstrated", "proven",
    "strong", "solid", "hands-on", "proficiency", "skills", "knowledge"
}

class RequirementEvaluator:
    """
    Evaluates a single JDRequirement against a CandidateProfile by synthesizing
    independent lexical and semantic signals into a transparent, deterministic score.
    Enforces strict guardrails for concrete skills, certifications, education, and experience tenure.
    """

    def __init__(self, keyword_matcher: KeywordMatcher, semantic_matcher: SemanticMatcher):
        self.keyword_matcher = keyword_matcher
        self.semantic_matcher = semantic_matcher

    def evaluate_requirement(
        self,
        requirement: JDRequirement,
        profile: CandidateProfile
    ) -> RequirementEvaluationResult:
        """
        Evaluates a requirement against a candidate profile, producing a structured
        RequirementEvaluationResult containing hybrid score, verdict, and traceable rationale.
        """
        req_id = str(requirement.id) if hasattr(requirement, 'id') else "req"
        req_text = requirement.requirement_text.strip() if requirement and requirement.requirement_text else ""
        is_req = requirement.is_required if hasattr(requirement, 'is_required') else True

        if not req_text:
            return RequirementEvaluationResult(
                requirement_id=req_id,
                requirement_text="",
                category=requirement.category,
                priority=requirement.priority,
                is_required=is_req,
                verdict=MatchVerdict.MISSING,
                hybrid_score=0.0,
                rationale="Empty requirement text."
            )

        # 1. Run Keyword Matcher
        lexical_matches = self.keyword_matcher.evaluate_requirement(requirement, profile)

        # 2. Run Semantic Matcher
        semantic_matches = self.semantic_matcher.evaluate_requirement(requirement, profile)

        # 3. Check for explicit negation across all candidate evidence regarding this requirement
        has_explicit_negation, negation_snippet = self._check_explicit_negation(requirement, profile)

        # 4. Filter semantic matches for aspirational/negative phrasing
        valid_semantic_matches: List[SemanticMatchResult] = []
        rejected_semantic_reasons: List[str] = []

        for sem_match in semantic_matches:
            if KeywordMatcher.is_negated_or_aspirational(sem_match.evidence_text, req_text):
                rejected_semantic_reasons.append(sem_match.evidence_text)
            else:
                valid_semantic_matches.append(sem_match)

        # Identify strongest valid signals
        strongest_lexical: Optional[KeywordMatchResult] = lexical_matches[0] if lexical_matches else None
        strongest_semantic: Optional[SemanticMatchResult] = valid_semantic_matches[0] if valid_semantic_matches else None

        # Check if candidate's only mention of this skill was aspirational
        is_only_aspirational = bool(
            not strongest_lexical and
            not has_explicit_negation and
            rejected_semantic_reasons and
            not valid_semantic_matches
        )

        # 5. Compute Hybrid Score with Semantic Safety Guardrails
        hybrid_score = 0.0
        rationale_parts: List[str] = []

        if has_explicit_negation:
            hybrid_score = 0.0
            rationale_parts.append(
                f"Explicit negation detected in candidate evidence ({negation_snippet!r}); zero credit awarded."
            )
        elif is_only_aspirational:
            hybrid_score = 0.0
            rationale_parts.append(
                f"Candidate evidence contains aspirational phrasing ({rejected_semantic_reasons[0]!r}); "
                "no positive skill credit awarded."
            )
        elif strongest_lexical is not None:
            lex_score = strongest_lexical.lexical_score
            sem_sim = max(0.0, strongest_semantic.similarity_score) if strongest_semantic else 0.0

            if strongest_lexical.match_type in ["EXACT", "ALIAS"]:
                hybrid_score = (WEIGHT_LEXICAL_EXACT * lex_score) + (WEIGHT_SEMANTIC_WITH_LEX * sem_sim)
                rationale_parts.append(
                    f"{strongest_lexical.match_type} lexical match ({strongest_lexical.matched_keyword!r}) "
                    f"supported by contextual semantic similarity ({sem_sim:.2f})."
                )
            else:  # FUZZY
                hybrid_score = (WEIGHT_LEXICAL_FUZZY * lex_score) + (WEIGHT_SEMANTIC_FUZZY * sem_sim)
                rationale_parts.append(
                    f"Fuzzy lexical match ({strongest_lexical.matched_keyword!r} -> {strongest_lexical.evidence_text!r}, score {lex_score:.2f}) "
                    f"balanced with semantic similarity ({sem_sim:.2f})."
                )
        else:
            # --- SEMANTIC-ONLY SAFETY GUARDRAILS ---
            # When lexical evidence is completely absent:
            hybrid_score, guardrail_rationale = self._evaluate_semantic_only(requirement, strongest_semantic)
            rationale_parts.append(guardrail_rationale)

        # Ensure bounds [0.0, 1.0]
        hybrid_score = max(0.0, min(1.0, float(hybrid_score)))

        # 6. Experience Duration Verification (Technology/Domain Specific)
        required_years: Optional[float] = getattr(requirement, 'min_years', None)
        candidate_years: Optional[float] = None
        experience_satisfied: Optional[bool] = None

        if required_years is not None and required_years > 0.0 and hybrid_score > 0.0:
            candidate_years = self._calculate_candidate_experience_years(requirement, profile, strongest_lexical)
            domain_label = requirement.experience_domain or req_text

            if candidate_years is not None:
                if candidate_years >= required_years:
                    experience_satisfied = True
                    rationale_parts.append(
                        f"Experience requirement satisfied: candidate has {candidate_years:.1f} verified years for {domain_label!r} (required {required_years:.1f}+ years)."
                    )
                else:
                    experience_satisfied = False
                    ratio = candidate_years / required_years
                    hybrid_score = hybrid_score * ratio
                    rationale_parts.append(
                        f"Partial experience: candidate has {candidate_years:.1f} verified years for {domain_label!r} of required {required_years:.1f}+ years (tenure ratio {ratio:.2f})."
                    )
            else:
                # Skill is present, but technology-specific duration is unverified in employment history
                experience_satisfied = False
                hybrid_score = min(hybrid_score * EXPERIENCE_UNVERIFIED_DURATION_MULTIPLIER, EXPERIENCE_UNVERIFIED_MAX_SCORE)
                rationale_parts.append(
                    f"Skill present, but technology-specific duration for {domain_label!r} ({required_years:.1f}+ years) is unverified in employment history."
                )

        # 6b. Evidence Claim Scope Audit (Technology Presence != Experience Scope)
        from app.services.coach.evidence.claim_scope import evaluate_claim_scope

        all_ev_texts = [m.evidence_text for m in lexical_matches if m.evidence_text] + [m.evidence_text for m in valid_semantic_matches if m.evidence_text]
        cand_techs = set(profile.technologies) if profile.technologies else set()
        for sk in (profile.skills or []):
            cand_techs.add(sk)
        for sd in (profile.skill_details or []):
            cand_techs.add(sd.name)

        scope_audit = evaluate_claim_scope(
            evidence_texts=all_ev_texts,
            requirement_text=req_text,
            candidate_technologies=cand_techs
        )

        scope_satisfied = True
        if scope_audit.demands_higher_scope and not scope_audit.scope_satisfied:
            scope_satisfied = False
            # Operational or architectural scope required, but candidate only has technology presence/exposure
            # MUST NOT be MATCHED
            hybrid_score = min(hybrid_score, VERDICT_PARTIAL_THRESHOLD - 0.05)
            rationale_parts.append(
                f"Scope distinction: {scope_audit.rationale}"
            )

        # 7. Determine Verdict (applied after requirement-specific semantics)
        if hybrid_score >= VERDICT_MATCHED_THRESHOLD and (experience_satisfied is not False) and (scope_satisfied is not False):
            verdict = MatchVerdict.MATCHED
        elif hybrid_score >= VERDICT_PARTIAL_THRESHOLD:
            verdict = MatchVerdict.PARTIAL
        else:
            verdict = MatchVerdict.MISSING

        # 8. Preserve Best Provenance
        best_evidence: Optional[Evidence] = None
        if strongest_lexical and strongest_lexical.evidence:
            best_evidence = strongest_lexical.evidence
        elif strongest_semantic and strongest_semantic.evidence:
            best_evidence = strongest_semantic.evidence

        return RequirementEvaluationResult(
            requirement_id=req_id,
            requirement_text=req_text,
            category=requirement.category,
            priority=requirement.priority,
            is_required=is_req,
            verdict=verdict,
            hybrid_score=round(hybrid_score, 4),
            strongest_lexical=strongest_lexical,
            strongest_semantic=strongest_semantic,
            all_lexical_matches=lexical_matches,
            all_semantic_matches=semantic_matches,
            required_years=required_years,
            candidate_years=candidate_years,
            experience_satisfied=experience_satisfied,
            rationale=" ".join(rationale_parts),
            is_aspirational_or_negated=(has_explicit_negation or is_only_aspirational),
            evidence=best_evidence
        )

    def _evaluate_semantic_only(
        self,
        requirement: JDRequirement,
        strongest_semantic: Optional[SemanticMatchResult]
    ) -> Tuple[float, str]:
        """
        Evaluates pure semantic matching when lexical match is absent.
        Guarantees that semantic similarity alone cannot invent possession of concrete skills,
        credentials, degrees, or quantified requirements.
        """
        if strongest_semantic is None or strongest_semantic.similarity_score < SEMANTIC_MIN_THRESHOLD:
            return 0.0, "No sufficient lexical or semantic evidence found in candidate profile."

        sem_sim = strongest_semantic.similarity_score
        cat = requirement.category
        req_text = requirement.requirement_text

        # Guardrail 1: Certifications require concrete credential evidence
        if cat == RequirementCategory.CERTIFICATION:
            return 0.0, (
                f"Certification requirement ({req_text!r}) requires concrete credential evidence; "
                f"semantic proximity ({sem_sim:.2f}) from general experience cannot substitute for a credential."
            )

        # Guardrail 2: Academic degrees require concrete educational qualification evidence
        if cat == RequirementCategory.EDUCATION:
            return 0.0, (
                f"Academic degree requirement ({req_text!r}) requires concrete qualification evidence; "
                f"semantic proximity ({sem_sim:.2f}) cannot substitute for an educational degree."
            )

        # Guardrail 3: Concrete named technical tools/languages require lexical/alias evidence.
        # Conceptual / architectural / domain requirements (e.g. "container orchestration", "microservices")
        # permit legitimate conceptual semantic matching.
        concrete_techs = extract_all_technologies(req_text)
        if not concrete_techs and requirement.extracted_keywords:
            # Check if any extracted keyword is a registered canonical technology
            from app.services.keyword_matcher import get_canonical_name
            concrete_techs = [
                kw for kw in requirement.extracted_keywords 
                if get_canonical_name(kw) is not None and kw.lower() not in GENERIC_EXPERIENCE_STOPWORDS
            ]

        if cat == RequirementCategory.SKILL and concrete_techs:
            return 0.0, (
                f"Concrete technical skill requirement ({', '.join(concrete_techs)!r}) requires lexical/alias evidence; "
                f"general semantic proximity ({sem_sim:.2f}) cannot prove possession of the specific skill."
            )

        # Guardrail 4: Conceptual / Domain / Architectural requirements (e.g. "container orchestration" -> "Kubernetes")
        # Legitimate conceptual matching is permitted
        hybrid_score = WEIGHT_SEMANTIC_ONLY * sem_sim
        return hybrid_score, (
            f"Conceptual semantic match ({strongest_semantic.evidence_text!r}, similarity {sem_sim:.2f}) "
            "satisfies conceptual/domain requirement without literal keyword match."
        )

    def _check_explicit_negation(
        self,
        requirement: JDRequirement,
        profile: CandidateProfile
    ) -> Tuple[bool, Optional[str]]:
        """
        Scans candidate profile for explicit negative statements regarding the required skill.
        e.g. "No experience with Python", "Never worked with Java".
        """
        target_terms: List[str] = []
        if requirement.experience_domain:
            target_terms.append(requirement.experience_domain)
        if requirement.extracted_keywords:
            target_terms.extend(requirement.extracted_keywords)
        target_terms.extend(extract_all_technologies(requirement.requirement_text))
        if not target_terms and requirement.requirement_text:
            target_terms.append(requirement.requirement_text)

        clean_terms = [t.strip() for t in target_terms if len(t.strip()) >= 2 and t.strip().lower() not in GENERIC_EXPERIENCE_STOPWORDS]
        if not clean_terms:
            return False, None

        evidence_items = self.keyword_matcher._gather_candidate_evidence(profile)
        for ev_text, _, _ in evidence_items:
            for pattern in NEGATION_PATTERNS:
                if pattern.search(ev_text):
                    for term in clean_terms:
                        boundary_pat = KeywordMatcher.build_boundary_pattern(term)
                        if boundary_pat.search(ev_text):
                            return True, ev_text

        return False, None

    def _calculate_candidate_experience_years(
        self,
        requirement: JDRequirement,
        profile: CandidateProfile,
        lexical_match: Optional[KeywordMatchResult]
    ) -> Optional[float]:
        """
        Calculates verified technology/domain-specific experience duration in years
        based on candidate's structured employment history.
        Does NOT confuse total career tenure with technology-specific experience.
        """
        if not profile.experience:
            return None

        # Build clean target terms for the specific technology/domain
        target_terms: Set[str] = set()
        if requirement.experience_domain:
            target_terms.add(requirement.experience_domain.strip())
        if requirement.extracted_keywords:
            for kw in requirement.extracted_keywords:
                clean_kw = kw.strip()
                if clean_kw.lower() not in GENERIC_EXPERIENCE_STOPWORDS and len(clean_kw) >= 2:
                    target_terms.add(clean_kw)
        if lexical_match:
            target_terms.add(lexical_match.matched_keyword.strip())

        # Also add technologies extracted from requirement text
        for t in extract_all_technologies(requirement.requirement_text):
            target_terms.add(t.strip())

        if not target_terms:
            # Fallback to non-stopwords from requirement text
            for w in requirement.requirement_text.split():
                clean_w = w.strip(".,;:()[]").lower()
                if len(clean_w) > 2 and clean_w not in GENERIC_EXPERIENCE_STOPWORDS:
                    target_terms.add(clean_w)

        if not target_terms:
            return None

        # Prepare boundary-safe regex patterns for domain terms
        patterns = [KeywordMatcher.build_boundary_pattern(t) for t in target_terms]

        total_months = 0.0
        has_matched_domain_entry = False

        for exp in profile.experience:
            # Search entry text for domain/technology terms
            entry_text = f"{exp.role or ''} {exp.company or ''} {exp.description or ''} {' '.join(exp.technologies)}"
            
            is_domain_match = any(p.search(entry_text) for p in patterns)
            if is_domain_match:
                has_matched_domain_entry = True
                if exp.duration_months is not None and exp.duration_months > 0:
                    total_months += exp.duration_months

        # Only return years if at least one experience entry verified this specific domain
        if has_matched_domain_entry and total_months > 0.0:
            return total_months / 12.0

        return None
