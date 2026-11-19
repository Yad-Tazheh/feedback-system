import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

EXPERT_MENTION_RE = re.compile(r'@expert\b', re.IGNORECASE)


def is_expert_mention(text):
    """True when a message starts with the '@expert' keyword (not '@experts', '@expertise', ...)."""
    return bool(EXPERT_MENTION_RE.match(text.strip()))


class ConversationQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(owner=user)

    def with_message_count(self):
        return self.annotate(message_count=models.Count('messages'))


class Conversation(models.Model):
    class Status(models.TextChoices):
        AI = 'ai', 'پاسخ هوش مصنوعی'
        WAITING_EXPERT = 'waiting_expert', 'در انتظار کارشناس'
        EXPERT_ACTIVE = 'expert_active', 'در حال پاسخگویی کارشناس'
        CLOSED = 'closed', 'بسته شده'

    TYPE_CHOICES = [
        ('request', 'درخواست'),
        ('criticism', 'انتقاد'),
        ('suggestion', 'پیشنهاد'),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversations',
        null=True,
        blank=True,
    )
    expert = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='assigned_conversations',
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AI,
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ConversationQuerySet.as_manager()

    class Meta:
        indexes = [
            models.Index(
                fields=['owner', '-created_at'],
                name='conv_owner_created_idx',
            ),
        ]

    def __str__(self):
        return f"{self.get_type_display()}: {self.title}"

    def get_context_prompt(self):
        return f"نوع پیام: {self.get_type_display()}\nعنوان: {self.title}"

    def as_messages(self):
        messages = []
        for msg in self.messages.exclude(ai_status='failed'):
            role = 'assistant' if msg.role == Message.Role.EXPERT else msg.role
            messages.append({'role': role, 'content': msg.content})
        return messages

    def transition_to(self, new_status, by_user, save=True):
        """
        State machine for conversation workflow:
        - ai -> waiting_expert (user requested human intervention or started message with @expert)
        - waiting_expert -> expert_active (expert claimed from queue; expert assigned)
        - expert_active -> ai (expert released back to AI; expert cleared)
        - any open state -> closed (closed by staff or assigned expert)
        Reject any other transition or unauthorized attempt with a ValidationError.
        """
        if not by_user or not by_user.is_authenticated:
            raise ValidationError("کاربر باید احراز هویت شده باشد.")

        from feedbacks.permissions import is_expert

        old_status, old_expert_id = self.status, self.expert_id

        # Closed is a terminal state
        if self.status == self.Status.CLOSED:
            raise ValidationError(
                f"گفتگوی بسته شده قابل تغییر وضعیت نیست (تلاش برای تغییر به '{new_status}')."
            )

        # Cannot transition to the identical status
        if self.status == new_status:
            raise ValidationError(
                f"وضعیت گفتگو در حال حاضر '{new_status}' است."
            )

        # 1. ai -> waiting_expert
        if self.status == self.Status.AI and new_status == self.Status.WAITING_EXPERT:
            if not (self.owner_id == by_user.id or by_user.is_staff):
                raise ValidationError("تنها مالک گفتگو یا مدیر سیستم می‌تواند درخواست کارشناس ثبت کند.")
            self.status = self.Status.WAITING_EXPERT

        # 2. waiting_expert -> expert_active
        elif self.status == self.Status.WAITING_EXPERT and new_status == self.Status.EXPERT_ACTIVE:
            if not is_expert(by_user):
                raise ValidationError("تنها کاربران عضو گروه کارشناسان می‌توانند گفتگو را بپذیرند.")
            if self.owner_id == by_user.id:
                raise ValidationError("مالک گفتگو نمی‌تواند گفتگوی خود را به عنوان کارشناس بپذیرد.")
            if self.expert_id is not None:
                raise ValidationError("این گفتگو قبلاً توسط کارشناس دیگری پذیرفته شده است.")
            self.status = self.Status.EXPERT_ACTIVE
            self.expert = by_user

        # 3. expert_active -> ai
        elif self.status == self.Status.EXPERT_ACTIVE and new_status == self.Status.AI:
            if not (is_expert(by_user) and self.expert_id == by_user.id):
                raise ValidationError("تنها کارشناس تخصیص‌داده‌شده می‌تواند گفتگو را به هوش مصنوعی بازگرداند.")
            self.status = self.Status.AI
            self.expert = None

        # 4. Any open state -> closed
        elif new_status == self.Status.CLOSED:
            is_assigned_expert = (is_expert(by_user) and self.expert_id == by_user.id)
            if not (by_user.is_staff or is_assigned_expert):
                raise ValidationError("تنها مدیر سیستم یا کارشناس تخصیص‌داده‌شده مجاز به بستن گفتگو هستند.")
            self.status = self.Status.CLOSED

        else:
            raise ValidationError(
                f"تغییر وضعیت نامعتبر از '{self.status}' به '{new_status}' توسط کاربر '{by_user.username}'."
            )

        if save:
            # Conditional write: only succeeds if nobody changed the state since we read it
            # (e.g. two experts claiming at once), and touches only the workflow fields.
            now = timezone.now()
            updated = type(self).objects.filter(
                pk=self.pk, status=old_status, expert_id=old_expert_id,
            ).update(status=self.status, expert_id=self.expert_id, updated_at=now)
            if not updated:
                self.status, self.expert_id = old_status, old_expert_id
                raise ValidationError("وضعیت گفتگو هم‌زمان تغییر کرده است. لطفاً صفحه را تازه کنید.")
            self.updated_at = now


class Message(models.Model):
    class Role(models.TextChoices):
        USER = 'user', 'کاربر'
        ASSISTANT = 'assistant', 'دستیار'
        EXPERT = 'expert', 'کارشناس'

    class AIStatus(models.TextChoices):
        OK = 'ok', 'موفق'
        FAILED = 'failed', 'ناموفق'

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='authored_messages',
        null=True,
        blank=True,
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
                    role__in=['user', 'expert'],
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
