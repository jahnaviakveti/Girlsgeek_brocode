# Scoring Design

## Architecture
The planned Scoring Engine will aggregate multiple component-level evaluations to produce a calibrated candidate score. The design relies on decoupled components whose formulas and weights will be tuned and verified in later phases.

### Configurable Components Under Consideration
- **Required Requirement Score:** Evaluation of candidate alignment with mandatory prerequisites.
- **Preferred Requirement Score:** Evaluation of candidate alignment with secondary or optional skills.
- **Semantic Score:** Meaning- and context-based similarity evaluation.
- **Keyword/Lexical Score:** Explicit term, token, and technology overlap.
- **Experience Score:** Tenure, seniority, and contextual experience alignment.
- **Qualification Score:** Education level and degree alignment.
- **Critical Requirement Penalty:** A potential penalty mechanism for unfulfilled core requirements, intended to aid in score differentiation across varied candidate profiles.

**Note:** Specific mathematical weights, normalization techniques, and penalty scaling formulas are intentionally not finalized in Phase 1. The scoring architecture is designed to expose these components as configurable parameters for empirical evaluation once implementation begins.
