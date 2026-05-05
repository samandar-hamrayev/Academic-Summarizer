import json
import logging

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView, DeleteView, DetailView, FormView, ListView
)

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
            Paper.objects
            .filter(uploaded_by=self.request.user)
            .select_related('uploaded_by')
            .prefetch_related('tags')
        )
        query = self.request.GET.get('query', '').strip()
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) | Q(author__icontains=query)
            )
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
        Paper.objects
        .filter(tags=tag, uploaded_by=request.user)
        .select_related('uploaded_by')
        .prefetch_related('tags')
    )
    query = request.GET.get('query', '').strip()
    if query:
        queryset = queryset.filter(
            Q(title__icontains=query) | Q(author__icontains=query)
        )
    from django.core.paginator import Paginator
    paginator = Paginator(queryset, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'papers/list.html', {
        'papers': page_obj.object_list,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'search_form': PaperSearchForm(request.GET),
        'query': query,
        'filter_tag': tag,
    })


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
            if isinstance(tag_names, list):
                for name in tag_names[:10]:
                    name = str(name).strip()[:50]
                    if name:
                        tag, _ = Tag.objects.get_or_create(name=name)
                        paper.tags.add(tag)
        except (json.JSONDecodeError, ValueError):
            pass  # Malformed input — skip tags silently

        # Extract text and trigger summarization
        try:
            text = extract_text_from_pdf(paper.file)
            if text.strip():
                from summarizer.services import summarize_paper_task
                summarize_paper_task(paper, text)
                messages.success(
                    self.request,
                    f'"{paper.title}" uploaded and summarized successfully!'
                )
            else:
                messages.warning(
                    self.request,
                    f'"{paper.title}" uploaded, but no text could be extracted from the PDF.'
                )
        except Exception as exc:
            logger.error('Error processing paper %s: %s', paper.pk, exc)
            messages.error(
                self.request,
                f'"{paper.title}" uploaded, but summarization failed: {exc}'
            )

        return redirect('papers:detail', pk=paper.pk)


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
def trigger_summarize(request, pk):
    """Re-run summarization for an existing paper."""
    paper = get_object_or_404(Paper, pk=pk, uploaded_by=request.user)
    try:
        text = extract_text_from_pdf(paper.file)
        if not text.strip():
            messages.error(request, 'No text could be extracted from this PDF.')
            return redirect('papers:detail', pk=pk)

        from summarizer.services import summarize_paper_task
        summarize_paper_task(paper, text)
        messages.success(request, 'Paper summarized successfully!')
    except Exception as exc:
        logger.error('Re-summarization failed for paper %s: %s', pk, exc)
        messages.error(request, f'Summarization failed: {exc}')

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
