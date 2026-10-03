import re
from typing import List, Optional, Dict, Any, Set
from app.schemas.candidate import CandidateProfile
from app.schemas.career_twin import CareerTwin
from app.schemas.evidence_vault import EvidenceVault, VaultEvidenceItem
from app.schemas.domain import JobDescription, MatchVerdict, RequirementCategory, RequirementPriority
from app.schemas.coach_api import JobFitAnalysisResponse
from app.schemas.scoring import CandidateRankingResult, RequirementEvaluationResult
from app.schemas.explanation import RequirementExplanation, EvidenceReference
from app.schemas.job_fit import (
    JobFitAnalysis,
    JobFitRequirement,
    JobFitEvidenceCitation,
    JobFitEvidenceGap,
    JobFitStrength,
    JobFitImprovementOpportunity,
    JobFitSummary,
    RequirementStatus,
    GapType,
)
from app.services.jd_analyzer import JDAnalyzer, JDBiasDetector
from app.services.keyword_matcher import KeywordMatcher
from app.services.semantic_matcher import LocalSentenceTransformerEmbeddingModel, SemanticMatcher
from app.services.hybrid_evaluator import RequirementEvaluator, ScoringEngine
from app.services.explanation_engine import ExplanationEngine
from app.services.jd_analyzer.taxonomy import extract_all_technologies

SOFT_SKILL_KEYWORDS = {
    "communication", "verbal", "written", "interpersonal", "collaborative",
    "collaboration", "team player", "leadership", "adaptable", "adaptability",
    "problem solving", "fast-paced", "self-starter", "self-motivated",
    "detail-oriented", "passion", "passionate", "critical thinking",
    "positive attitude", "work ethic", "time management", "conflict resolution"
}

