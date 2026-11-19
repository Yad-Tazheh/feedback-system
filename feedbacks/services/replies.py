import logging

from django.contrib import messages
from feedbacks.models import Message
from feedbacks.services.ai_service import AIService, AIServiceError

logger = logging.getLogger(__name__)


def create_ai_reply(conversation, request=None):
    """
    Calls the AI service with the conversation history and persists
    the resulting assistant message (ok or failed).
    Optionally attaches success/error flash messages to the request.
    """
    ai = AIService()
    try:
        context = conversation.get_context_prompt()
        result = ai.generate(conversation.as_messages(), context=context)
        assistant_message = Message.objects.create(
            conversation=conversation,
            role=Message.Role.ASSISTANT,
            content=result.content,
            ai_model=result.model or '',
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            cached_tokens=result.cached_tokens,
            total_tokens=result.total_tokens,
            ai_status=Message.AIStatus.OK,
            ai_error='',
        )
        if request is not None:
            messages.success(request, result.content)
        return assistant_message
    except AIServiceError as exc:
        logger.exception(
            "AI service failed for conversation %s: %s",
            conversation.pk,
            type(exc).__name__,
        )
        assistant_message = Message.objects.create(
            conversation=conversation,
            role=Message.Role.ASSISTANT,
            content='',
            ai_status=Message.AIStatus.FAILED,
            ai_error=str(exc),
        )
        if request is not None:
            messages.error(
                request,
                'خطا در برقراری ارتباط با سرویس هوش مصنوعی.'
            )
        return assistant_message
    except Exception as exc:
        logger.exception(
            "Unexpected error during AI reply for conversation %s: %s",
            conversation.pk,
            type(exc).__name__,
        )
        assistant_message = Message.objects.create(
            conversation=conversation,
            role=Message.Role.ASSISTANT,
            content='',
            ai_status=Message.AIStatus.FAILED,
            ai_error=str(exc),
        )
        if request is not None:
            messages.error(
                request,
                'خطا در برقراری ارتباط با سرویس هوش مصنوعی.'
            )
        return assistant_message
