from typing import List, Optional, Set, Tuple
from app.schemas.scoring import RequirementEvaluationResult
from app.schemas.domain import MatchVerdict
from app.schemas.explanation import EvidenceReference

FRIENDLY_EVIDENCE_TYPES = {
    "skill": "Technical Skill",
    "experience": "Work Experience",
    "project": "Project",
    "education": "Education",
    "certification": "Certification",
    "summary": "Professional Summary"
}

class EvidenceSelector:
    """
    Selects concise, high-quality supporting evidence from structured evaluation results.
    Does NOT perform matching or scoring; maps existing structured evidence to recruiter-readable references.
    """

    @classmethod
    def get_friendly_evidence_type(cls, raw_type: Optional[str]) -> str:
        if not raw_type:
            return "Resume Evidence"
        return FRIENDLY_EVIDENCE_TYPES.get(raw_type.lower(), raw_type.title())

    @classmethod
    def select_requirement_evidence(
        cls,
        eval_result: RequirementEvaluationResult
    ) -> List[EvidenceReference]:
        """
        Extracts up to 2 top supporting evidence references for a single requirement:
        1. Strongest lexical evidence (exact / alias / fuzzy)
        2. Strongest semantic evidence (if complementary and non-duplicate)
        Returns an empty list if verdict is MISSING.
        """
        if eval_result.verdict == MatchVerdict.MISSING:
            return []

        refs: List[EvidenceReference] = []
        seen_texts: Set[str] = set()

        # 1. Strongest lexical evidence
        if eval_result.strongest_lexical is not None:
            lex = eval_result.strongest_lexical
            clean_text = lex.evidence_text.strip()
            if clean_text:
                seen_texts.add(clean_text.lower())
                refs.append(
                    EvidenceReference(
                        evidence_text=clean_text,
                        evidence_type=cls.get_friendly_evidence_type(lex.evidence_type),
                        source_section=lex.source_section,
                        page_number=lex.page_number,
                        source_text=lex.source_text,
                        match_method=lex.match_type,
                        lexical_score=lex.lexical_score,
                        semantic_score=round(eval_result.strongest_semantic.similarity_score, 2) if eval_result.strongest_semantic else None
                    )
                )

        # 2. Strongest semantic evidence (if different text and non-aspirational/non-negative)
        if eval_result.strongest_semantic is not None and not eval_result.is_aspirational_or_negated:
            sem = eval_result.strongest_semantic
            clean_text = sem.evidence_text.strip()
            if clean_text and clean_text.lower() not in seen_texts:
                seen_texts.add(clean_text.lower())
                method = "SEMANTIC_CONCEPTUAL" if not eval_result.strongest_lexical else "SEMANTIC_CONTEXT"
                refs.append(
                    EvidenceReference(
                        evidence_text=clean_text,
                        evidence_type=cls.get_friendly_evidence_type(sem.evidence_type),
                        source_section=sem.source_section,
                        page_number=sem.page_number,
                        source_text=sem.source_text,
                        match_method=method,
                        lexical_score=None,
                        semantic_score=round(sem.similarity_score, 2)
                    )
                )

        return refs

    @classmethod
    def deduplicate_evidence(
        cls,
        evidence_list: List[EvidenceReference]
    ) -> List[EvidenceReference]:
        """
        Deduplicates candidate evidence references while preserving exact provenance.
        """
        deduped: List[EvidenceReference] = []
        seen: Set[Tuple[str, str, Optional[int]]] = set()

        for ref in evidence_list:
            key = (ref.evidence_text.lower().strip(), ref.evidence_type, ref.page_number)
            if key not in seen:
                seen.add(key)
                deduped.append(ref)

        return deduped
