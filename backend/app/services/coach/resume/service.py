import re
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Set

from app.schemas.career_twin import CareerTwin
from app.schemas.evidence_vault import EvidenceVault, VaultEvidenceItem
from app.schemas.resume_coach import (
    ResumeCoachRequest,
    ResumeCoachResponse,
    ResumeCoachStatus,
    ClaimValidationDetail,
    EvidenceCitation,
)
from app.services.coach.llm.provider import LLMProvider, get_llm_provider, EVIDENCE_LOCKED_SYSTEM_PROMPT
from app.services.coach.evidence.validation import EvidenceValidationService, METRIC_REGEX
from app.services.jd_analyzer.taxonomy import extract_all_technologies

WEAK_OPENERS = [
    re.compile(r'^(responsible\s+for|assisted\s+with|helped\s+to|worked\s+on|duties\s+included|handled|involved\s+in)\b', re.IGNORECASE),
]

STRONG_ACTION_VERBS = {
    "architected", "developed", "spearheaded", "engineered", "optimized",
    "designed", "deployed", "implemented", "orchestrated", "automated",
    "accelerated", "reduced", "increased", "scaled", "delivered"
}

UNSUPPORTED_SENIORITY_TITLES = {
    "principal", "director", "vice president", "vp", "chief", "head of",
    "distinguished", "fellow", "cto", "cio"
}

KNOWN_BIG_ORGS = {
    "google", "apple", "netflix", "meta", "amazon", "microsoft", "stripe", "uber", "airbnb"
}

