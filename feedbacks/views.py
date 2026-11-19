from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from .forms import (
    ConversationCreateForm,
    ConversationUpdateForm,
    MessageForm,
)
from .models import Conversation, Message
from .services.replies import create_ai_reply


class OwnedConversationMixin:
    def get_queryset(self):
        return Conversation.objects.for_user(self.request.user)


class FeedbackListView(LoginRequiredMixin, OwnedConversationMixin, ListView):
    model = Conversation
    template_name = 'feedbacks/feedback_list.html'
    context_object_name = 'conversations'

    def get_queryset(self):
        return (
            super().get_queryset()
            .with_message_count()
            .order_by('-created_at')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['feedbacks'] = context['conversations']
        return context


class FeedbackCreateView(LoginRequiredMixin, OwnedConversationMixin, CreateView):
    model = Conversation
    form_class = ConversationCreateForm
    template_name = 'feedbacks/feedback_form.html'
    success_url = reverse_lazy('feedback_list')

    def form_valid(self, form):
        with transaction.atomic():
            conversation = form.save(commit=False)
            conversation.owner = self.request.user
            conversation.save()
            Message.objects.create(
                conversation=conversation,
                role=Message.Role.USER,
                content=form.cleaned_data['text'],
            )

        self.object = conversation
        create_ai_reply(conversation, request=self.request)

        return redirect(self.get_success_url())


class FeedbackUpdateView(LoginRequiredMixin, OwnedConversationMixin, UpdateView):
    model = Conversation
    form_class = ConversationUpdateForm
    template_name = 'feedbacks/feedback_form.html'
    success_url = reverse_lazy('feedback_list')


class FeedbackDeleteView(LoginRequiredMixin, OwnedConversationMixin, DeleteView):
    model = Conversation
    template_name = 'feedbacks/feedback_confirm_delete.html'
    context_object_name = 'item'
    success_url = reverse_lazy('feedback_list')


class ConversationDetailView(LoginRequiredMixin, OwnedConversationMixin, DetailView):
    model = Conversation
    template_name = 'feedbacks/conversation_detail.html'
    context_object_name = 'conversation'

    def get_queryset(self):
        return super().get_queryset().prefetch_related('messages')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'form' not in context:
            context['form'] = MessageForm()
        context['messages_list'] = self.object.messages.all()
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = MessageForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                Message.objects.create(
                    conversation=self.object,
                    role=Message.Role.USER,
                    content=form.cleaned_data['content'],
                )
            create_ai_reply(self.object, request=request)
            return redirect(reverse('conversation_detail', kwargs={'pk': self.object.pk}))
        return self.render_to_response(self.get_context_data(form=form))


class AIUsageView(LoginRequiredMixin, TemplateView):
    template_name = 'feedbacks/ai_usage.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        usage = Message.objects.filter(
            role=Message.Role.ASSISTANT,
            conversation__owner=self.request.user,
        ).aggregate(
            prompt_tokens=Sum('prompt_tokens'),
            completion_tokens=Sum('completion_tokens'),
            cached_tokens=Sum('cached_tokens'),
            total_tokens=Sum('total_tokens'),
            ok_count=Count('id', filter=Q(ai_status=Message.AIStatus.OK)),
            failed_count=Count('id', filter=Q(ai_status=Message.AIStatus.FAILED)),
        )
        context['usage'] = usage
        return context


class SignUpView(CreateView):
    form_class = UserCreationForm
    template_name = 'registration/signup.html'
    success_url = reverse_lazy('feedback_list')

    def form_valid(self, form):
        user = form.save()
        self.object = user
        login(self.request, user)
        return redirect(self.get_success_url())
