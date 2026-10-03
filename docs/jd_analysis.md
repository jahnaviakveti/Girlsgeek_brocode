# Job Description Analysis & Requirement Extraction

## Overview
Phase 3 implements a fully local, deterministic, rule-based engine to analyze a generic `GenericDocument` representation of a Job Description and extract structured `JDRequirement` units. It operates without external APIs or cloud LLMs.

---

## 1. Extraction Pipeline Architecture
```
GenericDocument (from Phase 2 Parser)
      │
      ▼
Section & Sentence Reconstructor
  (Handles wrapped lines, paragraphs, bullets, and section context)
      │
      ▼
Actionable Candidate Filter
  (False-positive protection against company boilerplate and filler)
      │
      ▼
Linguistic Classifier & Extractor
  ├── Priority Classifier (REQUIRED vs PREFERRED + Negation Detection)
  ├── Category Classifier (SKILL, EXPERIENCE, EDUCATION, CERTIFICATION, DOMAIN, OTHER)
  └── Experience & Degree Attribute Extractor
      │
      ▼
Granularity Decomposer
  ├── Compound list splitter (atomic technical requirements)
  ├── Contextual conceptual preserver (retains holistic domain statements)
  └── Logical relationship mapper (OR alternatives / AND joint requirements)
      │
      ▼
Structured JobDescription Model
```

---

## 2. Requirement Granularity Strategy
Downstream matching requires granular atomic skills while preserving composite conceptual requirements:
- **Atomic Splitting:** When a sentence contains a list of 3 or more isolated technical tools (e.g., *"Experience with Python, Django, PostgreSQL and Docker"*), it decomposes into 4 atomic `JDRequirement` objects with `logical_operator = "AND"`. This enables precise individual requirement matching.
- **Contextual Preservation:** When a requirement describes complex system design or architectural responsibilities (e.g., *"Demonstrated experience designing scalable distributed systems"*), it is preserved intact as a conceptual requirement (`RequirementCategory.DOMAIN`) rather than broken into disconnected words.

---

## 3. Required vs. Preferred Classification
Priority classification is decoupled from requirement category:
- **Signals for REQUIRED:**
  - Explicit markers: `must`, `required`, `mandatory`, `essential`, `need to`, `should have`, `at least`, `minimum`.
  - Section context: Requirements found under section headings like `Minimum Qualifications`, `Requirements`, `Basic Qualifications`.
- **Signals for PREFERRED:**
  - Explicit markers: `preferred`, `desirable`, `nice to have`, `bonus`, `plus`, `advantage`, `ideally`, `is an advantage`.
  - Section context: Requirements found under section headings like `Preferred Qualifications`, `Nice to Have`, `Bonus Points`.
  - Soft wording: Phrasing such as `familiarity with`, `exposure to`, `interest in` defaults to `PREFERRED` with lower confidence.
- **Ambiguity Handling:** When no explicit markers exist, the system applies conservative default heuristics with an explicit extraction confidence score (e.g., 0.70) rather than assuming certainty.

---

## 4. Confidence Semantics

The `JDRequirement.extraction_confidence` field (aliased as `confidence` for backwards compatibility) measures:

> **Confidence that the JD analyzer correctly interpreted and extracted this requirement from the Job Description text.**

It explicitly does **NOT** mean:
> **Confidence that a candidate satisfies this requirement.**

$$\text{JD Extraction Confidence} \neq \text{Candidate Match Confidence}$$

- **Extraction Confidence (JD Analysis):** Evaluates linguistic clarity, presence of explicit modal keywords, and section context when parsing the JD (e.g., 1.0 for explicit *"must have"*, 0.80 for soft phrasing like *"familiarity with"*).
- **Candidate Match Confidence (Matching Engine):** Will be computed in downstream matching phases and captured within `RequirementMatch` (`keyword_match_score`, `semantic_match_score`, and evidence provenance), completely separate from JD extraction confidence.

---

## 5. Taxonomy Is Extensible

