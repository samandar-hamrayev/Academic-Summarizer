"""
Project-level views — currently just the smart home page.

Anonymous visitors see the marketing landing (existing home.html content).
Authenticated users see a personal dashboard: stats, charts, tag cloud,
recent activity. Both branches render from the same template so the
nav/footer/i18n machinery stays identical.
"""
from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from papers.models import Paper, Tag
from summarizer.models import ChatMessage, Summary


# Tier thresholds for tag-cloud font sizing (ratio of tag count / max count)
_CLOUD_TIERS = (
    (0.80, 5),
    (0.60, 4),
    (0.40, 3),
    (0.20, 2),
)


def _tag_tier(count: int, max_count: int) -> int:
    if max_count <= 0:
        return 1
    ratio = count / max_count
    for threshold, tier in _CLOUD_TIERS:
        if ratio >= threshold:
            return tier
    return 1


def _build_dashboard_context(user) -> dict:
    """Build all the data the dashboard template needs in as few queries
    as practical. Per-user library is small (tens to low hundreds of
    papers), so we lean on simple aggregations rather than caching."""
    papers_qs = Paper.objects.filter(uploaded_by=user)

    total_papers = papers_qs.count()
    total_summaries = Summary.objects.filter(paper__uploaded_by=user).count()

    # Tags this user has actually applied
    tag_qs = (
        Tag.objects
        .filter(papers__uploaded_by=user)
        .annotate(c=Count('papers', filter=Q(papers__uploaded_by=user)))
        .order_by('-c', 'name')
    )
    tag_rows = list(tag_qs.values('id', 'name', 'slug', 'c'))
    unique_tags = len(tag_rows)

    # Active days: union of distinct upload days + distinct chat days.
    # .order_by() clears Paper.Meta.ordering so it doesn't leak into the
    # SELECT and break distinct.
    active_dates = set()
    for row in (papers_qs
                .annotate(d=TruncDate('uploaded_at'))
                .order_by()
                .values_list('d', flat=True).distinct()):
        if row is not None:
            active_dates.add(row)
    for row in (ChatMessage.objects
                .filter(user=user)
                .annotate(d=TruncDate('created_at'))
                .order_by()
                .values_list('d', flat=True).distinct()):
        if row is not None:
            active_dates.add(row)
    active_days = len(active_dates)

    # Languages covered (distinct paper languages, e.g. ['en','uz']).
    # Same .order_by() trick — without it, the default '-uploaded_at'
    # ordering joins into the SELECT and distinct() yields duplicates.
    languages_covered = sorted(
        code for code in
        papers_qs.order_by().values_list('language', flat=True).distinct()
        if code
    )

    # ── Chart 1 — activity over last 30 calendar days ──────────────────
    today = timezone.localdate()
    start = today - timedelta(days=29)
    per_day = (
        papers_qs
        .filter(uploaded_at__date__gte=start)
        .annotate(d=TruncDate('uploaded_at'))
        .values('d')
        .annotate(c=Count('id'))
    )
    day_counts = {row['d'].isoformat(): row['c'] for row in per_day if row['d']}
    activity_30d = []
    for i in range(30):
        iso = (start + timedelta(days=i)).isoformat()
        activity_30d.append({'date': iso, 'count': day_counts.get(iso, 0)})

    # ── Chart 2 — language distribution ────────────────────────────────
    raw_lang = dict(
        papers_qs.values('language').annotate(c=Count('id'))
        .values_list('language', 'c')
    )
    language_distribution = {
        'en': raw_lang.get('en', 0),
        'ru': raw_lang.get('ru', 0),
        'uz': raw_lang.get('uz', 0),
    }

    # ── Chart 3 — top 5 tags ───────────────────────────────────────────
    top_tags = tag_rows[:5]

    # ── Tag cloud (all tags, sized by frequency) ───────────────────────
    max_tag_count = tag_rows[0]['c'] if tag_rows else 0
    for row in tag_rows:
        row['tier'] = _tag_tier(row['c'], max_tag_count)
    tag_cloud = tag_rows

    # ── Recent activity (last 7 papers) ────────────────────────────────
    recent_papers = list(
        papers_qs
        .select_related('summary')
        .order_by('-uploaded_at')[:7]
    )

    # Chart data for JSON serialization (json_script handles escaping)
    chart_data = {
        'activity_30d': activity_30d,
        'language_distribution': language_distribution,
        'top_tags': [{'name': t['name'], 'count': t['c']} for t in top_tags],
    }

    return {
        'is_dashboard': True,
        'dashboard_today': today,
        'stats': {
            'total_papers':           total_papers,
            'total_summaries':        total_summaries,
            'unique_tags':            unique_tags,
            'reading_minutes_saved':  total_papers * 30,
            'languages_covered':      languages_covered,
            'active_days':            active_days,
        },
        'tag_cloud':     tag_cloud,
        'recent_papers': recent_papers,
        'chart_data':    chart_data,
    }


def home(request):
    """Marketing landing for anon; personal dashboard for authenticated users."""
    if request.user.is_authenticated:
        ctx = _build_dashboard_context(request.user)
    else:
        ctx = {'is_dashboard': False}
    return render(request, 'home.html', ctx)
