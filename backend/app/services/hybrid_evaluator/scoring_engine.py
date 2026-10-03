from typing import List, Dict, Tuple
from app.schemas.candidate import CandidateProfile
from app.schemas.domain import (
    JobDescription,
    CandidateScore,
    RequirementCategory,
    MatchVerdict
)
from app.schemas.scoring import (
    RequirementEvaluationResult,
    ScoreBreakdown
)
from .requirement_evaluator import RequirementEvaluator
from .constants import (
    WEIGHT_PRIORITY_REQUIRED,
    WEIGHT_PRIORITY_PREFERRED
)

class ScoringEngine:
    """
    Evaluates all requirements of a JobDescription against a CandidateProfile,
    producing an overall normalized candidate score (0-100) and traceable score breakdown.
    Every score is mathematically reproducible without opaque magic numbers or bonuses.
    """

    def __init__(self, requirement_evaluator: RequirementEvaluator):
        self.requirement_evaluator = requirement_evaluator

    def score_candidate(
        self,
        job_description: JobDescription,
        profile: CandidateProfile
    ) -> Tuple[CandidateScore, ScoreBreakdown, List[RequirementEvaluationResult], List[str], List[str]]:
        """
        Computes the candidate's score and full evaluation details against the job description.
        Returns:
            (CandidateScore, ScoreBreakdown, List[RequirementEvaluationResult], matched_skills, missing_skills)
        """
        evaluations: List[RequirementEvaluationResult] = []
        requirements = job_description.requirements or []

        if not requirements:
            score = CandidateScore(
                candidate_id=profile.candidate_id,
                overall_score=0.0,
                required_score=0.0,
                preferred_score=0.0,
                semantic_score=0.0,
                keyword_score=0.0,
                experience_score=0.0,
                qualification_score=0.0,
                penalty_applied=0.0
            )
            breakdown = ScoreBreakdown(overall_score=0.0)
            return score, breakdown, [], [], []

        for req in requirements:
            res = self.requirement_evaluator.evaluate_requirement(req, profile)
            evaluations.append(res)

        # Calculate weighted overall score
        total_weight = 0.0
        weighted_points = 0.0

        required_scores: List[float] = []
        preferred_scores: List[float] = []
        keyword_scores: List[float] = []
        semantic_scores: List[float] = []

        category_points: Dict[str, List[float]] = {}
        experience_req_points: List[float] = []
        qualification_req_points: List[float] = []

        matched_skills: List[str] = []
        missing_skills: List[str] = []

        matched_count = 0
        partial_count = 0
        missing_count = 0
        req_matched_count = 0
        req_total_count = 0

        for ev in evaluations:
            w = WEIGHT_PRIORITY_REQUIRED if ev.is_required else WEIGHT_PRIORITY_PREFERRED
            total_weight += w
            weighted_points += (w * ev.hybrid_score)

            if ev.is_required:
                required_scores.append(ev.hybrid_score)
                req_total_count += 1
                if ev.verdict == MatchVerdict.MATCHED:
                    req_matched_count += 1
            else:
                preferred_scores.append(ev.hybrid_score)

            # Component contributions
            if ev.strongest_lexical:
                keyword_scores.append(ev.strongest_lexical.lexical_score)
            else:
                keyword_scores.append(0.0)

            if ev.strongest_semantic:
                semantic_scores.append(max(0.0, ev.strongest_semantic.similarity_score))
            else:
                semantic_scores.append(0.0)

            # Category tracking
            cat_name = ev.category.value if hasattr(ev.category, 'value') else str(ev.category)
            if cat_name not in category_points:
                category_points[cat_name] = []
            category_points[cat_name].append(ev.hybrid_score)

            # Experience-specific requirements (category == EXPERIENCE or min_years specified)
            if ev.category == RequirementCategory.EXPERIENCE or (ev.required_years is not None and ev.required_years > 0):
                experience_req_points.append(ev.hybrid_score)

            # Qualification-specific requirements (EDUCATION or CERTIFICATION)
            if ev.category in [RequirementCategory.EDUCATION, RequirementCategory.CERTIFICATION]:
                qualification_req_points.append(ev.hybrid_score)

            # Skills listing and verdict counters
            req_label = ev.requirement_text
            if ev.verdict == MatchVerdict.MATCHED:
                matched_count += 1
                matched_skills.append(req_label)
            elif ev.verdict == MatchVerdict.PARTIAL:
                partial_count += 1
                matched_skills.append(f"{req_label} (Partial)")
            else:
                missing_count += 1
                missing_skills.append(req_label)

        # Normalize overall score to 0-100 scale: (weighted_points / total_weight) * 100
        overall_score = (weighted_points / total_weight * 100.0) if total_weight > 0.0 else 0.0
        overall_score = max(0.0, min(100.0, overall_score))

        # Normalized component scores (0-100 scale)
        norm_required_score = (sum(required_scores) / len(required_scores) * 100.0) if required_scores else 0.0
        norm_preferred_score = (sum(preferred_scores) / len(preferred_scores) * 100.0) if preferred_scores else 0.0
        norm_keyword_score = (sum(keyword_scores) / len(keyword_scores) * 100.0) if keyword_scores else 0.0
        norm_semantic_score = (sum(semantic_scores) / len(semantic_scores) * 100.0) if semantic_scores else 0.0

        # Experience score: genuine average of experience-bearing requirements, or 0.0 if none
        norm_exp_score = (sum(experience_req_points) / len(experience_req_points) * 100.0) if experience_req_points else 0.0

        # Qualification score: genuine average of education/certification requirements, or 0.0 if none
        norm_qual_score = (sum(qualification_req_points) / len(qualification_req_points) * 100.0) if qualification_req_points else 0.0

        # Category scores map
        cat_scores_map = {
            cat: round(sum(pts) / len(pts) * 100.0, 2)
            for cat, pts in category_points.items()
        }

        candidate_score = CandidateScore(
            candidate_id=profile.candidate_id,
            overall_score=round(overall_score, 2),
            required_score=round(norm_required_score, 2),
            preferred_score=round(norm_preferred_score, 2),
            semantic_score=round(norm_semantic_score, 2),
            keyword_score=round(norm_keyword_score, 2),
            experience_score=round(norm_exp_score, 2),
            qualification_score=round(norm_qual_score, 2),
            penalty_applied=0.0
        )

        breakdown = ScoreBreakdown(
            overall_score=round(overall_score, 2),
            required_score=round(norm_required_score, 2),
            preferred_score=round(norm_preferred_score, 2),
            keyword_contribution=round(norm_keyword_score, 2),
            semantic_contribution=round(norm_semantic_score, 2),
            category_scores=cat_scores_map,
            total_requirements=len(requirements),
            matched_count=matched_count,
            partial_count=partial_count,
            missing_count=missing_count,
            required_matched_count=req_matched_count,
            required_total_count=req_total_count
        )

        return candidate_score, breakdown, evaluations, matched_skills, missing_skills
