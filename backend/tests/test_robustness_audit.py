import pytest
from app.schemas.candidate import CandidateProfile, CandidateSkill, CandidateExperience, CandidateProject
from app.schemas.domain import JobDescription, JDRequirement, RequirementPriority, RequirementCategory, Evidence
from app.schemas.robustness import (
    RankingRobustnessAudit,
    PerturbationType,
    RobustnessClassification
)
from app.services.hybrid_evaluator import (
    RequirementEvaluator,
    ScoringEngine,
    RankingService,
)
from app.services.keyword_matcher import KeywordMatcher
from app.services.semantic_matcher import LocalSentenceTransformerEmbeddingModel, SemanticMatcher
from app.services.robustness_auditor import (
    RankingRobustnessAuditor,
    LexicalNormalizationPerturbation,
    KeywordMaskingPerturbation,
    FormattingNormalizationPerturbation,
    compute_top_k_overlap,
    compute_spearman_rank_correlation,
    compute_rank_displacements,
    compute_pairwise_flips,
    compute_keyword_dependence_index,
)

# ------------------------------------------------------------------------------
# 1. Metric Unit Tests
# ------------------------------------------------------------------------------
def test_metric_top_k_overlap():
    base = ["c1", "c2", "c3", "c4", "c5"]
    pert_same = ["c1", "c2", "c3", "c4", "c5"]
    pert_perm = ["c3", "c1", "c2", "c5", "c4"]
    pert_diff = ["c4", "c5", "c6", "c7", "c8"]

    assert compute_top_k_overlap(base, pert_same, 3) == 1.0
    assert compute_top_k_overlap(base, pert_perm, 3) == 1.0  # Set overlap is 3/3
    assert compute_top_k_overlap(base, pert_diff, 3) == 0.0  # Disjoint sets

    pert_partial = ["c1", "c2", "c9", "c10"]
    assert compute_top_k_overlap(base, pert_partial, 3) == round(2/3, 4)

def test_metric_spearman_correlation():
    r_base = {"c1": 1, "c2": 2, "c3": 3, "c4": 4}
    r_same = {"c1": 1, "c2": 2, "c3": 3, "c4": 4}
    assert compute_spearman_rank_correlation(r_base, r_same) == 1.0

    r_inv = {"c1": 4, "c2": 3, "c3": 2, "c4": 1}
    assert compute_spearman_rank_correlation(r_base, r_inv) == -1.0

    assert compute_spearman_rank_correlation({"c1": 1}, {"c1": 1}) == 1.0

def test_metric_rank_displacements():
    r_base = {"c1": 1, "c2": 2, "c3": 3}
    r_pert = {"c1": 2, "c2": 1, "c3": 3}

    disp = compute_rank_displacements(r_base, r_pert)
    assert disp["c1"] == (1, -1)
    assert disp["c2"] == (1, 1)
    assert disp["c3"] == (0, 0)

def test_metric_pairwise_flips():
    r_base = {"c1": 1, "c2": 2, "c3": 3, "c4": 4}
    r_pert = {"c1": 2, "c2": 1, "c3": 3, "c4": 4}
    assert compute_pairwise_flips(r_base, r_pert) == 1

    r_inv = {"c1": 4, "c2": 3, "c3": 2, "c4": 1}
    assert compute_pairwise_flips(r_base, r_inv) == 6

def test_metric_keyword_dependence_index():
    b_scores = {"c1": 100.0, "c2": 80.0}
    assert compute_keyword_dependence_index(b_scores, {"c1": 100.0, "c2": 80.0}) == 0.0
    assert compute_keyword_dependence_index(b_scores, {"c1": 50.0, "c2": 40.0}) == 0.50

# ------------------------------------------------------------------------------
# 2. Perturbation Operator Tests
# ------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def sample_profile():
    return CandidateProfile(
        candidate_id="cand_test_01",
        name="Alex Mercer",
        skills=["NodeJS", "Postgres"],
        technologies=["NodeJS", "Postgres"],
        skill_details=[
            CandidateSkill(name="NodeJS", raw_name="NodeJS", evidence=Evidence(source_text="Proficient in NodeJS development", confidence_score=1.0, evidence_type="skill", source_section="Skills")),
            CandidateSkill(name="Postgres", raw_name="Postgres", evidence=Evidence(source_text="Experience with Postgres databases", confidence_score=1.0, evidence_type="skill", source_section="Skills"))
        ],
        experience=[
            CandidateExperience(
                role="Software Engineer",
                company="Tech Co",
                description="Deployed microservices onto k8s clusters with cpp backends.",
                technologies=["k8s", "cpp"],
                evidence=Evidence(source_text="Deployed microservices onto k8s clusters with cpp backends.", confidence_score=1.0, evidence_type="experience", source_section="Experience")
            )
        ],
        projects=[
            CandidateProject(
                name="Cloud Pipeline",
                description="Engineered AWS ETL workflows.",
                technologies=["aws"]
            )
        ]
    )

