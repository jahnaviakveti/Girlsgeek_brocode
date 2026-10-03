import re
import copy
from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Optional, Set

from app.schemas.candidate import CandidateProfile, CandidateSkill, CandidateExperience, CandidateProject
from app.schemas.domain import JobDescription, Evidence
from app.schemas.robustness import PerturbationType, AuditCaseProvenance

# Canonical bidirectional lexical pairs for perturbation testing
LEXICAL_EQUIVALENCE_PAIRS: Dict[str, str] = {
    "nodejs": "Node.js",
    "node.js": "NodeJS",
    "node js": "Node.js",
    "postgres": "PostgreSQL",
    "postgresql": "Postgres",
    "k8s": "Kubernetes",
    "kubernetes": "k8s",
    "cpp": "C++",
    "c++": "cpp",
    "golang": "Go",
    "reactjs": "React.js",
    "react.js": "ReactJS",
    "react js": "React.js",
    "vuejs": "Vue.js",
    "vue.js": "VueJS",
    "aws": "Amazon Web Services",
    "gcp": "Google Cloud Platform",
}

# Precompile single-pass regex to avoid re-substituting already replaced tokens
_SORTED_LEXICAL_KEYS = sorted(LEXICAL_EQUIVALENCE_PAIRS.keys(), key=len, reverse=True)
_LEXICAL_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _SORTED_LEXICAL_KEYS) + r")\b",
    flags=re.IGNORECASE
)

class BasePerturbation(ABC):
    """Abstract base class for deterministic candidate representation perturbations."""
    
    @property
    @abstractmethod
    def perturbation_type(self) -> PerturbationType:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @abstractmethod
    def perturb(
        self,
        profile: CandidateProfile,
        jd: JobDescription
    ) -> Tuple[CandidateProfile, List[AuditCaseProvenance]]:
        """
        Creates a perturbed clone of CandidateProfile and records transformation provenance.
        Must NOT mutate the original profile.
        """
        pass

class LexicalNormalizationPerturbation(BasePerturbation):
    """
    Applies deterministic lexical equivalence replacements (e.g. Postgres <-> PostgreSQL, k8s <-> Kubernetes)
    to test whether rankings remain stable under synonymous lexical representations.
    """

    @property
    def perturbation_type(self) -> PerturbationType:
        return PerturbationType.LEXICAL_NORMALIZATION

    @property
    def description(self) -> str:
        return "Deterministic lexical normalization of equivalent technology representations (e.g., Postgres <-> PostgreSQL, k8s <-> Kubernetes)."

    def perturb(
        self,
        profile: CandidateProfile,
        jd: JobDescription
    ) -> Tuple[CandidateProfile, List[AuditCaseProvenance]]:
        p = profile.model_copy(deep=True)
        provenance_list: List[AuditCaseProvenance] = []

        def _sub_handler(match: re.Match) -> str:
            token = match.group(0).lower()
            return LEXICAL_EQUIVALENCE_PAIRS.get(token, match.group(0))

        def transform_text(text: str, field_name: str) -> str:
            if not text:
                return text
            original = text
            transformed = _LEXICAL_PATTERN.sub(_sub_handler, text)
            
            if transformed != original:
                provenance_list.append(
                    AuditCaseProvenance(
                        candidate_id=p.candidate_id,
                        candidate_name=p.name or "Unknown Candidate",
                        perturbation_type=self.perturbation_type,
                        original_text=original,
                        transformed_text=transformed,
                        transformation_reason=f"Lexical equivalence normalization on {field_name}",
                        baseline_rank=0,
                        perturbed_rank=0,
                        rank_displacement=0
                    )
                )
            return transformed

        # 1. Transform Skills and Technologies
        if p.skills:
            p.skills = [transform_text(s, "skill") for s in p.skills]
        if p.technologies:
            p.technologies = [transform_text(t, "technology") for t in p.technologies]
        if p.skill_details:
            for s in p.skill_details:
                s.name = transform_text(s.name, "skill_detail_name")
                if hasattr(s, "raw_name") and s.raw_name:
                    s.raw_name = transform_text(s.raw_name, "skill_detail_raw_name")
                if s.evidence and s.evidence.source_text:
                    s.evidence.source_text = transform_text(s.evidence.source_text, "skill_evidence")

        # 2. Transform Experiences
        if p.experience:
            for exp in p.experience:
                if hasattr(exp, "role") and exp.role:
                    exp.role = transform_text(exp.role, "experience_role")
                if hasattr(exp, "title") and getattr(exp, "title", None):
                    exp.title = transform_text(exp.title, "experience_title")
                if exp.description:
                    exp.description = transform_text(exp.description, "experience_description")
                if exp.technologies:
                    exp.technologies = [transform_text(t, "experience_tech") for t in exp.technologies]
                if hasattr(exp, "achievements") and exp.achievements:
                    exp.achievements = [transform_text(a, "experience_achievement") for a in exp.achievements]
                if exp.evidence and exp.evidence.source_text:
                    exp.evidence.source_text = transform_text(exp.evidence.source_text, "experience_evidence")

        # 3. Transform Projects
        if p.projects:
            for proj in p.projects:
                if proj.name:
                    proj.name = transform_text(proj.name, "project_name")
                if proj.description:
                    proj.description = transform_text(proj.description, "project_description")
                if proj.technologies:
                    proj.technologies = [transform_text(t, "project_tech") for t in proj.technologies]

        # 4. Transform Sections
        if p.sections:
            p.sections = {sec: transform_text(txt, f"section_{sec}") for sec, txt in p.sections.items()}

        return p, provenance_list

