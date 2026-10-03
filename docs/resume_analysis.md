# Resume Intelligence & Candidate Profile Extraction

## Overview
Phase 4 implements a fully local, deterministic, rule-based Resume Analyzer that transforms a `GenericDocument` representation of a candidate's resume (parsed via PyMuPDF in Phase 2) into a structured `CandidateProfile`.

The module operates completely offline, without reliance on cloud APIs, external LLMs, or non-deterministic heuristics. It performs **extraction and normalization only**, keeping candidate profiling strictly decoupled from Job Description matching.

---

## 1. Resume Extraction Pipeline Architecture

```
GenericDocument (from Phase 2 PDF Parser)
      │
      ├──> Contact & Identity Extractor (Name, Email, Phone, Summary)
      │
      ├──> Resume Section Segmenter & Normalizer
      │     (Maps standard and messy headings, preserves page provenance)
      │
      ├──> Skill & Technology Extractor
      │     ├── Canonical Technology Taxonomy & Alias Normalizer (NodeJS -> Node.js)
      │     ├── False-Positive Guardrail (Blocks aspirational "Interested in learning...")
      │     └── Extensible Unfamiliar Term Preserver (CustomDSL -> other_skill)
      │
      ├──> Work Experience Extractor
      │     ├── Multi-line Header Reconciler (Role | Company | Date range)
      │     ├── Date Range & Duration Normalizer (Calculates duration_months)
      │     └── Current Role Detector (is_current = True, end_date = "Present")
      │
      ├──> Education Extractor
      │     └── Degree, Field of Study / Major, Institution, & Precise GPA
      │
      ├──> Certification Extractor
      │     └── Credential Title, Issuing Body, and Issue Date Normalization
      │
      └──> Project Extractor
            └── Project Names, Descriptions, and Associated Technologies
      │
      ▼
CandidateProfile (Normalized, Provenance-Backed Representation)
```

---

## 2. CandidateProfile Schema

