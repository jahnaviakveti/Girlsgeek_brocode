# Phase 8 — Evidence-First Explainability Architecture

## 1. Architectural Role of Phase 8 within the Pipeline

Phase 8 introduces the **Evidence-First Explainability Layer** to the InternLoom Smart Shortlisting Engine. It directly addresses the 20% competition rubric weight for explanation quality by converting structured candidate scoring results and hybrid requirement evaluations into recruiter-readable, fully auditable natural-language narratives.

```
                    ┌────────────────────────────┐
                    │      Job Description       │
                    │  (Phase 3 JD Intelligence) │
                    └─────────────┬──────────────┘
                                  │
                                  ▼
┌───────────────────┐       ┌────────────────────────────┐
│   Parsed Resume   ├──────►│     Hybrid Evaluator       │
│  CandidateProfile │       │  (Phase 7 Scoring Engine)  │
│(Phase 4 Intelligence)     └─────────────┬──────────────┘
└───────────────────┘                     │
                                          ▼
                            ┌────────────────────────────┐
                            │   CandidateRankingResult   │
                            │  • Rank & Overall Score    │
                            │  • Requirement Evaluations │
                            │  • Score Breakdown         │
                            └─────────────┬──────────────┘
                                          │
                                          ▼
                            ┌────────────────────────────┐
                            │     ExplanationEngine      │
                            │ ┌────────────────────────┐ │
                            │ │   EvidenceSelector     │ │
                            │ └───────────┬────────────┘ │
                            │             ▼              │
                            │ ┌────────────────────────┐ │
                            │ │  ExplanationTemplates  │ │
                            │ └────────────────────────┘ │
                            └─────────────┬──────────────┘
                                          │
                                          ▼
                            ┌────────────────────────────┐
                            │    CandidateExplanation    │
                            │  • why_ranked_here         │
                            │  • summary narrative       │
                            │  • key strengths & gaps    │
                            │  • requirement breakdown   │
                            │  • deduplicated evidence   │
                            └────────────────────────────┘
```

The explanation engine acts strictly as a **read-only consumer** of Phase 7 evaluation outputs (`CandidateRankingResult`). It does not calculate new scores, alter rankings, or perform independent keyword or semantic evaluations.

---

## 2. Why Explainability is Evidence-First rather than LLM-First

A traditional LLM-first shortlisting explanation layer introduces severe operational and legal risks:
- **Hallucinated Qualifications:** LLMs frequently invent experience, skills, or degrees that do not exist in the candidate's CV.
- **Unverifiable Rationale:** "Black-box" LLM output cannot point a hiring manager to the exact page, section, and line supporting a claim.
- **Non-Determinism:** The same candidate evaluated twice could receive conflicting explanations and verdicts.
- **Cloud Latency & Privacy Breaches:** Sending applicant CVs to third-party cloud APIs breaches candidate privacy and introduces unpredictable API throttling and latency.

**InternLoom's Evidence-First Architecture** guarantees:
1. **No Claim Without Evidence:** An explanation cannot state that a candidate possesses a qualification unless that exact qualification was extracted and verified in the candidate profile with provenance.
2. **Mathematical Coherence:** Every point value cited in an explanation matches the exact weight, hybrid score, and overall score computed by the scoring engine.
3. **Auditability & Provenance:** Every claim links directly to its source text snippet, document section, and page number.
4. **100% Determinism:** Running explanation generation repeatedly produces identical results bit-for-bit.

---

## 3. Exact Explanation Schemas

### `EvidenceReference`
Represents a single piece of verified document evidence supporting an evaluation claim:
- `evidence_text: str`: The extracted skill name, job sentence, or credential text.
- `evidence_type: str`: Recruiter-friendly evidence category (e.g., `"Technical Skill"`, `"Work Experience"`, `"Certification"`).
- `source_section: Optional[str]`: Resume section where evidence was found (e.g., `"WORK EXPERIENCE"`).
- `page_number: Optional[int]`: PDF page number (1-indexed).
- `source_text: Optional[str]`: Surrounding context or raw sentence.
- `match_method: Optional[str]`: Matching mechanism (`"EXACT"`, `"ALIAS"`, `"FUZZY"`, `"SEMANTIC_CONCEPTUAL"`, `"SEMANTIC_CONTEXT"`).
- `lexical_score: Optional[float]`: Normalized lexical match score (0.0–1.0).
- `semantic_score: Optional[float]`: Cosine similarity score (0.0–1.0).

