"""
Claim Scope & Evidence Granularity Evaluator.

Core Principle:
TECHNOLOGY PRESENCE != EXPERIENCE SCOPE

Distinguishes:
LEVEL 1 — TECHNOLOGY PRESENCE (e.g. "Kubernetes")
LEVEL 2 — USAGE (e.g. "Used Kubernetes for deployment.")
LEVEL 3 — IMPLEMENTATION (e.g. "Configured Kubernetes deployments and services.")
LEVEL 4 — OPERATIONAL / PRODUCTION (e.g. "Managed production EKS clusters.")
LEVEL 5 — SPECIFIC / ENTERPRISE SCOPE (e.g. "Managed multi-region production EKS infrastructure.")

Ensures that evidence of technology exposure is NEVER conflated with
production administration, architecture ownership, or operational scope.
"""

import re
from typing import List, Optional, Set, Tuple
from pydantic import BaseModel


class ClaimScopeAuditResult(BaseModel):
    demands_higher_scope: bool
    scope_satisfied: bool
    technology_present: bool
    required_scope_type: Optional[str] = None
    evidenced_scope_type: Optional[str] = None
    matched_technology: Optional[str] = None
    rationale: str


# Operational and production scope patterns in requirements
PRODUCTION_CLUSTER_PATTERNS = [
    re.compile(r'\b(?:production\s+(?:kubernetes|k8s|eks|gke|aks|cluster|clusters|environment))\b', re.IGNORECASE),
    re.compile(r'\b(?:managing\s+(?:production\s+)?(?:kubernetes|k8s|eks|gke|aks\s+)?clusters?)\b', re.IGNORECASE),
    re.compile(r'\b(?:production\s+cluster\s+management)\b', re.IGNORECASE),
    re.compile(r'\b(?:cluster\s+(?:management|administration|operations))\b', re.IGNORECASE),
    re.compile(r'\b(?:manage\s+production\s+.*?\s+clusters?)\b', re.IGNORECASE),
]

ARCHITECTURE_INFRASTRUCTURE_PATTERNS = [
    re.compile(r'\b(?:design(?:ed|ing)?\s+(?:scalable\s+)?(?:kubernetes|cloud|system|infrastructure))\b', re.IGNORECASE),
    re.compile(r'\b(?:architect(?:ed|ing)?\s+(?:scalable\s+)?(?:kubernetes|cloud|infrastructure))\b', re.IGNORECASE),
    re.compile(r'\b(?:scalable\s+kubernetes\s+infrastructure)\b', re.IGNORECASE),
]

SPECIFIC_PLATFORM_PATTERNS = [
    re.compile(r'\b(?:eks|gke|aks|openshift)\b', re.IGNORECASE),
]

DEPLOYMENT_CLAIM_PATTERNS = [
    re.compile(r'\b(?:deployed\s+(?:the\s+)?(?:application|services?|backend|microservices?)\s+using\s+([a-zA-Z0-9_\-\.\+#]+))\b', re.IGNORECASE),
    re.compile(r'\b(?:deployed\s+using\s+([a-zA-Z0-9_\-\.\+#]+))\b', re.IGNORECASE),
]


def detect_requirement_scope(requirement_text: str) -> Tuple[bool, Optional[str]]:
    """
    Analyzes requirement text to see if it demands higher-level operational, production,
    cluster management, or architectural scope beyond general technology familiarity.
    """
    if not requirement_text:
        return False, None

    req_lower = requirement_text.lower()

    for pat in PRODUCTION_CLUSTER_PATTERNS:
        if pat.search(req_lower):
            return True, "PRODUCTION_CLUSTER_OPERATIONS"

    for pat in ARCHITECTURE_INFRASTRUCTURE_PATTERNS:
        if pat.search(req_lower):
            return True, "SCALABLE_ARCHITECTURE_DESIGN"

    # Specific managed platform requirement when explicitly required in cluster context
    if any(p.search(req_lower) for p in SPECIFIC_PLATFORM_PATTERNS) and any(w in req_lower for w in ["manage", "cluster", "production", "infrastructure"]):
        return True, "MANAGED_PLATFORM_OPERATIONS"

    return False, None


def check_evidence_scope_satisfaction(
    evidence_texts: List[str],
    required_scope_type: str,
    requirement_text: str
) -> Tuple[bool, str]:
    """
    Evaluates whether the candidate's actual evidence texts substantiate the required scope.
    """
    combined_ev = " ".join(evidence_texts).lower()

    if required_scope_type == "PRODUCTION_CLUSTER_OPERATIONS":
        has_prod = "production" in combined_ev or "prod" in combined_ev
        has_cluster_mgmt = any(
            w in combined_ev for w in ["cluster", "clusters", "eks", "gke", "aks"]
        ) and any(
            w in combined_ev for w in ["manage", "managed", "admin", "operat", "maintain", "deploy"]
        )
        if has_prod and has_cluster_mgmt:
            return True, "Verified production cluster management operations evidenced in candidate history."
        return False, "Evidence documents technology exposure, but lacks verified production cluster management or administration operations."

    elif required_scope_type == "SCALABLE_ARCHITECTURE_DESIGN":
        has_design = any(w in combined_ev for w in ["design", "designed", "architect", "architected"])
        has_infra = any(w in combined_ev for w in ["infrastructure", "scalable", "platform", "cluster"])
        if has_design and has_infra:
            return True, "Verified scalable infrastructure architecture design evidenced in candidate history."
        return False, "Evidence documents technology exposure, but lacks verified scalable infrastructure design experience."

    elif required_scope_type == "MANAGED_PLATFORM_OPERATIONS":
        # Check specific platform match (EKS/GKE/AKS)
        has_platform = any(plat in combined_ev for plat in ["eks", "gke", "aks"])
        if has_platform:
            return True, "Verified specific managed platform experience evidenced in candidate history."
        return False, "Evidence documents general technology exposure, but lacks specific managed cloud platform (EKS/GKE) evidence."

    return True, "Scope verified."


