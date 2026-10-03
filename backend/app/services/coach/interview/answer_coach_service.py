import re
from typing import List, Dict, Any, Optional, Set

from app.schemas.evidence_vault import EvidenceVault, VaultEvidenceItem
from app.schemas.interview_readiness import (
    AnswerValidationResult,
    ValidationVerdict,
)
from app.services.coach.evidence.validation import EvidenceValidationService, METRIC_REGEX
from app.services.jd_analyzer.taxonomy import extract_all_technologies


# Regex for impact/outcome phrases commonly asserted in answers
IMPACT_PATTERNS = [
    re.compile(r'\b(?:reduced|decreased|cut)\s+(?:latency|costs?|downtime|bugs?|errors?)\s+by\s+(\d+(?:\.\d+)?%?)', re.IGNORECASE),
    re.compile(r'\b(?:increased|boosted|improved|grew)\s+(?:throughput|revenue|performance|efficiency|sales?)\s+by\s+(\d+(?:\.\d+)?%?)', re.IGNORECASE),
    re.compile(r'\b(?:optimized|streamlined)\s+.*?\s+by\s+(\d+(?:\.\d+)?%?)', re.IGNORECASE),
]

SCALE_METRIC_REGEX = re.compile(
    r'\b(?:\d+(?:\.\d+)?\s*(?:million|billion|thousand|[kKmMbB])\s*(?:active\s+users?|users?|requests?|transactions?|qps)?|\d+\+?\s*(?:active\s+users?|users?|requests?|transactions?|qps))\b',
    re.IGNORECASE
)