### `RequirementExplanation`
Details how an individual JD requirement was evaluated for the candidate:
- `requirement_id: str`: Unique identifier of the JD requirement.
- `requirement_text: str`: Exact text of the requirement.
- `category: RequirementCategory`: Category (`SKILL`, `EXPERIENCE`, `EDUCATION`, `CERTIFICATION`).
- `priority: RequirementPriority`: Priority (`REQUIRED`, `PREFERRED`).
- `is_required: bool`: Convenience flag indicating mandatory qualification.
- `verdict: MatchVerdict`: Structured verdict (`MATCHED`, `PARTIAL`, `MISSING`).
- `requirement_score: float`: Combined hybrid score (0.0–1.0).
- `contribution_to_score: float`: Exact point contribution to overall score (0.0–100.0 scale).
- `explanation: str`: Recruiter-friendly natural-language sentence explaining the verdict.
- `supporting_evidence: List[EvidenceReference]`: Up to 2 best pieces of verified evidence (empty for `MISSING`).

### `CandidateExplanation`
The root explanation document for a candidate:
- `candidate_id: str`: Unique candidate identifier.
- `candidate_name: Optional[str]`: Extracted candidate name.
- `rank: int`: Final rank position (1-indexed).
- `overall_score: float`: Final normalized score (0.0–100.0).
- `is_top_3: bool`: Flag indicating top-tier shortlisting status.
- `why_ranked_here: str`: Executive explanation comparing the candidate to peers and requirements.
- `summary: str`: High-level summary of requirement fulfillment and scores.
- `strengths: List[str]`: Distinct positive differentiators.
- `matched_requirements: List[RequirementExplanation]`: Fully matched requirements.
- `partial_requirements: List[RequirementExplanation]`: Partially matched requirements.
- `missing_required_requirements: List[RequirementExplanation]`: Missing mandatory criteria.
- `missing_preferred_requirements: List[RequirementExplanation]`: Missing preferred criteria.
- `score_breakdown: ScoreBreakdown`: Full requirement match counts and category breakdown.
- `all_evidence: List[EvidenceReference]`: Deduplicated list of all resume evidence cited.

---

## 4. Why-Ranked-Here Generation Logic (Top 3 vs Lower Ranks)

The engine provides differentiated depth based on ranking tier:

### Top 3 Candidates (In-Depth Executive Rationale)
For ranks 1, 2, and 3, `why_ranked_here` provides comprehensive comparative analysis:
- **Rank 1:** Explains why the candidate achieved the top position (e.g., `"Ranked #1 with top overall score 87.3/100. Fully satisfies all mandatory requirements (2/2 required) with verified experience and strong complementary skill coverage."`).
- **Rank 2 & 3:** Explains why they are shortlisted in the top tier and articulates the specific distinction that placed them behind higher ranks (e.g., `"Ranked #2 with overall score 82.7/100. Strong candidate satisfying 2/2 required criteria, ranking behind Rank #1 primarily due to lower overall evidence depth."`).
- **Detailed Strengths:** Highlights direct mandatory skill matches, verified experience longevity, and preferred bonus qualifications.

### Lower-Ranked Candidates (Concise, Constructive Diagnostics)
For ranks 4 and below:
- Clear, respectful, objective explanation of score and missing criteria.
- Specifically calls out unfulfilled mandatory requirements (e.g., `"Ranked #54 with score 0.0/100 due to absence of matching evidence for core requirements."`).
- Outlines exact areas where supporting evidence was not found in the submitted resume.

---

## 5. Evidence Selection, Ranking, and Deduplication Rules

The `EvidenceSelector` applies strict deterministic rules to select and format evidence:
1. **Selection Hierarchy:**
   - **Primary:** Strongest lexical match (exact keyword, recognized alias, or fuzzy stem) with exact provenance.
   - **Secondary:** Strongest semantic match from surrounding project or experience context, provided it adds distinct conceptual context and is not identical text.
2. **Missing Requirement Rule:** If `verdict == MatchVerdict.MISSING`, the supporting evidence list is strictly forced to `[]`.
3. **Candidate-Level Deduplication:** When multiple requirements reference the same resume statement, `deduplicate_evidence` indexes items by `(text_lowercase, evidence_type, page_number)`, ensuring candidate-level evidence summaries are concise and non-redundant.

---

## 6. Handling of Missing Evidence

The explanation engine never makes unprovable claims about a candidate's real-world abilities. Instead, it adheres to conservative, legally defensible language:
- **Never:** *"Candidate does not know Python."* or *"Candidate lacks cloud experience."*
- **Always:** *"Supporting evidence was not found in the submitted resume."*

