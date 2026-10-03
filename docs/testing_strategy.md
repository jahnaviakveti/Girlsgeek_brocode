# Testing Strategy

We employ a 12-layer independent testing methodology to validate each modular component independently during development without relying on final organizer-provided datasets.

1. **Document Parsing:** Test raw text extraction, multi-column handling, and layout resilience across varied PDF formats.
2. **JD Requirement Extraction:** Validate parsing of job descriptions into distinct categories and priority levels (required vs. preferred).
3. **Resume Extraction:** Validate segmentation of resume documents into standard structural sections (experience, skills, projects, education).
4. **Keyword/Lexical Matching:** Evaluate exact token overlaps, case and punctuation normalization, fuzzy string distance, and alias/synonym mappings across candidate text. Exact, normalized, fuzzy, alias, and other lexical techniques will be evaluated during later implementation rather than pre-committing to a specific algorithm.
5. **Fuzzy/Synonym Matching:** Test typo tolerance, acronym resolution, and canonical term normalization.
6. **Semantic Matching:** Test dense vector cosine similarities against conceptually equivalent phrasing and unrelated distractor concepts.
7. **Experience Matching:** Test calculation of duration, chronological validation, and domain-relevant tenure.
8. **Qualification Matching:** Validate degree tiering, field-of-study alignment, and education status.
9. **Scoring:** Validate sub-score aggregation, configurable component weighting, and penalty application logic.
10. **Ranking:** Ensure final sorted outputs correctly reflect score differentials and maintain deterministic ordering.
11. **Explainability:** Validate grounded evidence citations, matched skill lists, and missing requirement identification.
12. **End-to-End Integration:** Full pipeline tests using synthetic inputs to ensure smooth data contracts across all layers.
