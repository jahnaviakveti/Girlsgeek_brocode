# Hybrid Requirement Evaluation, Scoring, and Ranking (Phase 7)

## 1. Architecture Overview
Phase 7 synthesizes the independent lexical matching foundation (Phase 6) and semantic matching foundation (Phase 5) into requirement-level evaluations, candidate scores, and deterministic rankings.

```
                         JobDescription (JDRequirement)
                                       │
                        ┌──────────────┴──────────────┐
                        ↓                             ↓
                 KeywordMatcher                SemanticMatcher
                        │                             │
                        ↓                             ↓
                 Lexical Evidence              Semantic Evidence
                        │                             │
                        └──────────────┬──────────────┘
                                       ↓
                             RequirementEvaluator
                                       ↓
                          RequirementEvaluationResult
                                       ↓
                                 ScoringEngine
                                       ↓
                        CandidateScore + ScoreBreakdown
                                       ↓
                                RankingService
                                       ↓
                          CandidateRankingResult (1..N)
```

The scoring pipeline operates deterministically without any black-box LLM scoring, cloud APIs, or opaque heuristics.

---

## 2. Component Signals & Hybrid Combination Formula
Let $L$ be the normalized lexical score ($0.0 \dots 1.0$) from the strongest valid lexical match, and $S$ be the cosine similarity ($0.0 \dots 1.0$) from the strongest valid semantic match:

1. **Exact / Alias Lexical Match Present ($L = 1.0$)**:
   $$\text{hybrid\_score} = 0.65 \cdot L + 0.35 \cdot S$$
   - *Rationale*: An exact or canonical alias match provides direct proof that the candidate possesses or references the technology. Contextual semantic similarity ($S$) contributes depth (e.g. scale, responsibilities).
2. **Fuzzy Lexical Match Present ($0.85 \le L < 1.0$)**:
   $$\text{hybrid\_score} = 0.50 \cdot L + 0.50 \cdot S$$
   - *Rationale*: Because fuzzy matches carry minor spelling uncertainty, semantic similarity is weighted equally to confirm conceptual alignment.
3. **Pure Semantic / Conceptual Match ($L = 0.0, S \ge 0.35$)**:
   $$\text{hybrid\_score} = 0.75 \cdot S$$
   - *Rationale*: Legitimate conceptual overlap (e.g., "Kubernetes" fulfilling "container orchestration") receives positive credit. Credit is scaled to a maximum of $0.75 \times S$ to prevent semantic hallucination. Similarities below $0.35$ are treated as background noise ($0.0$).

> [!NOTE]
> All weights and multipliers are explicit engineering constants (`constants.py`). They are designed for transparent calibration and verification against ground truth rather than presented as scientifically optimal.

---

## 3. Critical Guardrails: Semantic-Only Matching Safety
Semantic similarity alone must **never** hallucinate possession of concrete skills, credentials, or degrees:
1. **Certifications (`RequirementCategory.CERTIFICATION`)**:
   - Requires concrete credential evidence. General semantic proximity from general experience (e.g. "cloud computing experience" $\leftrightarrow$ "AWS Certified Solutions Architect") awards **zero credit** ($0.0$, `MISSING`).
2. **Academic Degrees (`RequirementCategory.EDUCATION`)**:
   - Requires concrete educational qualification evidence. Semantic topical proximity from unrelated degrees (e.g. "Bachelor of Arts in History" $\leftrightarrow$ "Bachelor's degree in Computer Science") awards **zero credit** ($0.0$, `MISSING`).
3. **Concrete Named Technical Skills (`RequirementCategory.SKILL`)**:
   - If a requirement specifies a concrete technical language/tool (e.g. "Python", "Java", "Docker", "PostgreSQL", "React") and lexical evidence is absent, general semantic proximity from unrelated text (e.g. "data analysis and statistical modeling" $\leftrightarrow$ "Python programming") awards **zero credit** ($0.0$, `MISSING`).
4. **Conceptual / Architectural / Domain Requirements**:
   - Legitimate conceptual matching (e.g. "Kubernetes" fulfilling "container orchestration") remains fully supported.

---

