"""PDF validation and text extraction (pdfplumber primary, pypdf fallback)."""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

PDF_MAGIC = b'%PDF-'


def validate_pdf_upload(file_obj) -> str | None:
    """
    Validate an uploaded file is a PDF within the configured size limit.

    Checks the extension, the size and the ``%PDF-`` magic bytes (so a renamed
    non-PDF file is rejected). Returns an error message, or None if valid.
    """
    max_mb = settings.MAX_UPLOAD_MB
    if not file_obj.name.lower().endswith('.pdf'):
        return 'Only PDF files are allowed.'
    if file_obj.size > max_mb * 1024 * 1024:
        return f'File size must be under {max_mb} MB.'

    file_obj.seek(0)
    header = file_obj.read(1024)
    file_obj.seek(0)
    if PDF_MAGIC not in header:
        return 'The file does not look like a valid PDF.'
    return None


def extract_text_from_pdf(file_obj) -> str:
    """
    Extract text from a PDF file using pdfplumber (primary) with pypdf fallback.

    Args:
        file_obj: A file-like object containing PDF data.

    Returns:
        Extracted text as a string. Returns empty string on failure.
    """
    text = _extract_with_pdfplumber(file_obj)
    if not text.strip():
        text = _extract_with_pypdf(file_obj)
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


def _extract_with_pypdf(file_obj) -> str:
    """Extract text using pypdf — fallback for simple PDFs."""
    try:
        from pypdf import PdfReader

        file_obj.seek(0)
        reader = PdfReader(file_obj)
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return '\n\n'.join(text_parts)
    except Exception as exc:
        logger.warning('pypdf extraction failed: %s', exc)
        return ''
