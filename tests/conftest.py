import io
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

from papers.models import Paper
from summarizer.models import Summary

SAMPLE_TEXT = (
    'Attention Is All You Need. We propose the Transformer, a model architecture '
    'based solely on attention mechanisms. Experiments on two machine translation '
    'tasks show these models to be superior in quality while being more parallelizable.'
)


def make_pdf_bytes(text: str = SAMPLE_TEXT, pages: int = 1) -> bytes:
    """Generate a small, real PDF containing ``text`` on each page."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    for _ in range(pages):
        y = 800
        for chunk in [text[i : i + 80] for i in range(0, len(text), 80)]:
            pdf.drawString(40, y, chunk)
            y -= 16
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def make_upload(name: str = 'paper.pdf', content: bytes | None = None) -> SimpleUploadedFile:
    return SimpleUploadedFile(
        name, make_pdf_bytes() if content is None else content, content_type='application/pdf'
    )


VALID_SUMMARY = {
    'abstract': 'The paper introduces the Transformer.',
    'key_points': ['Attention only', 'Highly parallel'],
    'methodology': 'Encoder-decoder trained on WMT.',
    'results': 'BLEU 28.4 on EN-DE.',
    'conclusion': 'Attention suffices.',
    'citations': ['Bahdanau et al. (2015). Neural MT. ICLR.'],
}


def completion(content: str | None):
    """Build an object shaped like a Groq chat completion response."""
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


@pytest.fixture
def mock_groq(monkeypatch):
    """Replace the Groq client; tests set ``create.return_value``/``side_effect``."""
    client = MagicMock()
    client.chat.completions.create.return_value = completion(json.dumps(VALID_SUMMARY))
    factory = MagicMock(return_value=client)
    monkeypatch.setattr('summarizer.services.Groq', factory)
    return client


@pytest.fixture
def user(db):
    return User.objects.create_user('alice', 'alice@example.com', 'pw-alice-123')


@pytest.fixture
def other_user(db):
    return User.objects.create_user('mallory', 'mallory@example.com', 'pw-mallory-123')


@pytest.fixture
def auth_client(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def paper(user):
    return Paper.objects.create(
        title='Attention Is All You Need',
        author='Vaswani et al.',
        file=make_upload(),
        uploaded_by=user,
        file_size=1234,
    )


@pytest.fixture
def summary(paper):
    s = Summary(
        paper=paper,
        abstract=VALID_SUMMARY['abstract'],
        methodology=VALID_SUMMARY['methodology'],
        results=VALID_SUMMARY['results'],
        conclusion=VALID_SUMMARY['conclusion'],
    )
    s.set_key_points_list(VALID_SUMMARY['key_points'])
    s.set_citations_list(VALID_SUMMARY['citations'])
    s.save()
    return s
