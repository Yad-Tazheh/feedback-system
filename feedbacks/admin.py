from django.contrib import admin
from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ('role', 'content', 'ai_status', 'total_tokens', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'type',
        'created_at',
        'updated_at',
    )
    list_filter = ('type', 'messages__ai_status')
    search_fields = ('title', 'messages__content')
    inlines = [MessageInline]