class KeywordMaskingPerturbation(BasePerturbation):
    """
    Redacts explicit target keywords from candidate text with neutral token '[MASKED_SKILL]'.
    Evaluates semantic preservation and quantifies candidate reliance on literal keyword overlap.
    """

    @property
    def perturbation_type(self) -> PerturbationType:
        return PerturbationType.KEYWORD_MASKING

    @property
    def description(self) -> str:
        return "Deterministic masking of explicit JD keyword tokens with '[MASKED_SKILL]' to test pure semantic retention."

    def perturb(
        self,
        profile: CandidateProfile,
        jd: JobDescription
    ) -> Tuple[CandidateProfile, List[AuditCaseProvenance]]:
        p = profile.model_copy(deep=True)
        provenance_list: List[AuditCaseProvenance] = []

        # Collect unique target keywords from JD requirements
        jd_keywords: Set[str] = set()
        for req in (jd.requirements or []):
            for kw in (req.extracted_keywords or []):
                cleaned = kw.strip().lower()
                if len(cleaned) >= 2:
                    jd_keywords.add(cleaned)

        if not jd_keywords:
            return p, []

        # Build regex pattern for boundary-aware keyword matching
        sorted_kws = sorted(list(jd_keywords), key=lambda k: len(k), reverse=True)
        escaped_kws = [re.escape(k) for k in sorted_kws]
        kw_pattern = re.compile(r"\b(" + "|".join(escaped_kws) + r")\b", flags=re.IGNORECASE)

        def mask_text(text: str, field_name: str) -> str:
            if not text:
                return text
            original = text
            if kw_pattern.search(text):
                transformed = kw_pattern.sub("[MASKED_SKILL]", text)
                if transformed != original:
                    provenance_list.append(
                        AuditCaseProvenance(
                            candidate_id=p.candidate_id,
                            candidate_name=p.name or "Unknown Candidate",
                            perturbation_type=self.perturbation_type,
                            original_text=original,
                            transformed_text=transformed,
                            transformation_reason=f"Target keyword masking on {field_name}",
                            baseline_rank=0,
                            perturbed_rank=0,
                            rank_displacement=0
                        )
                    )
                return transformed
            return text

        # 1. Mask in Skills and Technologies
        if p.skills:
            p.skills = [mask_text(s, "skill") for s in p.skills]
        if p.technologies:
            p.technologies = [mask_text(t, "technology") for t in p.technologies]
        if p.skill_details:
            for s in p.skill_details:
                s.name = mask_text(s.name, "skill_detail_name")
                if hasattr(s, "raw_name") and s.raw_name:
                    s.raw_name = mask_text(s.raw_name, "skill_detail_raw_name")
                if s.evidence and s.evidence.source_text:
                    s.evidence.source_text = mask_text(s.evidence.source_text, "skill_evidence")

        # 2. Mask in Experience
        if p.experience:
            for exp in p.experience:
                if hasattr(exp, "role") and exp.role:
                    exp.role = mask_text(exp.role, "experience_role")
                if hasattr(exp, "title") and getattr(exp, "title", None):
                    exp.title = mask_text(exp.title, "experience_title")
                if exp.description:
                    exp.description = mask_text(exp.description, "experience_description")
                if exp.technologies:
                    exp.technologies = [mask_text(t, "experience_tech") for t in exp.technologies]
                if hasattr(exp, "achievements") and exp.achievements:
                    exp.achievements = [mask_text(a, "experience_achievement") for a in exp.achievements]
                if exp.evidence and exp.evidence.source_text:
                    exp.evidence.source_text = mask_text(exp.evidence.source_text, "experience_evidence")

        # 3. Mask in Projects
        if p.projects:
            for proj in p.projects:
                if proj.name:
                    proj.name = mask_text(proj.name, "project_name")
                if proj.description:
                    proj.description = mask_text(proj.description, "project_description")
                if proj.technologies:
                    proj.technologies = [mask_text(t, "project_tech") for t in proj.technologies]

        # 4. Mask in Sections
        if p.sections:
            p.sections = {sec: mask_text(txt, f"section_{sec}") for sec, txt in p.sections.items()}

        return p, provenance_list

