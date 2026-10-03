import uuid
from typing import List, Dict, Any, Optional

from app.schemas.career_twin import CareerTwin
from app.schemas.evidence_vault import EvidenceVault, VaultEvidenceItem
from app.schemas.interview_readiness import (
    InterviewQuestion,
    QuestionType,
    InterviewRequirementMapItem,
    PreparationStatus,
    EvidenceCitation,
)


class InterviewQuestionService:
    """
    Deterministic question generator grounded in target requirements, Career Twin, and Evidence Vault.
    Safety guarantee: Questions NEVER assert unsupported candidate claims in question text.
    """

    def generate_questions_for_target(
        self,
        interview_target_id: str,
        target_role: str,
        requirement_items: List[InterviewRequirementMapItem],
        twin: CareerTwin,
        vault: EvidenceVault
    ) -> List[InterviewQuestion]:
        """
        Generates safe, evidence-grounded questions from requirement items and authentic experience.
        """
        questions: List[InterviewQuestion] = []
        seen_questions = set()

        def add_q(q: InterviewQuestion):
            key = q.question.strip().lower()
            if key not in seen_questions:
                seen_questions.add(key)
                questions.append(q)

        # 1. Questions from Verified Strengths / READY requirements (Technical & Experience deep-dives)
        for req in requirement_items:
            if req.preparation_status == PreparationStatus.READY:
                # Find matching vault evidence
                ev_items = [it for it in vault.items if it.evidence_id in req.evidence_ids]
                snippets = [it.source_text for it in ev_items if it.source_text]
                primary_ev = ev_items[0] if ev_items else None
                skill_term = primary_ev.related_skill if primary_ev and primary_ev.related_skill else req.requirement_text

                citations = [
                    EvidenceCitation(
                        evidence_id=it.evidence_id,
                        source_text=it.source_text,
                        source_document=it.source_document or "Resume.pdf",
                        section=it.source_section or "Experience",
                        page_number=it.page_number or 1
                    )
                    for it in ev_items
                ]

                # Safe technical question asking how they solved problems with this skill
                add_q(InterviewQuestion(
                    question_id=f"q_{uuid.uuid4().hex[:10]}",
                    interview_target_id=interview_target_id,
                    requirement_id=req.requirement_id,
                    question_type=QuestionType.TECHNICAL,
                    question=f"Can you walk through your practical experience working with {skill_term} as required for the {target_role} role?",
                    rationale=f"Grounded in verified evidence ({', '.join(req.evidence_ids[:2])}). Evaluates technical depth.",
                    evidence_ids=req.evidence_ids,
                    citations=citations,
                    source_snippets=snippets[:2],
                    preparation_area=f"{skill_term} Architecture & Implementation",
                    difficulty="STANDARD",
                    source="EVIDENCE_VAULT",
                    star_prompts={
                        "situation": f"What was the context or architecture where you used {skill_term}?",
                        "task": f"What specific problem or component were you tasked with solving using {skill_term}?",
                        "action": f"What design decisions and implementation steps did you take?",
                        "result": "What observable outcome or system performance was achieved?"
                    }
                ))

            elif req.preparation_status == PreparationStatus.REVIEW:
                # Visibility gap or partial match: ask how they can surface this work clearly
                ev_items = [it for it in vault.items if it.evidence_id in req.evidence_ids]
                snippets = [it.source_text for it in ev_items if it.source_text]
                citations = [
                    EvidenceCitation(
                        evidence_id=it.evidence_id,
                        source_text=it.source_text,
                        source_document=it.source_document or "Resume.pdf",
                        section=it.source_section or "Experience",
                        page_number=it.page_number or 1
                    )
                    for it in ev_items
                ]
                add_q(InterviewQuestion(
                    question_id=f"q_{uuid.uuid4().hex[:10]}",
                    interview_target_id=interview_target_id,
                    requirement_id=req.requirement_id,
                    question_type=QuestionType.EXPERIENCE,
                    question=f"The {target_role} role emphasizes '{req.requirement_text}'. How have you applied this in your previous projects?",
                    rationale="Evidence exists in your vault; this question helps articulate your project scope and decisions clearly.",
                    evidence_ids=req.evidence_ids,
                    citations=citations,
                    source_snippets=snippets[:2],
                    preparation_area=f"Articulating {req.requirement_text}",
                    difficulty="STANDARD",
                    source="CAREER_TWIN",
                    star_prompts={
                        "situation": "Describe the business or technical scenario where this was relevant.",
                        "task": "What was your ownership boundary?",
                        "action": "What specific actions or tools did you use?",
                        "result": "What was the final impact or deliverable?"
                    }
                ))

            elif req.preparation_status == PreparationStatus.PREPARE:
                # Genuine experience gap: NEVER assert candidate has this skill or operational scope!
                # If candidate has technology exposure in vault, reference it honestly while acknowledging missing scope
                vault_techs = {it.related_skill.lower() for it in vault.items if it.related_skill}
                for it in vault.items:
                    for t in (it.related_technologies or []):
                        vault_techs.add(t.lower())
                for k in vault.technology_index.keys():
                    vault_techs.add(k.lower())

                matched_cand_tech = None
                for t in vault_techs:
                    if len(t) >= 3 and t in req.requirement_text.lower():
                        matched_cand_tech = t.capitalize()
                        break

                if matched_cand_tech and any(w in req.requirement_text.lower() for w in ["production", "cluster", "eks", "gke", "scale", "infrastructure", "architect"]):
                    q_text = f"While you have familiarity with {matched_cand_tech}, this role emphasizes '{req.requirement_text}'. What is your current familiarity with this specific scope, and how would you approach developing production {matched_cand_tech} experience?"
                    rationale_text = f"Your Evidence Vault documents exposure to {matched_cand_tech}, but no verified production/operational experience for '{req.requirement_text}'. Prepares candidate to answer honestly about foundational familiarity and ramp-up plan."
                    exp_note = f"Your vault documents foundational {matched_cand_tech} exposure, but no verified production cluster management or administration experience. Discuss your conceptual understanding and proactive ramp-up plan honestly."
                else:
                    q_text = f"The team relies on '{req.requirement_text}'. How would you approach learning and contributing to this area?"
                    rationale_text = f"No verified {req.requirement_text} experience is currently present in your Evidence Vault. Prepares candidate to answer honestly about current familiarity and ramp-up strategy."
                    exp_note = f"No verified {req.requirement_text} experience is currently present in your Evidence Vault. Be prepared to explain your current knowledge level honestly without fabricating claims."

                add_q(InterviewQuestion(
                    question_id=f"q_{uuid.uuid4().hex[:10]}",
                    interview_target_id=interview_target_id,
                    requirement_id=req.requirement_id,
                    question_type=QuestionType.REQUIREMENT_DISCUSSION,
                    question=q_text,
                    rationale=rationale_text,
                    evidence_ids=[],
                    citations=[],
                    source_snippets=[],
                    preparation_area=f"{req.requirement_text.title()} — Experience Gap",
                    difficulty="HARD",
                    source="JOB_FIT",
                    experience_gap_note=exp_note,
                    star_prompts={
                        "situation": "Acknowledge your current stage of hands-on familiarity honestly.",
                        "task": "Explain your structured plan or related foundational concepts.",
                        "action": "Describe projects or learning steps you are actively pursuing.",
                        "result": "Highlight your track record of rapidly ramping up on adjacent technologies."
                    }
                ))

        # 2. Questions derived from authentic candidate projects in Career Twin & Vault
        for proj in (twin.projects or [])[:3]:
            # Collect evidence for this project
            p_name = proj.name or "Key Project"
            p_desc = proj.description or ""
            p_ev_items = [it for it in vault.items if it.related_project and it.related_project.lower() in p_name.lower()]
            p_ev_ids = [it.evidence_id for it in p_ev_items]
            p_techs = [t for t in (proj.technologies or [])]
            tech_str = f" using {', '.join(p_techs[:2])}" if p_techs else ""

            p_citations = [
                EvidenceCitation(
                    evidence_id=it.evidence_id,
                    source_text=it.source_text,
                    source_document=it.source_document or "Resume.pdf",
                    section=it.source_section or "Projects",
                    page_number=it.page_number or 1
                )
                for it in p_ev_items
            ]

            add_q(InterviewQuestion(
                question_id=f"q_{uuid.uuid4().hex[:10]}",
                interview_target_id=interview_target_id,
                requirement_id=None,
                question_type=QuestionType.PROJECT,
                question=f"In your project '{p_name}', what were the most significant technical trade-offs you encountered{tech_str}?",
                rationale=f"Grounded in verified project '{p_name}'. Tests authentic engineering judgment and ownership.",
                evidence_ids=p_ev_ids,
                citations=p_citations,
                source_snippets=[p_desc] if p_desc else [],
                preparation_area=f"Project Deep Dive: {p_name}",
                difficulty="STANDARD",
                source="CAREER_TWIN",
                star_prompts={
                    "situation": f"Why was {p_name} built and what constraints did you face?",
                    "task": "What specific architectural components were you personally responsible for?",
                    "action": "What trade-offs did you evaluate, and why did you select this approach?",
                    "result": "What was the system outcome or lesson learned?"
                }
            ))

        # 3. Behavioral question grounded in verified past teamwork / problem resolution
        if twin.experience:
            primary_exp = twin.experience[0]
            role_title = primary_exp.role or "Engineer"
            comp = primary_exp.company or "your team"
            exp_ev_items = [it for it in vault.items if it.source_section and "experience" in it.source_section.lower()][:2]
            exp_ev_ids = [it.evidence_id for it in exp_ev_items]
            exp_citations = [
                EvidenceCitation(
                    evidence_id=it.evidence_id,
                    source_text=it.source_text,
                    source_document=it.source_document or "Resume.pdf",
                    section=it.source_section or "Experience",
                    page_number=it.page_number or 1
                )
                for it in exp_ev_items
            ]

            add_q(InterviewQuestion(
                question_id=f"q_{uuid.uuid4().hex[:10]}",
                interview_target_id=interview_target_id,
                requirement_id=None,
                question_type=QuestionType.BEHAVIORAL,
                question=f"During your time as {role_title} at {comp}, how did you handle a situation where system requirements or timelines unexpectedly shifted?",
                rationale=f"Grounded in verified experience at {comp}. Tests resilience and stakeholder communication.",
                evidence_ids=exp_ev_ids,
                citations=exp_citations,
                source_snippets=[it.source_text for it in exp_ev_items],
                preparation_area=f"Behavioral Experience: {comp}",
                difficulty="STANDARD",
                source="CAREER_TWIN",
                star_prompts={
                    "situation": f"What was the project at {comp} and what unexpectedly changed?",
                    "task": "What were your immediate responsibilities when the change occurred?",
                    "action": "How did you communicate with stakeholders and adjust engineering priorities?",
                    "result": "What was the final outcome for the delivery timeline and system quality?"
                }
            ))

        return questions
