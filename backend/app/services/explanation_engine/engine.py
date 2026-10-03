from typing import List, Dict, Tuple
from app.schemas.domain import (
    JobDescription,
    MatchVerdict
)
from app.schemas.scoring import (
    CandidateRankingResult,
    RequirementEvaluationResult,
    ScoreBreakdown
)
from app.schemas.explanation import (
    CandidateExplanation,
    RequirementExplanation,
    EvidenceReference
)
from app.services.hybrid_evaluator.constants import (
    WEIGHT_PRIORITY_REQUIRED,
    WEIGHT_PRIORITY_PREFERRED
)
from .evidence_selector import EvidenceSelector
from .templates import ExplanationTemplates

class ExplanationEngine:
    """
    Evidence-First Explanation Engine.
    Translates structured Phase 7 scoring and evidence outputs into concise,
    factual, recruiter-readable explanations without independent matching or LLM inference.
    """

    def __init__(self):
        self.evidence_selector = EvidenceSelector()
        self.templates = ExplanationTemplates()

    def explain_candidate(
        self,
        ranking_result: CandidateRankingResult,
        job_description: JobDescription
    ) -> CandidateExplanation:
        """
        Generates a comprehensive, evidence-backed CandidateExplanation for a ranked candidate.
        """
        evaluations = ranking_result.evaluations or []
        breakdown = ranking_result.score_breakdown
        rank = ranking_result.rank
        overall_score = ranking_result.score.overall_score
        is_top_3 = (rank <= 3)

        # Calculate total weight to determine each requirement's exact point contribution
        total_weight = sum(
            WEIGHT_PRIORITY_REQUIRED if ev.is_required else WEIGHT_PRIORITY_PREFERRED
            for ev in evaluations
        )
        if total_weight == 0.0:
            total_weight = 1.0

        matched_reqs: List[RequirementExplanation] = []
        partial_reqs: List[RequirementExplanation] = []
        missing_required_reqs: List[RequirementExplanation] = []
        missing_preferred_reqs: List[RequirementExplanation] = []

        all_candidate_evidence_refs: List[EvidenceReference] = []

        for ev in evaluations:
            # 1. Select concise supporting evidence
            ev_refs = self.evidence_selector.select_requirement_evidence(ev)
            all_candidate_evidence_refs.extend(ev_refs)

            # 2. Calculate exact mathematical point contribution to overall score (0-100 scale)
            w = WEIGHT_PRIORITY_REQUIRED if ev.is_required else WEIGHT_PRIORITY_PREFERRED
            contribution = (w * ev.hybrid_score / total_weight) * 100.0

            # 3. Generate natural-language requirement explanation
            explanation_text = self.templates.explain_requirement(ev, ev_refs)

            req_exp = RequirementExplanation(
                requirement_id=ev.requirement_id,
                requirement_text=ev.requirement_text,
                category=ev.category,
                priority=ev.priority,
                is_required=ev.is_required,
                verdict=ev.verdict,
                requirement_score=ev.hybrid_score,
                contribution_to_score=round(contribution, 2),
                explanation=explanation_text,
                supporting_evidence=ev_refs
            )

            # Categorize requirement
            if ev.verdict == MatchVerdict.MATCHED:
                matched_reqs.append(req_exp)
            elif ev.verdict == MatchVerdict.PARTIAL:
                partial_reqs.append(req_exp)
            else:  # MISSING
                if ev.is_required:
                    missing_required_reqs.append(req_exp)
                else:
                    missing_preferred_reqs.append(req_exp)

        # 4. Deduplicate evidence for candidate-level display
        deduped_evidence = self.evidence_selector.deduplicate_evidence(all_candidate_evidence_refs)

        # 5. Extract top strengths
        strengths = self.templates.extract_top_strengths(evaluations)

        # 6. Generate "Why ranked here?" explanation
        matched_required_names = [r.requirement_text for r in matched_reqs if r.is_required]
        missing_required_names = [r.requirement_text for r in missing_required_reqs]
        why_ranked_here = self.templates.generate_why_ranked_here(
            rank=rank,
            overall_score=overall_score,
            breakdown=breakdown,
            matched_required=matched_required_names,
            missing_required=missing_required_names,
            is_top_3=is_top_3
        )

        # 7. Candidate Summary
        cand_name = ranking_result.candidate_name or ranking_result.candidate_id
        summary = (
            f"Candidate {cand_name} ranks #{rank} with an overall score of {overall_score:.1f}/100. "
            f"Satisfies {breakdown.matched_count}/{breakdown.total_requirements} requirements "
            f"({breakdown.required_matched_count}/{breakdown.required_total_count} required criteria fully matched, "
            f"{breakdown.partial_count} partial, {breakdown.missing_count} missing)."
        )

        return CandidateExplanation(
            candidate_id=ranking_result.candidate_id,
            candidate_name=ranking_result.candidate_name,
            rank=rank,
            overall_score=overall_score,
            is_top_3=is_top_3,
            why_ranked_here=why_ranked_here,
            summary=summary,
            strengths=strengths,
            matched_requirements=matched_reqs,
            partial_requirements=partial_reqs,
            missing_required_requirements=missing_required_reqs,
            missing_preferred_requirements=missing_preferred_reqs,
            score_breakdown=breakdown,
            all_evidence=deduped_evidence
        )

    def explain_all(
        self,
        ranked_candidates: List[CandidateRankingResult],
        job_description: JobDescription
    ) -> List[CandidateExplanation]:
        """
        Generates explanations for all ranked candidates.
        """
        return [self.explain_candidate(cand, job_description) for cand in ranked_candidates]
