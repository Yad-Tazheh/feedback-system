from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
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
from .permissions import (
    can_claim,
    can_close,
    can_post,
    can_release,
    can_request_expert,
    can_view,
    is_expert,
)
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
            .select_related('expert')
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
        text = form.cleaned_data['text']
        is_at_expert = text.strip().lower().startswith('@expert')
        with transaction.atomic():
            conversation = form.save(commit=False)
            conversation.owner = self.request.user
            if is_at_expert:
                conversation.status = Conversation.Status.WAITING_EXPERT
            conversation.save()
            Message.objects.create(
                conversation=conversation,
                role=Message.Role.USER,
                author=self.request.user,
                content=text,
            )

        self.object = conversation
        if not is_at_expert and conversation.status == Conversation.Status.AI:
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


class ConversationDetailView(LoginRequiredMixin, DetailView):
    model = Conversation
    template_name = 'feedbacks/conversation_detail.html'
    context_object_name = 'conversation'

    def get_object(self, queryset=None):
        pk = self.kwargs.get(self.pk_url_kwarg)
        conv = get_object_or_404(
            Conversation.objects.select_related('owner', 'expert').prefetch_related('messages__author'),
            pk=pk,
        )
        if not can_view(self.request.user, conv):
            raise Http404("No Conversation matches the given query.")
        return conv

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'form' not in context:
            context['form'] = MessageForm()
        context['messages_list'] = self.object.messages.all()
        user = self.request.user
        context['can_post'] = can_post(user, self.object)
        context['can_claim'] = can_claim(user, self.object)
        context['can_release'] = can_release(user, self.object)
        context['can_close'] = can_close(user, self.object)
        context['can_request_expert'] = can_request_expert(user, self.object)
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not can_post(request.user, self.object):
            raise Http404("Cannot post to this conversation.")

        form = MessageForm(request.POST)
        if form.is_valid():
            content = form.cleaned_data['content']
            is_at_expert = content.strip().lower().startswith('@expert')
            is_assigned_expert = (
                self.object.expert_id == request.user.id
                and is_expert(request.user)
            )

            if is_assigned_expert:
                # Expert response: role=expert, AI silent
                with transaction.atomic():
                    Message.objects.create(
                        conversation=self.object,
                        role=Message.Role.EXPERT,
                        author=request.user,
                        content=content,
                    )
            else:
                # User response: role=user
                with transaction.atomic():
                    Message.objects.create(
                        conversation=self.object,
                        role=Message.Role.USER,
                        author=request.user,
                        content=content,
                    )
                    if is_at_expert and self.object.status == Conversation.Status.AI:
                        self.object.transition_to(
                            Conversation.Status.WAITING_EXPERT,
                            request.user,
                        )

                # AI reply only when status is ai and not addressing expert
                if not is_at_expert and self.object.status == Conversation.Status.AI:
                    create_ai_reply(self.object, request=request)

            return redirect(reverse('conversation_detail', kwargs={'pk': self.object.pk}))
        return self.render_to_response(self.get_context_data(form=form))


class ExpertQueueView(LoginRequiredMixin, ListView):
    model = Conversation
    template_name = 'feedbacks/expert_queue.html'
    context_object_name = 'waiting_conversations'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        if not (is_expert(request.user) or request.user.is_staff):
            raise Http404("Expert queue not accessible.")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return (
            Conversation.objects
            .filter(status=Conversation.Status.WAITING_EXPERT)
            .select_related('owner')
            .with_message_count()
            .order_by('created_at')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if user.is_staff:
            context['assigned_conversations'] = (
                Conversation.objects
                .filter(status=Conversation.Status.EXPERT_ACTIVE)
                .select_related('owner', 'expert')
                .with_message_count()
                .order_by('-updated_at')
            )
        else:
            context['assigned_conversations'] = (
                Conversation.objects
                .filter(expert=user, status=Conversation.Status.EXPERT_ACTIVE)
                .select_related('owner', 'expert')
                .with_message_count()
                .order_by('-updated_at')
            )
        return context


class RequestExpertView(LoginRequiredMixin, View):
    def post(self, request, pk):
        conv = get_object_or_404(Conversation, pk=pk)
        if not can_request_expert(request.user, conv):
            raise Http404("Cannot request expert for this conversation.")
        conv.transition_to(Conversation.Status.WAITING_EXPERT, request.user)
        messages.success(request, 'درخواست ارتباط با کارشناس ثبت شد.')
        return redirect('conversation_detail', pk=conv.pk)


class ClaimConversationView(LoginRequiredMixin, View):
    def post(self, request, pk):
        conv = get_object_or_404(Conversation, pk=pk)
        if not can_claim(request.user, conv):
            raise Http404("Cannot claim this conversation.")
        conv.transition_to(Conversation.Status.EXPERT_ACTIVE, request.user)
        messages.success(request, 'گفتگو توسط شما پذیرفته شد.')
        return redirect('conversation_detail', pk=conv.pk)


class ReleaseConversationView(LoginRequiredMixin, View):
    def post(self, request, pk):
        conv = get_object_or_404(Conversation, pk=pk)
        if not can_release(request.user, conv):
            raise Http404("Cannot release this conversation.")
        conv.transition_to(Conversation.Status.AI, request.user)
        messages.success(request, 'گفتگو به هوش مصنوعی ارجاع داده شد.')
        return redirect('conversation_detail', pk=conv.pk)


class CloseConversationView(LoginRequiredMixin, View):
    def post(self, request, pk):
        conv = get_object_or_404(Conversation, pk=pk)
        if not can_close(request.user, conv):
            raise Http404("Cannot close this conversation.")
        conv.transition_to(Conversation.Status.CLOSED, request.user)
        messages.success(request, 'گفتگو با موفقیت بسته شد.')
        return redirect('conversation_detail', pk=conv.pk)


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
