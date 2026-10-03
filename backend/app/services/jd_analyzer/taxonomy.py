import re
from typing import Dict, List, Set, Tuple

# Modular dictionary of common technical skills, languages, frameworks, and tools.
# Designed to assist with normalization and known aliases, but NOT treated as an exhaustive list.
CANONICAL_TECHNOLOGIES: Dict[str, str] = {
    # Programming Languages
    "python": "Python",
    "python3": "Python",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "java": "Java",
    "c++": "C++",
    "cpp": "C++",
    "c#": "C#",
    "csharp": "C#",
    "go": "Go",
    "golang": "Go",
    "rust": "Rust",
    "ruby": "Ruby",
    "php": "PHP",
    "swift": "Swift",
    "kotlin": "Kotlin",
    "sql": "SQL",
    "html": "HTML",
    "html5": "HTML",
    "css": "CSS",
    "css3": "CSS",
    "bash": "Bash",
    "shell": "Shell",

    # Frontend Frameworks & Libraries
    "react": "React",
    "react.js": "React",
    "reactjs": "React",
    "angular": "Angular",
    "angularjs": "Angular",
    "vue": "Vue",
    "vue.js": "Vue",
    "vuejs": "Vue",
    "next.js": "Next.js",
    "nextjs": "Next.js",
    "tailwind": "TailwindCSS",
    "tailwindcss": "TailwindCSS",
    "bootstrap": "Bootstrap",
    "redux": "Redux",

    # Backend Frameworks
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "node": "Node.js",
    "express": "Express",
    "express.js": "Express",
    "expressjs": "Express",
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "spring": "Spring Boot",
    "spring boot": "Spring Boot",
    "asp.net": "ASP.NET",
    "ruby on rails": "Rails",
    "rails": "Rails",

    # Databases & Storage
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "mongo": "MongoDB",
    "redis": "Redis",
    "sqlite": "SQLite",
    "elasticsearch": "Elasticsearch",
    "cassandra": "Cassandra",
    "dynamodb": "DynamoDB",

    # Cloud, DevOps & Infrastructure
    "aws": "AWS",
    "amazon web services": "AWS",
    "gcp": "GCP",
    "google cloud": "GCP",
    "azure": "Azure",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "ci/cd": "CI/CD",
    "jenkins": "Jenkins",
    "github actions": "GitHub Actions",
    "terraform": "Terraform",
    "linux": "Linux",
    "git": "Git",
    "github": "GitHub",

    # Architectural & Core Paradigms
    "rest": "REST APIs",
    "rest api": "REST APIs",
    "rest apis": "REST APIs",
    "restful apis": "REST APIs",
    "graphql": "GraphQL",
    "microservices": "Microservices",
    "distributed systems": "Distributed Systems",
    "object-oriented programming": "OOP",
    "oop": "OOP",
    "agile": "Agile",
    "scrum": "Scrum",
    "unit testing": "Unit Testing",
    "tdd": "TDD",
}

# Stop words to exclude from unfamiliar technical term candidates
EXCLUDED_TERM_STOPWORDS = {
    "the", "this", "our", "we", "must", "should", "experience", "knowledge",
    "minimum", "preferred", "bachelor", "master", "degree", "computer", "science",
    "engineering", "related", "field", "years", "year", "months", "demonstrated",
    "hands-on", "proven", "strong", "solid", "excellent", "working", "prior",
    "qualifications", "requirements", "responsibilities", "duties", "company"
}

def extract_technologies(text: str) -> List[str]:
    """
    Extracts known canonical technology names found within text.
    Handles exact case boundaries, punctuation, and multi-word phrases.
    """
    found: Set[str] = set()
    lowered = text.lower()

    # Match multi-word technologies first (e.g., 'spring boot', 'amazon web services')
    for alias, canonical in sorted(CANONICAL_TECHNOLOGIES.items(), key=lambda x: -len(x[0])):
        pattern = r'(?<![a-zA-Z0-9])' + re.escape(alias) + r'(?![a-zA-Z0-9])'
        if re.search(pattern, lowered):
            found.add(canonical)

    return sorted(list(found))

def extract_unfamiliar_terms(text: str) -> List[str]:
    """
    Extracts unfamiliar or proprietary technical terms, tools, or platforms that are
    not present in the known taxonomy.
    Identifies:
    1. CamelCase / inner-capitalized tokens (e.g. 'AcmeFlow', 'DataStreamer')
    2. Capitalized product/tool names following prepositions/lead-ins (e.g. 'with AcmeFlow', 'using CustomLib')
    """
    found: Set[str] = set()

    # 1. CamelCase or inner-capitalized tokens (e.g. AcmeFlow, SuperDB)
    camel_tokens = re.findall(r'\b([A-Z][a-z0-9]+[A-Z][a-zA-Z0-9]*)\b', text)
    for token in camel_tokens:
        if token.lower() not in CANONICAL_TECHNOLOGIES and token.lower() not in EXCLUDED_TERM_STOPWORDS:
            found.add(token)

    # 2. Capitalized terms following technical prepositions / lead-ins
    lead_in_matches = re.findall(
        r'(?:experience\s+with|knowledge\s+of|proficiency\s+in|familiarity\s+with|using|in|with)\s+([A-Z][a-zA-Z0-9_\-\.]+)(?:\s+(?:platform|tool|framework|engine|system|service|software|application|library|database|api|sdk))?',
        text,
        re.IGNORECASE
    )
    for term in lead_in_matches:
        term_clean = term.strip().strip(".,;:()")
        if (
            len(term_clean) >= 3
            and term_clean.lower() not in CANONICAL_TECHNOLOGIES
            and term_clean.lower() not in EXCLUDED_TERM_STOPWORDS
        ):
            found.add(term_clean)

    return sorted(list(found))

def extract_all_technologies(text: str) -> List[str]:
    """
    Extracts all technology and technical tool candidates, combining known canonical
    taxonomy hits with unfamiliar/proprietary terms.
    The taxonomy provides normalization assistance but is NOT an exhaustive gatekeeper.
    """
    known = extract_technologies(text)
    unfamiliar = extract_unfamiliar_terms(text)
    # Combine preserving canonical casing for known terms
    combined = set(known)
    for unfam in unfamiliar:
        # Don't add if already represented by a known canonical match
        if not any(unfam.lower() == k.lower() for k in known):
            combined.add(unfam)
    return sorted(list(combined))