The technical skills taxonomy (`CANONICAL_TECHNOLOGIES`) assists with:
- Canonical normalization (e.g., `ReactJS` $\to$ `React`, `Postgres` $\to$ `PostgreSQL`).
- Known aliases and abbreviations (`K8s` $\to$ `Kubernetes`, `JS` $\to$ `JavaScript`).
- Common technology recognition across languages, frameworks, databases, and cloud tools.

However, the taxonomy is **NOT an exhaustive gatekeeper**:
- An actionable skill or technical term is **never discarded merely because it is absent from the taxonomy**.
- When an unfamiliar, proprietary, or custom technical platform appears in an actionable requirement (e.g., *"Experience with AcmeFlow platform"*), the term is preserved within the requirement's `requirement_text`, `source_text`, and `extracted_keywords`.
- If an unfamiliar term cannot be classified under a known standard category, its category safely defaults to `RequirementCategory.OTHER` (or `SKILL` if accompanied by explicit skill verbs) rather than being dropped.

---

## 6. Requirement Categories
Requirements are mapped into the established `RequirementCategory` enum:
- **`SKILL`:** Specific programming languages, frameworks, libraries, databases, and developer tools.
- **`EXPERIENCE`:** Professional tenure, years of experience, and role-specific durations (e.g., `min_years: 2.0`, `experience_domain: 'backend'`).
- **`EDUCATION`:** Academic degrees (Bachelor's, Master's, PhD, Diploma) and fields of study.
- **`CERTIFICATION`:** Professional accreditations (AWS Certified, CKAD, PMP, Scrum Master).
- **`DOMAIN`:** Industry or architecture paradigms (e.g., Distributed Systems, Fintech, Cloud Security).
- **`OTHER`:** Actionable requirements not fitting above categories (including unfamiliar proprietary platforms).

---

## 7. Negation Handling
Linguistic negation is detected via negative polarity markers:
- Markers: `not required`, `not mandatory`, `not essential`, `no prior experience`, `no degree required`.
- Rule: If negation is detected:
  - `is_negated` is set to `True`.
  - `priority` is set to `PREFERRED` (never `REQUIRED`).
  - The `@property is_required` returns `False`, ensuring downstream matching does not penalize candidates lacking this skill.

---

## 8. Logical Relationships (OR / AND Logic)
- **OR / Alternative Relationships:**
  - Example: *"Experience with React or Angular for frontend development."*
  - Identified via disjunction patterns (`or`, `either ... or`).
  - Structured representation:
    - Single requirement with `is_alternative = True`
    - `logical_operator = "OR"`
    - `alternatives = ["React", "Angular"]`
  - Guarantees downstream scoring does not penalize a candidate who only has React or only has Angular.
- **AND / Joint Relationships:**
  - Example: *"Proficiency in Python and Django is required."*
  - Marked with `logical_operator = "AND"`.

---

## 9. Provenance & Auditability
Each extracted requirement retains complete source tracing:
- `source_text`: The exact sentence or bullet text as found in the original document.
- `page_number`: 1-indexed page where the requirement appeared.
- `source_section`: Title of the section (e.g., `Minimum Qualifications`) from which the requirement was extracted.

---

## 10. False Positive Protection
Ordinary conversational text, company promotional statements, and employee benefits lines are excluded using explicit rejection filters:
- Excludes: *"Working with a collaborative engineering team"*, *"Competitive compensation and comprehensive health benefits"*, *"TechNova Solutions is a fast-paced technology company"*.

---

## 11. Limitations & Future Work
- **Taxonomy Scope:** While proprietary and novel terms are preserved, deep semantic synonym expansion for unlisted tools will be supported by local dense embeddings in Phase 6.
- **Complex Nested Clauses:** Complex multi-clause sentences combining both required and preferred conditions (e.g., *"Python required, but Django is a plus"*) are classified based on the strongest clause signal; multi-clause splitting will be refined in future phases.
- **Intentionally Deferred:** Resume analysis, semantic vector matching, lexical scoring, and candidate ranking are deferred to subsequent phases.
