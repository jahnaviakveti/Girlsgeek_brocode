import os
import uuid
from pathlib import Path
from typing import Union, List, Tuple
import fitz  # PyMuPDF

from app.core.exceptions import (
    DocumentNotFoundError,
    InvalidPDFError,
    EmptyPDFError,
    CorruptPDFError,
    NoTextExtractedError,
    DocumentProcessingError,
)
from app.schemas.document import (
    GenericDocument,
    DocumentPage,
    DocumentBlock,
)
from app.services.document_parser.normalizer import normalize_text
from app.services.document_parser.section_detector import SectionDetector

class DocumentParser:
    """
    Generic local PDF document parser using PyMuPDF (fitz).
    Preserves page boundaries, bounding boxes, raw and normalized text,
    and structural section information.
    """

    @classmethod
    def parse_pdf(cls, file_path: Union[str, Path]) -> GenericDocument:
        """
        Parses a local PDF file into a GenericDocument.
        Does not make domain-specific assumptions about the document type.
        """
        path = Path(file_path)

        # 1. Check file existence
        if not path.exists():
            raise DocumentNotFoundError(f"Document file not found: {path}")

        if not path.is_file():
            raise DocumentNotFoundError(f"Specified path is not a file: {path}")

        # 2. Check for empty file
        file_size = path.stat().st_size
        if file_size == 0:
            raise EmptyPDFError(f"PDF file is empty (0 bytes): {path.name}")

        # 3. Check for valid PDF header (%PDF)
        try:
            with open(path, "rb") as f:
                header = f.read(1024)
                if b"%PDF" not in header:
                    raise InvalidPDFError(f"File is not a valid PDF document: {path.name}")
        except (IOError, OSError) as e:
            raise DocumentProcessingError(f"Failed to read file: {path.name}", str(e))

        # 4. Open document via PyMuPDF
        doc = None
        try:
            try:
                doc = fitz.open(str(path))
            except Exception as e:
                raise CorruptPDFError(f"Failed to open corrupt or encrypted PDF: {path.name}", str(e))

            if doc.is_encrypted:
                raise CorruptPDFError(f"Encrypted PDF documents are not supported: {path.name}")

            if doc.page_count == 0:
                raise EmptyPDFError(f"PDF document contains 0 pages: {path.name}")

            pages: List[DocumentPage] = []
            total_raw_text_parts: List[str] = []
            total_normalized_parts: List[str] = []

            # 5. Extract text and layout block by page
            for page_index in range(doc.page_count):
                page_number = page_index + 1
                try:
                    page = doc.load_page(page_index)
                except Exception as e:
                    raise CorruptPDFError(f"Failed to read page {page_number} in {path.name}", str(e))

                # Extract raw page text
                raw_page_text = page.get_text("text") or ""
                normalized_page_text = normalize_text(raw_page_text)

                # Extract block layout information
                # fitz get_text("blocks") returns (x0, y0, x1, y1, text, block_no, block_type)
                # block_type 0 = text, 1 = image
                blocks: List[DocumentBlock] = []
                try:
                    raw_blocks = page.get_text("blocks") or []
                    for block_no, b in enumerate(raw_blocks):
                        if len(b) >= 7 and b[6] == 0:  # Text block
                            x0, y0, x1, y1 = float(b[0]), float(b[1]), float(b[2]), float(b[3])
                            block_text = str(b[4]).strip()
                            if block_text:
                                blocks.append(
                                    DocumentBlock(
                                        page_number=page_number,
                                        block_index=block_no,
                                        text=block_text,
                                        bbox=(x0, y0, x1, y1),
                                    )
                                )
                except Exception:
                    # Fallback gracefully if block coordinates extraction encounters issues
                    blocks = []

                doc_page = DocumentPage(
                    page_number=page_number,
                    raw_text=raw_page_text,
                    normalized_text=normalized_page_text,
                    blocks=blocks,
                )
                pages.append(doc_page)

                if raw_page_text.strip():
                    total_raw_text_parts.append(raw_page_text)
                if normalized_page_text.strip():
                    total_normalized_parts.append(normalized_page_text)

            # 6. Verify that extractable text was actually found
            full_raw_text = "\n\n".join(total_raw_text_parts).strip()
            full_normalized_text = "\n\n".join(total_normalized_parts).strip()

            if not full_raw_text:
                raise NoTextExtractedError(
                    f"No digital text could be extracted from PDF: {path.name}. "
                    "The document may consist exclusively of scanned images or empty pages."
                )

            # 7. Conservative Section Detection
            sections_map, detected_sections = SectionDetector.detect_sections(pages)

            # 8. Assemble GenericDocument
            doc_id = str(uuid.uuid4())
            return GenericDocument(
                document_id=doc_id,
                filename=path.name,
                raw_text=full_raw_text,
                normalized_text=full_normalized_text,
                page_count=doc.page_count,
                pages=pages,
                sections=sections_map,
                detected_sections=detected_sections,
            )

        finally:
            if doc is not None:
                doc.close()


def parse_document(file_path: Union[str, Path]) -> GenericDocument:
    """
    Convenience function to parse a local PDF document.
    """
    return DocumentParser.parse_pdf(file_path)
