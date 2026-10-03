class DocumentProcessingError(Exception):
    """Base exception for all document processing errors."""
    def __init__(self, message: str, details: str = None):
        super().__init__(message)
        self.message = message
        self.details = details

class DocumentNotFoundError(DocumentProcessingError):
    """Raised when the specified document file does not exist."""
    pass

class InvalidPDFError(DocumentProcessingError):
    """Raised when the file is not a valid PDF or has invalid headers."""
    pass

class EmptyPDFError(DocumentProcessingError):
    """Raised when the PDF file has 0 pages or 0 bytes."""
    pass

class CorruptPDFError(DocumentProcessingError):
    """Raised when the PDF is damaged or cannot be decrypted/read."""
    pass

class NoTextExtractedError(DocumentProcessingError):
    """Raised when a valid PDF contains no extractable digital text (e.g. scanned-only image)."""
    pass
