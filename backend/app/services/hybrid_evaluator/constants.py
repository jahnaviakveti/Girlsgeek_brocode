"""
Configuration constants and weights for Phase 7 Hybrid Evaluation, Scoring, and Ranking.
All values are explicit, deterministic engineering decisions documented for auditability.
"""

# --- Hybrid Signal Combination Weights ---
# When direct exact/alias lexical match is found:
# Direct literal evidence is primary (65%), contextual semantic similarity is complementary (35%).
WEIGHT_LEXICAL_EXACT: float = 0.65
WEIGHT_SEMANTIC_WITH_LEX: float = 0.35

# When fuzzy lexical match is found (slight typo/variant):
# Lexical and semantic signals share equal responsibility (50%/50%).
WEIGHT_LEXICAL_FUZZY: float = 0.50
WEIGHT_SEMANTIC_FUZZY: float = 0.50

# When no lexical match is found (pure semantic / conceptual matching, e.g. "Kubernetes" for "container orchestration"):
# Pure semantic credit is scaled to 0.75 max to prevent semantic hallucination of unpossessed skills.
WEIGHT_SEMANTIC_ONLY: float = 0.75

# Minimum semantic similarity required for pure conceptual credit (below this is considered background noise).
SEMANTIC_MIN_THRESHOLD: float = 0.35

# --- Requirement Verdict Cutoffs ---
# Score >= 0.70 indicates the requirement is solidly matched.
VERDICT_MATCHED_THRESHOLD: float = 0.70
# 0.30 <= Score < 0.70 indicates partial satisfaction or conceptual overlap.
VERDICT_PARTIAL_THRESHOLD: float = 0.30

# --- Requirement Priority Weights for Candidate Scoring ---
# Required requirements have 3x the influence of preferred requirements on the overall candidate score.
WEIGHT_PRIORITY_REQUIRED: float = 3.0
WEIGHT_PRIORITY_PREFERRED: float = 1.0

# --- Experience Duration Scaling ---
# Score multiplier applied when a required skill is present, but required duration (years) is unknown or unverified.
EXPERIENCE_UNVERIFIED_DURATION_MULTIPLIER: float = 0.50
# Maximum score allowed when required duration is unverified (ensures PARTIAL status).
EXPERIENCE_UNVERIFIED_MAX_SCORE: float = 0.60
