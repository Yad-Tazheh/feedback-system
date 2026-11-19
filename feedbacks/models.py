from django.db import models


class Conversation(models.Model):
    TYPE_CHOICES = [
        ('request', 'درخواست'),
        ('criticism', 'انتقاد'),
        ('suggestion', 'پیشنهاد'),
    ]

    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_type_display()}: {self.title}"

    def as_messages(self):
        return [
            {'role': msg.role, 'content': msg.content}
            for msg in self.messages.exclude(ai_status='failed')
        ]


class Message(models.Model):
    class Role(models.TextChoices):
        USER = 'user', 'کاربر'
        ASSISTANT = 'assistant', 'دستیار'

    class AIStatus(models.TextChoices):
        OK = 'ok', 'موفق'
        FAILED = 'failed', 'ناموفق'

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    ai_model = models.CharField(max_length=100, blank=True, default='')
    prompt_tokens = models.PositiveIntegerField(null=True, blank=True)
    completion_tokens = models.PositiveIntegerField(null=True, blank=True)
    cached_tokens = models.PositiveIntegerField(null=True, blank=True)
    total_tokens = models.PositiveIntegerField(null=True, blank=True)
    ai_status = models.CharField(
        max_length=20,
        choices=AIStatus.choices,
        null=True,
        blank=True,
    )
    ai_error = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['created_at', 'id']
        indexes = [
            models.Index(
                fields=['conversation', 'created_at'],
                name='msg_conv_created_idx',
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role='assistant') | models.Q(
                    role='user',
                    prompt_tokens__isnull=True,
                    completion_tokens__isnull=True,
                    cached_tokens__isnull=True,
                    total_tokens__isnull=True,
                ),
                name='user_message_token_fields_null',
            ),
        ]

    def __str__(self):
        return f"{self.get_role_display()}: {self.content[:30]}"
