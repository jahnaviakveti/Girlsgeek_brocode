# Architecture

The system is designed as a locally hosted web application with a decoupled, modular pipeline.

## Planned High-Level Flow
```
Frontend (React/Vite)
    ↓
FastAPI backend (Local REST API)
    ↓
Document processing (PDF Extraction & Segmentation)
    ↓
JD analysis / Resume analysis (Entity & Requirement Extraction)
    ↓
Hybrid matching (Keyword/Lexical + Semantic execution)
    ↓
Requirement evaluation (Evaluating candidate data against JD requirements)
    ↓
Scoring (Component aggregation & rule gates)
    ↓
Ranking (Candidate sorting & score spread calibration)
    ↓
Explainability (Evidence extraction & match justification for top candidates)
    ↓
UI (Interactive presentation & recruiter insights)
```

## Future Matching Strategy
To satisfy the dual evaluation requirement, the future matching subsystem will combine:
- **Keyword/Lexical Matching:** Matching explicit skills, tools, and technical terms using exact tokenization, fuzzy matching, and alias expansion.
- **Semantic Matching:** Matching conceptual meaning, intent, and context using local open-source embedding models.

Both methods will genuinely factor into the final scoring and ranking decisions. Specific algorithms, tokenization strategies, and model architectures will be selected and benchmarked during their respective implementation phases.

---

## Phase 8: Career Execution & Evidence-Based Progress

### Core Principle: ACTION COMPLETION ≠ SKILL ACQUISITION

Phase 8 introduces the Career Execution layer bridging candidate ambition and verifiable qualifications. The system adheres to the non-negotiable rule that completing a task, course, or project does not automatically grant skills or update qualifications. Only authentic evidence validated and committed to the Evidence Vault can alter candidate state.

```
CAREER TARGET
      ↓
CAREER INTELLIGENCE
      ↓
CAREER ACTION
      ↓
EXECUTION / PROGRESS
      ↓
ARTIFACT / EVIDENCE
      ↓
EVIDENCE VALIDATION (Claim Scope & Provenance)
      ↓
EVIDENCE VAULT (Authoritative Ground Truth)
      ↓
CAREER TWIN REFRESH
      ↓
TARGET JOB FIT REFRESH
      ↓
CAREER INTELLIGENCE REFRESH
      ↓
INTERVIEW READINESS
```

### Execution Lifecycle & Deterministic Status Transitions

Every Career Execution enforces deterministic legal state transitions:

- `NOT_STARTED` (`PLANNED`): Initial action created.
- `IN_PROGRESS` (`IN_PROGRESS`): Active execution, logging notes and progress percentage.
- `BLOCKED`: Work impeded with explicit `blocker_reason` and `next_step`. Resuming returns to `IN_PROGRESS`.
- `AWAITING_EVIDENCE` (`EVIDENCE_SUBMITTED`): Artifact submitted with technical references.
- `COMPLETED` (`SELF_REPORTED_COMPLETE`): Candidate marks work finished. **Guaranteed zero mutation to Evidence Vault or Career Twin.**
- `VERIFIED`: Transitioned only after `EvidenceValidationService` verifies genuine artifacts and commits them to the Evidence Vault. Direct client mutation to `VERIFIED` is strictly prohibited.

### Claim Scope Preservation (Levels 1–5)

Grounded in `classify_claim_scope(text)`:
- **Level 1 — Technology Presence**: Mentioned or familiar.
- **Level 2 — Basic Usage**: Exercises, coursework, or tutorials.
- **Level 3 — Implementation**: Built functional applications or projects.
- **Level 4 — Operational / Production**: Deployed, managed, monitored in production environments.
- **Level 5 — Specific Scope**: High-scale cluster admin, multi-region failover.

Artifacts and claims claiming operational/production scope are validated against operational proof; implementation evidence (e.g. Minikube or local repository) is never promoted to operational/production experience.

### Before / After Target Diagnostic Delta

Target progress computes deterministic before/after requirement classification shifts:
- Tracks `matched`, `partial`, `missing`, `visibility_gaps`, and `experience_gaps`.
- Generates granular deltas with previous classification, new verified classification, previous/new claim scope, reason, and supporting evidence IDs.
- Strictly diagnostic: **No employability scores, hiring probabilities, or candidate rankings.**

