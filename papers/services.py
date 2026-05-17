"""PDF text extraction service using PyPDF2 and pdfplumber."""
import logging
import io
import re

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


# ── Citation generation ──────────────────────────────────────────────────────

_AUTHOR_SPLIT = re.compile(r'\s+and\s+|\s*;\s*|\s*&\s*', re.IGNORECASE)
_BIBTEX_STOPWORDS = {
    'the', 'a', 'an', 'of', 'for', 'to', 'in', 'on', 'and', 'or', 'with',
    'from', 'by', 'at', 'as', 'is', 'this', 'that', 'using',
}


def _split_authors(raw: str) -> list[str]:
    """Split a free-form author string into individual author names."""
    if not raw or not raw.strip():
        return []
    parts = [p.strip() for p in _AUTHOR_SPLIT.split(raw.strip()) if p.strip()]
    # Edge case: "Author1, Author2, Author3" with no 'and' — split on comma
    # only if multiple commas (a single comma is treated as "Last, First").
    if len(parts) == 1 and parts[0].count(',') >= 2:
        parts = [p.strip() for p in parts[0].split(',') if p.strip()]
    return parts


def _parse_name(name: str) -> tuple[str, str, str]:
    """Return (first_full, last, initials_dotted) for a single author name."""
    name = name.strip()
    if ',' in name:
        last, _, rest = name.partition(',')
        last = last.strip()
        first_tokens = rest.strip().split()
    else:
        tokens = name.split()
        if len(tokens) == 1:
            return (tokens[0], tokens[0], '')
        last = tokens[-1]
        first_tokens = tokens[:-1]
    first_full = ' '.join(first_tokens)
    initials = ' '.join(t[0].upper() + '.' for t in first_tokens if t)
    return (first_full, last, initials)


def _bibtex_key(first_last: str, year: int, title: str) -> str:
    """Build a citation key like 'hamrayev2026pos'."""
    last = re.sub(r'[^a-z]', '', first_last.lower()) or 'anon'
    words = re.findall(r'[a-zA-Z]+', title.lower())
    significant = next(
        (w for w in words if w not in _BIBTEX_STOPWORDS and len(w) >= 3),
        'paper',
    )
    return f'{last}{year}{significant}'


def _strip_url_scheme(url: str) -> str:
    """For APA/MLA: strip protocol but keep the rest, e.g. summarizer.example.com/papers/7/."""
    return re.sub(r'^https?://', '', url).rstrip('/')


def generate_citations(paper, base_url: str) -> dict:
    """
    Build APA, MLA, IEEE, and BibTeX citation strings for a Paper.

    Args:
        paper:    a papers.models.Paper instance.
        base_url: absolute URL to this paper's detail page,
                  e.g. 'https://summarizer.example.com/papers/7/'.

    Returns:
        {'apa': str, 'mla': str, 'ieee': str, 'bibtex': str}
    """
    title = (paper.title or 'Untitled').strip().rstrip('.')
    year = paper.uploaded_at.year if paper.uploaded_at else None
    if year is None:
        from django.utils import timezone
        year = timezone.now().year

    authors_raw = (paper.author or '').strip()
    parsed = [_parse_name(n) for n in _split_authors(authors_raw)]
    if not parsed:
        parsed = [('', 'Unknown Author', '')]

    short_url = _strip_url_scheme(base_url)

    # ── APA ────────────────────────────────────────────────────────────────
    def apa_name(first_full, last, initials):
        return f'{last}, {initials}' if initials else last
    apa_names = [apa_name(*p) for p in parsed]
    if len(apa_names) == 1:
        apa_authors = apa_names[0]
    elif len(apa_names) == 2:
        apa_authors = f'{apa_names[0]} & {apa_names[1]}'
    elif len(apa_names) <= 20:
        apa_authors = ', '.join(apa_names[:-1]) + f', & {apa_names[-1]}'
    else:
        # APA 7 rule: list first 19, ellipsis, then last
        apa_authors = ', '.join(apa_names[:19]) + f', … {apa_names[-1]}'
    apa = f'{apa_authors} ({year}). {title}. Retrieved from {short_url}'

    # ── MLA ────────────────────────────────────────────────────────────────
    first_first, first_last, _ = parsed[0]
    if len(parsed) == 1:
        mla_authors = f'{first_last}, {first_first}' if first_first else first_last
    elif len(parsed) == 2:
        f2, l2, _ = parsed[1]
        primary = f'{first_last}, {first_first}' if first_first else first_last
        secondary = f'{f2} {l2}'.strip() if f2 else l2
        mla_authors = f'{primary}, and {secondary}'
    else:
        primary = f'{first_last}, {first_first}' if first_first else first_last
        mla_authors = f'{primary}, et al'
    mla = f'{mla_authors}. "{title}." {year}, {short_url}.'

    # ── IEEE ───────────────────────────────────────────────────────────────
    def ieee_name(first_full, last, initials):
        return f'{initials} {last}'.strip() if initials else last
    ieee_names = [ieee_name(*p) for p in parsed]
    if len(ieee_names) == 1:
        ieee_authors = ieee_names[0]
    elif len(ieee_names) == 2:
        ieee_authors = f'{ieee_names[0]} and {ieee_names[1]}'
    else:
        ieee_authors = ', '.join(ieee_names[:-1]) + f', and {ieee_names[-1]}'
    ieee = f'{ieee_authors}, "{title}," {year}. [Online]. Available: {base_url}'

    # ── BibTeX ─────────────────────────────────────────────────────────────
    bibtex_authors = ' and '.join(
        (f'{last}, {first_full}' if first_full else last)
        for first_full, last, _ in parsed
    )
    key = _bibtex_key(parsed[0][1], year, title)
    bibtex = (
        f'@misc{{{key},\n'
        f'  author = {{{bibtex_authors}}},\n'
        f'  title  = {{{title}}},\n'
        f'  year   = {{{year}}},\n'
        f'  url    = {{{base_url}}}\n'
        f'}}'
    )

    return {
        'apa': apa,
        'mla': mla,
        'ieee': ieee,
        'bibtex': bibtex,
        'bibtex_key': key,
    }
