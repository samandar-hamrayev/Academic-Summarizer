import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from papers.services import extract_text_from_pdf, validate_pdf_upload

from .exports import DOCX_CONTENT_TYPE, build_summary_docx, build_summary_pdf, export_filename
from .models import ShareLink, Summary
from .services import extract_tags_from_text

MAX_SHARE_EXPIRY_DAYS = 365

logger = logging.getLogger(__name__)


# ── AI Tag Preview ────────────────────────────────────────────────────────────


@login_required
@require_POST
def preview_tags(request):
    """
    AJAX endpoint: extract AI-suggested tags from an uploaded PDF without saving it.
    Called by the upload form before submission so the user can confirm/edit tags.
    """
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file provided'}, status=400)

    pdf_file = request.FILES['file']
    error = validate_pdf_upload(pdf_file)
    if error:
        return JsonResponse({'error': error}, status=400)

    text = extract_text_from_pdf(pdf_file)
    if len(text.strip()) < 100:
        return JsonResponse({'suggested_tags': [], 'warning': 'Not enough readable text in PDF'})

    suggested_tags = extract_tags_from_text(text, max_tags=5)
    return JsonResponse({'suggested_tags': suggested_tags})


# ── Summary Views ─────────────────────────────────────────────────────────────


class SummaryHistoryView(LoginRequiredMixin, ListView):
    model = Summary
    template_name = 'summarizer/history.html'
    context_object_name = 'summaries'
    paginate_by = 15

    def get_queryset(self):
        return (
            Summary.objects.filter(paper__uploaded_by=self.request.user)
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
        ctx['citations'] = self.object.get_citations_list()
        ctx['share_links'] = self.object.share_links.filter(is_active=True).order_by('-created_at')
        return ctx


# ---- Share Links ---------------------------------------------------------


def _parse_expiry_days(raw) -> int:
    """Parse the share-link lifetime; 0 means never expires. Invalid -> 7 days."""
    try:
        days = int(raw)
    except (TypeError, ValueError):
        return 7
    return max(0, min(days, MAX_SHARE_EXPIRY_DAYS))


@login_required
@require_POST
def create_share_link(request, pk):
    """Create a new share link for a summary."""
    summary = get_object_or_404(Summary, pk=pk, paper__uploaded_by=request.user)

    expiry_days = _parse_expiry_days(request.POST.get('expiry_days', 7))
    expires_at = timezone.now() + timedelta(days=expiry_days) if expiry_days else None

    ShareLink.objects.create(summary=summary, expires_at=expires_at)
    messages.success(request, 'Share link created successfully.')
    return redirect('summarizer:detail', pk=pk)


@login_required
@require_POST
def revoke_share_link(request, link_pk):
    """Deactivate a share link."""
    link = get_object_or_404(ShareLink, pk=link_pk, summary__paper__uploaded_by=request.user)
    link.is_active = False
    link.save(update_fields=['is_active'])
    messages.success(request, 'Share link revoked.')
    return redirect('summarizer:detail', pk=link.summary_id)


def shared_summary_view(request, token):
    """Public view of a shared summary — no login required."""
    link = get_object_or_404(ShareLink.objects.select_related('summary__paper'), token=token)

    if not link.is_valid():
        return render(request, 'summarizer/share_expired.html', status=410)

    # Atomic increment so concurrent views don't lose counts.
    ShareLink.objects.filter(pk=link.pk).update(access_count=F('access_count') + 1)
    link.refresh_from_db(fields=['access_count'])

    summary = link.summary
    return render(
        request,
        'summarizer/shared_summary.html',
        {
            'summary': summary,
            'key_points': summary.get_key_points_list(),
            'citations': summary.get_citations_list(),
            'link': link,
        },
    )


# ---- PDF / Word exports --------------------------------------------------


def _export(request, pk, builder, extension: str, content_type: str) -> HttpResponse:
    summary = get_object_or_404(
        Summary.objects.select_related('paper'), pk=pk, paper__uploaded_by=request.user
    )
    try:
        payload = builder(summary)
    except Exception:
        logger.exception('%s export failed for summary %s', extension.upper(), pk)
        return HttpResponse('Export failed. Please try again later.', status=500)

    response = HttpResponse(payload, content_type=content_type)
    response['Content-Disposition'] = content_disposition_header(
        as_attachment=True, filename=export_filename(summary, extension)
    )
    return response


@login_required
def export_summary_pdf(request, pk):
    return _export(request, pk, build_summary_pdf, 'pdf', 'application/pdf')


@login_required
def export_summary_word(request, pk):
    return _export(request, pk, build_summary_docx, 'docx', DOCX_CONTENT_TYPE)
