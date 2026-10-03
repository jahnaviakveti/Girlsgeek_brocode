import re
from typing import Dict, Optional
from app.services.jd_analyzer.taxonomy import CANONICAL_TECHNOLOGIES
from .normalization import normalize_text, clean_token

# Extended alias mapping for lexical normalization
# Maps normalized lowercase representations to canonical technology names
ADDITIONAL_ALIASES: Dict[str, str] = {
    "node js": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "react js": "React",
    "reactjs": "React",
    "react.js": "React",
    "vue js": "Vue",
    "vuejs": "Vue",
    "vue.js": "Vue",
    "angular js": "Angular",
    "angularjs": "Angular",
    "next js": "Next.js",
    "nextjs": "Next.js",
    "next.js": "Next.js",
    "amazon web services": "AWS",
    "aws": "AWS",
    "google cloud platform": "GCP",
    "google cloud": "GCP",
    "gcp": "GCP",
    "microsoft azure": "Azure",
    "azure": "Azure",
    "golang": "Go",
    "go": "Go",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "cpp": "C++",
    "c++": "C++",
    "csharp": "C#",
    "c#": "C#",
    "py": "Python",
    "python": "Python",
    "python3": "Python",
    "cicd": "CI/CD",
    "ci/cd": "CI/CD",
    "mongo": "MongoDB",
    "mongodb": "MongoDB",
}

def build_alias_registry() -> Dict[str, str]:
    registry: Dict[str, str] = {}
    # 1. Populate from CANONICAL_TECHNOLOGIES
    for k, v in CANONICAL_TECHNOLOGIES.items():
        norm_k = normalize_text(k)
        registry[norm_k] = v
        # Also clean punctuation variation (e.g. node.js -> nodejs)
        compact = re.sub(r'[\s\.\-_]', '', norm_k)
        if compact:
            registry[compact] = v

    # 2. Populate / override with explicit ADDITIONAL_ALIASES
    for k, v in ADDITIONAL_ALIASES.items():
        norm_k = normalize_text(k)
        registry[norm_k] = v
        compact = re.sub(r'[\s\.\-_]', '', norm_k)
        if compact:
            registry[compact] = v

    return registry

ALIAS_REGISTRY = build_alias_registry()

def get_canonical_name(term: str) -> Optional[str]:
    """
    Returns the canonical technology name for a term if it is in the alias registry.
    Returns None if the term is unknown / not registered.
    """
    if not term:
        return None
    norm = normalize_text(term)
    if norm in ALIAS_REGISTRY:
        return ALIAS_REGISTRY[norm]
    # Check compacted without dots/spaces/hyphens
    compact = re.sub(r'[\s\.\-_]', '', norm)
    if compact in ALIAS_REGISTRY:
        return ALIAS_REGISTRY[compact]
    return None

def is_alias_match(term1: str, term2: str) -> bool:
    """
    Determines if two terms resolve to the same canonical technology alias.
    """
    if not term1 or not term2:
        return False
    c1 = get_canonical_name(term1)
    c2 = get_canonical_name(term2)
    if c1 is not None and c2 is not None:
        return c1.lower() == c2.lower()
    return False
