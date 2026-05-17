from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify


def paper_upload_path(instance, filename):
    return f'papers/user_{instance.uploaded_by.id}/{filename}'


class Tag(models.Model):
    name  = models.CharField(max_length=50, unique=True)
    slug  = models.SlugField(unique=True, blank=True)
    color = models.CharField(max_length=7, default='#4361ee')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Paper(models.Model):
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('ru', 'Russian'),
        ('uz', "Uzbek (Lotin)"),
    ]

    title       = models.CharField(max_length=500)
    author      = models.CharField(max_length=300, blank=True)
    file        = models.FileField(upload_to=paper_upload_path)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='papers')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed   = models.BooleanField(default=False)
    file_size   = models.PositiveIntegerField(default=0, help_text='Size in bytes')
    tags        = models.ManyToManyField(Tag, blank=True, related_name='papers')
    language    = models.CharField(
        max_length=5, choices=LANGUAGE_CHOICES, default='en',
        help_text='Detected (or user-overridden) language of the paper text. '
                  'Summaries and chat replies are generated in this language.',
    )
    language_confidence = models.FloatField(
        default=0.0,
        help_text='Detector confidence 0.0–1.0. 0.0 means user-provided or unknown.',
    )

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
