from django.db import models
from django.contrib.auth.models import User


def paper_upload_path(instance, filename):
    return f'papers/user_{instance.uploaded_by.id}/{filename}'


class Paper(models.Model):
    title = models.CharField(max_length=500)
    author = models.CharField(max_length=300, blank=True)
    file = models.FileField(upload_to=paper_upload_path)
    uploaded_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='papers'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    file_size = models.PositiveIntegerField(default=0, help_text='Size in bytes')

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Paper'
        verbose_name_plural = 'Papers'

    def __str__(self):
        return self.title

    @property
    def filename(self):
        return self.file.name.split('/')[-1]

    @property
    def file_size_display(self):
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f'{size:.1f} {unit}'
            size /= 1024
        return f'{size:.1f} TB'

    def has_summary(self):
        return hasattr(self, 'summary')
