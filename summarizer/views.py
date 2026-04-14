import io
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView

from .models import Summary

logger = logging.getLogger(__name__)


class SummaryHistoryView(LoginRequiredMixin, ListView):
    model = Summary
    template_name = 'summarizer/history.html'
    context_object_name = 'summaries'
    paginate_by = 10

    def get_queryset(self):
        return (
            Summary.objects
            .filter(paper__uploaded_by=self.request.user)
            .select_related('paper')
            .order_by('-created_at')
        )


class SummaryDetailView(LoginRequiredMixin, DetailView):
    model = Summary
    template_name = 'summarizer/summary_detail.html'
    context_object_name = 'summary'

    def get_queryset(self):
        return Summary.objects.filter(paper__uploaded_by=self.request.user).select_related('paper')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['key_points'] = self.object.get_key_points_list()
        return ctx


@login_required
def export_summary_pdf(request, pk):
    """Export a summary as a formatted PDF using ReportLab."""
    summary = get_object_or_404(
        Summary, pk=pk, paper__uploaded_by=request.user
    )

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
        )

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=2.5 * cm,
            rightMargin=2.5 * cm,
            topMargin=2.5 * cm,
            bottomMargin=2.5 * cm,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=18,
            spaceAfter=12,
            textColor=colors.HexColor('#1a1a2e'),
        )
        heading_style = ParagraphStyle(
            'SectionHeading',
            parent=styles['Heading2'],
            fontSize=13,
            spaceAfter=6,
            spaceBefore=14,
            textColor=colors.HexColor('#16213e'),
            borderPad=4,
        )
        body_style = ParagraphStyle(
            'Body',
            parent=styles['Normal'],
            fontSize=10,
            leading=15,
            spaceAfter=6,
        )

        story = [
            Paragraph(summary.paper.title, title_style),
            Paragraph(f'Author(s): {summary.paper.author or "N/A"}', body_style),
            Spacer(1, 0.3 * cm),
        ]

        sections = [
            ('Abstract', summary.abstract),
            ('Methodology', summary.methodology),
            ('Results', summary.results),
            ('Conclusion', summary.conclusion),
        ]
        for heading, content in sections:
            if content:
                story.append(Paragraph(heading, heading_style))
                story.append(Paragraph(content.replace('\n', '<br/>'), body_style))

        key_points = summary.get_key_points_list()
        if key_points:
            story.append(Paragraph('Key Points', heading_style))
            items = [
                ListItem(Paragraph(pt, body_style), bulletColor=colors.HexColor('#0f3460'))
                for pt in key_points
            ]
            story.append(ListFlowable(items, bulletType='bullet'))

        doc.build(story)
        buffer.seek(0)

        safe_title = ''.join(c for c in summary.paper.title[:50] if c.isalnum() or c in ' -_').strip()
        filename = f'summary_{safe_title or summary.pk}.pdf'

        response = HttpResponse(buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as exc:
        logger.error('PDF export failed for summary %s: %s', pk, exc)
        return HttpResponse(f'Export failed: {exc}', status=500)


@login_required
def export_summary_word(request, pk):
    """Export a summary as a .docx Word document using python-docx."""
    summary = get_object_or_404(
        Summary, pk=pk, paper__uploaded_by=request.user
    )

    try:
        from docx import Document
        from docx.shared import Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        doc = Document()

        # Title
        title_para = doc.add_heading(summary.paper.title, level=0)
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        if summary.paper.author:
            author_para = doc.add_paragraph(f'Author(s): {summary.paper.author}')
            author_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        doc.add_paragraph()

        sections = [
            ('Abstract', summary.abstract),
            ('Methodology', summary.methodology),
            ('Results', summary.results),
            ('Conclusion', summary.conclusion),
        ]
        for heading, content in sections:
            if content:
                doc.add_heading(heading, level=1)
                doc.add_paragraph(content)

        key_points = summary.get_key_points_list()
        if key_points:
            doc.add_heading('Key Points', level=1)
            for point in key_points:
                doc.add_paragraph(point, style='List Bullet')

        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)

        safe_title = ''.join(c for c in summary.paper.title[:50] if c.isalnum() or c in ' -_').strip()
        filename = f'summary_{safe_title or summary.pk}.docx'

        response = HttpResponse(
            buffer.read(),
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as exc:
        logger.error('Word export failed for summary %s: %s', pk, exc)
        return HttpResponse(f'Export failed: {exc}', status=500)
