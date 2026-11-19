# Generated manually for Sprint 03

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('feedbacks', '0004_migrate_feedback_to_conversation'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Feedback',
        ),
    ]
