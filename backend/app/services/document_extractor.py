"""
Document text extractor service.
Extracts clean plain text from PDF and DOCX files.
Detects unreadable documents, scanned PDFs, and malformed files.
"""
import io
import os
from typing import Tuple
import pymupdf as fitz
import docx


class DocumentExtractionError(Exception):
    """Base exception for document extraction failures."""
    pass


class UnsupportedFileError(DocumentExtractionError):
    """Raised when an unsupported file format is uploaded."""
    pass


class UnreadableDocumentError(DocumentExtractionError):
    """Raised when the document is empty or a scanned image without selectable text."""
    pass


class CorruptDocumentError(DocumentExtractionError):
    """Raised when the file is corrupt or cannot be parsed."""
    pass


class DocumentExtractor:
    """Service to extract plain text from uploaded resume documents."""

    @staticmethod
    def extract_from_bytes(file_bytes: bytes, filename: str) -> str:
        """
        Extract text from file bytes based on file extension.
        Enforces validation against empty or unreadable content.
        """
        if not file_bytes or len(file_bytes) == 0:
            raise UnreadableDocumentError("The uploaded file is empty. Please upload a valid resume.")

        ext = os.path.splitext(filename)[1].lower()

        if ext == ".pdf":
            text = DocumentExtractor._extract_pdf(file_bytes)
        elif ext in [".docx", ".doc"]:
            text = DocumentExtractor._extract_docx(file_bytes)
        else:
            raise UnsupportedFileError(f"Unsupported file format '{ext}'. Only PDF and DOCX resumes are supported.")

        cleaned = text.strip()

        # Check if text is too short (e.g. image-only scanned PDF)
        if len(cleaned) < 50:
            raise UnreadableDocumentError(
                "Unable to extract text from the resume. If this is a scanned image PDF, "
                "please provide a text-based PDF or DOCX format."
            )

        return cleaned

    @staticmethod
    def _extract_pdf(file_bytes: bytes) -> str:
        """Extract text from PDF using PyMuPDF (fitz)."""
        text_parts = []
        try:
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                if doc.page_count == 0:
                    raise UnreadableDocumentError("The PDF document has 0 pages.")

                for page_num in range(doc.page_count):
                    page = doc.load_page(page_num)
                    page_text = page.get_text("text")
                    if page_text:
                        text_parts.append(page_text)

        except fitz.FileDataError as e:
            raise CorruptDocumentError(f"The PDF file is corrupted and cannot be read: {e}")
        except Exception as e:
            if isinstance(e, DocumentExtractionError):
                raise
            raise CorruptDocumentError(f"Failed to parse PDF document: {e}")

        return "\n\n".join(text_parts)

    @staticmethod
    def _extract_docx(file_bytes: bytes) -> str:
        """Extract text from DOCX using python-docx."""
        try:
            stream = io.BytesIO(file_bytes)
            doc = docx.Document(stream)
            text_parts = []

            for paragraph in doc.paragraphs:
                p_text = paragraph.text.strip()
                if p_text:
                    text_parts.append(p_text)

            # Also check text inside tables if any
            for table in doc.tables:
                for row in table.rows:
                    row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_cells:
                        text_parts.append(" | ".join(row_cells))

            return "\n\n".join(text_parts)
        except Exception as e:
            raise CorruptDocumentError(f"Failed to read DOCX document: {e}")
