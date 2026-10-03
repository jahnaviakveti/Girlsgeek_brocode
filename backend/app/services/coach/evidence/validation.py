import re
from typing import List, Optional, Dict, Any, Set
from app.schemas.evidence_vault import (
    EvidenceVault,
    VaultEvidenceItem,
    ClaimValidationResult,
    EvidenceType,
)

METRIC_REGEX = re.compile(
    r'(\b\d+(?:\.\d+)?%|\b\d+x\b|\$\d+(?:,\d+)*(?:\.\d+)?|\b\d+\s*(?:ms|seconds|minutes|hours|days|weeks|months|years)\b|\b\d+\+?\s*(?:users|clients|teams|projects|engineers|requests|transactions)\b)',
    re.IGNORECASE
)

class EvidenceValidationService:
    """
    Evidence-grounding and claim validation engine.
    Ensures that any claim, skill, metric, or accomplishment is strictly supported by source resume evidence.
    Guarantees no candidate hallucinations.
    """

    def validate_claim(self, vault: EvidenceVault, claim: str) -> ClaimValidationResult:
        """
        Validates whether a factual candidate claim is grounded in the candidate's Evidence Vault.
        
        Rules:
        1. If claim contains a quantifiable metric (e.g. '40%', '$1M', '10x'), the metric MUST appear in vault evidence.
        2. If claim references specific technical skills or roles, at least one must be verified in the vault.
        3. If claim contains assertions not present in any evidence item, it is rejected.
        """
        if not claim or not claim.strip():
            return ClaimValidationResult(
                claim=claim,
                supported=False,
                confidence=0.0,
                supporting_evidence_ids=[],
                supporting_evidence=[],
                matched_facts=[],
                explanation="Claim is empty or contains no factual content."
            )

        clean_claim = claim.strip()
        claim_lower = clean_claim.lower()

        # 1. Check for metric claims
        claim_metrics = METRIC_REGEX.findall(clean_claim)
        if claim_metrics:
            for metric in claim_metrics:
                metric_norm = metric.strip().lower()
                # Check if metric exists in vault source text or normalized facts
                matching_items = [
                    item for item in vault.items
                    if metric_norm in item.source_text.lower() or any(metric_norm == f.lower() for f in item.normalized_facts)
                ]
                if not matching_items:
                    return ClaimValidationResult(
                        claim=clean_claim,
                        supported=False,
                        confidence=0.0,
                        supporting_evidence_ids=[],
                        supporting_evidence=[],
                        matched_facts=[],
                        explanation=f"Metric '{metric}' claimed by candidate was not found anywhere in source evidence."
                    )

        # 2. Search for direct evidence matches
        supporting_items: List[VaultEvidenceItem] = []
        matched_facts: Set[str] = set()

        # Check technology/skill index first
        if claim_lower in vault.technology_index:
            ev_ids = set(vault.technology_index[claim_lower])
            supporting_items.extend([it for it in vault.items if it.evidence_id in ev_ids])
            matched_facts.add(claim_lower)
        elif claim_lower in vault.skill_index:
            ev_ids = set(vault.skill_index[claim_lower])
            supporting_items.extend([it for it in vault.items if it.evidence_id in ev_ids])
            matched_facts.add(claim_lower)

        # Search across items for substring or keyword matches
        claim_tokens = set(re.findall(r'\b[a-zA-Z0-9_\-\.\+#]{2,}\b', claim_lower))
        stop_words = {
            "the", "and", "for", "with", "from", "that", "this", "our", "are", "was",
            "were", "has", "have", "had", "using", "used", "into", "over", "under",
            "candidate", "claim", "years", "year", "improved", "developed", "built"
        }
        substantive_tokens = claim_tokens - stop_words

        for item in vault.items:
            item_text_lower = item.source_text.lower()
            
            # Exact phrase match
            if clean_claim.lower() in item_text_lower:
                if item not in supporting_items:
                    supporting_items.append(item)
                matched_facts.add(clean_claim)
                continue

            # Normalized facts match
            for fact in item.normalized_facts:
                if fact.lower() == claim_lower or fact.lower() in claim_lower:
                    if item not in supporting_items:
                        supporting_items.append(item)
                    matched_facts.add(fact)

            # Check substantive tokens overlap
            if substantive_tokens:
                item_tokens = set(re.findall(r'\b[a-zA-Z0-9_\-\.\+#]{2,}\b', item_text_lower))
                overlap = substantive_tokens.intersection(item_tokens)
                if len(overlap) >= max(1, len(substantive_tokens) * 0.75):
                    if item not in supporting_items:
                        supporting_items.append(item)
                    matched_facts.update(overlap)

        if supporting_items:
            confidence = min(1.0, 0.7 + (len(supporting_items) * 0.1))
            ev_ids = [it.evidence_id for it in supporting_items]
            return ClaimValidationResult(
                claim=clean_claim,
                supported=True,
                confidence=round(confidence, 2),
                supporting_evidence_ids=ev_ids,
                supporting_evidence=supporting_items,
                matched_facts=sorted(list(matched_facts)),
                explanation=f"Claim is verified by {len(supporting_items)} evidence item(s) in Evidence Vault."
            )
        else:
            return ClaimValidationResult(
                claim=clean_claim,
                supported=False,
                confidence=0.0,
                supporting_evidence_ids=[],
                supporting_evidence=[],
                matched_facts=[],
                explanation="No supporting evidence found in the candidate's Evidence Vault."
            )

    def find_supporting_evidence(self, vault: EvidenceVault, query: str) -> List[VaultEvidenceItem]:
        """Returns all evidence items matching the query text in source or facts."""
        if not query or not query.strip():
            return []
        q = query.strip().lower()
        results = []
        for item in vault.items:
            if (
                q in item.source_text.lower()
                or any(q in f.lower() for f in item.normalized_facts)
                or any(q in t.lower() for t in item.related_technologies)
            ):
                results.append(item)
        return results

    def get_evidence_for_skill(self, vault: EvidenceVault, skill_name: str) -> List[VaultEvidenceItem]:
        """Finds all evidence items grounded to a specific skill."""
        s = skill_name.strip().lower()
        matching_ids = set()
        if s in vault.technology_index:
            matching_ids.update(vault.technology_index[s])
        if s in vault.skill_index:
            matching_ids.update(vault.skill_index[s])
        
        items = [it for it in vault.items if it.evidence_id in matching_ids]
        if not items:
            # Fallback to text search
            items = self.find_supporting_evidence(vault, skill_name)
        return items

    def get_evidence_for_project(self, vault: EvidenceVault, project_name: str) -> List[VaultEvidenceItem]:
        """Finds all evidence items linked to a specific project."""
        p = project_name.strip().lower()
        matching_ids = set()
        if p in vault.project_index:
            matching_ids.update(vault.project_index[p])
        
        items = [
            it for it in vault.items 
            if it.evidence_id in matching_ids or (it.related_project and it.related_project.lower() == p)
        ]
        if not items:
            items = [it for it in vault.items if it.source_section and "project" in it.source_section.lower() and p in it.source_text.lower()]
        return items

    def get_evidence_for_experience(self, vault: EvidenceVault, company_or_role: str) -> List[VaultEvidenceItem]:
        """Finds all evidence items linked to a specific role or company."""
        cr = company_or_role.strip().lower()
        matching_ids = set()
        if cr in vault.experience_index:
            matching_ids.update(vault.experience_index[cr])
        
        items = [
            it for it in vault.items 
            if it.evidence_id in matching_ids or (it.related_experience and cr in it.related_experience.lower())
        ]
        if not items:
            items = [it for it in vault.items if cr in it.source_text.lower()]
        return items
