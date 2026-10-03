from typing import Optional
from pydantic import BaseModel, Field
from app.schemas.domain import Evidence

class KeywordMatchResult(BaseModel):
    """
    Represents a lexical/keyword match between a JD requirement and candidate evidence.
    This contains strictly lexical observations and NOT a final match verdict or score.
    """
    requirement_id: str = Field(..., description="ID of the JD requirement being evaluated")
    evidence_id: Optional[str] = Field(default=None, description="Optional ID for the evidence (None if unassigned)")
    requirement_text: str = Field(..., description="The original JD requirement text")
    matched_keyword: str = Field(..., description="The specific keyword/term that matched")
    evidence_text: str = Field(..., description="The text of the candidate evidence where match occurred")
    match_type: str = Field(..., description="Method of match: EXACT, ALIAS, or FUZZY")
    lexical_score: float = Field(..., description="Confidence/similarity of the lexical match [0.0, 1.0]", ge=0.0, le=1.0)
    page_number: Optional[int] = Field(default=None, description="Page number of the original evidence")
    source_section: Optional[str] = Field(default=None, description="Section of the resume where the evidence was found")
    source_text: Optional[str] = Field(default=None, description="Original source text snippet of the evidence")
    evidence_type: Optional[str] = Field(default=None, description="Type of evidence: skill, experience, project, education, certification, summary")
    evidence: Optional[Evidence] = Field(default=None, description="Underlying domain Evidence object if available")
