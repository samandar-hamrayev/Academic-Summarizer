"""Render a Summary as a downloadable PDF (ReportLab) or Word (python-docx) file."""

import io
import logging
from pathlib import Path
from xml.sax.saxutils import escape

from django.utils.text import slugify

logger = logging.getLogger(__name__)

DOCX_CONTENT_TYPE = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

# ReportLab's built-in Helvetica has no Cyrillic glyphs, so Russian/Uzbek
# summaries would render as empty boxes. Use DejaVu Sans when it is installed
# (the Docker image ships it via fonts-dejavu-core).
_UNICODE_FONT_CANDIDATES = (
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/dejavu/DejaVuSans.ttf',
    '/Library/Fonts/Arial Unicode.ttf',
)
_UNICODE_FONT_NAME = 'SummaryUnicode'


def _body_font() -> str:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if _UNICODE_FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return _UNICODE_FONT_NAME
    for candidate in _UNICODE_FONT_CANDIDATES:
        if Path(candidate).is_file():
            try:
                pdfmetrics.registerFont(TTFont(_UNICODE_FONT_NAME, candidate))
                return _UNICODE_FONT_NAME
            except Exception as exc:  # corrupt/unsupported font file
                logger.warning('Could not register font %s: %s', candidate, exc)
    return 'Helvetica'


def export_filename(summary, extension: str) -> str:
    slug = slugify(summary.paper.title[:60], allow_unicode=True)
    return f'summary_{slug or summary.pk}.{extension}'


def _sections(summary) -> list[tuple[str, str]]:
    return [
        ('Abstract', summary.abstract),
        ('Methodology', summary.methodology),
        ('Results', summary.results),
        ('Conclusion', summary.conclusion),
    ]


def _markup(text: str) -> str:
    """Escape model output for ReportLab's mini-XML Paragraph markup.

    Unescaped ``<``/``&`` (e.g. "p < 0.05", "Smith & Jones") would otherwise
    make Paragraph raise and the whole export fail.
    """
    return escape(text).replace('\n', '<br/>')


def build_summary_pdf(summary) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

    font = _body_font()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
        title=summary.paper.title,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'T',
        parent=styles['Title'],
        fontName=font,
        fontSize=18,
        spaceAfter=12,
        textColor=colors.HexColor('#1a1a2e'),
    )
    heading_style = ParagraphStyle(
        'H',
        parent=styles['Heading2'],
        fontName=font,
        fontSize=13,
        spaceAfter=6,
        spaceBefore=14,
        textColor=colors.HexColor('#16213e'),
    )
    body_style = ParagraphStyle(
        'B', parent=styles['Normal'], fontName=font, fontSize=10, leading=15, spaceAfter=6
    )

    story = [
        Paragraph(_markup(summary.paper.title), title_style),
        Paragraph(_markup(f'Author(s): {summary.paper.author or "N/A"}'), body_style),
        Spacer(1, 0.3 * cm),
    ]

    for heading, content in _sections(summary):
        if content:
            story += [Paragraph(heading, heading_style), Paragraph(_markup(content), body_style)]

    key_points = summary.get_key_points_list()
    if key_points:
        story.append(Paragraph('Key Points', heading_style))
        story.append(
            ListFlowable(
                [
                    ListItem(
                        Paragraph(_markup(point), body_style),
                        bulletColor=colors.HexColor('#4361ee'),
                    )
                    for point in key_points
                ],
                bulletType='bullet',
            )
        )

    citations = summary.get_citations_list()
    if citations:
        story.append(Paragraph('References', heading_style))
        for i, citation in enumerate(citations, 1):
            story.append(Paragraph(_markup(f'[{i}] {citation}'), body_style))

    doc.build(story)
    return buffer.getvalue()


def build_summary_docx(summary) -> bytes:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    title = doc.add_heading(summary.paper.title, level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    if summary.paper.author:
        author = doc.add_paragraph(f'Author(s): {summary.paper.author}')
        author.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()

    for heading, content in _sections(summary):
        if content:
            doc.add_heading(heading, level=1)
            doc.add_paragraph(content)

    key_points = summary.get_key_points_list()
    if key_points:
        doc.add_heading('Key Points', level=1)
        for point in key_points:
            doc.add_paragraph(point, style='List Bullet')

    citations = summary.get_citations_list()
    if citations:
        doc.add_heading('References', level=1)
        for i, citation in enumerate(citations, 1):
            doc.add_paragraph(f'[{i}] {citation}')

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
