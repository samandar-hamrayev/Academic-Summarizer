import json
import logging

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView

from summarizer.services import SummarizationError, summarize_paper_task

from .forms import PaperSearchForm, PaperUploadForm, UserRegistrationForm
from .models import Paper, Tag
from .services import extract_text_from_pdf

logger = logging.getLogger(__name__)


class PaperListView(LoginRequiredMixin, ListView):
    model = Paper
    template_name = 'papers/list.html'
    context_object_name = 'papers'
    paginate_by = 12

    def get_queryset(self):
        queryset = (
            Paper.objects.filter(uploaded_by=self.request.user)
            .select_related('uploaded_by')
            .prefetch_related('tags')
        )
        query = self.request.GET.get('query', '').strip()
        if query:
            queryset = queryset.filter(Q(title__icontains=query) | Q(author__icontains=query))
        return queryset

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search_form'] = PaperSearchForm(self.request.GET)
        ctx['query'] = self.request.GET.get('query', '')
        return ctx


@login_required
def papers_by_tag(request, tag_slug):
    """Filter the paper list by a specific tag."""
    tag = get_object_or_404(Tag, slug=tag_slug)
    queryset = (
        Paper.objects.filter(tags=tag, uploaded_by=request.user)
        .select_related('uploaded_by')
        .prefetch_related('tags')
    )
    query = request.GET.get('query', '').strip()
    if query:
        queryset = queryset.filter(Q(title__icontains=query) | Q(author__icontains=query))
    paginator = Paginator(queryset, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(
        request,
        'papers/list.html',
        {
            'papers': page_obj.object_list,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'search_form': PaperSearchForm(request.GET),
            'query': query,
            'filter_tag': tag,
        },
    )


class PaperUploadView(LoginRequiredMixin, CreateView):
    model = Paper
    form_class = PaperUploadForm
    template_name = 'papers/upload.html'

    def form_valid(self, form):
        paper = form.save(commit=False)
        paper.uploaded_by = self.request.user
        paper.file_size = form.cleaned_data['file'].size
        paper.save()

        # Attach AI-suggested + user-confirmed tags
        tags_raw = self.request.POST.get('tags_json', '[]')
        try:
            tag_names = json.loads(tags_raw)
        except (json.JSONDecodeError, ValueError):
            tag_names = []  # Malformed input — skip tags silently
        if isinstance(tag_names, list):
            for name in tag_names[:10]:
                tag = Tag.get_or_create_by_name(str(name))
                if tag:
                    paper.tags.add(tag)

        # Extract text and trigger summarization
        text = extract_text_from_pdf(form.cleaned_data['file'])
        if not text.strip():
            messages.warning(
                self.request,
                f'"{paper.title}" uploaded, but no text could be extracted from the PDF.',
            )
        elif _run_summarization(self.request, paper, text):
            messages.success(self.request, f'"{paper.title}" uploaded and summarized successfully!')

        return redirect('papers:detail', pk=paper.pk)


def _run_summarization(request, paper, text: str) -> bool:
    """Summarize a paper, reporting failures as user-friendly flash messages."""
    try:
        summarize_paper_task(paper, text)
    except SummarizationError as exc:
        logger.warning('Summarization failed for paper %s: %s', paper.pk, exc)
        messages.error(request, f'Summarization failed: {exc}')
        return False
    except Exception:
        logger.exception('Unexpected error summarizing paper %s', paper.pk)
        messages.error(request, 'Summarization failed due to an unexpected error.')
        return False
    return True


class PaperDetailView(LoginRequiredMixin, DetailView):
    model = Paper
    template_name = 'papers/detail.html'
    context_object_name = 'paper'

    def get_queryset(self):
        return Paper.objects.filter(uploaded_by=self.request.user)


class PaperDeleteView(LoginRequiredMixin, DeleteView):
    model = Paper
    success_url = reverse_lazy('papers:list')
    template_name = 'papers/confirm_delete.html'

    def get_queryset(self):
        return Paper.objects.filter(uploaded_by=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, 'Paper deleted successfully.')
        return super().form_valid(form)


@login_required
def download_paper(request, pk):
    """Serve the original PDF to its owner only (media files are not public)."""
    paper = get_object_or_404(Paper, pk=pk, uploaded_by=request.user)
    try:
        handle = paper.file.open('rb')
    except FileNotFoundError as exc:
        raise Http404('File not found.') from exc
    return FileResponse(handle, content_type='application/pdf', filename=paper.filename)


@login_required
@require_POST
def trigger_summarize(request, pk):
    """Re-run summarization for an existing paper."""
    paper = get_object_or_404(Paper, pk=pk, uploaded_by=request.user)
    try:
        with paper.file.open('rb') as handle:
            text = extract_text_from_pdf(handle)
    except FileNotFoundError:
        text = ''
    if not text.strip():
        messages.error(request, 'No text could be extracted from this PDF.')
    elif _run_summarization(request, paper, text):
        messages.success(request, 'Paper summarized successfully!')

    return redirect('papers:detail', pk=pk)


class RegisterView(FormView):
    template_name = 'registration/register.html'
    form_class = UserRegistrationForm
    success_url = reverse_lazy('papers:list')

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, f'Welcome, {user.username}! Your account has been created.')
        return super().form_valid(form)