This phrasing reflects the objective reality of resume screening: the system only assesses what is documented in the candidate's submission.

---

## 7. Protection Against Semantic Hallucinations

To prevent embedding similarity from fabricating concrete factual credentials:
- **Concrete Technical Skills:** If a JD requires a specific skill (e.g., `AWS`, `PostgreSQL`), a purely semantic similarity against an unrelated skill (e.g., `Photoshop` with cosine similarity ~0.11) cannot yield a `MATCHED` verdict.
- **Certifications:** Professional certifications (e.g., `AWS Certified Solutions Architect`, `PMP`) require verified certification records; high semantic similarity in project descriptions cannot claim a certification is held.
- **Academic Degrees:** Educational degrees (e.g., `Master of Science in Computer Science`) cannot be inferred from years of experience or general technical terms.

---

## 8. Protection Against Aspirational and Negative Statements

Candidates often mention technologies in negative or aspirational contexts:
- *"Interested in learning Kubernetes"*
- *"Familiar with basic Python syntax but no production experience"*
- *"Did not use AWS due to budget constraints"*

During Phase 4 and Phase 7, such statements are flagged (`is_aspirational_or_negated=True`). Phase 8 enforces that:
- Aspirational or negated evidence is never used to generate positive `MATCHED` requirement explanations.
- Aspirational evidence is disqualified from candidate key strengths.

---

## 9. Recruiter-Friendly Phrasing Translations

Technical internal enums and symbols are mapped to polished, professional human terminology:

| Internal Category | Recruiter-Friendly Terminology |
| :--- | :--- |
| `skill` | Technical Skill |
| `experience` | Work Experience |
| `project` | Project |
| `education` | Education |
| `certification` | Certification |
| `summary` | Professional Summary |
| `EXACT` | Direct exact match in resume text |
| `ALIAS` | Verified domain alias match |
| `FUZZY` | Lexical variation / stem match |
| `SEMANTIC_CONTEXT` | Verified project / experience context |
| `SEMANTIC_CONCEPTUAL` | Strong conceptual alignment |

---

## 10. Offline Guarantee and Zero-Cloud Compliance

Phase 8 operates under the same strict offline guarantee as previous phases:
- **No LLMs:** All sentences are generated using deterministic templates and verified structured evidence.
- **No Network Requests:** `HF_HUB_OFFLINE=1` is enforced across all test and evaluation scripts.
- **Zero Third-Party APIs:** Candidate data never leaves the local execution environment.

---

## 11. Performance Characteristics

- **Explanation Generation Latency:** `< 0.15 ms` per candidate explanation.
- **End-to-End Batch Explanation (54 Candidates):** `< 8 ms` total explanation runtime after scoring.
- **Memory Footprint:** Zero additional persistent memory overhead (stateless template rendering).

---

## 12. 54-PDF External Corpus Evaluation Results

The complete explanation pipeline was evaluated across all 54 local PDF resumes from `data/external_resumes/`:

| Metric | Result | Target / Threshold | Status |
| :--- | :--- | :--- | :--- |
| **Resumes Discovered** | 54 | 54 | PASS |
| **Resumes Parsed** | 54 | 54 (100%) | PASS |
| **Document Parsing Crashes** | 0 | 0 | PASS |
| **Candidates Scored & Ranked** | 54 | 54 | PASS |
| **Explanations Generated** | 54 | 54 (100%) | PASS |
| **Top-3 `why_ranked_here` Verified** | 100% | 100% | PASS |
| **Top-3 `strengths` Verified** | 100% | 100% | PASS |
| **Provenance Integrity (page/sec)** | 100% | 100% | PASS |
| **Verification Errors** | 0 | 0 | PASS |
| **Total Pipeline Runtime (Parse + Rank + Explain)**| 14.28s | < 60s | PASS |

---

## 13. Extensibility Guide for Phase 9 UI

Phase 8 outputs provide first-class JSON schemas designed for direct consumption by modern frontend frameworks:
- **Top 3 Candidate Banner:** Render `why_ranked_here` in an executive card atop the shortlisting table.
- **Provenance Badges:** Display `page_number` and `source_section` chips next to each cited skill or project evidence.
- **Score Contribution Breakdown:** Plot each requirement's `contribution_to_score` on a visual progress bar or radar chart.
- **Evidence Drawer:** Click on any requirement explanation to reveal the exact snippet from `supporting_evidence` highlighting the candidate's original resume sentence.
