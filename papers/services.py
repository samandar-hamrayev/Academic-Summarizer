"""PDF text extraction service using PyPDF2 and pdfplumber."""
import logging
import io

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_obj) -> str:
    """
    Extract text from a PDF file using pdfplumber (primary) with PyPDF2 fallback.

    Args:
        file_obj: A file-like object containing PDF data.

    Returns:
        Extracted text as a string. Returns empty string on failure.
    """
    text = _extract_with_pdfplumber(file_obj)
    if not text.strip():
        file_obj.seek(0)
        text = _extract_with_pypdf2(file_obj)
    return text


def _extract_with_pdfplumber(file_obj) -> str:
    """Extract text using pdfplumber — better for complex layouts."""
    try:
        import pdfplumber

        file_obj.seek(0)
        text_parts = []
        with pdfplumber.open(file_obj) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return '\n\n'.join(text_parts)
    except Exception as exc:
        logger.warning('pdfplumber extraction failed: %s', exc)
        return ''


def _extract_with_pypdf2(file_obj) -> str:
    """Extract text using PyPDF2 — fallback for simple PDFs."""
    try:
        import PyPDF2

        file_obj.seek(0)
        reader = PyPDF2.PdfReader(file_obj)
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return '\n\n'.join(text_parts)
    except Exception as exc:
        logger.warning('PyPDF2 extraction failed: %s', exc)
        return ''
