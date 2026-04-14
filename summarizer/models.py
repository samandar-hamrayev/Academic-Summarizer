import json
from django.db import models
from papers.models import Paper


class Summary(models.Model):
    paper = models.OneToOneField(
        Paper, on_delete=models.CASCADE, related_name='summary'
    )
    abstract = models.TextField(blank=True)
    key_points = models.TextField(
        blank=True,
        help_text='Stored as JSON list of strings'
    )
    methodology = models.TextField(blank=True)
    results = models.TextField(blank=True)
    conclusion = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Summary'
        verbose_name_plural = 'Summaries'

    def __str__(self):
        return f'Summary of: {self.paper.title}'

    def get_key_points_list(self) -> list[str]:
        """Return key_points as a Python list."""
        if not self.key_points:
            return []
        try:
            data = json.loads(self.key_points)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_key_points_list(self, points: list[str]) -> None:
        """Store a list of key points as JSON."""
        self.key_points = json.dumps(points)
