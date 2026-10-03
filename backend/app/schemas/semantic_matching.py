from pydantic import BaseModel, Field
from typing import Optional
from app.schemas.domain import Evidence

class SemanticMatchResult(BaseModel):
    """
    Represents the semantic similarity between a JD requirement and a piece of candidate evidence.
    This is NOT a final match verdict.
    """
    requirement_id: str = Field(..., description="ID of the JD requirement being evaluated")
    evidence_id: Optional[str] = Field(default=None, description="Optional ID for the evidence")
    requirement_text: str = Field(..., description="The text of the requirement")
    evidence_text: str = Field(..., description="The text of the candidate evidence")
    similarity_score: float = Field(..., description="Cosine similarity score [-1.0, 1.0]", ge=-1.0, le=1.0)
    page_number: Optional[int] = Field(default=None, description="Page number of the original evidence")
    source_section: Optional[str] = Field(default=None, description="Section of the resume where the evidence was found")
    source_text: Optional[str] = Field(default=None, description="Original source text snippet of the evidence")
    evidence_type: Optional[str] = Field(default=None, description="Type of evidence (e.g., skill, experience, project)")
    evidence: Optional[Evidence] = Field(default=None, description="Underlying domain Evidence object if available")
