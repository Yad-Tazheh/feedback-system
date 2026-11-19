# Generated manually for Sprint 05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('feedbacks', '0006_conversation_owner'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='conversation',
            index=models.Index(fields=['owner', '-created_at'], name='conv_owner_created_idx'),
        ),
    ]
