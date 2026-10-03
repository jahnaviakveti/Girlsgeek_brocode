# Keyword Matching Foundation (Phase 6)

## 1. Purpose & Core Principles
The Keyword Matching foundation provides a deterministic, local, lexical evidence evaluation engine. It serves as the lexical complement to the Semantic Matcher (Phase 5).

The `KeywordMatcher` evaluates a structured `JDRequirement` against structured candidate evidence extracted from a `CandidateProfile`. It identifies lexical matches across exact phrasing, technical aliases, and conservative spelling/format variations, while preserving exact provenance and filtering out aspirational or negated statements.

> [!IMPORTANT]
> **"Lexical match observations are evidence, not final match decisions or candidate scores."**
> A keyword match observation does not independently decide a candidate's final shortlisting rank or requirement verdict. The subsequent Hybrid Requirement Evaluator (Phase 7) is responsible for synthesizing keyword and semantic evidence.

---

## 2. Architecture & Modules
Located under `backend/app/services/keyword_matcher/`:
- `normalization.py`: Case normalization, whitespace collapsing, tokenization, and technical boundary punctuation cleaning.
- `aliases.py`: Technical alias registry mapping normalized aliases (e.g. `NodeJS`, `node js`, `node.js` -> `Node.js`) to canonical forms.
- `matcher.py`: Core `KeywordMatcher` implementing exact matching, alias lookup, conservative fuzzy matching, false-positive protection, and result ranking.
- `backend/app/schemas/keyword_matching.py`: Defines the `KeywordMatchResult` schema.

---

## 3. Normalization Strategy
Text and tokens are normalized deterministically:
1. **Case Normalization**: All comparisons are lowercased.
2. **Whitespace Normalization**: Multiple consecutive whitespace characters are collapsed into a single space; leading/trailing spaces are stripped.
3. **Punctuation Trimming with Technical Symbol Preservation**:
   - Strips enclosing formatting punctuation (parentheses, brackets, commas, colons, quotes).
   - Carefully preserves interior technical characters such as `+` (`C++`), `#` (`C#`), `.` (`.NET`, `Node.js`), and `/` (`CI/CD`).

---

## 4. Technical Alias Handling
The alias registry (`aliases.py`) unifies common technical nomenclature variations without requiring brittle external models:
- Reuses and extends the canonical technology taxonomy from Phase 3/4.
- Examples of registered alias mappings:
  - `NodeJS` / `node js` / `node.js` -> `Node.js`
  - `Postgres` / `postgresql` -> `PostgreSQL`
  - `Golang` / `go` -> `Go`
  - `K8s` / `kubernetes` -> `Kubernetes`
  - `JS` / `javascript` -> `JavaScript`
  - `TS` / `typescript` -> `TypeScript`
  - `ReactJS` / `react.js` / `react` -> `React`
  - `AWS` / `amazon web services` -> `AWS`
  - `GCP` / `google cloud platform` -> `GCP`
  - `C++` / `cpp` -> `C++`
  - `C#` / `csharp` -> `C#`
- **Unknown / Proprietary Terms**: Proprietary or non-standard technical terms (e.g. internal company frameworks like "KubeVortex") are never dropped; they remain fully matchable through exact and fuzzy matching.

---

## 5. Exact Matching & False-Positive Protections
Lexical matching avoids substring and character-level false positives:
- **Tech-Safe Boundary Patterns**: Regex boundary patterns `(?<![a-zA-Z0-9+#])term(?![a-zA-Z0-9+#])` prevent matches inside other words.
- **Substring Protection**:
  - `Java` does NOT match inside `JavaScript`.
  - `C` does NOT match inside `C++` or `C#`.
  - `R` does NOT match inside `Raspberry Pi`, `Ruby`, or `React`.
- **Short-Token Safety**: Short tokens (length <= 3) are strictly matched on explicit token or tech boundaries and are never passed to fuzzy matching.

---

## 6. Conservative Fuzzy Matching
To accommodate genuine typos or alternate formats (e.g., `typescrpt` -> `TypeScript`), controlled fuzzy matching is supported using Python's deterministic `difflib.SequenceMatcher`:
- **Conservative Threshold**: Similarity ratio $\ge 0.85$.
- **Length Constraints**:
  - Minimum token length $\ge 4$ characters.
  - Maximum character length difference $\le 2$ characters.
- **Safe Evaluation**: Unrelated terms (e.g. `Docker` vs `Photoshop`) or differing lengths (e.g. `Java` vs `JavaScript`) are rejected immediately.

---

## 7. Evidence Awareness & CandidateProfile Integration
Candidate evidence is extracted from the structured `CandidateProfile`, distinguishing the context of where the keyword appeared:
- **Explicit Skills** (`CandidateSkill`): Direct skill evidence (`evidence_type="skill"`).
- **Work Experience** (`CandidateExperience`): Experience descriptions and roles (`evidence_type="experience"`).
- **Projects** (`CandidateProject`): Project titles and descriptions (`evidence_type="project"`).
- **Education** (`CandidateEducation`): Degree and field of study (`evidence_type="education"`).
- **Certifications** (`CandidateCertification`): Credential names (`evidence_type="certification"`).
- **Summary**: Professional summary text (`evidence_type="summary"`).

---

## 8. Aspirational & Negation Protections
Lexical matches inside aspirational or negated statements are filtered out and not treated as positive capability evidence:
- **Aspirational Statements**:
  - Statements matching cues like `"interested in learning <skill>"`, `"plans to learn <skill>"`, `"seeking to learn <skill>"` are rejected.
- **Negated Statements**:
  - Statements matching cues like `"no experience with <skill>"`, `"never worked with <skill>"`, `"little to no experience with <skill>"` are rejected.

---

## 9. Result Contract: `KeywordMatchResult`
`KeywordMatchResult` contains strictly lexical observations:
- `requirement_id`: ID of the evaluated requirement.
- `evidence_id`: `None` (no synthetic IDs fabricated).
- `requirement_text`: Original requirement string.
- `matched_keyword`: Specific keyword that triggered the match.
- `evidence_text`: Full text snippet of candidate evidence.
- `match_type`: `EXACT`, `ALIAS`, or `FUZZY`.
- `lexical_score`: `1.0` for EXACT and ALIAS; similarity ratio for FUZZY.
- `page_number`, `source_section`, `source_text`: Full provenance from domain `Evidence`.
- `evidence_type`: `skill`, `experience`, `project`, etc.
- `evidence`: Direct reference to domain `Evidence`.

### What This Phase Deliberately Does NOT Do
- No candidate scoring or point calculation.
- No weighting of `required` vs `preferred` requirements.
- No ranking or top-3 selection.
- No final `MATCHED`, `PARTIAL`, or `MISSING` verdicts.
- No hybrid combination with semantic embeddings.

---

## 10. Offline Verification & Performance
- **100% Offline**: Requires zero network access, zero external APIs, zero LLMs.
- **Performance**: Evaluated across all 54 external resume PDFs in 1.23 seconds (average <23ms per resume).
