import os
import shutil
import tempfile
from pathlib import Path
from typing import List, Tuple

from fastapi import APIRouter, UploadFile, File, HTTPException, status
from app.schemas.api import AnalysisResponse
from app.services.pipeline import ShortlistingPipeline
from app.core.exceptions import (
    DocumentProcessingError,
    InvalidPDFError,
    EmptyPDFError,
    CorruptPDFError,
    NoTextExtractedError,
)

router = APIRouter()

@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze candidate resumes against a Job Description",
    description="Accepts one Job Description PDF and a batch of candidate resume PDFs, returning ranked candidates with evidence-backed explanations."
)
async def analyze_candidates(
    jd_file: UploadFile = File(..., description="Single Job Description PDF"),
    resume_files: List[UploadFile] = File(..., description="Batch of candidate resume PDFs (15-18 expected)")
) -> AnalysisResponse:
    # 1. Validate JD file
    if not jd_file or not jd_file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A Job Description PDF file is required."
        )

    if not jd_file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format for Job Description: '{jd_file.filename}'. Only PDF files are accepted."
        )

    # 2. Validate Resumes batch size (1-25 candidate resumes allowed)
    if not resume_files or len(resume_files) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No candidate resumes provided. Batch size must be between 1 and 25 candidate resumes."
        )

    if len(resume_files) < 1 or len(resume_files) > 25:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch size must be between 1 and 25 candidate resumes (received {len(resume_files)})."
        )

    for r_file in resume_files:
        if not r_file.filename or not r_file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format for resume: '{r_file.filename or 'unnamed'}'. Only PDF files are accepted."
            )

    # 3. Create isolated temporary directory for file processing
    temp_dir = tempfile.mkdtemp(prefix="internloom_analysis_")
    try:
        temp_dir_path = Path(temp_dir)

        # Save JD file
        jd_path = temp_dir_path / f"jd_{jd_file.filename}"
        with open(jd_path, "wb") as f_out:
            content = await jd_file.read()
            if len(content) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Job Description PDF '{jd_file.filename}' is empty (0 bytes)."
                )
            f_out.write(content)

        # Save resume files
        resume_inputs: List[Tuple[str, Path]] = []
        for idx, r_file in enumerate(resume_files):
            clean_name = f"resume_{idx}_{r_file.filename}"
            r_path = temp_dir_path / clean_name
            with open(r_path, "wb") as f_out:
                content = await r_file.read()
                f_out.write(content)
            resume_inputs.append((r_file.filename, r_path))

        # 4. Execute pipeline
        pipeline = ShortlistingPipeline.get_instance()
        try:
            response = pipeline.process_batch(jd_path, resume_inputs)
            return response
        except (InvalidPDFError, EmptyPDFError, CorruptPDFError, NoTextExtractedError) as doc_err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to process Job Description: {doc_err.message}"
            )
        except DocumentProcessingError as proc_err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document processing error: {proc_err.message}"
            )
        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Analysis pipeline error: {str(err)}"
            )

    finally:
        # Safe cleanup of uploaded temporary files
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