## 4. Total vs. Technology-Specific Experience
For requirements demanding quantified experience (e.g., "3+ years of Python experience"):
- **Total Employment Tenure $\neq$ Technology-Specific Tenure**:
  - A candidate with 5 years of total career employment (e.g. 5 years as a Java developer) who merely lists Python in skills must **not** receive credit for 3+ years of Python experience.
- **Tenure Verification Protocol**:
  - The evaluator scans candidate employment history specifically for the required domain/technology using boundary-safe matching.
  - If verified tenure $\ge \text{min\_years}$: Full score awarded ($1.0\times$ multiplier, `MATCHED`).
  - If $0 < \text{verified tenure} < \text{min\_years}$: Prorated by tenure ratio $\frac{\text{candidate\_years}}{\text{required\_years}}$ (`PARTIAL`).
  - If skill is present but domain-specific tenure is unverified/unknown: Capped at `PARTIAL` status ($\le 0.60$) with an unverified tenure multiplier ($0.50\times$).

---

## 5. Aspirational & Negative Evidence Filtering
Filtering occurs **before** selecting the strongest semantic or lexical signals:
- **Aspirational Statements** (e.g. "Interested in learning Python", "Plans to learn Python"): Award $0.0$ positive credit and verdict `MISSING`.
- **Negative Disclaimers** (e.g. "No experience with Python", "Haven't worked with Java"): Explicitly detected and award $0.0$ credit.
- **Strongest-Evidence Protection**: If a candidate has valid positive evidence (e.g. "Python" in skills or experience) alongside an aspirational mention elsewhere, the valid evidence is evaluated and the aspirational mention is ignored (does not distort or override valid skill evidence).

---

## 6. Required vs. Preferred Weighting
Requirements carry differential weighting based on priority:
- **Required Requirements**: Weight multiplier $W_{\text{req}} = 3.0$
- **Preferred Requirements**: Weight multiplier $W_{\text{pref}} = 1.0$

$$\text{overall\_score} = 100.0 \times \frac{\sum_i w_i \cdot \text{hybrid\_score}_i}{\sum_i w_i}$$

- *Ranking System, Not Hard Filter*: Missing a required requirement depresses a candidate's score 3x more than missing a preferred requirement, ensuring candidates satisfying required criteria rank substantially higher without arbitrary binary disqualification.

---

## 7. Verdict Determination
Applied **after** requirement-specific semantics (experience duration, concrete skill guardrails) are verified:
- **`MATCHED`**: $\text{hybrid\_score} \ge 0.70$ and experience duration verified.
- **`PARTIAL`**: $0.30 \le \text{hybrid\_score} < 0.70$, or conceptual match, or unverified experience duration.
- **`MISSING`**: $\text{hybrid\_score} < 0.30$.

---

## 8. Keyword Stuffing Protection
Candidate scores are derived from the **strongest valid evidence item** per requirement:
- Repeating "Python" 30 times yields the exact same lexical score ($L = 1.0$) as mentioning it once.
- An authentic, rich production experience entry achieves higher contextual semantic similarity ($S \approx 0.90$) and verified tenure, outranking stuffed profiles.

---

## 9. Score Traceability & Score Breakdown
Every candidate's `overall_score` is directly:
$$\text{overall\_score} = 100.0 \times \frac{\sum_i w_i \cdot \text{hybrid\_score}_i}{\sum_i w_i}$$
- **Zero Hidden Terms**: No magic bonuses, no resume-length modifiers, no arbitrary penalties.
- **Genuine Component Calculations**:
  - `required_score`: Average hybrid score of required requirements ($0\dots 100$).
  - `preferred_score`: Average hybrid score of preferred requirements ($0\dots 100$).
  - `keyword_contribution`: Average lexical score across requirements ($0\dots 100$).
  - `semantic_contribution`: Average semantic similarity across requirements ($0\dots 100$).
  - `experience_score`: Average score of requirements specifying experience tenure.
  - `qualification_score`: Average score of education/certification requirements.

---

## 10. Deterministic Ranking & Tie-Breaking
Candidates are ranked $1 \dots N$ using a five-tier deterministic tie-breaker:
1. `overall_score` descending
2. `required_score` descending (mandatory requirement superiority)
3. `experience_score` descending (verified professional tenure)
4. Number of `MATCHED` requirements descending
5. `candidate_id` alphabetical ascending (stable deterministic tie-breaker)
