# Generated manually for Sprint 06

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('feedbacks', '0007_conversation_conv_owner_created_idx'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='message',
            name='user_message_token_fields_null',
        ),
        migrations.AddField(
            model_name='conversation',
            name='expert',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='assigned_conversations',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='conversation',
            name='status',
            field=models.CharField(
                choices=[
                    ('ai', 'پاسخ هوش مصنوعی'),
                    ('waiting_expert', 'در انتظار کارشناس'),
                    ('expert_active', 'در حال پاسخگویی کارشناس'),
                    ('closed', 'بسته شده'),
                ],
                default='ai',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='message',
            name='author',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='authored_messages',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='message',
            name='role',
            field=models.CharField(
                choices=[
                    ('user', 'کاربر'),
                    ('assistant', 'دستیار'),
                    ('expert', 'کارشناس'),
                ],
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name='message',
            constraint=models.CheckConstraint(
                condition=models.Q(role='assistant') | models.Q(
                    role__in=['user', 'expert'],
                    prompt_tokens__isnull=True,
                    completion_tokens__isnull=True,
                    cached_tokens__isnull=True,
                    total_tokens__isnull=True,
                ),
                name='user_message_token_fields_null',
            ),
        ),
    ]
