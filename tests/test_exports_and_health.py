import io

import pytest
from django.urls import reverse
from docx import Document
from pypdf import PdfReader

from summarizer.exports import build_summary_docx, build_summary_pdf, export_filename

pytestmark = pytest.mark.django_db


def test_pdf_escapes_markup_characters(summary):
    # Unescaped "<" / "&" used to crash ReportLab's Paragraph parser.
    summary.results = 'p < 0.05 & accuracy > 90% <b>unclosed'
    summary.set_key_points_list(['A < B', 'Smith & Jones'])
    pdf = build_summary_pdf(summary)
    text = '\n'.join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)
    assert 'p < 0.05 & accuracy > 90%' in text
    assert 'Smith & Jones' in text


def test_docx_contains_all_sections(summary):
    doc = Document(io.BytesIO(build_summary_docx(summary)))
    text = '\n'.join(p.text for p in doc.paragraphs)
    for heading in ('Abstract', 'Methodology', 'Results', 'Conclusion', 'Key Points'):
        assert heading in text
    assert '[1] Bahdanau' in text


def test_export_filename_falls_back_to_pk(summary):
    summary.paper.title = '???'
    assert export_filename(summary, 'pdf') == f'summary_{summary.pk}.pdf'


def test_healthz_ok(client):
    response = client.get(reverse('healthz'))
    assert response.status_code == 200
    assert response.json() == {'status': 'ok', 'database': 'ok'}


def test_healthz_reports_db_failure(client, monkeypatch):
    def broken_cursor():
        raise RuntimeError('db down')

    monkeypatch.setattr('academic_summarizer.views.connection.cursor', broken_cursor)
    response = client.get(reverse('healthz'))
    assert response.status_code == 503


def test_model_helpers(summary):
    summary.key_points = 'not json'
    assert summary.get_key_points_list() == []
    summary.citations = '{"a": 1}'
    assert summary.get_citations_list() == []
    assert 'English' in summary.get_language_display_short()
    assert str(summary).startswith('Summary of:')
