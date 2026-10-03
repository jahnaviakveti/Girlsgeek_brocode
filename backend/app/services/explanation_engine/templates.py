from typing import List, Optional
from app.schemas.domain import (
    RequirementCategory,
    RequirementPriority,
    MatchVerdict
)
from app.schemas.scoring import (
    RequirementEvaluationResult,
    ScoreBreakdown
)
from app.schemas.explanation import EvidenceReference

class ExplanationTemplates:
    """
    Deterministic rule-based templates for generating recruiter-readable explanations.
    Uses conservative language when evidence is missing or uncertain.
    Strictly forbids unsupported claims.
    """

    @classmethod
    def explain_requirement(
        cls,
        eval_result: RequirementEvaluationResult,
        evidence_refs: List[EvidenceReference]
    ) -> str:
        """
        Generates a concise, evidence-backed explanation for a single requirement evaluation.
        """
        req_text = eval_result.requirement_text
        verdict = eval_result.verdict
        cat = eval_result.category

        # --- 1. MATCHED VERDICT ---
        if verdict == MatchVerdict.MATCHED:
            # Experience tenure verified
            if eval_result.candidate_years is not None and eval_result.required_years is not None:
                domain_str = eval_result.strongest_lexical.matched_keyword if eval_result.strongest_lexical else req_text
                return (
                    f"Matched. Candidate provides verified professional experience in {domain_str} "
                    f"({eval_result.candidate_years:.1f} years, meeting the {eval_result.required_years:.1f}+ years requirement)."
                )

            # Lexical match
            if eval_result.strongest_lexical is not None:
                lex = eval_result.strongest_lexical
                source_info = f" in {lex.source_section}" if lex.source_section else ""
                if lex.page_number:
                    source_info += f" (page {lex.page_number})"

                if lex.match_type == "EXACT":
                    return f"Matched. Candidate lists {lex.matched_keyword!r}{source_info} and demonstrates relevant usage."
                elif lex.match_type == "ALIAS":
                    return f"Matched via alias. Candidate demonstrates {lex.evidence_text!r} (recognized canonical {lex.matched_keyword!r}){source_info}."
                else:  # FUZZY
                    return f"Matched. Candidate provides {lex.evidence_text!r} (spelling variation of {lex.matched_keyword!r}){source_info}."

            # Pure conceptual match
            if eval_result.strongest_semantic is not None:
                sem = eval_result.strongest_semantic
                return (
                    f"Matched conceptually. Candidate demonstrates strong conceptual experience with {sem.evidence_text!r} "
                    f"(semantic similarity {sem.similarity_score:.2f}) aligning with {req_text!r}."
                )

            return f"Matched. Sufficient evidence found in candidate profile for {req_text!r}."

        # --- 2. PARTIAL VERDICT ---
        if verdict == MatchVerdict.PARTIAL:
            # Partial experience duration (insufficient years)
            if eval_result.candidate_years is not None and eval_result.required_years is not None:
                domain_str = eval_result.strongest_lexical.matched_keyword if eval_result.strongest_lexical else req_text
                return (
                    f"Partial match. Candidate has {eval_result.candidate_years:.1f} verified years with {domain_str}, "
                    f"which is below the required {eval_result.required_years:.1f}+ years."
                )

            # Skill present, but duration unverified in employment history
            if eval_result.required_years is not None and eval_result.candidate_years is None:
                return (
                    f"Partial match. {req_text!r} is listed in candidate profile, but the required "
                    f"{eval_result.required_years:.1f}+ years duration could not be verified from employment history."
                )

            # Pure conceptual semantic match without literal keyword
            if eval_result.strongest_semantic is not None and not eval_result.strongest_lexical:
                sem = eval_result.strongest_semantic
                return (
                    f"Partial match. Candidate demonstrates related experience via {sem.evidence_text!r} "
                    f"(semantic similarity {sem.similarity_score:.2f}), though explicit literal keyword for {req_text!r} was not found."
                )

            # Fuzzy match or moderate lexical evidence
            if eval_result.strongest_lexical is not None:
                return f"Partial match. Candidate references related term {eval_result.strongest_lexical.evidence_text!r} with moderate contextual alignment."

            return f"Partial match. Some relevant evidence found for {req_text!r}, but does not fully satisfy all criteria."

        # --- 3. MISSING VERDICT ---
        # Explicit negation detected
        if eval_result.is_aspirational_or_negated and any("negation" in eval_result.rationale.lower() or "no experience" in eval_result.rationale.lower() for _ in [1]):
            return f"Missing. Candidate explicitly states a lack of experience with {req_text!r}."

        # Aspirational mention only
        if eval_result.is_aspirational_or_negated:
            return f"Missing. Candidate mentions an interest or future aspiration to learn {req_text!r}, but active professional capability was not evidenced."

        # Category-specific missing phrasing (conservative, avoids claiming absolute absence)
        if cat == RequirementCategory.CERTIFICATION:
            return f"Missing. Required certification {req_text!r} was not found in candidate certifications."
        elif cat == RequirementCategory.EDUCATION:
            return f"Missing. Educational qualification {req_text!r} was not found in candidate academic history."
        else:
            return f"Missing. Supporting evidence was not found for required skill {req_text!r} in candidate profile."

    @classmethod
    def generate_why_ranked_here(
        cls,
        rank: int,
        overall_score: float,
        breakdown: ScoreBreakdown,
        matched_required: List[str],
        missing_required: List[str],
        is_top_3: bool
    ) -> str:
        """
        Generates a concise 'Why ranked here?' explanation reflecting the exact Phase 7 score structure.
        """
        req_matched = breakdown.required_matched_count
        req_total = breakdown.required_total_count
        total_matched = breakdown.matched_count
        total_reqs = breakdown.total_requirements

        if rank == 1:
            if missing_required:
                return (
                    f"Ranked #1 with overall score {overall_score:.1f}/100. Demonstrates top performance across requirements "
                    f"({req_matched}/{req_total} required matched), outperforming other candidates despite partial coverage on {missing_required[0]!r}."
                )
            return (
                f"Ranked #1 with top overall score {overall_score:.1f}/100. Fully satisfies all mandatory requirements "
                f"({req_matched}/{req_total} required) with verified experience and strong complementary skill coverage."
            )

        if rank in [2, 3]:
            gap_summary = f"unverified required skill {missing_required[0]!r}" if missing_required else "lower overall evidence depth"
            return (
                f"Ranked #{rank} with overall score {overall_score:.1f}/100. Strong candidate satisfying {req_matched}/{req_total} "
                f"required criteria, ranking behind Rank #{rank - 1} primarily due to {gap_summary}."
            )

        # Lower-ranked candidates
        if req_matched == 0 and total_matched == 0:
            return f"Ranked #{rank} with score {overall_score:.1f}/100 due to absence of matching evidence for core requirements."

        return (
            f"Ranked #{rank} with score {overall_score:.1f}/100. Matched {req_matched}/{req_total} required requirements; "
            f"limited by {len(missing_required)} missing mandatory criteria."
        )

    @classmethod
    def extract_top_strengths(
        cls,
        evaluations: List[RequirementEvaluationResult]
    ) -> List[str]:
        """
        Extracts up to 4 key evidence-backed strengths.
        Only generates claims directly supported by structured evaluations.
        """
        strengths: List[str] = []

        # 1. Verified experience requirements
        for ev in evaluations:
            if ev.verdict == MatchVerdict.MATCHED and ev.candidate_years is not None and ev.required_years is not None:
                domain = ev.strongest_lexical.matched_keyword if ev.strongest_lexical else ev.requirement_text
                strengths.append(
                    f"Verified {ev.candidate_years:.1f} years professional experience in {domain} (required {ev.required_years:.1f}+ years)"
                )
                if len(strengths) >= 4:
                    return strengths

        # 2. Fully matched required skills
        matched_req_skills = [
            ev.strongest_lexical.matched_keyword if ev.strongest_lexical else ev.requirement_text
            for ev in evaluations
            if ev.is_required and ev.verdict == MatchVerdict.MATCHED
        ]
        if matched_req_skills:
            if len(matched_req_skills) <= 3:
                strengths.append(f"Direct match on mandatory technical skills: {', '.join(matched_req_skills)}")
            else:
                strengths.append(f"Direct match on {len(matched_req_skills)} mandatory skills including {', '.join(matched_req_skills[:3])}")
            if len(strengths) >= 4:
                return strengths

        # 3. Conceptual matches
        for ev in evaluations:
            if ev.verdict == MatchVerdict.MATCHED and not ev.strongest_lexical and ev.strongest_semantic:
                strengths.append(
                    f"Strong conceptual match for {ev.requirement_text!r} supported by {ev.strongest_semantic.evidence_text!r}"
                )
                if len(strengths) >= 4:
                    return strengths

        # 4. Matched preferred skills
        matched_pref_skills = [
            ev.strongest_lexical.matched_keyword if ev.strongest_lexical else ev.requirement_text
            for ev in evaluations
            if not ev.is_required and ev.verdict == MatchVerdict.MATCHED
        ]
        if matched_pref_skills:
            strengths.append(f"Bonus qualification on preferred skills: {', '.join(matched_pref_skills[:3])}")

        return strengths[:4]
