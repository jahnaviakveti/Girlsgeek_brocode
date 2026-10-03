# Phase 10 — Ranking Robustness Audit Documentation

## 1. Motivation & Purpose

In automated resume shortlisting and candidate ranking systems, a recurring vulnerability is susceptibility to superficial phrasing variations:
- Candidates who happen to write an exact acronym (e.g., `k8s` vs `Kubernetes`, `NodeJS` vs `Node.js`) may receive disparate scores in fragile keyword engines.
- Formatting discrepancies (bullet characters, whitespace collapse, tab stops) can artificially alter token boundaries.
- Over-reliance on exact keyword stuffing can overshadow strong semantic experience.

**Phase 10 implements a deterministic local Ranking Robustness Audit** designed as an inspection and diagnostic layer. It quantifies how resilient candidate rankings are when subjected to controlled perturbations, measuring whether the underlying shortlisting decisions are governed by genuine semantic and contextual competence or mere lexical coincidence.

---

## 2. Architecture & Design Principles

### 2.1 Non-Invasive Diagnostic Wrapper
The `RankingRobustnessAuditor` operates strictly as a read-only harness around the production `RankingService`:
- **Production Immutability:** No production scoring formulas, requirement multipliers (REQUIRED=3, PREFERRED=1), hybrid weights (0.65/0.35, 0.50/0.50, 0.75), or semantic thresholds (0.35) are modified.
- **Deepcopy Isolation:** All candidate profiles are deepcopied before any perturbation is applied. Baseline candidate profiles remain untouched.
- **100% Offline & Local:** Fully functional under `HF_HUB_OFFLINE=1` using pre-cached local embeddings. Zero cloud inference, zero external API calls, zero LLMs.

```
+-------------------------------------------------------------------------+
|                       Baseline Candidate Profiles                       |
+-------------------------------------------------------------------------+
                                     |
                +--------------------+--------------------+
                |                                         |
                v                                         v
   +---------------------------+             +---------------------------+
   |  Production Ranking Engine |             |    Perturbation Harness   |
   |      (Phase 7 Service)    |             |    (Lexical / Mask / Fmt) |
   +---------------------------+             +---------------------------+
                |                                         |
                | Baseline Ranking                        v Perturbed Profiles
                |                            +---------------------------+
                |                            |  Production Ranking Engine |
                |                            |      (Identical Model)    |
                |                            +---------------------------+
                |                                         |
                |                                         | Perturbed Ranking
                +--------------------+--------------------+
                                     |
                                     v
                 +---------------------------------------+
                 |       Audit Metrics Computation       |
                 |  - Top-K Overlap (K=3, 5)             |
                 |  - Spearman Rank Correlation (rho)    |
                 |  - Displacement (Mean / Max)          |
                 |  - Pairwise Inversions & Flips        |
                 |  - Keyword Dependence Index (KDI)     |
                 +---------------------------------------+
                                     |
                                     v
                 +---------------------------------------+
                 |        Robustness Audit Report        |
                 |  - Diagnostic Status Classification   |
                 |  - Requirement Provenance Diff        |
                 +---------------------------------------+
```

---

## 3. Perturbation Operators

The audit implements three deterministic, rule-based perturbation operators:

### 3.1 Lexical Normalization (`LEXICAL_NORMALIZATION`)
- **Mechanism:** Applies a precompiled single-pass regular expression matching canonical software engineering terms, tools, and libraries to their bidirectional synonyms (e.g. `NodeJS` <-> `Node.js`, `Postgres` <-> `PostgreSQL`, `k8s` <-> `Kubernetes`, `cpp` <-> `C++`, `TS` <-> `TypeScript`, `Golang` <-> `Go`, `reactjs` <-> `React`).
- **Objective:** Verifies that candidate rank and scores do not fluctuate when standard technical aliases are swapped.
- **Target Fields:** `skills`, `technologies`, `skill_details`, and text blocks across `experience`, `projects`, and `summary`.

### 3.2 Keyword Masking (`KEYWORD_MASKING`)
- **Mechanism:** Scans candidate evidence for exact JD keyword occurrences and replaces them with a neutral placeholder `[MASKED_SKILL]`.
- **Objective:** Isolates pure semantic and contextual matching. Measures how much of a candidate's score is derived from genuine descriptive experience versus verbatim keyword repetition.
- **Derived Metric:** Keyword Dependence Index (KDI) and Semantic Retention Rate.

### 3.3 Formatting Normalization (`FORMATTING_NORMALIZATION`)
- **Mechanism:** Standardizes exotic Unicode bullet glyphs (`•`, `◦`, `▪`, `►`, `✓`, `★`) into standard markdown hyphens (`-`), collapses repeated whitespace (`[ \t]+` -> single space), strips non-standard indentation, and normalizes line breaks.
- **Objective:** Ensures structural PDF layout noise does not degrade candidate parsing or scoring.

---

## 4. Quantitative Metrics & Equations

### 4.1 Top-K Set Overlap
Measures the intersection stability of the shortlisted top candidates:
Overlap_K = |Top_K_base ∩ Top_K_pert| / K
Evaluated at K = 3 and K = 5.

### 4.2 Spearman Rank Correlation (rho)
Quantifies overall monotonic ranking stability:
rho = 1 - (6 * sum(d_i^2)) / (N * (N^2 - 1))
where d_i = Rank_base(i) - Rank_pert(i) and N is the number of candidates.

### 4.3 Rank Displacement
- **Mean Absolute Displacement (MAD):**
  MAD = (1/N) * sum(|Rank_base(i) - Rank_pert(i)|)
- **Max Absolute Displacement:** max_i |Rank_base(i) - Rank_pert(i)|.

### 4.4 Pairwise Inversions (Flips)
For all candidate pairs (A, B) where A ranked higher than B at baseline:
Flips = sum_{A <_base B} [B <_pert A]
Flip Rate = Flips / (N * (N - 1) / 2)

### 4.5 Keyword Dependence Index (KDI)
Quantifies vulnerability to keyword masking:
KDI = (1/N) * sum((Score_base(i) - Score_masked(i)) / Score_base(i))
Semantic Retention Rate = 1.0 - KDI

---

## 5. Engineering Interpretation & Diagnostic Classifications

To guide recruiter understanding, perturbation runs receive a documented engineering classification based on composite thresholds:
- **ROBUST**: Top-3 Overlap >= 0.67, rho >= 0.85, and Mean Displacement <= 1.5.
- **MODERATELY_SENSITIVE**: Top-3 Overlap >= 0.33, rho >= 0.60, and Mean Displacement <= 3.5.
- **HIGHLY_SENSITIVE**: Top-3 Overlap < 0.33, rho < 0.60, or Mean Displacement > 3.5.

*Note: These qualitative classifications are diagnostic interpretations for human recruiters and auditors; they do not alter automated ranking.*
