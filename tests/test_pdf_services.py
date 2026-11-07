import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from papers import services
from papers.services import extract_text_from_pdf, validate_pdf_upload
from tests.conftest import make_pdf_bytes, make_upload


class TestExtractText:
    def test_extracts_text_from_generated_pdf(self):
        text = extract_text_from_pdf(io.BytesIO(make_pdf_bytes('Hello transformer world')))
        assert 'Hello transformer world' in text

    def test_joins_multiple_pages(self):
        text = extract_text_from_pdf(io.BytesIO(make_pdf_bytes('Page text', pages=3)))
        assert text.count('Page text') == 3

    def test_garbage_returns_empty_string_instead_of_raising(self):
        assert extract_text_from_pdf(io.BytesIO(b'definitely not a pdf')) == ''

    def test_falls_back_to_pypdf_when_pdfplumber_finds_nothing(self, monkeypatch):
        monkeypatch.setattr(services, '_extract_with_pdfplumber', lambda f: '')
        text = extract_text_from_pdf(io.BytesIO(make_pdf_bytes('Fallback text')))
        assert 'Fallback text' in text


class TestValidateUpload:
    def test_valid_pdf_passes(self):
        assert validate_pdf_upload(make_upload()) is None

    def test_rejects_wrong_extension(self):
        assert 'Only PDF' in validate_pdf_upload(make_upload(name='notes.txt'))

    def test_rejects_renamed_non_pdf(self):
        fake = SimpleUploadedFile('evil.pdf', b'MZ\x90\x00 not a pdf')
        assert 'valid PDF' in validate_pdf_upload(fake)

    @pytest.mark.parametrize('limit_mb', [1])
    def test_rejects_oversized_file(self, settings, limit_mb):
        settings.MAX_UPLOAD_MB = limit_mb
        big = SimpleUploadedFile('big.pdf', b'%PDF-1.4\n' + b'0' * (limit_mb * 1024 * 1024))
        assert 'under 1 MB' in validate_pdf_upload(big)

    def test_resets_file_pointer(self):
        upload = make_upload()
        validate_pdf_upload(upload)
        assert upload.tell() == 0
