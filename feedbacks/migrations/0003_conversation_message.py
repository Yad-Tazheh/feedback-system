# Generated manually for Sprint 03

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('feedbacks', '0002_feedback_ai_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='Conversation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[('request', 'درخواست'), ('criticism', 'انتقاد'), ('suggestion', 'پیشنهاد')], max_length=20)),
                ('title', models.CharField(max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='Message',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('user', 'کاربر'), ('assistant', 'دستیار')], max_length=20)),
                ('content', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('ai_model', models.CharField(blank=True, default='', max_length=100)),
                ('prompt_tokens', models.PositiveIntegerField(blank=True, null=True)),
                ('completion_tokens', models.PositiveIntegerField(blank=True, null=True)),
                ('cached_tokens', models.PositiveIntegerField(blank=True, null=True)),
                ('total_tokens', models.PositiveIntegerField(blank=True, null=True)),
                ('ai_status', models.CharField(blank=True, choices=[('ok', 'موفق'), ('failed', 'ناموفق')], max_length=20, null=True)),
                ('ai_error', models.TextField(blank=True, default='')),
                ('conversation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='feedbacks.conversation')),
            ],
            options={
                'ordering': ['created_at', 'id'],
                'indexes': [models.Index(fields=['conversation', 'created_at'], name='msg_conv_created_idx')],
                'constraints': [models.CheckConstraint(condition=models.Q(role='assistant') | models.Q(role='user', prompt_tokens__isnull=True, completion_tokens__isnull=True, cached_tokens__isnull=True, total_tokens__isnull=True), name='user_message_token_fields_null')],
            },
        ),
    ]
