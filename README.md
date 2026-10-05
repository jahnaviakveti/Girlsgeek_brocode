# 🌟 Vettora — AI Vetting & Vectorized Shortlisting Platform
### *AI-Powered Multimodal Resume-to-Job Matching, Inclusivity Auditing & Explainable Shortlisting Suite*

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/Frontend-React_19_Vite-61DAFB.svg)](https://react.dev/)
[![Tests](https://img.shields.io/badge/Pytest-397%2F397_Passed-brightgreen.svg)](https://pytest.org/)
[![Embeddings](https://img.shields.io/badge/Embeddings-all--MiniLM--L6--v2-orange.svg)](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

---

## 📌 Executive Summary

**Vettora** is a production-grade, evidence-grounded career intelligence and candidate vetting platform. Built across 9 meticulous phases, Vettora transforms career coaching from speculative keyword manipulation into a verifiable, deterministic science. 

Candidates start with their actual resume, build an immutable **Evidence Vault** and **Career Twin**, evaluate realistic **Job Fit** against market requirements, bridge gaps through **Career Intelligence** and **Career Execution**, prepare with **Interview Readiness**, and publish an honest, shareable **Career Showcase** containing exclusively verified accomplishments with claim scope preservation (Levels 1–5).

### The Complete End-to-End Pipeline
```
RESUME → EVIDENCE VAULT → CAREER TWIN → JOB FIT → RESUME COACH → RESUME BUILDER → CAREER INTELLIGENCE → INTERVIEW READINESS → CAREER EXECUTION → CAREER SHOWCASE
```

---

## 🚀 Key System Highlights

```mermaid
graph TD
    A[Job Description PDF] --> B[MuPDF Parser & Section Extractor]
    C[Candidate Resumes PDFs] --> D[Multi-Column Text Parser & Normalizer]
    
    B --> E[JD Requirement Classifier & Bias Detector]
    D --> F[Resume Skill/Experience Extractor]
    
    E --> G[Hybrid Multi-Factor Evaluation Engine]
    F --> G
    
    G --> H[Semantic Cosine Matching: MiniLM]
    G --> I[Keyword & N-Gram BM25 Matcher]
    G --> J[Experience & Requirement Scorer]
    
    H --> K[Calibrated Hybrid Score 0-100]
    I --> K
    J --> K
    
    K --> L[Explainability & Gap Analysis Generator]
    K --> M[Robustness Auditor & Outlier Detector]
    
    L --> N[React 19 Interactive Recruiter Dashboard]
    M --> N
    E --> O[JD Inclusivity & Bias Audit Card]
    O --> N
```

---

## 💡 Core Capabilities & Innovation

### 1. 📄 Robust Multimodal Document Parsing
- High-fidelity PDF extraction via **PyMuPDF / pdfplumber** handling single/multi-column layouts, tabular resume blocks, and irregular headings.
- Deterministic section detection (Education, Experience, Skills, Projects, Certifications) with smart whitespace and Unicode normalization.

### 2. 🧠 Hybrid Multi-Factor Evaluation Engine
Nexora avoids simplistic keyword counts by computing a calibrated multi-dimensional match score:
$$\text{Score} = w_{\text{req}} S_{\text{req}} + w_{\text{pref}} S_{\text{pref}} + w_{\text{exp}} S_{\text{exp}} + w_{\text{sem}} S_{\text{sem}} + w_{\text{key}} S_{\text{key}} - \text{Penalties}$$
- **Required Requirements Weight**: 35%
- **Preferred Qualifications Weight**: 15%
- **Experience Duration & Depth Weight**: 20%
- **Semantic Vector Alignment (`all-MiniLM-L6-v2`)**: 20%
- **Direct Keyword & Technical Skill Overlap**: 10%

### 3. 🛡️ Bonus Task 1: Job Description Inclusivity & Bias Detector
Nexora automatically audits job postings before candidate ranking to eliminate barriers to diverse talent:
- **5 Bias Classifications**:
  1. 🚻 **Gender-Coded / Hyper-Aggressive Terms** (e.g., *"rockstar"*, *"ninja"*, *"aggressive closer"*)
  2. 🎓 **Pedigree & Tier-1 Degree Locks** (e.g., *"IIT/NIT/Ivy League only"*, *"top-tier university graduates"*)
  3. ⏳ **Unrealistic Experience Ceilings** for entry/intern roles (e.g., *"5+ years required for junior intern"*)
  4. 🎂 **Age & Generational Markers** (e.g., *"digital native"*, *"young energetic team"*)
  5. ♿ **Ableist & Non-Essential Physical Demands** (e.g., *"stand for 8 hours"* on software roles)
- **Scoring & Feedback**: 0–100 Inclusivity Score, Letter Grade (A+ through F), highlighted contextual snippets, and direct **Inclusive Alternatives**.

### 4. 🔍 Explainability & Gap Analysis Engine
- Generates **plain-language hiring justifications** for every candidate.
- Highlights exact **Matched Strengths** and **Critical Missing Requirements**.
- Provides candidate-specific interview prompt suggestions based on detected experience gaps.

### 5. 🏆 Interactive Recruiter Experience (React 19 + Vite)
- **Top-3 Podium Cards** for instant visual identification of best-fit candidates.
- **Dynamic Candidate Inspection Modal** with side-by-side match breakdown, radial score gauges, and evidence snippets.
- **Live Search, Filter & CSV Export** for streamlined recruiting workflows.

---

## 📂 Repository Structure

```
nexora/
├── backend/                       # FastAPI backend service
│   ├── app/
│   │   ├── api/routes/            # API endpoints (/api/v1/analyze, /health)
│   │   ├── core/                  # Configuration & CORS settings
│   │   ├── schemas/               # Pydantic v2 schemas (bias, api, analysis)
│   │   └── services/              # Core algorithms
│   │       ├── document_parser/   # PDF parsing & text normalization
│   │       ├── jd_analyzer/       # Requirement extractor & Bias Detector
│   │       ├── resume_analyzer/   # Candidate profile & experience extractor
│   │       ├── semantic_matcher/  # MiniLM embedding similarity
│   │       ├── keyword_matcher/   # Skill & token matching
│   │       ├── hybrid_evaluator/  # Multi-factor score computation
│   │       ├── explanation_engine/# Structured explainability & gap analysis
│   │       └── robustness_auditor/# Outlier & ranking stability auditor
│   ├── tests/                     # 159 comprehensive unit & integration tests
│   ├── requirements.txt           # Python dependencies
│   └── pytest.ini                 # Pytest configuration
├── frontend/                      # React 19 + Vite dashboard
│   ├── src/
│   │   ├── App.jsx                # Recruiter dashboard with Inclusivity widget
│   │   ├── App.css                # Premium modern UI design system
│   │   └── main.jsx               # React entry point
│   ├── package.json               # Frontend dependencies & scripts
│   └── vite.config.js             # Vite development & build config
├── data/                          # Datasets & evaluation samples
│   ├── testing_dataset/           # Official hackathon sample JD & 18 candidate resumes
│   └── dummy_resumes/             # Multidisciplinary candidate resumes
├── hackathon_information/         # Official hackathon prompts & summary PDFs
│   ├── nexora_Hackathon_Problem_Statement.pdf
│   ├── generate_summary_pdf.py
│   └── generate_1page_summary_pdf.py
├── assets/                        # Walkthrough video, GIF, and thumbnails
│   ├── demo_preview.gif
│   ├── demo_thumbnail.png
│   └── demo_walkthrough.mp4
├── docs/                          # Comprehensive technical documentation
│   ├── architecture.md
│   ├── hybrid_scoring.md
│   ├── explainability.md
│   └── local_web_app.md
└── README.md                      # Project documentation
```

---

## ⚡ Quickstart Guide

### Prerequisites
- **Python 3.11+**
- **Node.js 18+** & **npm**

---

### 1. Start Backend (FastAPI)

```bash
cd backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate       # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run FastAPI backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
> Backend API Swagger Docs: `http://127.0.0.1:8000/docs`  
> Health Check: `http://127.0.0.1:8000/health`

---

### 2. Start Frontend (React + Vite)

In a new terminal window:

```bash
cd frontend

# Install packages
npm install

# Start Vite dev server
npm run dev
```
> Open browser at `http://127.0.0.1:5173`

---

### 3. Run Automated Tests

To execute the entire 397-test suite spanning all 9 phases:

```bash
cd backend
source venv/bin/activate
pytest
```

**Output**:
```text
======================== 397 passed in 20.42s ========================
```

---

## 📊 Evaluation & Sample Testing

1. Launch the frontend dashboard at `http://localhost:5173`.
2. Drag and drop the Job Description from `data/testing_dataset/Sample_JD.pdf`.
3. Select all 18 candidate resumes from `data/testing_dataset/Testing Dataset/`.
4. Click **"Analyze Resumes with AI Engine"**.
5. View:
   - **Job Inclusivity & Bias Audit Pill** (Score & Grade breakdown).
   - **Podium Best Matches** (Top 3 candidates).
   - **Ranked Candidates Table** with overall score, semantic score, and required qualifications met.
   - Click **"Inspect"** on any candidate for deep explainability breakdown and gap analysis.

---

## 👥 Team Brocode — Nexora Hackathon
- **Team**: Brocode
- **Project**: Vettora — AI Vetting & Vectorized Shortlisting Platform
- **Repository**: 
