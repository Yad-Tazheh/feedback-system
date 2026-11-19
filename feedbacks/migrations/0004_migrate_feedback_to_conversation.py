# Generated manually for Sprint 03

from django.db import migrations


def migrate_feedback_to_conversation(apps, schema_editor):
    Feedback = apps.get_model('feedbacks', 'Feedback')
    Conversation = apps.get_model('feedbacks', 'Conversation')
    Message = apps.get_model('feedbacks', 'Message')

    for fb in Feedback.objects.all():
        conv = Conversation.objects.create(
            type=fb.type,
            title=fb.title,
        )
        Conversation.objects.filter(pk=conv.pk).update(
            created_at=fb.created_at,
            updated_at=fb.created_at,
        )

        user_msg = Message.objects.create(
            conversation=conv,
            role='user',
            content=fb.text,
        )
        Message.objects.filter(pk=user_msg.pk).update(
            created_at=fb.created_at,
        )

        if fb.ai_response:
            ai_status = fb.ai_status if fb.ai_status in ('ok', 'failed') else 'ok'
            asst_msg = Message.objects.create(
                conversation=conv,
                role='assistant',
                content=fb.ai_response,
                ai_model=fb.ai_model,
                prompt_tokens=fb.prompt_tokens,
                completion_tokens=fb.completion_tokens,
                cached_tokens=fb.cached_tokens,
                total_tokens=fb.total_tokens,
                ai_status=ai_status,
                ai_error=fb.ai_error,
            )
            created_time = fb.ai_responded_at or fb.created_at
            Message.objects.filter(pk=asst_msg.pk).update(
                created_at=created_time,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('feedbacks', '0003_conversation_message'),
    ]

    operations = [
        migrations.RunPython(
            migrate_feedback_to_conversation,
            reverse_code=migrations.RunPython.noop,  # Reverse is noop because Feedback model is removed in 0005
        ),
    ]
