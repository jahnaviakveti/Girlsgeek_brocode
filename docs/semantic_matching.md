# Semantic Matching Foundation (Phase 5)

## 1. Purpose & Core Principles
The Semantic Matching layer provides an evidence retrieval primitive that compares a structured `JDRequirement` against extracted candidate evidence from a `CandidateProfile`. It uses a local Sentence Transformers embedding model to produce numerical cosine similarity scores reflecting semantic closeness without brittle keyword-only restrictions.

> [!IMPORTANT]
> **"Semantic similarity is evidence, not the final candidate-match decision."**
> High semantic similarity (e.g., "Interested in learning Python" vs "Expert Python developer") does not automatically constitute a requirement `MATCH`. Context, proficiency, seniority, and negations are interpreted downstream by the Hybrid Requirement Evaluator.

## 2. Architecture & Batch Encoding
```
JobDescription → JDRequirement
                     ↓
             [Local Embedding]
                     ↓
CandidateProfile → Candidate Evidence Items (Skills, Experience, Projects, Education, Certs, Summary)
                     ↓
            [Batch Embedding: model.encode(texts)]
                     ↓
         Batch Cosine Similarity
                     ↓
       List[SemanticMatchResult] (Sorted by similarity descending)
```

### Batch Encoding Implementation
Candidate evidence is aggregated across all structured sections (`CandidateSkill`, `CandidateExperience`, `CandidateProject`, `CandidateEducation`, `CandidateCertification`, and `summary`) and passed as a single batch to `model.encode(texts)`.
Batch cosine similarity (`batch_cosine_similarity`) then computes similarities simultaneously against the requirement vector via optimized vector-matrix operations:
- Prevents repetitive forward passes through the transformer model.
- Reduces inference latency across 15–18 resumes from minutes to seconds.
- Reuses the singleton/lazy model instance across evaluations.

## 3. Local Embedding Model & Offline Behavior
- **Model:** `all-MiniLM-L6-v2` (384-dimensional embeddings).
- **Interface:** `EmbeddingModel` abstract base class implemented by `LocalSentenceTransformerEmbeddingModel`.
- **Offline Operation:** Once the model weights are downloaded into the local cache (`~/.cache/huggingface/hub`), the matcher runs completely offline. Environment variable `HF_HUB_OFFLINE=1` enforces strict zero-network local execution.
- **Zero Cloud APIs:** Operates 100% locally on CPU without external API keys, OpenAI, Gemini, or Claude.

## 4. Evidence Contract & Provenance Preservation
The `SemanticMatcher` consumes the existing domain contracts without modifying or fabricating data:
- **No Fabricated IDs:** The domain `Evidence` model does not possess an `id` field; `evidence_id` in `SemanticMatchResult` is explicitly kept as `None`.
- **Full Provenance Preserved:**
  - `page_number`: Document page where the evidence appeared.
  - `source_section`: Mapped canonical section name (e.g. "Skills", "Experience").
  - `source_text`: The exact source text snippet from the resume.
  - `evidence_type`: Domain category (`skill`, `experience`, `project`, `education`, `certification`, `summary`).
  - `evidence`: Direct reference to the original domain `Evidence` instance.
- **Confidence Semantics Protected:** Phase 3/4 `confidence_score` on `Evidence` represents extractor parsing confidence. It is strictly separated from `similarity_score`, which represents cosine similarity.

## 5. Result Semantics & No Production Thresholds
`SemanticMatchResult` strictly encapsulates:
- `requirement_id`
- `evidence_id` (None)
- `requirement_text`
- `evidence_text`
- `similarity_score` (cosine similarity in `[-1.0, 1.0]`)
- `page_number`, `source_section`, `source_text`
- `evidence_type`
- `evidence`

It explicitly does **NOT** contain:
- Final match verdicts (`MATCHED`, `PARTIAL`, `MISSING`)
- Requirement satisfaction flags
- Candidate scores or weights
- Ranking scores or positions

### Why No Production Thresholds Are Defined in Phase 5
No arbitrary thresholds (e.g., `sim > 0.4 = MATCH`) are defined in Phase 5. Semantic similarity varies across short phrases (skills) versus long prose (experience bullets). Threshold calibration belongs exclusively in Phase 6, where semantic evidence is evaluated alongside keyword matching and logical operators (`AND`/`OR`).
Testing verifies relative semantic ordering (e.g. `Kubernetes` > `graphic design` for container orchestration) rather than brittle magic numbers.
