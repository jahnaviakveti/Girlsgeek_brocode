import re
from typing import Dict, List, Optional, Tuple

# Negation patterns indicating a skill or qualification is NOT required
NEGATION_PATTERNS = [
    re.compile(r'\b(not\s+(?:required|mandatory|essential|expected|needed))\b', re.IGNORECASE),
    re.compile(r'\b(no\s+prior\s+(?:experience|knowledge))\b', re.IGNORECASE),
    re.compile(r'\b(no\s+(?:degree|certification)\s+required)\b', re.IGNORECASE),
    re.compile(r'\b(do\s+not\s+need|does\s+not\s+require)\b', re.IGNORECASE),
    re.compile(r'\b(neither|never)\b', re.IGNORECASE),
]

# Explicit signals for REQUIRED priority
REQUIRED_SIGNALS = [
    re.compile(r'\b(must(?:\s+have)?|required|mandatory|essential|need\s+to|should\s+have)\b', re.IGNORECASE),
    re.compile(r'\b(minimum\s+of|at\s+least)\b', re.IGNORECASE),
    re.compile(r'\b(basic\s+qualifications?|minimum\s+qualifications?|must-have)\b', re.IGNORECASE),
]

# Explicit signals for PREFERRED priority
PREFERRED_SIGNALS = [
    re.compile(r'\b(preferred|desirable|nice\s+to\s+have|good\s+to\s+have|bonus|plus|advantage|ideally|desired)\b', re.IGNORECASE),
    re.compile(r'\b(preferred\s+qualifications?|bonus\s+points?)\b', re.IGNORECASE),
    re.compile(r'\b(is\s+a\s+plus|is\s+an\s+advantage)\b', re.IGNORECASE),
]

# Soft wording that signals preference when no explicit requirement marker exists
SOFT_WORDING_SIGNALS = [
    re.compile(r'\b(familiarity\s+with|exposure\s+to|interest\s+in|appreciation\s+for)\b', re.IGNORECASE),
]

# Experience duration patterns
# Matches: "2+ years", "3-5 years", "minimum 2 years of experience", "at least 1 year", "6 months"
EXPERIENCE_YEARS_RANGE = re.compile(
    r'(?:at\s+least|minimum|min|over|\+)?\s*(\d+(?:\.\d+)?)\s*(?:-|to|–)\s*(\d+(?:\.\d+)?)\s*\+?\s*years?',
    re.IGNORECASE
)
EXPERIENCE_YEARS_SINGLE = re.compile(
    r'(?:at\s+least|minimum|min|over|\+)?\s*(\d+(?:\.\d+)?)\s*\+?\s*years?(?:\s+of)?(?:\s+(?:professional\s+)?experience)?',
    re.IGNORECASE
)
EXPERIENCE_MONTHS = re.compile(
    r'(\d+)\s*months?(?:\s+of)?(?:\s+(?:professional\s+)?experience)?',
    re.IGNORECASE
)

# Education patterns
EDUCATION_DEGREES = [
    re.compile(r"\b(bachelor'?s?(?:\s+degree)?|b\.?s\.?|b\.?tech|b\.?e\.?|undergraduate)\b", re.IGNORECASE),
    re.compile(r"\b(master'?s?(?:\s+degree)?|m\.?s\.?|m\.?tech|graduate\s+degree)\b", re.IGNORECASE),
    re.compile(r"\b(ph\.?d\.?|doctorate)\b", re.IGNORECASE),
    re.compile(r"\b(associate'?s?(?:\s+degree)?|diploma)\b", re.IGNORECASE),
    re.compile(r"\bdegree\s+in\s+([A-Za-z\s,]+)", re.IGNORECASE),
]

# Certification patterns
CERTIFICATION_SIGNALS = [
    re.compile(r'\b(certified|certification|aws\s+certified|pmp|cissp|scrum\s+master|ckad|cka|comptia)\b', re.IGNORECASE),
    re.compile(r'\b(certificate\s+in|accredited)\b', re.IGNORECASE),
]

# Actionable requirement cue indicators (verbs and lead-ins)
REQUIREMENT_LEAD_INS = [
    re.compile(r'\b(experience\s+with|proficiency\s+in|proficient\s+(?:with|in)|knowledge\s+of)\b', re.IGNORECASE),
    re.compile(r'\b(hands-on\s+experience|familiarity\s+with|background\s+in|skilled\s+in)\b', re.IGNORECASE),
    re.compile(r'\b(ability\s+to|responsible\s+for|understanding\s+of|working\s+knowledge)\b', re.IGNORECASE),
    re.compile(r'\b(proven\s+track\s+record|demonstrated\s+experience|solid\s+understanding)\b', re.IGNORECASE),
]

# Section headers strongly indicative of requirement priority
REQUIRED_SECTION_NAMES = {
    "requirements",
    "minimum_qualifications",
    "basic_qualifications",
    "required_skills",
    "must_have",
    "what_you_need",
    "what_you_bring",
    "skills_required",
    "qualifications",
}

PREFERRED_SECTION_NAMES = {
    "preferred_qualifications",
    "nice_to_have",
    "bonus",
    "bonus_points",
    "desired_skills",
    "preferred_skills",
    "good_to_have",
    "what_gives_you_an_edge",
}
