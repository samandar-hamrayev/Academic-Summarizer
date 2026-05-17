import json
import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from papers.models import Paper


class Summary(models.Model):
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('ru', 'Russian'),
        ('uz', 'Uzbek'),
    ]

    paper       = models.OneToOneField(Paper, on_delete=models.CASCADE, related_name='summary')
    abstract    = models.TextField(blank=True)
    key_points  = models.TextField(blank=True, help_text='Stored as JSON list of strings')
    methodology = models.TextField(blank=True)
    results     = models.TextField(blank=True)
    conclusion  = models.TextField(blank=True)
    citations   = models.TextField(blank=True, help_text='Stored as JSON list of citation strings')
    language    = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default='en')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Summary'
        verbose_name_plural = 'Summaries'

    def __str__(self):
        return f'Summary of: {self.paper.title}'

    def get_key_points_list(self) -> list[str]:
        if not self.key_points:
            return []
        try:
            data = json.loads(self.key_points)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_key_points_list(self, points: list[str]) -> None:
        self.key_points = json.dumps(points)

    def get_citations_list(self) -> list[str]:
        if not self.citations:
            return []
        try:
            data = json.loads(self.citations)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_citations_list(self, items: list[str]) -> None:
        self.citations = json.dumps(items)

    def get_language_display_short(self) -> str:
        flags = {'en': '🇬🇧', 'ru': '🇷🇺', 'uz': '🇺🇿'}
        names = {'en': 'English', 'ru': 'Russian', 'uz': 'Uzbek'}
        return f"{flags.get(self.language, '')} {names.get(self.language, self.language)}"


class ShareLink(models.Model):
    summary      = models.ForeignKey(Summary, on_delete=models.CASCADE, related_name='share_links')
    token        = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at   = models.DateTimeField(auto_now_add=True)
    expires_at   = models.DateTimeField(null=True, blank=True)
    access_count = models.PositiveIntegerField(default=0)
    is_active    = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Share link for "{self.summary.paper.title}"'

    def is_valid(self) -> bool:
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True

    def get_absolute_url(self) -> str:
        return reverse('summarizer:shared', kwargs={'token': str(self.token)})


class ChatMessage(models.Model):
    ROLE_CHOICES = [
        ('user',      'User'),
        ('assistant', 'Assistant'),
    ]

    paper      = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='chat_messages')
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_messages')
    role       = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content    = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes  = [models.Index(fields=['paper', 'user', 'created_at'])]

    def __str__(self):
        return f'{self.role} @ paper #{self.paper_id} ({self.created_at:%Y-%m-%d %H:%M})'
