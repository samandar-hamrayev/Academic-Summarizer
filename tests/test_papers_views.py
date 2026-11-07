import json
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from papers.models import Paper, Tag
from summarizer.models import Summary
from tests.conftest import completion, make_pdf_bytes, make_upload

pytestmark = pytest.mark.django_db


class TestAuth:
    @pytest.mark.parametrize(
        'url',
        [
            reverse('papers:list'),
            reverse('papers:upload'),
            reverse('summarizer:history'),
        ],
    )
    def test_login_required(self, client, url):
        response = client.get(url)
        assert response.status_code == 302
        assert response.url.startswith(reverse('login'))

    def test_home_is_public(self, client):
        assert client.get(reverse('home')).status_code == 200

    def test_register_creates_user_and_logs_in(self, client):
        response = client.post(
            reverse('register'),
            {
                'username': 'newbie',
                'email': 'newbie@example.com',
                'password1': 'a-Strong-pass-42',
                'password2': 'a-Strong-pass-42',
            },
        )
        assert response.status_code == 302
        assert User.objects.filter(username='newbie').exists()
        assert '_auth_user_id' in client.session

    def test_login_page_renders(self, client):
        assert client.get(reverse('login')).status_code == 200


class TestUpload:
    def test_upload_summarizes_and_attaches_tags(self, auth_client, user, mock_groq):
        response = auth_client.post(
            reverse('papers:upload'),
            {
                'title': 'Attention',
                'author': 'Vaswani',
                'file': make_upload(),
                'tags_json': json.dumps(['Deep Learning', 'deep learning', 'Нейросети', '!!!']),
            },
        )
        paper = Paper.objects.get()
        assert response.status_code == 302
        assert response.url == reverse('papers:detail', args=[paper.pk])
        assert paper.uploaded_by == user
        assert paper.processed is True
        assert paper.file_size > 0
        assert Summary.objects.filter(paper=paper).exists()
        assert sorted(paper.tags.values_list('slug', flat=True)) == ['deep-learning', 'нейросети']

    def test_upload_with_llm_failure_keeps_paper_and_shows_error(self, auth_client, mock_groq):
        mock_groq.chat.completions.create.return_value = completion('garbage')
        response = auth_client.post(
            reverse('papers:upload'), {'title': 'X', 'file': make_upload()}, follow=True
        )
        paper = Paper.objects.get()
        assert paper.processed is False
        messages = [str(m) for m in response.context['messages']]
        assert any('Summarization failed' in m for m in messages)

    def test_upload_with_unexpected_error_hides_details(self, auth_client, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError('secret internal detail')

        monkeypatch.setattr('papers.views.summarize_paper_task', boom)
        response = auth_client.post(
            reverse('papers:upload'), {'title': 'X', 'file': make_upload()}, follow=True
        )
        messages = [str(m) for m in response.context['messages']]
        assert any('unexpected error' in m for m in messages)
        assert not any('secret internal detail' in m for m in messages)

    def test_upload_pdf_without_text_warns(self, auth_client, mock_groq):
        response = auth_client.post(
            reverse('papers:upload'),
            {'title': 'Blank', 'file': make_upload(content=make_pdf_bytes(text=''))},
            follow=True,
        )
        assert Paper.objects.count() == 1
        mock_groq.chat.completions.create.assert_not_called()
        assert any('no text' in str(m) for m in response.context['messages'])

    def test_rejects_non_pdf(self, auth_client, mock_groq):
        response = auth_client.post(
            reverse('papers:upload'),
            {'title': 'Fake', 'file': make_upload(content=b'<html>not a pdf</html>')},
        )
        assert response.status_code == 200
        assert 'file' in response.context['form'].errors
        assert not Paper.objects.exists()

    def test_malformed_tags_json_is_ignored(self, auth_client, mock_groq):
        auth_client.post(
            reverse('papers:upload'),
            {'title': 'T', 'file': make_upload(), 'tags_json': '{not json'},
        )
        assert Paper.objects.get().tags.count() == 0


class TestOwnership:
    """A user must never see or act on another user's papers."""

    @pytest.mark.parametrize('name', ['papers:detail', 'papers:delete', 'papers:download'])
    def test_other_users_paper_is_404(self, client, other_user, paper, name):
        client.force_login(other_user)
        assert client.get(reverse(name, args=[paper.pk])).status_code == 404

    def test_other_user_cannot_resummarize(self, client, other_user, paper, mock_groq):
        client.force_login(other_user)
        assert client.post(reverse('papers:summarize', args=[paper.pk])).status_code == 404
        mock_groq.chat.completions.create.assert_not_called()

    def test_other_user_cannot_delete(self, client, other_user, paper):
        client.force_login(other_user)
        client.post(reverse('papers:delete', args=[paper.pk]))
        assert Paper.objects.filter(pk=paper.pk).exists()

    def test_list_only_shows_own_papers(self, client, other_user, paper):
        Paper.objects.create(
            title='Mallory paper', file=make_upload(), uploaded_by=other_user, file_size=1
        )
        client.force_login(other_user)
        titles = [p.title for p in client.get(reverse('papers:list')).context['papers']]
        assert titles == ['Mallory paper']


class TestPaperViews:
    def test_list_search(self, auth_client, paper, user):
        Paper.objects.create(title='Other topic', file=make_upload(), uploaded_by=user)
        response = auth_client.get(reverse('papers:list'), {'query': 'attention'})
        assert [p.title for p in response.context['papers']] == [paper.title]

    def test_by_tag_filters_and_supports_unicode_slugs(self, auth_client, paper):
        tag = Tag.get_or_create_by_name('Нейросети')
        paper.tags.add(tag)
        response = auth_client.get(reverse('papers:by_tag', args=[tag.slug]))
        assert response.status_code == 200
        assert list(response.context['papers']) == [paper]

    def test_detail_renders(self, auth_client, paper, summary):
        response = auth_client.get(reverse('papers:detail', args=[paper.pk]))
        assert response.status_code == 200
        assert reverse('papers:download', args=[paper.pk]) in response.content.decode()

    def test_download_streams_pdf_to_owner(self, auth_client, paper):
        response = auth_client.get(reverse('papers:download', args=[paper.pk]))
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/pdf'
        assert b''.join(response.streaming_content).startswith(b'%PDF-')

    def test_download_missing_file_is_404(self, auth_client, paper):
        Path(paper.file.path).unlink()
        assert auth_client.get(reverse('papers:download', args=[paper.pk])).status_code == 404

    def test_resummarize_requires_post(self, auth_client, paper, mock_groq):
        response = auth_client.get(reverse('papers:summarize', args=[paper.pk]))
        assert response.status_code == 405
        mock_groq.chat.completions.create.assert_not_called()

    def test_resummarize(self, auth_client, paper, mock_groq):
        response = auth_client.post(reverse('papers:summarize', args=[paper.pk]))
        assert response.status_code == 302
        paper.refresh_from_db()
        assert paper.processed is True

    def test_resummarize_when_file_missing(self, auth_client, paper, mock_groq):
        Path(paper.file.path).unlink()
        response = auth_client.post(reverse('papers:summarize', args=[paper.pk]), follow=True)
        assert any('No text' in str(m) for m in response.context['messages'])
        mock_groq.chat.completions.create.assert_not_called()

    def test_delete_removes_row_and_file(
        self, auth_client, paper, django_capture_on_commit_callbacks
    ):
        path = Path(paper.file.path)
        assert path.exists()
        with django_capture_on_commit_callbacks(execute=True):
            response = auth_client.post(reverse('papers:delete', args=[paper.pk]))
        assert response.status_code == 302
        assert not Paper.objects.exists()
        assert not path.exists()


class TestTagModel:
    def test_case_insensitive_dedupe(self):
        a = Tag.get_or_create_by_name('Deep Learning')
        b = Tag.get_or_create_by_name('deep learning ')
        assert a.pk == b.pk
        assert Tag.objects.count() == 1

    def test_unsluggable_name_is_skipped(self):
        assert Tag.get_or_create_by_name('!!!') is None

    def test_truncates_long_names(self):
        assert len(Tag.get_or_create_by_name('x' * 80).name) == 50

    def test_existing_name_with_custom_slug(self):
        Tag.objects.create(name='NLP', slug='natural-language')
        assert Tag.get_or_create_by_name('NLP').slug == 'natural-language'


class TestPaperModel:
    def test_file_size_display(self, paper):
        paper.file_size = 2048
        assert paper.file_size_display == '2.0 KB'
        paper.file_size = 5 * 1024**4
        assert paper.file_size_display == '5.0 TB'

    def test_has_summary_and_filename(self, paper, summary):
        assert paper.has_summary()
        assert paper.filename.endswith('.pdf')
        assert str(paper) == paper.title