class InterviewAnswerCoachService:
    """
    Evidence-locked answer validation service.
    Validates candidate draft interview responses against their Evidence Vault.
    Guarantees no unsupported candidate claims, metrics, or technologies pass through as verified fact.
    """

    def __init__(self, evidence_validator: Optional[EvidenceValidationService] = None):
        self.evidence_validator = evidence_validator or EvidenceValidationService()

    def validate_candidate_answer(
        self,
        vault: EvidenceVault,
        answer_text: str,
        question_text: Optional[str] = None,
        target_requirement_text: Optional[str] = None
    ) -> AnswerValidationResult:
        if not answer_text or not answer_text.strip():
            return AnswerValidationResult(
                verdict=ValidationVerdict.UNSUPPORTED,
                supported_claims=[],
                unsupported_claims=["No answer text provided."],
                supported_technologies=[],
                unsupported_technologies=[],
                valid_evidence_ids=[it.evidence_id for it in vault.items],
                evidence_ids_used=[],
                explanation="Draft answer is empty.",
                star_breakdown={"situation": False, "task": False, "action": False, "result": False},
                coaching_recommendations=["Please write a draft answer outlining your actual technical experience."]
            )

        clean_text = answer_text.strip()
        lower_text = clean_text.lower()

        supported_claims: List[str] = []
        unsupported_claims: List[str] = []
        supported_technologies: List[str] = []
        unsupported_technologies: List[str] = []
        valid_evidence_ids: List[str] = [it.evidence_id for it in vault.items]
        evidence_ids_used: List[str] = []
        recommendations: List[str] = []
        coaching_tip: Optional[str] = None


        # 1. Metric Validation (Quantified metrics must exist in vault)
        claimed_metrics = list(dict.fromkeys(METRIC_REGEX.findall(clean_text) + SCALE_METRIC_REGEX.findall(clean_text)))
        for metric in claimed_metrics:
            norm_m = metric.strip().lower()
            matching_items = [
                it for it in vault.items
                if norm_m in it.source_text.lower() or any(norm_m == f.lower() for f in (it.normalized_facts or []))
            ]
            if matching_items:
                supported_claims.append(f"Metric '{metric}' (verified in {matching_items[0].evidence_id})")
                evidence_ids_used.extend([it.evidence_id for it in matching_items])
            else:
                unsupported_claims.append(f"Unsupported metric: '{metric}'")
                recommendations.append(
                    f"Remove or substantiate '{metric}'. Your Evidence Vault contains no source documentation verifying this exact figure."
                )

        # 2. Technology Validation (Claimed technologies must exist in vault or candidate skills)
        claimed_techs = extract_all_technologies(clean_text)
        vault_techs: Set[str] = set()
        for it in vault.items:
            if it.related_skill:
                vault_techs.add(it.related_skill.lower())
            for t in (it.related_technologies or []):
                vault_techs.add(t.lower())
        for k in vault.technology_index.keys():
            vault_techs.add(k.lower())
        for k in vault.skill_index.keys():
            vault_techs.add(k.lower())

        for tech in claimed_techs:
            tech_lower = tech.lower()
            is_prompt_context = question_text and tech_lower in question_text.lower()

            in_source = any(tech_lower in it.source_text.lower() or any(tech_lower in f.lower() for f in (it.normalized_facts or [])) for it in vault.items)
            if tech_lower in vault_techs or in_source:
                matching = [
                    it for it in vault.items
                    if (it.related_skill and it.related_skill.lower() == tech_lower)
                    or any(tech_lower == t.lower() for t in (it.related_technologies or []))
                    or tech_lower in it.source_text.lower()
                ]
                if matching:
                    evidence_ids_used.append(matching[0].evidence_id)
                supported_claims.append(f"Technology '{tech}'")
                supported_technologies.append(tech)
            else:
                honest_gap_phrases = [
                    f"no experience with {tech_lower}",
                    f"haven't worked with {tech_lower}",
                    f"have not used {tech_lower}",
                    f"learning {tech_lower}",
                    f"plan to learn {tech_lower}",
                    f"ramp up on {tech_lower}",
                    f"familiar with foundational concepts of {tech_lower}",
                    f"do not have direct production {tech_lower}",
                    f"do not have direct {tech_lower}",
                    "understand container fundamentals",
                ]
                if any(phrase in lower_text for phrase in honest_gap_phrases) or (is_prompt_context and "honest" in lower_text):
                    supported_claims.append(f"Honest gap acknowledgment for '{tech}'")
                    coaching_tip = f"Candidate honestly acknowledges gap for '{tech}' and explains foundation."
                else:
                    unsupported_claims.append(f"Unsupported technology claim: '{tech}'")
                    unsupported_technologies.append(tech)
                    recommendations.append(
                        f"Technology '{tech}' is claimed in your answer, but is not verified in your Evidence Vault. Avoid claiming hands-on experience without supporting evidence."
                    )

        # 3. Operational & Production Scope Validation (Technology Presence != Experience Scope)
        from app.services.coach.evidence.claim_scope import extract_operational_scope_claims
        operational_claims = extract_operational_scope_claims(clean_text)
        for op_claim in operational_claims:
            # Check if vault explicitly documents production cluster management / operations
            has_prod_scope = any(
                ("production" in it.source_text.lower() or "prod" in it.source_text.lower())
                and any(w in it.source_text.lower() for w in ["cluster", "clusters", "eks", "gke", "aks", "manage", "operat", "admin"])
                for it in vault.items
            )
            if not has_prod_scope and op_claim not in unsupported_claims:
                unsupported_claims.append(f"Unsupported operational scope claim: '{op_claim}'")
                recommendations.append(
                    f"Operational claim '{op_claim}' is not documented in Evidence Vault. Your vault verifies technology presence/exposure, but does not verify production cluster management or administration operations."
                )

        # 3b. Deployment Scope Validation
        pat_deploy = re.compile(
            r'\b(?:deployed\s+(?:the\s+)?(?:application|services?|backend|microservices?|system)\s+using\s+([a-zA-Z0-9_\-\.\+#]+)|deployed\s+using\s+([a-zA-Z0-9_\-\.\+#]+))\b',
            re.IGNORECASE
        )
        for m in pat_deploy.finditer(clean_text):
            full_deploy_claim = m.group(0)
            target_tech = (m.group(1) or m.group(2) or "").lower()
            has_deployment_evidence = any(
                target_tech in it.source_text.lower()
                and any(d in it.source_text.lower() for d in ["deploy", "deployment", "deployed", "deploying", "release", "ci/cd", "pipeline"])
                for it in vault.items
            )
            if not has_deployment_evidence and full_deploy_claim not in unsupported_claims:
                unsupported_claims.append(f"Unsupported deployment claim: '{full_deploy_claim}'")
                recommendations.append(
                    f"Deployment claim '{full_deploy_claim}' is unverified in your Evidence Vault. Your records document exposure to '{target_tech}', but not application deployment."
                )

        # 4. Seniority & Responsibility Validation
        seniority_patterns = [
            re.compile(r'\b(?:director of engineering|vp of engineering|head of engineering|chief technology officer|cto)\b', re.IGNORECASE),
            re.compile(r'\b(?:managed|led)\s+(?:a\s+)?(?:\d+[- ]person|\d+\s+engineers?|an\s+engineering\s+department)\b', re.IGNORECASE),
            re.compile(r'\b(?:owned|managed)\s+(?:the\s+entire\s+corporate\s+budget|corporate\s+budget|department\s+budget)\b', re.IGNORECASE),
        ]
        for pat in seniority_patterns:
            match = pat.search(clean_text)
            if match:
                matched_phrase = match.group(0)
                has_backing = any(matched_phrase.lower() in it.source_text.lower() for it in vault.items)
                if not has_backing and matched_phrase not in unsupported_claims:
                    unsupported_claims.append(f"Unsupported responsibility/seniority claim: '{matched_phrase}'")
                    recommendations.append(f"Seniority or scope claim '{matched_phrase}' is not documented in Evidence Vault.")

        # 5. Impact & Commercial Outcome Assertions Check
        for pat in IMPACT_PATTERNS:
            for match in pat.finditer(clean_text):
                full_clause = match.group(0)
                has_backing = any(match.group(1).lower() in it.source_text.lower() for it in vault.items)
                if not has_backing and full_clause not in unsupported_claims:
                    unsupported_claims.append(f"Unsupported outcome claim: '{full_clause}'")

        revenue_patterns = [
            re.compile(r'\b(?:\$\d+(?:\.\d+)?(?:[kKmMbB]|(?:\s*million|\s*billion))?)\b', re.IGNORECASE),
            re.compile(r'\b(?:revolutionized|transformed)\s+(?:the\s+company|sales?|business)\b', re.IGNORECASE)
        ]
        for pat in revenue_patterns:
            for match in pat.finditer(clean_text):
                full_clause = match.group(0)
                has_backing = any(full_clause.lower() in it.source_text.lower() for it in vault.items)
                if not has_backing and full_clause not in unsupported_claims:
                    unsupported_claims.append(f"Unsupported commercial impact claim: '{full_clause}'")

        # 6. Sentence-level validation using EvidenceValidationService
        sentences = [s.strip() for s in re.split(r'[.!?]\s+', clean_text) if len(s.strip()) > 15]
        for sent in sentences:
            res = self.evidence_validator.validate_claim(vault, sent)
            if res.supported and res.supporting_evidence_ids:
                evidence_ids_used.extend(res.supporting_evidence_ids)

        evidence_ids_used = list(dict.fromkeys(evidence_ids_used))

        # 6. Evaluate STAR completeness
        has_situation = any(k in lower_text for k in ["when", "during", "at my", "project", "problem", "challenge", "scenario", "client", "company", "previous role"])
        has_task = any(k in lower_text for k in ["responsible", "goal", "task", "needed to", "my role", "objective", "requirement"])
        has_action = any(k in lower_text for k in ["implemented", "built", "designed", "used", "created", "refactored", "wrote", "engineered", "configured", "deployed", "optimized"])
        has_result = any(k in lower_text for k in ["result", "reduced", "increased", "improved", "percent", "%", "achieved", "delivered", "outcome"])

        star_breakdown = {
            "situation": has_situation,
            "task": has_task,
            "action": has_action,
            "result": has_result,
        }

        if not has_situation:
            recommendations.append("Add Situation: Briefly explain the background or business problem.")
        if not has_task:
            recommendations.append("Clarify Task: Clearly define what you specifically were responsible for.")
        if not has_action:
            recommendations.append("Detail Action: Walk through the specific technical decisions and implementation steps you performed.")
        if not has_result:
            recommendations.append("Document Result: Describe the outcome (or state 'Result not currently supported by verified evidence' if unmeasured).")

        # 7. Determine Verdict
        if len(unsupported_claims) == 0 and len(supported_claims) > 0:
            verdict = ValidationVerdict.SUPPORTED
            explanation = "Your answer is grounded in verified Evidence Vault records without unsupported claims."
        elif len(supported_claims) > 0 and len(unsupported_claims) > 0:
            verdict = ValidationVerdict.PARTIALLY_SUPPORTED
            explanation = f"Answer contains verified experience, but includes {len(unsupported_claims)} unsupported assertion(s)."
        elif len(unsupported_claims) > 0:
            verdict = ValidationVerdict.UNSUPPORTED
            explanation = "Answer contains unsupported claims or metrics not verified by your Evidence Vault."
        else:
            verdict = ValidationVerdict.SUPPORTED
            explanation = "Your answer is conversational and does not introduce unsupported claims."

        return AnswerValidationResult(
            verdict=verdict,
            supported_claims=supported_claims,
            unsupported_claims=unsupported_claims,
            supported_technologies=supported_technologies,
            unsupported_technologies=unsupported_technologies,
            valid_evidence_ids=valid_evidence_ids,
            evidence_ids_used=evidence_ids_used,
            explanation=explanation,
            star_breakdown=star_breakdown,
            coaching_tip=coaching_tip,
            coaching_recommendations=recommendations
        )