### API Endpoints

- `POST /api/coach/career-executions`: Create execution record linked to action and target.
- `GET /api/coach/career-executions/{candidate_id}`: List candidate executions.
- `GET /api/coach/career-executions/{candidate_id}/{execution_id}`: Get execution details.
- `POST /api/coach/career-executions/{execution_id}/start`: Transition to `IN_PROGRESS`.
- `POST /api/coach/career-executions/{execution_id}/progress`: Update percentage and private notes.
- `POST /api/coach/career-executions/{execution_id}/submit-artifact`: Submit genuine artifacts.
- `POST /api/coach/career-executions/{execution_id}/complete`: Mark self-reported complete.
- `POST /api/coach/career-executions/{execution_id}/block`: Record blocker reason and next step.
- `POST /api/coach/career-executions/{execution_id}/verify-evidence`: Execute evidence verification pipeline.
- `GET /api/coach/career-targets/{target_id}/progress`: Get before/after target progress comparison and timeline.

### Tenancy & Security Model

- Strict candidate isolation: Every execution requires explicit candidate ownership.
- Cross-candidate read, write, start, or verify operations return `403 Forbidden`.
- Server-side verification: Client-side assertions of verification or scope promotion are completely ignored.

---

## Phase 9: Career Showcase & Production Release

### Core Objective
Transform Vettora into a polished, evidence-grounded career platform where candidates can understand their career state, improve it, execute against gaps, and showcase only verified accomplishments.

```
RESUME
  ↓
EVIDENCE VAULT (Authoritative Ground Truth)
  ↓
CAREER TWIN
  ↓
JOB FIT (Candidate-Centric Alignment)
  ↓
RESUME COACH (Evidence-Locked AI Recommendations)
  ↓
RESUME BUILDER (Verifiable ATS Tailoring & Versioning)
  ↓
CAREER INTELLIGENCE (Visibility vs. Experience Gap Planning)
  ↓
INTERVIEW READINESS (Honest Questions & STAR/CAR Stories)
  ↓
CAREER EXECUTION (Track Progress Without Automatic Skill Granting)
  ↓
VERIFIED CAREER STATE (Committed Evidence Artifacts)
  ↓
CAREER SHOWCASE (Target-Aligned, Provenance-Backed Portfolio)
  ↓
PRODUCTION-READY VETTORA
```

### Key Pillars of Career Showcase

1. **Strict Evidence Vault Authority**:
   - Zero hallucinations or ungrounded claims.
   - Every displayed skill, experience, project, education, certification, and achievement is directly traceable to the Evidence Vault.
   - Unevidenced technologies or skills (e.g. self-assertions without artifacts) are strictly omitted.

2. **Claim Scope Preservation (Levels 1–5)**:
   - Technology Presence (Level 1) is never inflated to Operational/Production (Level 4/5).
   - Projects and stories use honest, measured language based on verified evidence snippets.

3. **STAR / CAR Project Story Builder**:
   - Structured breakdown: Context, Problem, Approach, Implementation, Result, Learning.
   - If a quantitative outcome or metric is not present in the Evidence Vault, it is never fabricated.

4. **Target Alignment with Transparent Gap Honesty**:
   - Showcases align against a candidate's selected Career Target.
   - Honest categorization: Verified Strength, Visibility Gap, Experience Gap, Not Verifiable.
   - The showcase does not hide gaps to look good; it transparently exhibits proven competence.

5. **Privacy, Security & Shareable Profile Architecture**:
   - Visibility states: `PRIVATE` (default), `SHAREABLE`.
   - Unguessable cryptographically random 32-byte share token (`secrets.token_urlsafe(32)`).
   - Zero sequential ID or candidate ID exposure in public URLs.
   - Public view (`GET /api/coach/showcase/public/{token}`) strips all internal database IDs, candidate IDs, and private execution notes.
   - Instant token revocation capability immediately returning `404 Not Found`.

6. **Deterministic Verifiable Export**:
   - Clean structured JSON export matching verified persisted database state.
   - Guaranteed 0% LLM mutation or post-processing alterations during export.