class JobFitService:
    """
    Evaluates candidate-to-job fit and gap analysis.
    Leverages existing Vettora hybrid evaluation engine while formatting insights
    for candidate self-improvement rather than recruiter screening.
    Never predicts hiring chances or fabricates evidence.
    """

    def __init__(
        self,
        embedding_model: Optional[LocalSentenceTransformerEmbeddingModel] = None,
        jd_analyzer: Optional[JDAnalyzer] = None,
        bias_detector: Optional[JDBiasDetector] = None,
        keyword_matcher: Optional[KeywordMatcher] = None,
    ):
        self.embedding_model = embedding_model or LocalSentenceTransformerEmbeddingModel()
        self.jd_analyzer = jd_analyzer or JDAnalyzer()
        self.bias_detector = bias_detector or JDBiasDetector()
        self.keyword_matcher = keyword_matcher or KeywordMatcher()
        self.semantic_matcher = SemanticMatcher(self.embedding_model)
        self.evaluator = RequirementEvaluator(self.keyword_matcher, self.semantic_matcher)
        self.scoring_engine = ScoringEngine(self.evaluator)
        self.explanation_engine = ExplanationEngine()

    def evaluate_fit(
        self,
        profile: CandidateProfile,
        jd: JobDescription,
        twin: Optional[CareerTwin] = None,
        vault: Optional[EvidenceVault] = None,
        raw_jd_text: Optional[str] = None
    ) -> JobFitAnalysisResponse:
        """
        Executes bidirectional candidate-centric fit analysis between candidate profile and target JD.
        Integrates directly with persisted CareerTwin and EvidenceVault without reparsing resume.
        """
        # 1. Run core hybrid scoring engine
        score, breakdown, evaluations, matched_skills, missing_skills = self.scoring_engine.score_candidate(jd, profile)

        # 2. Package candidate ranking result for explanation generation
        ranking_result = CandidateRankingResult(
            rank=1,
            candidate_id=profile.candidate_id,
            candidate_name=profile.name,
            score=score,
            score_breakdown=breakdown,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            evaluations=evaluations,
        )
        candidate_exp = self.explanation_engine.explain_candidate(ranking_result, jd)

        # 3. Inclusivity and bias audit on the target JD
        bias_audit = self.bias_detector.audit_jd(jd, raw_text=raw_jd_text or jd.raw_text)

        # 4. Construct Candidate-Centric JobFitAnalysis model
        job_fit_analysis = self._build_candidate_job_fit(
            profile=profile,
            jd=jd,
            evaluations=evaluations,
            twin=twin,
            vault=vault,
            breakdown=breakdown,
            score=score,
            bias_audit=bias_audit
        )

        # 5. Extract critical gaps and coaching recommendations
        critical_gaps: List[str] = []
        for req in job_fit_analysis.missing_requirements:
            if req.is_required:
                critical_gaps.append(f"Missing required qualification: {req.requirement_text}")

        for req in job_fit_analysis.partial_requirements:
            if req.is_required:
                critical_gaps.append(f"Partial match on required criterion: {req.requirement_text} (Evidence coverage: {req.combined_score * 100:.0f}%)")

        recommended_actions: List[str] = []
        if job_fit_analysis.fit_summary.visibility_gaps_count > 0:
            recommended_actions.append(
                f"You have {job_fit_analysis.fit_summary.visibility_gaps_count} potential resume visibility opportunities where existing project experience can be surfaced more clearly."
            )
        if job_fit_analysis.fit_summary.experience_gaps_count > 0:
            recommended_actions.append(
                "Prioritize developing portfolio projects or hands-on practice for genuine experience gaps."
            )
        if job_fit_analysis.fit_summary.not_verifiable_count > 0:
            recommended_actions.append(
                "Prepare structured STAR stories for non-verifiable behavioral qualities during interview prep."
            )
        if not recommended_actions:
            recommended_actions.append("Your resume provides high evidence coverage for this role. Prepare for deep technical questions on your cited projects.")

        return JobFitAnalysisResponse(
            candidate_id=profile.candidate_id,
            job_title=jd.title or "Target Role",
            fit_score=score.overall_score,
            required_fit_score=score.required_score,
            preferred_fit_score=score.preferred_score,
            score_breakdown=breakdown,
            matched_requirements=candidate_exp.matched_requirements,
            partial_requirements=candidate_exp.partial_requirements,
            missing_required=candidate_exp.missing_required_requirements,
            missing_preferred=candidate_exp.missing_preferred_requirements,
            coaching_summary=job_fit_analysis.fit_summary.narrative,
            top_strengths=[s.title for s in job_fit_analysis.strengths],
            critical_gaps=critical_gaps,
            recommended_actions=recommended_actions,
            evidence_coverage=job_fit_analysis.fit_summary.evidence_coverage_score,
            job_fit_analysis=job_fit_analysis,
            bias_audit=bias_audit,
        )

    def _build_candidate_job_fit(
        self,
        profile: CandidateProfile,
        jd: JobDescription,
        evaluations: List[RequirementEvaluationResult],
        twin: Optional[CareerTwin],
        vault: Optional[EvidenceVault],
        breakdown: Any,
        score: Any,
        bias_audit: Optional[Any]
    ) -> JobFitAnalysis:
        """
        Builds the candidate-facing JobFitAnalysis data model.
        Distinguishes the three types of gaps and maps every claim to verified Evidence Vault citations.
        """
        candidate_requirements: List[JobFitRequirement] = []
        evidence_gaps: List[JobFitEvidenceGap] = []
        improvement_opportunities: List[JobFitImprovementOpportunity] = []
        strengths: List[JobFitStrength] = []

        # Map candidate skills and technologies
        candidate_skills_lower = {s.lower() for s in profile.skills}
        candidate_techs_lower = {t.lower() for t in profile.technologies}
        all_candidate_terms = candidate_skills_lower.union(candidate_techs_lower)

        for eval_res in evaluations:
            req_id = eval_res.requirement_id
            req_text = eval_res.requirement_text
            req_words = set(re.findall(r'\b[a-zA-Z0-9_\-\.\+#]{2,}\b', req_text.lower()))
            category_str = eval_res.category.value if hasattr(eval_res.category, 'value') else str(eval_res.category)
            priority_str = "REQUIRED" if eval_res.is_required else "PREFERRED"
            
            # Map verdict to status
            if eval_res.verdict == MatchVerdict.MATCHED:
                status = RequirementStatus.MATCHED
            elif eval_res.verdict == MatchVerdict.PARTIAL:
                status = RequirementStatus.PARTIAL
            else:
                status = RequirementStatus.MISSING

            lex_matched = bool(eval_res.strongest_lexical and eval_res.strongest_lexical.lexical_score > 0.0)
            sem_matched = bool(eval_res.strongest_semantic and eval_res.strongest_semantic.similarity_score >= 0.45)
            combined_score = float(eval_res.hybrid_score)

            # 1. Collect Supporting Evidence Citations
            evidence_citations: List[JobFitEvidenceCitation] = []
            matched_terms: List[str] = []

            # Check lexical matches
            if eval_res.strongest_lexical and eval_res.strongest_lexical.lexical_score > 0.0:
                matched_terms.append(eval_res.strongest_lexical.matched_keyword)

            # Find matching evidence in vault or evaluation
            if vault:
                # 1. Search vault for citations by matched_terms
                for term in matched_terms:
                    vault_items = vault.technology_index.get(term.lower(), [])
                    for vid in vault_items[:3]:
                        item = next((it for it in vault.items if it.evidence_id == vid), None)
                        if item and not any(c.evidence_id == item.evidence_id for c in evidence_citations):
                            evidence_citations.append(
                                JobFitEvidenceCitation(
                                    evidence_id=item.evidence_id,
                                    source_text=item.source_text,
                                    source_section=item.source_section,
                                    page_number=item.page_number,
                                    entity=item.related_entity,
                                    matched_terms=[term]
                                )
                            )

                # 2. Search vault items for requirement keywords or related skills
                if not evidence_citations:
                    for it in vault.items:
                        it_lower = it.source_text.lower()
                        overlap_words = [w for w in req_words if len(w) > 4 and (w in it_lower or (it.related_skill and w == it.related_skill.lower()))]
                        if overlap_words:
                            evidence_citations.append(
                                JobFitEvidenceCitation(
                                    evidence_id=it.evidence_id,
                                    source_text=it.source_text,
                                    source_section=it.source_section,
                                    page_number=it.page_number,
                                    entity=it.related_entity,
                                    matched_terms=overlap_words
                                )
                            )
                            if len(evidence_citations) >= 2:
                                break

            # 3. Fallback to eval_res.evidence
            if not evidence_citations and eval_res.evidence and (combined_score > 0.25 or matched_terms):
                ev = eval_res.evidence
                ev_id = None
                if vault:
                    found_item = next((it for it in vault.items if it.source_text == ev.source_text), None)
                    if found_item:
                        ev_id = found_item.evidence_id
                evidence_citations.append(
                    JobFitEvidenceCitation(
                        evidence_id=ev_id,
                        source_text=ev.source_text or req_text,
                        source_section=ev.source_section,
                        page_number=ev.page_number or 1,
                        entity=None,
                        matched_terms=matched_terms
                    )
                )

            # If status is MISSING, ensure no citations are fabricated unless candidate has verified related technology
            from app.services.coach.evidence.claim_scope import evaluate_claim_scope
            scope_res_pre = evaluate_claim_scope(
                evidence_texts=[c.source_text for c in evidence_citations],
                requirement_text=req_text,
                candidate_technologies=all_candidate_terms
            )
            if status == RequirementStatus.MISSING:
                if not (scope_res_pre.demands_higher_scope and scope_res_pre.technology_present):
                    evidence_citations = []

            # 2. Extract Missing Elements
            missing_elements: List[str] = []
            for term in req_words:
                if term in all_candidate_terms:
                    continue
                # If term looks like a known skill or substantive noun
                if len(term) >= 3 and term not in {"the", "and", "for", "with", "from", "that", "this", "our", "are", "experience", "skills", "years", "knowledge"}:
                    # Check if term is an unfulfilled technology or keyword
                    if term not in [t.lower() for t in matched_terms]:
                        missing_elements.append(term.capitalize())

            # 3. Experience / Tenure verification
            required_months = (eval_res.required_years * 12.0) if eval_res.required_years else None
            verified_months = None
            tenure_gap_months = None

            if required_months and twin:
                # Look up verified tenure in twin
                verified_months = 0.0
                for node in twin.skill_nodes:
                    if node.name.lower() in req_text.lower() and node.verified_tenure_months:
                        verified_months = max(verified_months, node.verified_tenure_months)
                if verified_months == 0.0:
                    verified_months = eval_res.candidate_years * 12.0 if eval_res.candidate_years else 0.0

                if verified_months < required_months:
                    tenure_gap_months = round(required_months - verified_months, 1)

            # 4. Classify Gap Type (Section 4)
            gap_type = None
            candidate_action = ""
            explanation = eval_res.rationale or ""

            scope_res = evaluate_claim_scope(
                evidence_texts=[c.source_text for c in evidence_citations],
                requirement_text=req_text,
                candidate_technologies=all_candidate_terms
            )

            if status == RequirementStatus.MATCHED:
                gap_type = None
                candidate_action = "Requirement verified from resume evidence. Highlight this accomplishment in your interview."
                if not explanation:
                    explanation = f"Direct supporting evidence verified for {req_text}."
            else:
                # Check for NOT_VERIFIABLE (Soft skills / behavioral)
                is_soft_skill = any(sw in req_text.lower() for sw in SOFT_SKILL_KEYWORDS)
                has_concrete_tech = bool(extract_all_technologies(req_text))

                if is_soft_skill and not has_concrete_tech:
                    gap_type = GapType.NOT_VERIFIABLE
                    explanation = "Not verifiable from current resume evidence. Behavioral and interpersonal qualities cannot be proven directly on a technical CV."
                    candidate_action = "Prepare concrete behavioral examples (STAR method) to demonstrate this during your interview rather than adding ungrounded claims."

                # Check for Operational / Scope Mismatch: Technology Presence != Experience Scope
                elif scope_res.demands_higher_scope and not scope_res.scope_satisfied:
                    gap_type = GapType.EXPERIENCE_GAP
                    tech_desc = f"exposure to '{scope_res.matched_technology}'" if scope_res.matched_technology else "related technology mentions"
                    explanation = f"Experience gap: Your Evidence Vault contains {tech_desc}, but no verified evidence for '{req_text}' (e.g. production cluster management or infrastructure operations). This cannot be resolved by resume rephrasing."
                    candidate_action = f"Do not add '{req_text}' to your resume unless you have genuine hands-on experience. Build a project or gain experience before claiming this qualification."

                # Check for Tenure Gap
                elif tenure_gap_months and tenure_gap_months > 0:
                    gap_type = GapType.EXPERIENCE_GAP
                    explanation = f"Experience gap: Required tenure ({int(required_months)} months) exceeds verified tenure ({int(verified_months)} months) for {req_text}."
                    candidate_action = f"Gain additional verified experience in {req_text} before claiming full senior tenure."

                # Check for RESUME_VISIBILITY_GAP (partial evidence, or candidate has related technology evidence in vault)
                elif status == RequirementStatus.PARTIAL or len(evidence_citations) > 0:
                    gap_type = GapType.RESUME_VISIBILITY_GAP
                    missing_str = ", ".join(missing_elements) if missing_elements else "this qualification"
                    explanation = f"Potential resume visibility gap: Your existing project and experience evidence indicates related background, but your current wording does not explicitly surface {missing_str}."
                    candidate_action = f"If you have actually worked on this in your past projects or roles, update your resume bullet points to surface {missing_str} explicitly."

                # Otherwise Genuine EXPERIENCE_GAP
                else:
                    gap_type = GapType.EXPERIENCE_GAP
                    missing_str = ", ".join(missing_elements) if missing_elements else req_text
                    explanation = f"Experience gap — no supporting evidence was found in your resume for {missing_str}."
                    candidate_action = f"Do not add {missing_str} to your resume unless you have genuine hands-on experience. Build a project or gain experience before claiming this qualification."

            # Update explanation if tenure gap exists
            if tenure_gap_months and tenure_gap_months > 0:
                explanation += f" (Required: {int(required_months)} months, Verified: {int(verified_months)} months, Evidence gap: {int(tenure_gap_months)} months)."

            fit_req = JobFitRequirement(
                requirement_id=req_id,
                requirement_text=req_text,
                category=category_str,
                priority=priority_str,
                is_required=eval_res.is_required,
                status=status,
                lexical_match=lex_matched,
                semantic_match=sem_matched,
                combined_score=round(combined_score, 2),
                evidence=evidence_citations,
                missing_evidence=missing_elements,
                explanation=explanation,
                candidate_action=candidate_action,
                gap_type=gap_type,
                required_months=required_months,
                verified_months=verified_months,
                tenure_gap_months=tenure_gap_months
            )
            candidate_requirements.append(fit_req)

            # Record Evidence Gap and Improvement Opportunity if not fully matched
            if status != RequirementStatus.MATCHED and gap_type:
                can_rewrite = (gap_type == GapType.RESUME_VISIBILITY_GAP)
                gap_id = f"gap_{req_id}"
                
                evidence_gaps.append(
                    JobFitEvidenceGap(
                        gap_id=gap_id,
                        requirement_id=req_id,
                        requirement_text=req_text,
                        gap_type=gap_type,
                        priority=priority_str,
                        missing_elements=missing_elements,
                        existing_related_evidence=evidence_citations,
                        explanation=explanation,
                        action_recommendation=candidate_action,
                        can_rewrite_resume=can_rewrite
                    )
                )

                # Prepare Handoff Payload for Resume Coach (Section 14)
                handoff_payload = {
                    "candidate_id": profile.candidate_id,
                    "requirement_id": req_id,
                    "requirement_text": req_text,
                    "target_role": jd.title or "Target Role",
                    "priority": priority_str,
                    "gap_type": gap_type.value,
                    "can_rewrite": can_rewrite,
                    "evidence_ids": [c.evidence_id for c in evidence_citations if c.evidence_id],
                    "existing_evidence_snippets": [c.source_text for c in evidence_citations],
                    "missing_elements": missing_elements,
                    "action_prompt": f"Explicitly surface {', '.join(missing_elements) or req_text} within existing experience if genuinely performed."
                }

                improvement_opportunities.append(
                    JobFitImprovementOpportunity(
                        opportunity_id=f"opp_{req_id}",
                        requirement_id=req_id,
                        requirement_text=req_text,
                        priority=priority_str,
                        status=status,
                        gap_type=gap_type,
                        current_evidence=evidence_citations,
                        missing_elements=missing_elements,
                        candidate_action=candidate_action,
                        can_improve_via_rewriting=can_rewrite,
                        handoff_payload=handoff_payload
                    )
                )

            # Record Strengths for Matched Requirements (Section 8)
            elif status == RequirementStatus.MATCHED and combined_score >= 0.70:
                ev_ids = [c.evidence_id for c in evidence_citations if c.evidence_id]
                first_entity = evidence_citations[0].entity if evidence_citations else None
                first_section = evidence_citations[0].source_section if evidence_citations else "Resume"
                
                if first_entity:
                    strength_title = f"Verified {req_text} experience in {first_entity}"
                else:
                    strength_title = f"Strong evidence for {req_text}"

                strengths.append(
                    JobFitStrength(
                        strength_id=f"str_{req_id}",
                        title=strength_title,
                        explanation=f"Directly demonstrated in {first_section} with high verified confidence.",
                        evidence_ids=ev_ids,
                        supporting_evidence=evidence_citations
                    )
                )

        # 5. Partition by status and priority
        req_required = [r for r in candidate_requirements if r.is_required]
        req_preferred = [r for r in candidate_requirements if not r.is_required]

        matched_reqs = [r for r in candidate_requirements if r.status == RequirementStatus.MATCHED]
        partial_reqs = [r for r in candidate_requirements if r.status == RequirementStatus.PARTIAL]
        missing_reqs = [r for r in candidate_requirements if r.status == RequirementStatus.MISSING]

        # 6. Compute Evidence Coverage Summary (Section 7)
        total_reqs = max(1, len(candidate_requirements))
        supported_points = len(matched_reqs) + (0.5 * len(partial_reqs))
        evidence_coverage_pct = round((supported_points / total_reqs) * 100, 1)

        req_matched_count = len([r for r in req_required if r.status == RequirementStatus.MATCHED])
        pref_matched_count = len([r for r in req_preferred if r.status == RequirementStatus.MATCHED])

        vis_gaps_count = len([g for g in evidence_gaps if g.gap_type == GapType.RESUME_VISIBILITY_GAP])
        exp_gaps_count = len([g for g in evidence_gaps if g.gap_type == GapType.EXPERIENCE_GAP])
        not_verif_count = len([g for g in evidence_gaps if g.gap_type == GapType.NOT_VERIFIABLE])

        if evidence_coverage_pct >= 75.0:
            evidence_strength = "Strong"
        elif evidence_coverage_pct >= 50.0:
            evidence_strength = "Moderate"
        else:
            evidence_strength = "Developing"

        narrative = (
            f"Your resume currently demonstrates verified evidence for {req_matched_count}/{len(req_required)} "
            f"required criteria and {pref_matched_count}/{len(req_preferred)} preferred criteria "
            f"({evidence_coverage_pct:.0f}% evidence coverage). "
        )
        if vis_gaps_count > 0:
            narrative += f"Identified {vis_gaps_count} resume visibility opportunities where existing project experience can be surfaced more clearly."

        summary = JobFitSummary(
            evidence_coverage_score=evidence_coverage_pct,
            requirement_coverage_score=round(score.overall_score, 1),
            evidence_strength=evidence_strength,
            required_total=len(req_required),
            required_matched=req_matched_count,
            preferred_total=len(req_preferred),
            preferred_matched=pref_matched_count,
            visibility_gaps_count=vis_gaps_count,
            experience_gaps_count=exp_gaps_count,
            not_verifiable_count=not_verif_count,
            narrative=narrative
        )

        return JobFitAnalysis(
            target_role=jd.title or "Target Role",
            company=getattr(jd, "company", None),
            requirements=candidate_requirements,
            required_requirements=req_required,
            preferred_requirements=req_preferred,
            matched_requirements=matched_reqs,
            partial_requirements=partial_reqs,
            missing_requirements=missing_reqs,
            evidence_gaps=evidence_gaps,
            strengths=strengths,
            improvement_opportunities=improvement_opportunities,
            bias_warnings=bias_audit,
            fit_summary=summary
        )
