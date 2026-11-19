from django.contrib import admin
from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = (
        'role',
        'content',
        'ai_model',
        'ai_status',
        'prompt_tokens',
        'completion_tokens',
        'cached_tokens',
        'total_tokens',
        'ai_error',
        'created_at',
    )
    readonly_fields = (
        'ai_model',
        'ai_status',
        'prompt_tokens',
        'completion_tokens',
        'cached_tokens',
        'total_tokens',
        'ai_error',
        'created_at',
    )


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'type',
        'owner',
        'created_at',
        'updated_at',
    )
    list_filter = ('owner', 'type')
    search_fields = ('title', 'owner__username')
    list_select_related = ('owner',)
    inlines = [MessageInline]
