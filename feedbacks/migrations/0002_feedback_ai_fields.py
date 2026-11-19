# Generated manually for Sprint 02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('feedbacks', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='feedback',
            name='ai_error',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='feedback',
            name='ai_model',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='feedback',
            name='ai_responded_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='feedback',
            name='ai_status',
            field=models.CharField(
                choices=[('pending', 'در انتظار'), ('ok', 'موفق'), ('failed', 'ناموفق')],
                default='pending',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='feedback',
            name='cached_tokens',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='feedback',
            name='completion_tokens',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='feedback',
            name='prompt_tokens',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='feedback',
            name='total_tokens',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
