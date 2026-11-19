from django.contrib import admin
from .models import Feedback


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'type',
        'ai_status',
        'total_tokens',
        'created_at',
    )
    list_filter = ('type', 'ai_status')
    search_fields = ('title', 'text')
