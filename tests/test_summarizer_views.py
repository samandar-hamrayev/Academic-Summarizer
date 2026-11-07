from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from summarizer.models import ShareLink
from tests.conftest import completion, make_pdf_bytes, make_upload

pytestmark = pytest.mark.django_db

DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'


class TestSummaryPages:
    def test_history_lists_own_summaries(self, auth_client, summary):
        response = auth_client.get(reverse('summarizer:history'))
        assert list(response.context['summaries']) == [summary]

    def test_history_hides_other_users(self, client, other_user, summary):
        client.force_login(other_user)
        assert list(client.get(reverse('summarizer:history')).context['summaries']) == []

    def test_detail(self, auth_client, summary):
        response = auth_client.get(reverse('summarizer:detail', args=[summary.pk]))
        assert response.status_code == 200
        assert response.context['key_points'] == summary.get_key_points_list()

    @pytest.mark.parametrize(
        'name',
        ['summarizer:detail', 'summarizer:export_pdf', 'summarizer:export_word'],
    )
    def test_other_user_gets_404(self, client, other_user, summary, name):
        client.force_login(other_user)
        assert client.get(reverse(name, args=[summary.pk])).status_code == 404


class TestExports:
    def test_pdf_export(self, auth_client, summary):
        response = auth_client.get(reverse('summarizer:export_pdf', args=[summary.pk]))
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/pdf'
        assert response.content.startswith(b'%PDF-')
        assert 'attachment' in response['Content-Disposition']
        assert 'summary_attention-is-all-you-need.pdf' in response['Content-Disposition']

    def test_word_export(self, auth_client, summary):
        response = auth_client.get(reverse('summarizer:export_word', args=[summary.pk]))
        assert response.status_code == 200
        assert response['Content-Type'] == DOCX
        assert response.content.startswith(b'PK')  # docx is a zip archive

    def test_export_failure_returns_generic_500(self, auth_client, summary, monkeypatch):
        def boom(_summary):
            raise RuntimeError('internal detail')

        monkeypatch.setattr('summarizer.views.build_summary_pdf', boom)
        response = auth_client.get(reverse('summarizer:export_pdf', args=[summary.pk]))
        assert response.status_code == 500
        assert b'internal detail' not in response.content

    def test_unicode_title_filename(self, auth_client, summary):
        summary.paper.title = 'Нейронные сети'
        summary.paper.save()
        response = auth_client.get(reverse('summarizer:export_word', args=[summary.pk]))
        assert "filename*=utf-8''" in response['Content-Disposition']


class TestShareLinks:
    def test_create_with_expiry(self, auth_client, summary):
        auth_client.post(reverse('summarizer:create_share', args=[summary.pk]), {'expiry_days': 30})
        link = ShareLink.objects.get()
        assert timedelta(days=29) < link.expires_at - timezone.now() <= timedelta(days=30)

    def test_create_never_expires(self, auth_client, summary):
        auth_client.post(reverse('summarizer:create_share', args=[summary.pk]), {'expiry_days': 0})
        assert ShareLink.objects.get().expires_at is None

    @pytest.mark.parametrize(('raw', 'days'), [('abc', 7), ('-5', 0), ('99999', 365)])
    def test_invalid_expiry_is_sanitised(self, auth_client, summary, raw, days):
        response = auth_client.post(
            reverse('summarizer:create_share', args=[summary.pk]), {'expiry_days': raw}
        )
        assert response.status_code == 302
        link = ShareLink.objects.get()
        if days == 0:
            assert link.expires_at is None
        else:
            delta = link.expires_at - timezone.now()
            assert timedelta(days=days - 1) < delta <= timedelta(days=days)

    def test_create_requires_post(self, auth_client, summary):
        response = auth_client.get(reverse('summarizer:create_share', args=[summary.pk]))
        assert response.status_code == 405

    def test_cannot_share_other_users_summary(self, client, other_user, summary):
        client.force_login(other_user)
        response = client.post(reverse('summarizer:create_share', args=[summary.pk]))
        assert response.status_code == 404
        assert not ShareLink.objects.exists()

    def test_public_view_counts_access(self, client, summary):
        link = ShareLink.objects.create(summary=summary)
        url = reverse('summarizer:shared', args=[link.token])
        assert client.get(url).status_code == 200
        client.get(url)
        link.refresh_from_db()
        assert link.access_count == 2

    def test_expired_link_returns_410(self, client, summary):
        link = ShareLink.objects.create(
            summary=summary, expires_at=timezone.now() - timedelta(minutes=1)
        )
        assert client.get(reverse('summarizer:shared', args=[link.token])).status_code == 410

    def test_revoke(self, auth_client, summary):
        link = ShareLink.objects.create(summary=summary)
        assert (
            auth_client.get(reverse('summarizer:revoke_share', args=[link.pk])).status_code == 405
        )
        auth_client.post(reverse('summarizer:revoke_share', args=[link.pk]))
        link.refresh_from_db()
        assert link.is_active is False
        assert auth_client.get(link.get_absolute_url()).status_code == 410

    def test_other_user_cannot_revoke(self, client, other_user, summary):
        link = ShareLink.objects.create(summary=summary)
        client.force_login(other_user)
        assert client.post(reverse('summarizer:revoke_share', args=[link.pk])).status_code == 404
        link.refresh_from_db()
        assert link.is_active is True


class TestPreviewTags:
    URL = reverse('summarizer:preview_tags')

    def test_requires_login(self, client):
        assert client.post(self.URL).status_code == 302

    def test_requires_file(self, auth_client):
        assert auth_client.post(self.URL).status_code == 400

    def test_rejects_non_pdf(self, auth_client):
        response = auth_client.post(self.URL, {'file': make_upload('x.pdf', b'not a pdf')})
        assert response.status_code == 400

    def test_short_text_returns_warning(self, auth_client, mock_groq):
        upload = make_upload(content=make_pdf_bytes('tiny'))
        data = auth_client.post(self.URL, {'file': upload}).json()
        assert data['suggested_tags'] == []
        assert 'warning' in data
        mock_groq.chat.completions.create.assert_not_called()

    def test_returns_suggested_tags(self, auth_client, mock_groq):
        mock_groq.chat.completions.create.return_value = completion('["NLP", "Attention"]')
        data = auth_client.post(self.URL, {'file': make_upload()}).json()
        assert data == {'suggested_tags': ['NLP', 'Attention']}
