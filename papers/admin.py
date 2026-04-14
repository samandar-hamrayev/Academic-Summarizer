from django.contrib import admin
from .models import Paper


@admin.register(Paper)
class PaperAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'uploaded_by', 'uploaded_at', 'processed', 'file_size_display')
    list_filter = ('processed', 'uploaded_at')
    search_fields = ('title', 'author', 'uploaded_by__username')
    readonly_fields = ('uploaded_at', 'file_size')
    ordering = ('-uploaded_at',)

    def file_size_display(self, obj):
        return obj.file_size_display
    file_size_display.short_description = 'File Size'