class FormattingNormalizationPerturbation(BasePerturbation):
    """
    Normalizes superficial formatting: collapses redundant whitespace, standardizes bullet punctuation,
    and removes non-standard ASCII ornamentations without modifying semantic words.
    """

    @property
    def perturbation_type(self) -> PerturbationType:
        return PerturbationType.FORMATTING_NORMALIZATION

    @property
    def description(self) -> str:
        return "Superficial formatting normalization: whitespace collapse, bullet standardizing, and punctuation cleanup."

    def perturb(
        self,
        profile: CandidateProfile,
        jd: JobDescription
    ) -> Tuple[CandidateProfile, List[AuditCaseProvenance]]:
        p = profile.model_copy(deep=True)
        provenance_list: List[AuditCaseProvenance] = []

        def clean_formatting(text: str, field_name: str) -> str:
            if not text:
                return text
            original = text
            # Collapse multiple spaces and tabs
            cleaned = re.sub(r"[ \t]+", " ", text)
            # Standardize bullet symbols
            cleaned = re.sub(r"[•▪►*]\s*", "- ", cleaned)
            # Clean leading/trailing spaces per line
            cleaned = "\n".join([line.strip() for line in cleaned.splitlines() if line.strip()])
            
            if cleaned != original:
                provenance_list.append(
                    AuditCaseProvenance(
                        candidate_id=p.candidate_id,
                        candidate_name=p.name or "Unknown Candidate",
                        perturbation_type=self.perturbation_type,
                        original_text=original,
                        transformed_text=cleaned,
                        transformation_reason=f"Whitespace and punctuation formatting normalization on {field_name}",
                        baseline_rank=0,
                        perturbed_rank=0,
                        rank_displacement=0
                    )
                )
            return cleaned

        if p.skills:
            p.skills = [clean_formatting(s, "skill") for s in p.skills]
        if p.technologies:
            p.technologies = [clean_formatting(t, "technology") for t in p.technologies]
        if p.skill_details:
            for s in p.skill_details:
                s.name = clean_formatting(s.name, "skill_detail_name")
                if hasattr(s, "raw_name") and s.raw_name:
                    s.raw_name = clean_formatting(s.raw_name, "skill_detail_raw_name")
                if s.evidence and s.evidence.source_text:
                    s.evidence.source_text = clean_formatting(s.evidence.source_text, "skill_evidence")

        if p.experience:
            for exp in p.experience:
                if hasattr(exp, "role") and exp.role:
                    exp.role = clean_formatting(exp.role, "experience_role")
                if hasattr(exp, "title") and getattr(exp, "title", None):
                    exp.title = clean_formatting(exp.title, "experience_title")
                if exp.description:
                    exp.description = clean_formatting(exp.description, "experience_description")
                if exp.technologies:
                    exp.technologies = [clean_formatting(t, "experience_tech") for t in exp.technologies]
                if hasattr(exp, "achievements") and exp.achievements:
                    exp.achievements = [clean_formatting(a, "experience_achievement") for a in exp.achievements]
                if exp.evidence and exp.evidence.source_text:
                    exp.evidence.source_text = clean_formatting(exp.evidence.source_text, "experience_evidence")

        if p.projects:
            for proj in p.projects:
                if proj.name:
                    proj.name = clean_formatting(proj.name, "project_name")
                if proj.description:
                    proj.description = clean_formatting(proj.description, "project_description")
                if proj.technologies:
                    proj.technologies = [clean_formatting(t, "project_tech") for t in proj.technologies]

        if p.sections:
            p.sections = {sec: clean_formatting(txt, f"section_{sec}") for sec, txt in p.sections.items()}

        return p, provenance_list
