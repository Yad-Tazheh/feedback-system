from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    TemplateView,
    UpdateView,
)

from .forms import FeedbackForm
from .models import Feedback
from .services.ai_service import AIService, AIServiceError


class FeedbackListView(ListView):
    model = Feedback
    template_name = 'feedbacks/feedback_list.html'
    context_object_name = 'feedbacks'
    ordering = ['-created_at']


class FeedbackCreateView(CreateView):
    model = Feedback
    form_class = FeedbackForm
    template_name = 'feedbacks/feedback_form.html'
    success_url = reverse_lazy('feedback_list')

    def form_valid(self, form):
        self.object = form.save()

        ai = AIService()
        try:
            result = ai.generate(self.object.as_messages())
            self.object.ai_response = result.content
            self.object.ai_model = result.model or ''
            self.object.prompt_tokens = result.prompt_tokens
            self.object.completion_tokens = result.completion_tokens
            self.object.cached_tokens = result.cached_tokens
            self.object.total_tokens = result.total_tokens
            self.object.ai_status = 'ok'
            self.object.ai_error = ''
            self.object.ai_responded_at = timezone.now()
            self.object.save()
            messages.success(self.request, result.content)
        except AIServiceError as exc:
            self.object.ai_status = 'failed'
            self.object.ai_error = str(exc)
            self.object.save()
            messages.error(
                self.request,
                'خطا در برقراری ارتباط با سرویس هوش مصنوعی.'
            )
        except Exception as exc:
            self.object.ai_status = 'failed'
            self.object.ai_error = str(exc)
            self.object.save()
            messages.error(
                self.request,
                'خطا در پردازش هوش مصنوعی.'
            )

        return redirect(self.get_success_url())


class FeedbackUpdateView(UpdateView):
    model = Feedback
    form_class = FeedbackForm
    template_name = 'feedbacks/feedback_form.html'
    success_url = reverse_lazy('feedback_list')


class FeedbackDeleteView(DeleteView):
    model = Feedback
    template_name = 'feedbacks/feedback_confirm_delete.html'
    context_object_name = 'item'
    success_url = reverse_lazy('feedback_list')


class AIUsageView(TemplateView):
    template_name = 'feedbacks/ai_usage.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        usage = Feedback.objects.aggregate(
            prompt_tokens=Sum('prompt_tokens'),
            completion_tokens=Sum('completion_tokens'),
            cached_tokens=Sum('cached_tokens'),
            total_tokens=Sum('total_tokens'),
            ok_count=Count('id', filter=Q(ai_status='ok')),
            failed_count=Count('id', filter=Q(ai_status='failed')),
        )
        context['usage'] = usage
        return context


# Backward-compatible view aliases
feedback_list = FeedbackListView.as_view()
feedback_create = FeedbackCreateView.as_view()
feedback_update = FeedbackUpdateView.as_view()
feedback_delete = FeedbackDeleteView.as_view()
ai_usage = AIUsageView.as_view()
