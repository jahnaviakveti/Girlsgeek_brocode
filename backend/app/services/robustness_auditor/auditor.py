import uuid
import datetime
from typing import List, Dict, Tuple, Optional

from app.schemas.candidate import CandidateProfile
from app.schemas.domain import JobDescription
from app.schemas.scoring import CandidateRankingResult
from app.schemas.robustness import (
    RankingRobustnessAudit,
    PerturbationRunResult,
    CandidateAuditEntry,
    AuditCaseProvenance,
    PerturbationType,
    RobustnessClassification
)
from app.services.hybrid_evaluator import RankingService
from .perturbations import (
    BasePerturbation,
    LexicalNormalizationPerturbation,
    KeywordMaskingPerturbation,
    FormattingNormalizationPerturbation,
)
from .metrics import (
    compute_top_k_overlap,
    compute_spearman_rank_correlation,
    compute_rank_displacements,
    compute_pairwise_flips,
    compute_keyword_dependence_index,
)

class RankingRobustnessAuditor:
    """
    Deterministic Diagnostic Auditor for Evaluating Ranking Robustness.
    Compares baseline candidate ranking with controlled perturbation representations
    (lexical normalization, keyword masking, formatting normalization)
    without modifying production scoring code or model weights.
    """

    def __init__(
        self,
        ranking_service: RankingService,
        perturbations: Optional[List[BasePerturbation]] = None
    ):
        self.ranking_service = ranking_service
        self.perturbations = perturbations or [
            LexicalNormalizationPerturbation(),
            KeywordMaskingPerturbation(),
            FormattingNormalizationPerturbation(),
        ]

    def audit(
        self,
        job_description: JobDescription,
        profiles: List[CandidateProfile]
    ) -> RankingRobustnessAudit:
        """
        Executes complete robustness audit for a job description and candidate profiles batch.
        """
        audit_id = f"audit_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        job_title = job_description.title or "Target Position"

        if not profiles:
            return RankingRobustnessAudit(
                audit_id=audit_id,
                timestamp=timestamp,
                candidate_count=0,
                job_title=job_title,
                baseline_ranking=[],
                perturbation_runs=[],
                overall_top3_overlap=1.0,
                overall_top5_overlap=1.0,
                overall_rank_correlation=1.0,
                overall_average_rank_displacement=0.0,
                overall_max_rank_displacement=0,
                total_pairwise_flips=0,
                keyword_dependence_indicator=0.0,
                robustness_status=RobustnessClassification.ROBUST,
                status_interpretation_note="Zero candidate profiles supplied; vacuous baseline audit.",
                limitations=["No candidates provided to evaluate."],
                audit_cases=[]
            )

        # 1. Run Baseline Ranking
        baseline_ranked: List[CandidateRankingResult] = self.ranking_service.rank_candidates(job_description, profiles)
        baseline_ranks: Dict[str, int] = {r.candidate_id: r.rank for r in baseline_ranked}
        baseline_scores: Dict[str, float] = {r.candidate_id: r.score.overall_score for r in baseline_ranked}
        baseline_names: Dict[str, str] = {r.candidate_id: (r.candidate_name or r.candidate_id) for r in baseline_ranked}
        baseline_ordered_ids: List[str] = [r.candidate_id for r in baseline_ranked]

        baseline_entries: List[CandidateAuditEntry] = [
            CandidateAuditEntry(
                candidate_id=cid,
                candidate_name=baseline_names[cid],
                baseline_rank=baseline_ranks[cid],
                baseline_score=baseline_scores[cid],
                perturbed_rank=baseline_ranks[cid],
                perturbed_score=baseline_scores[cid],
                absolute_rank_displacement=0,
                signed_rank_displacement=0,
                score_delta=0.0
            )
            for cid in baseline_ordered_ids
        ]

        # 2. Run Controlled Perturbations
        run_results: List[PerturbationRunResult] = []
        all_provenance_cases: List[AuditCaseProvenance] = []
        keyword_dep_index: float = 0.0

        for pert in self.perturbations:
            pert_profiles: List[CandidateProfile] = []
            run_provenance: List[AuditCaseProvenance] = []

            for p in profiles:
                cloned_p, prov = pert.perturb(p, job_description)
                pert_profiles.append(cloned_p)
                run_provenance.extend(prov)

            # Re-rank perturbed profiles using existing production ranking service
            pert_ranked: List[CandidateRankingResult] = self.ranking_service.rank_candidates(job_description, pert_profiles)
            pert_ranks: Dict[str, int] = {r.candidate_id: r.rank for r in pert_ranked}
            pert_scores: Dict[str, float] = {r.candidate_id: r.score.overall_score for r in pert_ranked}
            pert_ordered_ids: List[str] = [r.candidate_id for r in pert_ranked]

            # Compute displacements and audit entries
            displacements = compute_rank_displacements(baseline_ranks, pert_ranks)
            abs_displacements = [disp[0] for disp in displacements.values()]
            avg_abs_disp = round(float(sum(abs_displacements) / len(abs_displacements)), 2) if abs_displacements else 0.0
            max_abs_disp = max(abs_displacements) if abs_displacements else 0

            top3 = compute_top_k_overlap(baseline_ordered_ids, pert_ordered_ids, 3)
            top5 = compute_top_k_overlap(baseline_ordered_ids, pert_ordered_ids, 5)
            rho = compute_spearman_rank_correlation(baseline_ranks, pert_ranks)
            flips = compute_pairwise_flips(baseline_ranks, pert_ranks)

            kdi: Optional[float] = None
            if pert.perturbation_type == PerturbationType.KEYWORD_MASKING:
                kdi = compute_keyword_dependence_index(baseline_scores, pert_scores)
                keyword_dep_index = kdi

            # Enrich provenance cases with rank displacement info
            for pc in run_provenance:
                cid = pc.candidate_id
                pc.baseline_rank = baseline_ranks.get(cid, 0)
                pc.perturbed_rank = pert_ranks.get(cid, 0)
                pc.rank_displacement = displacements.get(cid, (0, 0))[1]

            all_provenance_cases.extend(run_provenance)

            perturbed_entries = [
                CandidateAuditEntry(
                    candidate_id=cid,
                    candidate_name=baseline_names[cid],
                    baseline_rank=baseline_ranks[cid],
                    baseline_score=baseline_scores[cid],
                    perturbed_rank=pert_ranks.get(cid, 0),
                    perturbed_score=pert_scores.get(cid, 0.0),
                    absolute_rank_displacement=displacements.get(cid, (0, 0))[0],
                    signed_rank_displacement=displacements.get(cid, (0, 0))[1],
                    score_delta=round(pert_scores.get(cid, 0.0) - baseline_scores[cid], 2)
                )
                for cid in pert_ordered_ids
            ]

            run_result = PerturbationRunResult(
                perturbation_type=pert.perturbation_type,
                description=pert.description,
                total_candidates=len(profiles),
                perturbed_rankings=perturbed_entries,
                top3_overlap=top3,
                top5_overlap=top5,
                rank_correlation=rho,
                average_absolute_rank_displacement=avg_abs_disp,
                max_absolute_rank_displacement=max_abs_disp,
                pairwise_ranking_flips=flips,
                keyword_dependence_indicator=kdi,
                provenance_cases=run_provenance
            )
            run_results.append(run_result)

        # 3. Aggregate Overall Summary Metrics
        avg_top3 = round(sum(r.top3_overlap for r in run_results) / len(run_results), 4) if run_results else 1.0
        avg_top5 = round(sum(r.top5_overlap for r in run_results) / len(run_results), 4) if run_results else 1.0
        avg_rho = round(sum(r.rank_correlation for r in run_results) / len(run_results), 4) if run_results else 1.0
        avg_disp = round(sum(r.average_absolute_rank_displacement for r in run_results) / len(run_results), 2) if run_results else 0.0
        overall_max_disp = max((r.max_absolute_rank_displacement for r in run_results), default=0)
        total_flips = sum(r.pairwise_ranking_flips for r in run_results)

        # 4. Determine Robustness Classification (Engineering Interpretation Thresholds)
        # Note: These qualitative bands are project engineering interpretation thresholds, not universal laws.
        if avg_rho >= 0.85 and avg_top3 >= 0.67:
            status = RobustnessClassification.ROBUST
            note = "High ranking stability: rankings exhibit strong correlation (rho >= 0.85) and high Top-3 retention across lexical perturbations."
        elif avg_rho >= 0.60:
            status = RobustnessClassification.MODERATELY_SENSITIVE
            note = "Moderate ranking sensitivity: overall candidate tiering is preserved (0.60 <= rho < 0.85), but minor rank shifts occur under keyword or representation changes."
        else:
            status = RobustnessClassification.HIGHLY_SENSITIVE
            note = "High ranking sensitivity: rankings fluctuate substantially (rho < 0.60) under lexical alterations, indicating heavy dependence on surface keyword phrasing."

        limitations = [
            "Deterministic perturbations cover known canonical equivalence aliases; uncataloged proprietary acronyms remain unperturbed.",
            "Synthetic keyword masking measures upper-bound sensitivity; actual recruiter CV variation is more nuanced than uniform token redaction.",
            "Paraphrase variations relying on generative LLM transformation were excluded to prevent hallucination of ungrounded candidate claims.",
            "Tie-breaking jitter between candidates with near-identical composite scores can produce minor rank displacements without denoting material semantic mismatch."
        ]

        return RankingRobustnessAudit(
            audit_id=audit_id,
            timestamp=timestamp,
            candidate_count=len(profiles),
            job_title=job_title,
            baseline_ranking=baseline_entries,
            perturbation_runs=run_results,
            overall_top3_overlap=avg_top3,
            overall_top5_overlap=avg_top5,
            overall_rank_correlation=avg_rho,
            overall_average_rank_displacement=avg_disp,
            overall_max_rank_displacement=overall_max_disp,
            total_pairwise_flips=total_flips,
            keyword_dependence_indicator=keyword_dep_index,
            robustness_status=status,
            status_interpretation_note=note,
            limitations=limitations,
            audit_cases=all_provenance_cases
        )
