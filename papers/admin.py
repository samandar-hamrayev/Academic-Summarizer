from django.contrib import admin
from .models import Paper, Tag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display  = ('name', 'slug', 'color')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Paper)
class PaperAdmin(admin.ModelAdmin):
    list_display  = ('title', 'author', 'uploaded_by', 'uploaded_at', 'processed', 'file_size_display')
    list_filter   = ('processed', 'uploaded_at', 'tags')
    search_fields = ('title', 'author', 'uploaded_by__username')
    readonly_fields = ('uploaded_at', 'file_size')
    filter_horizontal = ('tags',)
    ordering = ('-uploaded_at',)

    def file_size_display(self, obj):
        return obj.file_size_display
    file_size_display.short_description = 'File Size'
