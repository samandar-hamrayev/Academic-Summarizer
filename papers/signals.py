"""Keep uploaded files in sync with Paper rows."""

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Paper


@receiver(post_delete, sender=Paper, dispatch_uid='papers_delete_pdf_file')
def delete_pdf_file(sender, instance: Paper, **kwargs) -> None:
    """Remove the stored PDF once the deleting transaction commits.

    Covers the delete view, the admin and cascades (e.g. deleting a user),
    so orphaned uploads don't accumulate on disk.
    """
    if not instance.file:
        return
    storage, name = instance.file.storage, instance.file.name
    transaction.on_commit(lambda: storage.delete(name))