The structured candidate output is defined in [candidate.py](file:///Users/jahnaviakveti/Downloads/nexora/internloom-smart-shortlisting/backend/app/schemas/candidate.py):

| Field | Type | Description |
|---|---|---|
| `candidate_id` | `str` | Deterministic or assigned unique identifier |
| `filename` | `Optional[str]` | Source PDF filename |
| `name` | `Optional[str]` | Full name extracted from document header |
| `email` | `Optional[str]` | Contact email address |
| `phone` | `Optional[str]` | Contact phone number |
| `summary` | `Optional[str]` | Professional summary or objective text |
| `sections` | `Dict[str, str]` | Canonical section mapping (`skills`, `experience`, `education`, etc.) |
| `skills` | `List[str]` | Unified list of all identified skills & technologies |
| `technologies` | `List[str]` | Normalized technology names |
| `skill_details` | `List[CandidateSkill]` | Detailed skill entities with classification and provenance |
| `experience` | `List[CandidateExperience]` | Professional work entries with roles, dates, durations, and tools |
| `education` | `List[CandidateEducation]` | Degrees, fields of study, institutions, and GPAs |
| `certifications` | `List[CandidateCertification]`| Professional licenses, issuing bodies, and dates |
| `projects` | `List[CandidateProject]` | Projects with descriptions and technologies used |
| `evidence` | `List[Evidence]` | Aggregated provenance items for auditable explainability |

---

## 3. Section Segmentation & Multi-Column Support

Resume layouts vary widely in structure and typography:
- **Heading Normalization:** The [ResumeSectionExtractor](file:///Users/jahnaviakveti/Downloads/nexora/internloom-smart-shortlisting/backend/app/services/resume_analyzer/section_extractor.py) expands canonical aliases:
  - `"Skills & Technologies"`, `"Technical Proficiencies"`, `"Programming Skills"` $\rightarrow$ `skills`
  - `"Employment History"`, `"Work Background"`, `"Internships"` $\rightarrow$ `experience`
  - `"Academic History"`, `"Degrees"`, `"Higher Education"` $\rightarrow$ `education`
  - `"Selected Projects"`, `"Portfolio"`, `"Key Initiatives"` $\rightarrow$ `projects`
  - `"Licenses & Certifications"`, `"Courses & Workshops"` $\rightarrow$ `certifications`
- **Metadata Protection:** Inline key-value tokens (e.g. `GPA: 3.9/4.0` or `Languages: Python`) and numeric lines are prevented from falsely triggering as top-level section boundaries.
- **Two-Column & Block Layouts:** Because the Phase 2 parser sorts text blocks top-to-bottom and left-to-right, text flows sequentially without crashing or truncating content across columns.

---

## 4. Skills Extraction & Taxonomy Extensibility

The [SkillExtractor](file:///Users/jahnaviakveti/Downloads/nexora/internloom-smart-shortlisting/backend/app/services/resume_analyzer/skill_extractor.py) provides reliable technical discovery:
1. **Canonical Normalization:** Aliases are normalized to canonical standards:
   - `NodeJS` $\rightarrow$ `Node.js`
   - `Postgres` $\rightarrow$ `PostgreSQL`
   - `ReactJS` $\rightarrow$ `React`
2. **False-Positive Protection (Aspirational Phrases):** Phrases indicating future intent rather than acquired skills are filtered out:
   - *"Interested in learning Rust"* $\rightarrow$ `Rust` is **not** extracted as an active skill.
   - *"Looking to explore WebAssembly"* $\rightarrow$ `WebAssembly` is **not** credited.
3. **Taxonomy Extensibility:** Technical terms absent from the taxonomy (e.g. `CustomDSL`, `AcmeFlow`) appearing in dedicated skills sections are retained and labeled with `category="other_skill"` rather than discarded.
4. **Soft Skill Filtering:** Common generic words (`communication`, `leadership`, `teamwork`) are filtered out to keep technical matches focused and actionable.

---

## 5. Work Experience & Date Handling

The [ExperienceExtractor](file:///Users/jahnaviakveti/Downloads/nexora/internloom-smart-shortlisting/backend/app/services/resume_analyzer/experience_extractor.py) and [date_parser.py](file:///Users/jahnaviakveti/Downloads/nexora/internloom-smart-shortlisting/backend/app/services/resume_analyzer/date_parser.py) process employment histories:
- **Multi-Line Header Reconciliation:** Accommodates formats where job titles and company names appear on one line (e.g. `Senior Software Engineer | TechCorp Inc.`) and the date range appears on the next line (`Jan 2023 - Present`), cleanly merging them into a single entry.
- **Date Normalization:** Dates are normalized into standard formats (`Jan 2023`, `Jun 2020`, `2022`).
- **Current Role Detection:** Ongoing positions (`Present`, `Current`, `Ongoing`) set `is_current = True` and `end_date = "Present"`.
- **Duration Calculation:** Calculates `duration_months` using month-year spans (e.g. `Jun 2020` to `Dec 2022` yields `30.0` months).
- **Embedded Technologies:** Mentions of tools and languages within bullet points (e.g. `FastAPI`, `Docker`) are extracted and associated with the specific role.

---

## 6. Education, Certifications, & Projects

- **Education:** Identifies degree (`Bachelor of Science`, `B.Tech`, `M.S.`), field of study (`Computer Science`), institution (`Tech University`), and precisely captures GPAs (`3.8/4.0`, `3.9`, `85%`) while ignoring graduation years.
- **Certifications:** Extracts credential titles (`AWS Certified Solutions Architect`, `CKAD`), standardizes issuing authorities (`Amazon Web Services (AWS)`, `Linux Foundation`), and absorbs wrapped continuation lines and issue date metadata lines (`Issued: Mar 2022`).
- **Projects:** Extracts project names, bulleted summaries, and technology stacks utilized.

---

## 7. Evidence Provenance Architecture

Every extracted entity attaches an `Evidence` object:
```python
Evidence(
    source_text="• Architected scalable microservices using Python and FastAPI.",
    source_section="Experience",
    page_number=1,
    confidence_score=0.95,
    evidence_type="experience_entry"
)
```
This guarantees full auditability: down the line, when candidate scoring or recruiter explanations are generated, every claim links directly back to the exact resume snippet and page number.

---

## 8. Verification & Quality Metrics

- **Unit Test Coverage:** 19/19 Phase 4 unit tests passing in [test_resume_analyzer.py](file:///Users/jahnaviakveti/Downloads/nexora/internloom-smart-shortlisting/backend/tests/test_resume_analyzer.py).
- **Backend Regression:** All 53 backend tests passing with 0 warnings in 0.36s.
- **Smoke Tests:** End-to-end extraction verified across root test suites.
- **Frontend Regression:** Vite production bundle builds cleanly in under 60ms.
