from django.contrib.auth.models import User
from django.db import IntegrityError, models
from django.utils.text import slugify


def paper_upload_path(instance, filename):
    return f'papers/user_{instance.uploaded_by.id}/{filename}'


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True, blank=True, allow_unicode=True)
    color = models.CharField(max_length=7, default='#4361ee')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)

    @classmethod
    def get_or_create_by_name(cls, name: str) -> 'Tag | None':
        """
        Return the tag matching ``name`` by slug, creating it if needed.

        Matching on the slug (not the raw name) means "Deep Learning" and
        "deep learning" resolve to one tag instead of violating the unique
        slug constraint. Unicode is kept so Russian/Uzbek tags get real slugs.
        """
        name = name.strip()[:50]
        slug = slugify(name, allow_unicode=True)
        if not slug:
            return None
        try:
            tag, _ = cls.objects.get_or_create(slug=slug, defaults={'name': name})
        except IntegrityError:
            # Same name already stored under a different (hand-edited) slug.
            tag = cls.objects.get(name=name)
        return tag


class Paper(models.Model):
    title = models.CharField(max_length=500)
    author = models.CharField(max_length=300, blank=True)
    file = models.FileField(upload_to=paper_upload_path)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='papers')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    file_size = models.PositiveIntegerField(default=0, help_text='Size in bytes')
    tags = models.ManyToManyField(Tag, blank=True, related_name='papers')

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
