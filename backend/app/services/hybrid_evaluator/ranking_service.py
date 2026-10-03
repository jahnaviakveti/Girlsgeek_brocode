from typing import List
from app.schemas.candidate import CandidateProfile
from app.schemas.domain import JobDescription, CandidateRanking
from app.schemas.scoring import CandidateRankingResult
from .scoring_engine import ScoringEngine

class RankingService:
    """
    Ranks a collection of CandidateProfiles against a JobDescription deterministically.
    """

    def __init__(self, scoring_engine: ScoringEngine):
        self.scoring_engine = scoring_engine

    def rank_candidates(
        self,
        job_description: JobDescription,
        candidates: List[CandidateProfile]
    ) -> List[CandidateRankingResult]:
        """
        Evaluates and ranks all candidates best-to-worst.
        Guarantees:
        - Every candidate receives a score and a rank
        - No candidate is dropped
        - Ties are broken deterministically
        """
        if not candidates:
            return []

        scored_candidates: List[CandidateRankingResult] = []

        for candidate in candidates:
            score, breakdown, evaluations, matched_skills, missing_skills = self.scoring_engine.score_candidate(
                job_description,
                candidate
            )

            # Structured summary explanation
            cand_name = candidate.name or candidate.candidate_id
            explanation = (
                f"Candidate {cand_name}: Overall Score {score.overall_score:.1f}/100 "
                f"(Required: {score.required_score:.1f}%, Preferred: {score.preferred_score:.1f}%). "
                f"Matched {breakdown.matched_count}/{breakdown.total_requirements} requirements, "
                f"{breakdown.partial_count} partial, {breakdown.missing_count} missing."
            )

            result = CandidateRankingResult(
                rank=0,  # placeholder before sorting
                candidate_id=candidate.candidate_id,
                candidate_name=candidate.name,
                score=score,
                score_breakdown=breakdown,
                matched_skills=matched_skills,
                missing_skills=missing_skills,
                evaluations=evaluations,
                explanation=explanation
            )
            scored_candidates.append(result)

        # Deterministic Sorting:
        # 1. Overall score descending
        # 2. Required requirements score descending (mandatory skills priority)
        # 3. Experience score descending
        # 4. Number of fully matched requirements descending
        # 5. Candidate ID alphabetical ascending (stable tie-break)
        scored_candidates.sort(
            key=lambda r: (
                -r.score.overall_score,
                -r.score.required_score,
                -r.score.experience_score,
                -r.score_breakdown.matched_count,
                r.candidate_id
            )
        )

        # Assign 1-indexed ranks
        for idx, item in enumerate(scored_candidates, start=1):
            item.rank = idx

        return scored_candidates
