from django.contrib import admin
from .models import ShareLink, Summary


@admin.register(Summary)
class SummaryAdmin(admin.ModelAdmin):
    list_display  = ('paper', 'language', 'created_at', 'updated_at')
    list_filter   = ('language', 'created_at')
    search_fields = ('paper__title', 'paper__author')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)

    fieldsets = (
        ('Paper',           {'fields': ('paper',)}),
        ('Summary Content', {'fields': ('abstract', 'key_points', 'methodology', 'results', 'conclusion', 'citations')}),
        ('Metadata',        {'fields': ('language', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


@admin.register(ShareLink)
class ShareLinkAdmin(admin.ModelAdmin):
    list_display  = ('summary', 'token', 'is_active', 'access_count', 'created_at', 'expires_at')
    list_filter   = ('is_active',)
    readonly_fields = ('token', 'created_at', 'access_count')
    search_fields = ('summary__paper__title',)
    ordering = ('-created_at',)
