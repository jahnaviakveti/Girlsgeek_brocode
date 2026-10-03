# Phase 9 — Local Web Application & End-to-End Integration

## 1. System Architecture Overview

Phase 9 integrates the complete 8-phase local intelligence engine into an interactive, recruiter-oriented web application. The platform allows a recruiter to upload a single Job Description PDF along with a batch of candidate resume PDFs (15–18 typical in competition evaluation), process them locally, and view transparent, evidence-backed candidate rankings.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        BROWSER FRONTEND (React 19)                     │
│  • Upload View (JD + Resume Batch)                                     │
│  • Processing State (Local Progress)                                   │
│  • Results Dashboard (Top-3 Shortlist Cards + Full Ranking Table)      │
│  • Candidate Detail Drawer (Provenance, Evidence Quotes, Breakdowns)   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP multipart/form-data
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        FASTAPI BACKEND (Localhost:8000)                │
│  POST /api/analyze                                                     │
│  ├── DocumentParser (PyMuPDF - PDF text & section extraction)          │
│  ├── JDAnalyzer (Extensible rule-based requirement extraction)         │
│  ├── ResumeAnalyzer (CandidateProfile & experience extraction)         │
│  ├── KeywordMatcher (Deterministic lexical matching with provenance)   │
│  ├── SemanticMatcher (Local Sentence-Transformer embedding similarity) │
│  ├── RequirementEvaluator (Hybrid keyword + semantic verdicts)         │
│  ├── ScoringEngine (Mathematically weighted candidate scoring)         │
│  ├── RankingService (Monotonic non-increasing ranking & tie-breaks)    │
│  └── ExplanationEngine (Deterministic, evidence-first explainability)  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. API Specifications

### `POST /api/analyze` (and `POST /api/v1/analyze`)
- **Content-Type:** `multipart/form-data`
- **Parameters:**
  - `jd_file: UploadFile` (Required): Single PDF file containing the target Job Description.
  - `resume_files: List[UploadFile]` (Required): Multiple PDF files containing candidate resumes.
- **Success Response (`200 OK`):** Returns `AnalysisResponse` containing:
  - `job`: Extracted title, requirement counts (required vs. preferred), and requirement summaries.
  - `total_resumes_received`: Total files received in upload.
  - `total_candidates_processed`: Number of successfully parsed resumes.
  - `total_ranked`: Number of scored and ranked candidates.
  - `ranked_candidates`: Array of `CandidateExplanation` objects in rank order (1 to N).
  - `failed_candidates`: Array of `{ filename, error }` objects describing isolated document failures.
- **Error Responses:**
  - `400 Bad Request`: Missing JD, zero resumes provided, non-PDF file uploaded, or empty/0-byte file.
  - `500 Internal Server Error`: Unexpected pipeline failure.

### `GET /health`
- **Response:** `{"status": "ok", "app_name": "InternLoom Smart Shortlisting Engine"}`

---

## 3. Upload & Processing Flow

1. **Client-Side Validation:**
   - Validates that the uploaded Job Description has a `.pdf` extension.
   - Validates that all candidate resumes are `.pdf` files.
   - Disables the primary action button until at least 1 JD and 1 resume are selected.
2. **Batch Submission:**
   - Multi-part form stream sends files to `http://localhost:8000/api/analyze`.
3. **Pipeline Execution:**
   - Creates an isolated temporary directory.
   - Parses the JD PDF via `DocumentParser` and extracts requirements via `JDAnalyzer`.
   - Iterates through the resume batch:
     - Valid resumes are parsed and structured into `CandidateProfile`.
     - Corrupt or empty resumes are caught, logged, and appended to `failed_candidates` without terminating the batch.
   - Executes hybrid requirement evaluation, computes overall candidate scores, and assigns deterministic ranks.
   - Assembles natural-language, evidence-backed explanations for all candidates.
   - Cleans up temporary disk files in a `finally` block.

---

## 4. Failure Isolation Policy

To satisfy competition and enterprise operational requirements:
- **No Silent Drops:** If a candidate resume cannot be parsed (e.g. scanned-only image without digital text, corrupted binary stream, or encrypted PDF), the engine isolates the error.
- **Batch Resilience:** The remaining valid candidates in the batch are processed and ranked normally.
- **Recruiter Alert Banner:** The frontend prominently renders a warning banner detailing the filename and diagnostic reason for any failed files.

---

## 5. Division of Responsibilities

### Backend (Authoritative Intelligence)
- All PDF parsing, text normalization, and section detection.
- All keyword matching, alias resolution, and fuzzy stem evaluation.
- All local embedding generation and cosine similarity calculation.
- All hybrid scoring, weight normalization, and candidate ranking.
- All deterministic explanation template rendering and evidence selection.

### Frontend (Presentation Only)
- Upload interface with drag-and-drop and count indicators.
- Loading indicator during asynchronous processing.
- Direct visualization of backend scores, ranks, and badges.
- Filtering and displaying candidate details and supporting evidence quotes.
- **Strict Ban:** The frontend contains **zero** scoring formulas, **zero** ranking comparisons, and **zero** skill-matching heuristics.

---

## 6. Theme Adaptation from `peepsmain-main`

The visual design system of `peepsmain-main` was evaluated and adapted to provide a warm, editorial aesthetic suited for executive recruitment:

| Design Element | `peepsmain-main` Source | InternLoom Adaptation |
| :--- | :--- | :--- |
| **Color Palette** | Warm linen (`#F5F2EB`), espresso (`#3D3935`), taupe (`#8A8273`) | **Reused:** Identical warm, high-contrast palette with accessibility badges. |
| **Card Geometry** | 20px–24px rounded corners with subtle borders | **Reused:** Applied to Podium cards, table containers, and evidence drawers. |
| **Pills & Tags** | Uppercase, tracking-widest rounded pills | **Reused:** Applied to rank badges, provenance tags, and requirement chips. |
| **Noise Texture** | Embedded fractal SVG background overlay | **Reused:** Inline SVG noise texture (`opacity: 0.035`) for tactile feel. |
| **Typography** | Remote Google Fonts (`Playfair Display`, `Outfit`) | **Adapted:** Replaced with system fonts (`ui-serif, Georgia` and `ui-sans-serif, system-ui`) for 100% offline compliance. |
| **Cursor System** | `cursor: none` with custom DOM ball cursor | **Rejected:** Standard native OS cursor restored for usability and accessibility. |
| **Scroll Control** | Lenis smooth scroll interception | **Rejected:** Native browser scrolling restored for table and modal stability. |
| **Entry Shutter** | Animated splash sequence delaying access | **Rejected:** Direct immediate interface rendering. |

---

## 7. How to Run Locally

### Prerequisites
- Python 3.9+ with virtual environment configured in `backend/venv`
- Node.js 18+ and npm installed in `frontend/`

### 1. Start Backend API Server
```bash
cd backend
HF_HUB_OFFLINE=1 ./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```
*The backend will be available at `http://localhost:8000` (Health check: `http://localhost:8000/health`).*

### 2. Start Frontend Development Server
```bash
cd frontend
npm run dev
```
*The web UI will be accessible at `http://localhost:5173`.*

### 3. Production Frontend Build
```bash
cd frontend
npm run build
npm run preview
```