class ResumeCoachService:
    """
    Evidence-Locked Resume Coach and Rewriting Engine.
    Improves wording, action verbs, and clarity ONLY using verified facts
    from the candidate's Evidence Vault.
    Strictly rejects fabricated technologies, metrics, organizations, or titles.
    """

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        validation_service: Optional[EvidenceValidationService] = None
    ):
        self.llm_provider = llm_provider or get_llm_provider()
        self.validation_service = validation_service or EvidenceValidationService()

    def generate_rewrite(
        self,
        request: ResumeCoachRequest,
        twin: CareerTwin,
        vault: EvidenceVault,
        original_resume_text: Optional[str] = None
    ) -> ResumeCoachResponse:
        """
        Executes the Evidence-Locked Rewriting Pipeline:
        1. Guard against Experience Gaps (Mode B: NOT rewriteable).
        2. Retrieve verified ground truth from Evidence Vault.
        3. Invoke LLM with strict evidence-bounded context.
        4. Split generated text into factual claims.
        5. Validate each claim strictly against Evidence Vault.
        6. Accept only if 100% of claims are grounded; otherwise Reject.
        """
        suggestion_id = f"sug_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        original_text = request.current_resume_text or ""

        if not original_text and request.existing_evidence_snippets:
            original_text = request.existing_evidence_snippets[0]

        # ----------------------------------------------------
        # 1. Check Coaching Mode
        # MODE B: EXPERIENCE_GAP -> NO_SAFE_REWRITE
        # ----------------------------------------------------
        if request.gap_type == "EXPERIENCE_GAP":
            missing_str = ", ".join(request.missing_elements) if request.missing_elements else request.requirement_text
            return ResumeCoachResponse(
                suggestion_id=suggestion_id,
                candidate_id=request.candidate_id,
                requirement_id=request.requirement_id,
                status=ResumeCoachStatus.NO_SAFE_REWRITE,
                original_text=original_text,
                suggested_text=None,
                changes=[],
                evidence_used=[],
                unsupported_claims=[],
                validation=[],
                explanation=(
                    f"No verified evidence supports {missing_str}. "
                    "The Evidence-Locked Coach will not rewrite your resume to claim unverified experience. "
                    "Gain genuine hands-on experience or document past unindexed projects first."
                ),
                can_rewrite=False,
                created_at=now_iso
            )

        # ----------------------------------------------------
        # 2. Collect Verified Ground Truth from Evidence Vault
        # ----------------------------------------------------
        relevant_evidence_items: List[VaultEvidenceItem] = []
        if request.evidence_ids:
            for eid in request.evidence_ids:
                item = next((it for it in vault.items if it.evidence_id == eid), None)
                if item and item not in relevant_evidence_items:
                    relevant_evidence_items.append(item)

        # Fallback to search if items not found by ID
        if not relevant_evidence_items and request.existing_evidence_snippets:
            for snip in request.existing_evidence_snippets:
                matching = self.validation_service.find_supporting_evidence(vault, snip)
                for it in matching:
                    if it not in relevant_evidence_items:
                        relevant_evidence_items.append(it)

        # Also fallback to searching vault for requirement text / role / current_resume_text keywords
        if not relevant_evidence_items:
            search_query = request.current_resume_text or request.requirement_text
            matching = self.validation_service.find_supporting_evidence(vault, search_query)
            for it in matching[:3]:
                if it not in relevant_evidence_items:
                    relevant_evidence_items.append(it)

        # Build verified evidence context strings
        verified_evidence_texts = [it.source_text for it in relevant_evidence_items]
        if not verified_evidence_texts and request.existing_evidence_snippets:
            verified_evidence_texts = request.existing_evidence_snippets

        if not relevant_evidence_items and not verified_evidence_texts:
            return ResumeCoachResponse(
                suggestion_id=suggestion_id,
                candidate_id=request.candidate_id,
                requirement_id=request.requirement_id,
                status=ResumeCoachStatus.NO_SAFE_REWRITE,
                original_text=original_text,
                suggested_text=None,
                changes=[],
                evidence_used=[],
                unsupported_claims=[],
                validation=[],
                explanation="No valid supporting evidence matching the provided citations was found in Evidence Vault.",
                can_rewrite=False,
                created_at=now_iso
            )


        llm_context: Dict[str, Any] = {
            "candidate_id": request.candidate_id,
            "requirement_id": request.requirement_id,
            "requirement_text": request.requirement_text,
            "target_role": request.target_role or "Software Engineer",
            "priority": request.priority or "REQUIRED",
            "gap_type": request.gap_type or "RESUME_VISIBILITY_GAP",
            "evidence_ids": request.evidence_ids,
            "existing_evidence_snippets": verified_evidence_texts,
            "missing_elements": request.missing_elements,
            "current_resume_text": original_text,
            "action_prompt": request.action_prompt,
            "system_prompt": EVIDENCE_LOCKED_SYSTEM_PROMPT
        }

        # ----------------------------------------------------
        # 3. Generate candidate rewrite using LLM provider
        # ----------------------------------------------------
        try:
            raw_generated = self.llm_provider.generate_resume_rewrite(llm_context)
        except Exception as exc:
            return ResumeCoachResponse(
                suggestion_id=suggestion_id,
                candidate_id=request.candidate_id,
                requirement_id=request.requirement_id,
                status=ResumeCoachStatus.NO_SAFE_REWRITE,
                original_text=original_text,
                suggested_text=None,
                changes=[],
                evidence_used=[],
                unsupported_claims=[],
                validation=[],
                explanation=f"Rewriter encountered provider error: {str(exc)}",
                can_rewrite=False,
                created_at=now_iso
            )

        # Handle empty, malformed, or explicit NO_SAFE_REWRITE
        if not raw_generated or not raw_generated.strip() or raw_generated.strip() == "NO_SAFE_REWRITE":
            return ResumeCoachResponse(
                suggestion_id=suggestion_id,
                candidate_id=request.candidate_id,
                requirement_id=request.requirement_id,
                status=ResumeCoachStatus.NO_SAFE_REWRITE,
                original_text=original_text,
                suggested_text=None,
                changes=[],
                evidence_used=[],
                unsupported_claims=[],
                validation=[],
                explanation="No safe evidence-grounded rewrite could be produced for this requirement.",
                can_rewrite=False,
                created_at=now_iso
            )

        if raw_generated.startswith("{[") or raw_generated.startswith("Error:"):
            return ResumeCoachResponse(
                suggestion_id=suggestion_id,
                candidate_id=request.candidate_id,
                requirement_id=request.requirement_id,
                status=ResumeCoachStatus.REJECTED,
                original_text=original_text,
                suggested_text=raw_generated,
                changes=[],
                evidence_used=[],
                unsupported_claims=["Malformed model response"],
                validation=[],
                explanation="Model produced malformed or unparsable output.",
                can_rewrite=True,
                created_at=now_iso
            )

        suggested_text = raw_generated.strip().strip('"\'')

        import string
        def _normalize(text: str) -> str:
            if not text:
                return ""
            return text.translate(str.maketrans('', '', string.whitespace)).lower()

        if _normalize(original_text) == _normalize(suggested_text):
            return ResumeCoachResponse(
                suggestion_id=suggestion_id,
                candidate_id=request.candidate_id,
                requirement_id=request.requirement_id,
                status=ResumeCoachStatus.NO_SAFE_REWRITE,
                original_text=original_text,
                suggested_text=None,
                changes=[],
                evidence_used=[],
                unsupported_claims=[],
                validation=[],
                explanation="AI suggestion generated identical or negligibly different text. No meaningful rewrite produced.",
                can_rewrite=True,
                created_at=now_iso
            )


        # ----------------------------------------------------
        # 4. Claim-Level Validation Pipeline
        # Break suggested text into individual factual claims
        # ----------------------------------------------------
        claims = self._extract_claims(suggested_text)
        if not claims:
            claims = [suggested_text]

        claim_validations: List[ClaimValidationDetail] = []
        unsupported_claims: List[str] = []
        used_evidence_map: Dict[str, EvidenceCitation] = {}

        # Pre-extract all known verified facts for fast lookup
        known_vault_texts = " ".join([it.source_text.lower() for it in vault.items])
        known_vault_techs = {t.lower() for t in vault.technology_index.keys()}
        known_vault_skills = {s.lower() for s in vault.skill_index.keys()}
        known_techs_all = known_vault_techs.union(known_vault_skills)
        if twin and twin.skills:
            known_techs_all.update([s.lower() for s in twin.skills])
        if twin and twin.technologies:
            known_techs_all.update([t.lower() for t in twin.technologies])

        for claim in claims:
            claim_clean = claim.strip()
            if not claim_clean:
                continue

            claim_lower = claim_clean.lower()
            is_supported = True
            rejection_reasons: List[str] = []
            claim_ev_ids: List[str] = []

            # Check 1: Metric Hallucination
            claim_metrics = METRIC_REGEX.findall(claim_clean)
            if claim_metrics:
                for metric in claim_metrics:
                    metric_norm = metric.strip().lower()
                    if metric_norm not in known_vault_texts:
                        is_supported = False
                        reason = f"Unsupported metric: '{metric}' is not present in verified evidence."
                        rejection_reasons.append(reason)

            # Check 2: Technology Hallucination
            extracted_techs = extract_all_technologies(claim_clean)
            for tech in extracted_techs:
                if tech.lower() not in known_techs_all and tech.lower() not in known_vault_texts:
                    is_supported = False
                    reason = f"Unsupported technology: '{tech}' is not present in verified evidence."
                    rejection_reasons.append(reason)

            # Check 3: Seniority/Responsibility Hallucination
            for senior_title in UNSUPPORTED_SENIORITY_TITLES:
                if senior_title in claim_lower and senior_title not in known_vault_texts:
                    is_supported = False
                    reason = f"Unsupported seniority/responsibility claim: '{senior_title}' was not found in verified experience."
                    rejection_reasons.append(reason)

            # Check 4: Unverified Organization Hallucination
            for org in KNOWN_BIG_ORGS:
                if re.search(rf'\b{org}\b', claim_lower) and org not in known_vault_texts:
                    is_supported = False
                    reason = f"Unsupported organization claim: '{org.capitalize()}' is not present in verified evidence."
                    rejection_reasons.append(reason)

            # Check 5: Unsupported Inferred Impact, Benefit, Outcome, Optimization, Scale, or Causal Claim
            evidence_context_text = " ".join([it.source_text.lower() for it in relevant_evidence_items]) or known_vault_texts
            impact_rejections = self._validate_impact_and_outcome_claims(claim_clean, evidence_context_text)
            if impact_rejections:
                is_supported = False
                rejection_reasons.extend(impact_rejections)

            # Check 6: General factual grounding via EvidenceValidationService
            val_res = self.validation_service.validate_claim(vault, claim_clean)
            if val_res.supported:
                claim_ev_ids.extend(val_res.supporting_evidence_ids)
                for item in val_res.supporting_evidence:
                    if item.evidence_id not in used_evidence_map:
                        used_evidence_map[item.evidence_id] = EvidenceCitation(
                            evidence_id=item.evidence_id,
                            source_text=item.source_text,
                            source_section=item.source_section or "Experience",
                            page_number=item.page_number or 1,
                            matched_terms=item.related_technologies or []
                        )
            elif is_supported:
                # If no direct violation above but validation service finds zero overlap
                # Check if it's purely stylistic variation of existing evidence
                has_semantic_anchor = any(
                    ev_item.source_text.lower() in claim_lower or claim_lower in ev_item.source_text.lower()
                    or any(w in ev_item.source_text.lower() for w in claim_lower.split() if len(w) > 4)
                    for ev_item in relevant_evidence_items
                )
                if not has_semantic_anchor:
                    is_supported = False
                    rejection_reasons.append(f"Claim lacks factual anchor in Evidence Vault: '{claim_clean}'")

            if not is_supported:
                unsupported_claims.extend(rejection_reasons or [f"Claim '{claim_clean}' is unsupported."])
                claim_validations.append(
                    ClaimValidationDetail(
                        claim=claim_clean,
                        supported=False,
                        confidence=0.0,
                        supporting_evidence_ids=[],
                        matched_facts=[],
                        explanation="; ".join(rejection_reasons) if rejection_reasons else "Unsupported claim."
                    )
                )
            else:
                claim_validations.append(
                    ClaimValidationDetail(
                        claim=claim_clean,
                        supported=True,
                        confidence=val_res.confidence if val_res.supported else 0.85,
                        supporting_evidence_ids=claim_ev_ids,
                        matched_facts=val_res.matched_facts,
                        explanation="Claim verified against Evidence Vault."
                    )
                )

        # ----------------------------------------------------
        # 5. Determine Overall Response Verdict
        # ----------------------------------------------------
        if unsupported_claims:
            return ResumeCoachResponse(
                suggestion_id=suggestion_id,
                candidate_id=request.candidate_id,
                requirement_id=request.requirement_id,
                status=ResumeCoachStatus.REJECTED,
                original_text=original_text,
                suggested_text=suggested_text,
                changes=[],
                evidence_used=[],
                unsupported_claims=unsupported_claims,
                validation=claim_validations,
                explanation=(
                    f"Rewrite rejected: {len(unsupported_claims)} unsupported claim(s) detected. "
                    "The Evidence-Locked Coach prevents ungrounded additions."
                ),
                can_rewrite=True,
                created_at=now_iso
            )

        # Ensure at least one evidence item is credited
        if not used_evidence_map and relevant_evidence_items:
            for item in relevant_evidence_items:
                used_evidence_map[item.evidence_id] = EvidenceCitation(
                    evidence_id=item.evidence_id,
                    source_text=item.source_text,
                    source_section=item.source_section or "Experience",
                    page_number=item.page_number or 1,
                    matched_terms=item.related_technologies or []
                )

        # Change explanation (Section 8)
        changes: List[str] = [
            "Strengthened action verb orientation",
            "Improved professional conciseness and visibility",
            "Preserved verified technology facts without metric alteration",
            "No ungrounded claims or external technologies introduced"
        ]

        return ResumeCoachResponse(
            suggestion_id=suggestion_id,
            candidate_id=request.candidate_id,
            requirement_id=request.requirement_id,
            status=ResumeCoachStatus.ACCEPTED,
            original_text=original_text,
            suggested_text=suggested_text,
            changes=changes,
            evidence_used=list(used_evidence_map.values()),
            unsupported_claims=[],
            validation=claim_validations,
            explanation=f"Rewrite accepted: all {len(claim_validations)} claim(s) strictly verified by Evidence Vault.",
            can_rewrite=True,
            created_at=now_iso
        )

    def _extract_claims(self, text: str) -> List[str]:
        """
        Splits text into atomic factual claims (sentences, compound metric clauses).
        """
        if not text:
            return []
        # Split on sentence terminals
        raw_sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
        claims: List[str] = []
        for s in raw_sentences:
            s_clean = s.strip().strip("•-* ")
            if not s_clean:
                continue
            # Check for compound conjunctions with metric or secondary action
            clauses = re.split(r'\s+(?:and\s+(?:reduced|increased|optimized|improved|achieving|resulting\s+in))\s+', s_clean, flags=re.IGNORECASE)
            if len(clauses) > 1:
                for c in clauses:
                    c_clean = c.strip()
                    if c_clean:
                        claims.append(c_clean)
            else:
                claims.append(s_clean)
        return claims

    def _validate_impact_and_outcome_claims(self, claim_text: str, vault_text: str) -> List[str]:
        """
        Validates that impact, benefit, outcome, efficiency, performance,
        optimization, scale, and causal claims are explicitly supported by Evidence Vault.
        """
        reasons: List[str] = []
        text_lower = claim_text.lower()
        vault_lower = vault_text.lower()

        # 1. Efficiency Claims
        eff_patterns = [
            r'\b(?:improv(?:e[ds]?|ing)|increas(?:e[ds]?|ing)|boost(?:ed|ing|s)?|enhanc(?:e[ds]?|ing)|driv(?:e[ds]?|ing)|gain(?:ed|ing|s)?)\s+(?:the\s+)?efficiency\b',
            r'\befficiency\s+(?:improvements?|gains?|boosts?)\b',
            r'\befficiency\b'
        ]
        for pat in eff_patterns:
            for m in re.finditer(pat, text_lower):
                matched = m.group(0).strip()
                if "efficiency" not in vault_lower and "efficient" not in vault_lower:
                    reasons.append(f"Unsupported efficiency claim: '{matched}' is not explicitly supported by verified evidence.")
                    break
            if any("efficiency" in r.lower() for r in reasons):
                break

        # 2. Performance Improvement Claims
        perf_patterns = [
            r'\b(?:improv(?:e[ds]?|ing)|increas(?:e[ds]?|ing)|boost(?:ed|ing|s)?|enhanc(?:e[ds]?|ing)|optimiz(?:e[ds]?|ing)|accelerat(?:e[ds]?|ing))\s+(?:the\s+)?performance\b',
            r'\bperformance\s+(?:improvements?|gains?|boosts?|optimizations?)\b',
        ]
        for pat in perf_patterns:
            for m in re.finditer(pat, text_lower):
                matched = m.group(0).strip()
                if "performance" not in vault_lower:
                    reasons.append(f"Unsupported performance improvement claim: '{matched}' is not explicitly supported by verified evidence.")
                    break
            if any("performance" in r.lower() for r in reasons):
                break

        # 3. Streamlining / Operations Impact Claims
        streamline_matches = re.finditer(
            r'\bstreamlin(?:e[ds]?|ing|es?)(?:\s+(?:the\s+)?([a-zA-Z0-9_\-\.\+]+(?:\s+[a-zA-Z0-9_\-\.\+]+){0,3}))?\b',
            text_lower
        )
        for m in streamline_matches:
            matched = m.group(0).strip()
            if "streamlin" not in vault_lower:
                reasons.append(f"Unsupported impact/benefit claim: '{matched}' is not explicitly supported by verified evidence.")
                break

        # 4. Scalability Claims
        scale_patterns = [
            r'\b(?:improv(?:e[ds]?|ing)|increas(?:e[ds]?|ing)|enhanc(?:e[ds]?|ing)|ensur(?:e[ds]?|ing)|boost(?:ed|ing|s)?)\s+(?:the\s+)?scalability\b',
            r'\b(?:enhanced|improved|high)\s+scalability\b',
            r'\bscalability\b',
            r'\bscalable\b'
        ]
        for pat in scale_patterns:
            for m in re.finditer(pat, text_lower):
                matched = m.group(0).strip()
                if "scalab" not in vault_lower:
                    reasons.append(f"Unsupported scalability claim: '{matched}' is not explicitly supported by verified evidence.")
                    break
            if any("scalability" in r.lower() for r in reasons):
                break

        # 5. Cost Reduction Claims
        cost_patterns = [
            r'\b(?:reduc(?:e[ds]?|ing|tion)|cut(?:ting)?|lower(?:ed|ing)?|sav(?:e[ds]?|ing))\s+(?:the\s+)?cost[s]?\b',
            r'\bcost[\s\-]effective(?:ness)?\b',
            r'\bcost[\s\-]saving[s]?\b'
        ]
        for pat in cost_patterns:
            for m in re.finditer(pat, text_lower):
                matched = m.group(0).strip()
                if "cost" not in vault_lower:
                    reasons.append(f"Unsupported cost reduction claim: '{matched}' is not explicitly supported by verified evidence.")
                    break
            if any("cost" in r.lower() for r in reasons):
                break

        # 6. Reliability Claims
        rel_patterns = [
            r'\b(?:improv(?:e[ds]?|ing)|increas(?:e[ds]?|ing)|enhanc(?:e[ds]?|ing)|boost(?:ed|ing|s)?|ensur(?:e[ds]?|ing))\s+(?:the\s+)?reliability\b',
            r'\breliability\b'
        ]
        for pat in rel_patterns:
            for m in re.finditer(pat, text_lower):
                matched = m.group(0).strip()
                if "reliab" not in vault_lower:
                    reasons.append(f"Unsupported reliability claim: '{matched}' is not explicitly supported by verified evidence.")
                    break
            if any("reliability" in r.lower() for r in reasons):
                break

        # 7. Productivity Claims
        prod_patterns = [
            r'\b(?:boost(?:ed|ing|s)?|increas(?:e[ds]?|ing)|improv(?:e[ds]?|ing)|enhanc(?:e[ds]?|ing))\s+(?:the\s+)?productivity\b',
            r'\bproductivity\b'
        ]
        for pat in prod_patterns:
            for m in re.finditer(pat, text_lower):
                matched = m.group(0).strip()
                if "productiv" not in vault_lower:
                    reasons.append(f"Unsupported productivity claim: '{matched}' is not explicitly supported by verified evidence.")
                    break
            if any("productivity" in r.lower() for r in reasons):
                break

        # 8. Acceleration / Processing Claims
        accel_matches = re.finditer(
            r'\baccelerat(?:e[ds]?|ing)\s+(?:the\s+)?([a-zA-Z0-9_\-\.\+]+(?:\s+[a-zA-Z0-9_\-\.\+]+){0,3})\b',
            text_lower
        )
        for m in accel_matches:
            matched = m.group(0).strip()
            if "accelerat" not in vault_lower:
                reasons.append(f"Unsupported acceleration claim: '{matched}' is not explicitly supported by verified evidence.")
                break

        # 9. Throughput Claims
        thru_patterns = [
            r'\b(?:increas(?:e[ds]?|ing)|improv(?:e[ds]?|ing)|boost(?:ed|ing|s)?|enhanc(?:e[ds]?|ing)|higher|maximiz(?:e[ds]?|ing))\s+(?:the\s+)?throughput\b',
            r'\bthroughput\b'
        ]
        for pat in thru_patterns:
            for m in re.finditer(pat, text_lower):
                matched = m.group(0).strip()
                if "throughput" not in vault_lower:
                    reasons.append(f"Unsupported throughput claim: '{matched}' is not explicitly supported by verified evidence.")
                    break
            if any("throughput" in r.lower() for r in reasons):
                break

        # 10. Latency Claims
        lat_patterns = [
            r'\b(?:reduc(?:e[ds]?|ing|tion)|decreas(?:e[ds]?|ing)|lower(?:ed|ing)?|minimiz(?:e[ds]?|ing))\s+(?:the\s+)?latency\b',
            r'\blatency\b'
        ]
        for pat in lat_patterns:
            for m in re.finditer(pat, text_lower):
                matched = m.group(0).strip()
                if "latency" not in vault_lower:
                    reasons.append(f"Unsupported latency claim: '{matched}' is not explicitly supported by verified evidence.")
                    break
            if any("latency" in r.lower() for r in reasons):
                break

        # 11. Optimization Claims
        opt_matches = re.finditer(
            r'\b(?:optimiz(?:e[ds]?|ing)|optimizations?)\s+(?:the\s+)?([a-zA-Z0-9_\-\.\+]+(?:\s+[a-zA-Z0-9_\-\.\+]+){0,3})\b',
            text_lower
        )
        for m in opt_matches:
            matched = m.group(0).strip()
            target = m.group(1).strip() if m.group(1) else ""
            if "optimiz" not in vault_lower:
                reasons.append(f"Unsupported optimization claim: '{matched}' is not explicitly supported by verified evidence.")
            elif target:
                stop_words = {"for", "and", "the", "across", "of", "to", "in", "with", "by", "on", "a", "an"}
                target_words = [w for w in target.split() if w not in stop_words and len(w) > 2]
                if target_words and not any(w in vault_lower for w in target_words):
                    reasons.append(f"Unsupported optimization claim: '{matched}' is not explicitly supported by verified evidence.")

        # 12. Causal / Purpose Benefit Clauses
        causal_matches = re.finditer(
            r'\b(?P<prefix>to\s+(?:streamline|optimize|improve|enhance|accelerate|boost|maximize|minimize)|resulting\s+in|leading\s+to|driving|yielding|achieving)\s+(?P<target>[a-zA-Z0-9_\-\.\+]+(?:\s+[a-zA-Z0-9_\-\.\+]+){0,4})\b',
            text_lower
        )
        for m in causal_matches:
            matched = m.group(0).strip()
            if any(matched in r or r in matched for r in reasons):
                continue
            prefix = m.group("prefix").strip()
            target = m.group("target").strip()
            action_word = prefix.split()[-1]
            stop_words = {"for", "and", "the", "across", "of", "to", "in", "with", "by", "on", "a", "an"}
            target_words = [w for w in target.split() if w not in stop_words and len(w) > 2]
            action_supported = action_word[:5] in vault_lower if len(action_word) >= 5 else action_word in vault_lower
            target_supported = any(w in vault_lower for w in target_words) if target_words else True
            if not action_supported or not target_supported:
                reasons.append(f"Unsupported causal/benefit claim: '{matched}' is not explicitly supported by verified evidence.")

        return list(dict.fromkeys(reasons))

    def analyze_resume_quality(self, twin: CareerTwin, vault: Optional[EvidenceVault] = None) -> Dict[str, Any]:
        """
        Audits bullet points for action orientation, quantification, and impact.
        Preserved for backwards compatibility.
        """
        all_bullets: List[Dict[str, Any]] = []
        weak_bullets: List[Dict[str, Any]] = []
        quantified_count = 0
        strong_verb_count = 0

        for exp in twin.experience:
            if not exp.description:
                continue
            for line in exp.description.split("\n"):
                clean = line.strip().strip("•-* ")
                if len(clean) < 15:
                    continue

                words = clean.split()
                # Check weak opener
                is_weak = any(p.search(clean) for p in WEAK_OPENERS)
                has_metric = bool(re.search(r'\d+(?:\.\d+)?%|\$\d+|\b\d+\b', clean))
                has_strong_verb = words[0].lower() in STRONG_ACTION_VERBS if words else False

                if has_metric:
                    quantified_count += 1
                if has_strong_verb:
                    strong_verb_count += 1

                bullet_info = {
                    "text": clean,
                    "role": exp.role,
                    "company": exp.company,
                    "has_metric": has_metric,
                    "has_strong_verb": has_strong_verb,
                    "is_weak": is_weak,
                }
                all_bullets.append(bullet_info)

                if is_weak or not has_metric:
                    weak_bullets.append(bullet_info)

        total = len(all_bullets)
        quant_pct = round((quantified_count / total * 100), 1) if total else 0.0
        strong_pct = round((strong_verb_count / total * 100), 1) if total else 0.0

        score = 100.0
        if quant_pct < 40:
            score -= 20
        if strong_pct < 50:
            score -= 15
        if len(weak_bullets) > 3:
            score -= 15

        return {
            "overall_resume_health_score": max(40.0, score),
            "total_bullets_audited": total,
            "quantified_bullets_percentage": quant_pct,
            "strong_action_verb_percentage": strong_pct,
            "bullets_needing_improvement": weak_bullets[:5],
            "recommendation": (
                "Transform passive descriptions into XYZ accomplishments: "
                "'Accomplished [X], as measured by [Y], by doing [Z]'."
            )
        }
