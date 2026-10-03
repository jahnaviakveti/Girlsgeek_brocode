from typing import List, Optional, Dict, Tuple
from pydantic import BaseModel, Field

class DocumentBlock(BaseModel):
    """
    Represents a discrete layout block (e.g., paragraph or heading) on a page.
    """
    page_number: int = Field(..., description="1-indexed page number")
    block_index: int = Field(..., description="0-indexed order of block on page")
    text: str = Field(..., description="Raw text of the block")
    bbox: Optional[Tuple[float, float, float, float]] = Field(
        default=None, 
        description="Bounding box coordinates (x0, y0, x1, y1)"
    )

class DocumentPage(BaseModel):
    """
    Represents an extracted page with boundary and provenance preservation.
    """
    page_number: int = Field(..., description="1-indexed page number")
    raw_text: str = Field(..., description="Unaltered raw extracted text for this page")
    normalized_text: str = Field(..., description="Normalized text for downstream NLP processing")
    blocks: List[DocumentBlock] = Field(default_factory=list, description="Ordered layout blocks on this page")

class DocumentSection(BaseModel):
    """
    Represents a detected section within the document.
    """
    title: str = Field(..., description="Raw heading text as detected in the document")
    canonical_name: str = Field(..., description="Normalized/canonical heading identifier")
    text: str = Field(..., description="Body content of the section")
    start_page: int = Field(..., description="1-indexed page number where the section starts")

class GenericDocument(BaseModel):
    """
    Generic structured document representation produced by the document processing pipeline.
    Agnostic to document type (neither JD-specific nor resume-specific).
    """
    document_id: str = Field(..., description="Unique identifier for the parsed document")
    filename: str = Field(..., description="Original filename")
    raw_text: str = Field(..., description="Concatenated raw extracted text preserving document structure")
    normalized_text: str = Field(..., description="Cleaned and normalized text preserving source fidelity")
    page_count: int = Field(..., description="Total number of pages")
    pages: List[DocumentPage] = Field(default_factory=list, description="Per-page structured representations")
    sections: Dict[str, str] = Field(
        default_factory=dict, 
        description="Map of canonical section names to normalized section content"
    )
    detected_sections: List[DocumentSection] = Field(
        default_factory=list,
        description="List of detected sections with provenance"
    )
