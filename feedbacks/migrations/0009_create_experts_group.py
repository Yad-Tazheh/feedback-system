# Generated manually for Sprint 06

from django.db import migrations


def create_experts_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name='experts')


def remove_experts_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name='experts').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('feedbacks', '0008_conversation_status_expert_message_role_author'),
    ]

    operations = [
        migrations.RunPython(create_experts_group, reverse_code=remove_experts_group),
    ]
