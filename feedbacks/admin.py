from django.contrib import admin
from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = (
        'role',
        'author',
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
        'status',
        'owner',
        'expert',
        'created_at',
        'updated_at',
    )
    list_filter = ('status', 'expert', 'owner', 'type')
    search_fields = ('title', 'owner__username', 'expert__username')
    list_select_related = ('owner', 'expert')
    actions = ['close_selected']
    inlines = [MessageInline]

    @admin.action(description="بستن گفتگوهای انتخاب‌شده")
    def close_selected(self, request, queryset):
        count = 0
        for conv in queryset:
            if conv.status != Conversation.Status.CLOSED:
                conv.transition_to(Conversation.Status.CLOSED, request.user)
                count += 1
        self.message_user(request, f"{count} گفتگو با موفقیت بسته شد.")
