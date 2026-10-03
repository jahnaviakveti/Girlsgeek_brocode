import logging
from pathlib import Path
from typing import List, Optional

from app.schemas.api import (
    AnalysisResponse,
    JobSummary,
    JobRequirementSummary,
    FailedCandidate,
)
from app.schemas.domain import JobDescription, RequirementPriority
from app.schemas.candidate import CandidateProfile
from app.services.document_parser import DocumentParser
from app.services.jd_analyzer import JDAnalyzer, JDBiasDetector
from app.services.resume_analyzer import ResumeAnalyzer
from app.services.keyword_matcher import KeywordMatcher
from app.services.semantic_matcher import LocalSentenceTransformerEmbeddingModel, SemanticMatcher
from app.services.hybrid_evaluator import (
    RequirementEvaluator,
    ScoringEngine,
    RankingService,
)
from app.services.explanation_engine import ExplanationEngine

logger = logging.getLogger(__name__)

class ShortlistingPipeline:
    """
    End-to-end Local Shortlisting Pipeline.
    Encapsulates all processing stages from PDF parsing to ranking and evidence-first explainability.
    Reuses a single persistent local sentence transformer embedding model to ensure fast sub-second execution.
    """

    _instance: Optional["ShortlistingPipeline"] = None

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        logger.info("Initializing ShortlistingPipeline services...")
        self.parser = DocumentParser()
        self.jd_analyzer = JDAnalyzer()
        self.bias_detector = JDBiasDetector()
        self.resume_analyzer = ResumeAnalyzer()
        self.keyword_matcher = KeywordMatcher()
        
        # Singleton local embedding model
        self.embedding_model = LocalSentenceTransformerEmbeddingModel(model_name)
        self.semantic_matcher = SemanticMatcher(self.embedding_model)
        self.evaluator = RequirementEvaluator(self.keyword_matcher, self.semantic_matcher)
        self.scoring_engine = ScoringEngine(self.evaluator)
        self.ranking_service = RankingService(self.scoring_engine)
        self.explanation_engine = ExplanationEngine()
        logger.info("ShortlistingPipeline initialized successfully.")

    @classmethod
    def get_instance(cls) -> "ShortlistingPipeline":
        """
        Singleton accessor to avoid re-instantiating heavy models per request.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def process_batch(
        self,
        jd_path: Path,
        resume_paths: List[any]
    ) -> AnalysisResponse:
        """
        Executes end-to-end shortlisting workflow for 1 JD and N resumes.
        Isolates per-document parse errors to prevent a single bad file from crashing the batch.
        """
        # 1. Parse and analyze Job Description
        jd_doc = self.parser.parse_pdf(jd_path)
        jd = self.jd_analyzer.analyze(jd_doc)

        # 2. Parse and analyze candidate resumes with isolated error handling
        candidates: List[CandidateProfile] = []
        failed_candidates: List[FailedCandidate] = []

        for item in resume_paths:
            if isinstance(item, tuple):
                display_name, r_path = item
            else:
                display_name, r_path = item.name, item

            try:
                doc = self.parser.parse_pdf(r_path)
                profile = self.resume_analyzer.analyze(doc)
                candidates.append(profile)
            except Exception as exc:
                logger.warning(f"Failed to process resume {display_name}: {exc}")
                failed_candidates.append(
                    FailedCandidate(
                        filename=display_name,
                        error=str(exc)
                    )
                )

        # 3. Score and rank candidates if any successfully parsed
        ranked_explanations = []
        if candidates and jd.requirements:
            ranked_results = self.ranking_service.rank_candidates(jd, candidates)
            ranked_explanations = self.explanation_engine.explain_all(ranked_results, jd)
        elif candidates and not jd.requirements:
            logger.warning("Job Description contained 0 extractable requirements.")

        # 4. Assemble Job Summary & Audit for Bias (Bonus Task 1)
        bias_audit = self.bias_detector.audit_jd(jd, raw_text=jd_doc.raw_text)

        req_summaries = [
            JobRequirementSummary(
                id=r.id,
                requirement_text=r.requirement_text,
                category=r.category.value,
                priority=r.priority.value,
                extracted_keywords=r.extracted_keywords or []
            )
            for r in jd.requirements
        ]

        required_count = sum(1 for r in jd.requirements if r.priority == RequirementPriority.REQUIRED)
        preferred_count = sum(1 for r in jd.requirements if r.priority == RequirementPriority.PREFERRED)

        job_summary = JobSummary(
            job_id=jd.jd_id,
            job_title=jd.title or "Job Description",
            total_requirements=len(jd.requirements),
            required_count=required_count,
            preferred_count=preferred_count,
            requirements=req_summaries,
            bias_audit=bias_audit
        )

        return AnalysisResponse(
            job=job_summary,
            total_resumes_received=len(resume_paths),
            total_candidates_processed=len(candidates),
            total_ranked=len(ranked_explanations),
            ranked_candidates=ranked_explanations,
            failed_candidates=failed_candidates
        )
