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
