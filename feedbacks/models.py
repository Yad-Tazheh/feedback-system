from django.db import models


class Feedback(models.Model):
    TYPE_CHOICES = [
        ('request', 'درخواست'),
        ('criticism', 'انتقاد'),
        ('suggestion', 'پیشنهاد'),
    ]

    AI_STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('ok', 'موفق'),
        ('failed', 'ناموفق'),
    ]

    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    text = models.TextField()
    ai_response = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    ai_model = models.CharField(max_length=100, blank=True, default='')
    prompt_tokens = models.PositiveIntegerField(null=True, blank=True)
    completion_tokens = models.PositiveIntegerField(null=True, blank=True)
    cached_tokens = models.PositiveIntegerField(null=True, blank=True)
    total_tokens = models.PositiveIntegerField(null=True, blank=True)
    ai_status = models.CharField(
        max_length=20,
        choices=AI_STATUS_CHOICES,
        default='pending',
    )
    ai_error = models.TextField(blank=True, default='')
    ai_responded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.get_type_display()}: {self.title}"

    def as_messages(self):
        prompt = f"""نوع پیام:
{self.get_type_display()}

عنوان:
{self.title}

متن کاربر:
{self.text}"""
        return [{"role": "user", "content": prompt}]