def evaluate_claim_scope(
    evidence_texts: List[str],
    requirement_text: str,
    candidate_technologies: Optional[Set[str]] = None
) -> ClaimScopeAuditResult:
    """
    Audits requirement against candidate evidence to enforce:
    TECHNOLOGY PRESENCE != EXPERIENCE SCOPE.
    """
    demands_scope, scope_type = detect_requirement_scope(requirement_text)

    # Check if base technology is present in evidence or profile
    tech_present = False
    matched_tech = None

    # Check common container/cloud technologies
    tracked_techs = ["kubernetes", "k8s", "docker", "eks", "gke", "aks", "python", "flask", "aws", "terraform"]
    req_lower = requirement_text.lower()
    combined_ev = " ".join(evidence_texts).lower()

    for t in tracked_techs:
        if t in req_lower:
            if t in combined_ev or (candidate_technologies and any(t == ct.lower() for ct in candidate_technologies)):
                tech_present = True
                matched_tech = t.capitalize()
                break

    if not demands_scope:
        # Standard requirement (e.g. "Python" or "Kubernetes" without operational cluster qualification)
        return ClaimScopeAuditResult(
            demands_higher_scope=False,
            scope_satisfied=True,
            technology_present=tech_present or bool(evidence_texts),
            required_scope_type=None,
            evidenced_scope_type="STANDARD_USAGE",
            matched_technology=matched_tech,
            rationale="Standard requirement scope."
        )

    # Demands higher scope
    satisfied, rationale = check_evidence_scope_satisfaction(evidence_texts, scope_type, requirement_text)

    return ClaimScopeAuditResult(
        demands_higher_scope=True,
        scope_satisfied=satisfied,
        technology_present=tech_present,
        required_scope_type=scope_type,
        evidenced_scope_type=scope_type if satisfied else "TECHNOLOGY_PRESENCE_ONLY",
        matched_technology=matched_tech,
        rationale=rationale
    )


def extract_operational_scope_claims(text: str) -> List[str]:
    """
    Extracts operational/production claims asserted in a candidate answer.
    """
    claims = []
    text_lower = text.lower()

    # Managing production clusters
    pat_cluster = re.compile(
        r'\b(?:managed|managing|administrated|administered|operated|maintained)\s+(?:production\s+)?(?:kubernetes|k8s|eks|gke|aks\s+)?clusters?\b',
        re.IGNORECASE
    )
    for m in pat_cluster.finditer(text):
        claims.append(m.group(0))

    # Production Kubernetes
    pat_prod_k8s = re.compile(
        r'\b(?:production\s+kubernetes(?:\s+clusters?)?|production\s+eks(?:\s+clusters?)?|production\s+gke(?:\s+clusters?)?)\b',
        re.IGNORECASE
    )
    for m in pat_prod_k8s.finditer(text):
        if m.group(0) not in claims:
            claims.append(m.group(0))

    # Scalable infrastructure design
    pat_arch = re.compile(
        r'\b(?:designed|architected)\s+(?:scalable\s+)?(?:kubernetes|k8s|cloud)\s+infrastructure\b',
        re.IGNORECASE
    )
    for m in pat_arch.finditer(text):
        if m.group(0) not in claims:
            claims.append(m.group(0))

    return claims


def classify_claim_scope(text: str) -> str:
    """
    Deterministically assigns one of the 5 claim levels:
    LEVEL 1 — TECHNOLOGY PRESENCE
    LEVEL 2 — USAGE
    LEVEL 3 — IMPLEMENTATION
    LEVEL 4 — OPERATIONAL / PRODUCTION
    LEVEL 5 — SPECIFIC SCOPE
    """
    if not text:
        return "LEVEL 1 — TECHNOLOGY PRESENCE"
    t_lower = text.lower()

    # Level 5: Specific / Multi-region enterprise scope
    if any(w in t_lower for w in ["multi-region", "multi-cluster", "cross-region", "global infrastructure", "disaster recovery architecture"]):
        return "LEVEL 5 — SPECIFIC SCOPE"

    # Level 4: Operational / Production
    if any(w in t_lower for w in ["production", "on-call", "sre", "cluster management", "managed production", "eks cluster", "gke cluster", "aks cluster", "cluster administration", "incident response"]):
        return "LEVEL 4 — OPERATIONAL / PRODUCTION"

    # Level 3: Implementation / Deployment / Configuration
    if any(w in t_lower for w in ["configured", "implemented", "authored", "helm", "manifest", "deploy", "deployed", "deployment", "service", "ingress", "pipeline", "dockerfile", "docker compose", "schema", "resolver", "rest api", "endpoints", "fastapi", "flask", "caching", "cache"]):
        return "LEVEL 3 — IMPLEMENTATION"

    # Level 2: Usage
    if any(w in t_lower for w in ["used", "using", "utilized", "worked with", "familiar with", "exposure"]):
        return "LEVEL 2 — USAGE"

    # Level 1: Presence
    return "LEVEL 1 — TECHNOLOGY PRESENCE"
