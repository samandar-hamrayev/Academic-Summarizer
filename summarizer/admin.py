from django.contrib import admin
from .models import Summary


@admin.register(Summary)
class SummaryAdmin(admin.ModelAdmin):
    list_display = ('paper', 'created_at', 'updated_at')
    list_select_related = ('paper',)
    search_fields = ('paper__title', 'paper__author')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)

    fieldsets = (
        ('Paper', {'fields': ('paper',)}),
        ('Summary Content', {
            'fields': ('abstract', 'key_points', 'methodology', 'results', 'conclusion')
        }),
        ('Metadata', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