@pytest.fixture(scope="module")
def sample_jd():
    return JobDescription(
        jd_id="jd_01",
        title="Senior Backend Engineer",
        raw_text="Required: Node.js, PostgreSQL, Kubernetes, C++.",
        requirements=[
            JDRequirement(
                id="req_1",
                requirement_text="3+ years of experience with Node.js and PostgreSQL",
                category=RequirementCategory.SKILL,
                priority=RequirementPriority.REQUIRED,
                extracted_keywords=["node.js", "postgresql", "node", "postgres"]
            ),
            JDRequirement(
                id="req_2",
                requirement_text="Container orchestration with Kubernetes",
                category=RequirementCategory.SKILL,
                priority=RequirementPriority.REQUIRED,
                extracted_keywords=["kubernetes", "k8s"]
            )
        ]
    )

def test_perturbation_lexical_normalizer(sample_profile, sample_jd):
    op = LexicalNormalizationPerturbation()
    perturbed, prov = op.perturb(sample_profile, sample_jd)

    assert "Node.js" in perturbed.skills
    assert "PostgreSQL" in perturbed.skills

    exp_desc = perturbed.experience[0].description
    assert "Kubernetes" in exp_desc
    assert "C++" in exp_desc
    assert len(prov) > 0

def test_perturbation_keyword_masker(sample_profile, sample_jd):
    op = KeywordMaskingPerturbation()
    perturbed, prov = op.perturb(sample_profile, sample_jd)

    exp_desc = perturbed.experience[0].description
    assert "[MASKED_SKILL]" in exp_desc
    assert len(prov) > 0

def test_perturbation_formatting_normalizer():
    messy_profile = CandidateProfile(
        candidate_id="cand_messy",
        name="John Doe",
        skills=["Python   ,    SQL"],
        experience=[
            CandidateExperience(
                role="Lead   Dev",
                company="Corp",
                description="Managed   high   throughput  systems.\n▪ Handled 10k requests.",
                technologies=["Python"]
            )
        ]
    )
    op = FormattingNormalizationPerturbation()
    clean_p, prov = op.perturb(messy_profile, JobDescription(jd_id="jd", title="test", raw_text="test"))
    
    assert "   " not in clean_p.experience[0].description
    assert "▪" not in clean_p.experience[0].description
    assert "-" in clean_p.experience[0].description
    assert len(prov) > 0

def test_perturbation_immutability(sample_profile, sample_jd):
    original_skill_0 = sample_profile.skills[0]
    original_exp_desc = sample_profile.experience[0].description

    op = LexicalNormalizationPerturbation()
    perturbed, _ = op.perturb(sample_profile, sample_jd)

    assert sample_profile.skills[0] == original_skill_0
    assert sample_profile.experience[0].description == original_exp_desc
    assert perturbed.skills[0] != original_skill_0

# ------------------------------------------------------------------------------
# 3. Auditor End-to-End Tests
# ------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def ranking_service():
    kw_matcher = KeywordMatcher()
    model = LocalSentenceTransformerEmbeddingModel("all-MiniLM-L6-v2")
    sem_matcher = SemanticMatcher(model)
    evaluator = RequirementEvaluator(kw_matcher, sem_matcher)
    scoring_engine = ScoringEngine(evaluator)
    return RankingService(scoring_engine)

def test_auditor_empty_candidates(ranking_service, sample_jd):
    auditor = RankingRobustnessAuditor(ranking_service)
    audit = auditor.audit(sample_jd, [])
    assert audit.candidate_count == 0
    assert audit.robustness_status == RobustnessClassification.ROBUST

def test_auditor_end_to_end(ranking_service, sample_jd, sample_profile):
    c2 = CandidateProfile(
        candidate_id="cand_test_02",
        name="Bob Vance",
        skills=["Python"],
        experience=[]
    )

    auditor = RankingRobustnessAuditor(ranking_service)
    audit = auditor.audit(sample_jd, [sample_profile, c2])

    assert isinstance(audit, RankingRobustnessAudit)
    assert audit.candidate_count == 2
    assert len(audit.baseline_ranking) == 2
    assert len(audit.perturbation_runs) == 3

    for run in audit.perturbation_runs:
        assert 0.0 <= run.top3_overlap <= 1.0
        assert -1.0 <= run.rank_correlation <= 1.0
        assert run.average_absolute_rank_displacement >= 0.0

    assert audit.robustness_status in [
        RobustnessClassification.ROBUST,
        RobustnessClassification.MODERATELY_SENSITIVE,
        RobustnessClassification.HIGHLY_SENSITIVE
    ]
    assert len(audit.limitations) > 0

def test_auditor_deterministic_execution(ranking_service, sample_jd, sample_profile):
    auditor = RankingRobustnessAuditor(ranking_service)
    audit_1 = auditor.audit(sample_jd, [sample_profile])
    audit_2 = auditor.audit(sample_jd, [sample_profile])

    assert audit_1.overall_rank_correlation == audit_2.overall_rank_correlation
    assert audit_1.overall_top3_overlap == audit_2.overall_top3_overlap
    assert audit_1.overall_average_rank_displacement == audit_2.overall_average_rank_displacement
