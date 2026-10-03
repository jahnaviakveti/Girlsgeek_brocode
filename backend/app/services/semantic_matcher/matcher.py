import numpy as np
from typing import List, Optional, Tuple
from app.schemas.candidate import CandidateProfile
from app.schemas.domain import JDRequirement, Evidence
from app.schemas.semantic_matching import SemanticMatchResult
from .embeddings import EmbeddingModel
from .similarity import batch_cosine_similarity

class SemanticMatcher:
    def __init__(self, embedding_model: EmbeddingModel):
        self.model = embedding_model

    def evaluate_requirement(self, requirement: JDRequirement, profile: CandidateProfile) -> List[SemanticMatchResult]:
        """
        Evaluate a single JDRequirement against a CandidateProfile and return semantic match evidence.
        Candidate evidence is encoded in a single batch for efficient inference.
        """
        req_text = self._get_requirement_text(requirement)
        if not req_text or not req_text.strip():
            return []
            
        candidate_evidence = self._extract_evidence(profile)
        if not candidate_evidence:
            return []
            
        # Filter out empty or whitespace-only evidence texts
        valid_evidence: List[Tuple[str, str, Optional[Evidence]]] = [
            (text.strip(), etype, prov) 
            for text, etype, prov in candidate_evidence 
            if text and text.strip()
        ]
        if not valid_evidence:
            return []

        # 1. Encode requirement text
        req_embedding = self.model.encode_one(req_text.strip())
        if req_embedding.size == 0:
            return []

        # 2. Batch encode candidate evidence texts
        evidence_texts = [item[0] for item in valid_evidence]
        batch_embeddings = self.model.encode(evidence_texts)
        if batch_embeddings.size == 0:
            return []

        # 3. Compute cosine similarities in batch
        sims = batch_cosine_similarity(req_embedding, batch_embeddings)

        # 4. Construct SemanticMatchResult with preserved provenance
        results = []
        for i, (text, evidence_type, provenance) in enumerate(valid_evidence):
            sim = float(sims[i]) if i < len(sims) else 0.0
            
            # Extract actual provenance fields from the domain Evidence model
            page_num = provenance.page_number if provenance else None
            sec_name = provenance.source_section if provenance else None
            src_text = provenance.source_text if provenance and hasattr(provenance, 'source_text') else None
            
            res = SemanticMatchResult(
                requirement_id=str(requirement.id) if hasattr(requirement, 'id') else "req",
                evidence_id=None,  # Domain Evidence has no stable ID; do not fabricate one
                requirement_text=req_text.strip(),
                evidence_text=text,
                similarity_score=sim,
                page_number=page_num,
                source_section=sec_name,
                source_text=src_text,
                evidence_type=evidence_type,
                evidence=provenance
            )
            results.append(res)
            
        # Sort by similarity descending
        results.sort(key=lambda x: x.similarity_score, reverse=True)
        return results
        
    def _get_requirement_text(self, requirement: JDRequirement) -> str:
        if hasattr(requirement, 'requirement_text') and requirement.requirement_text:
            return requirement.requirement_text
        return ""
        
    def _extract_evidence(self, profile: CandidateProfile) -> List[Tuple[str, str, Optional[Evidence]]]:
        """
        Extract strings of evidence and their provenance from the profile.
        Returns List of (text, evidence_type, Evidence object or None).
        Consumes the existing Evidence model and CandidateProfile structure.
        """
        evidence_list: List[Tuple[str, str, Optional[Evidence]]] = []
        
        # 1. Skills
        for skill in profile.skill_details:
            text = skill.name or skill.raw_name
            if text:
                evidence_list.append((text, "skill", skill.evidence))
                
        # 2. Experience
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
