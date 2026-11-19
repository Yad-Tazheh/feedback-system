import subprocess
import sys
from unittest.mock import Mock, patch
from requests.exceptions import ConnectionError, HTTPError, Timeout

from django.contrib.auth.models import Group, User
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.db import connection, IntegrityError
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from .forms import (
    ConversationCreateForm,
    ConversationUpdateForm,
    FeedbackForm,
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
from .services.ai_service import AIService, AIServiceError, AIResult
from .services.replies import create_ai_reply


class FormTests(TestCase):

    def test_conversation_create_form_valid(self):
        form = ConversationCreateForm({
            'type': 'request',
            'title': 'عنوان تست',
            'text': 'متن تست',
        })
        self.assertTrue(form.is_valid())

    def test_conversation_create_form_title_required(self):
        form = ConversationCreateForm({
            'type': 'request',
            'title': '',
            'text': 'متن تست',
        })
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors['title'][0],
            'لطفاً عنوان را وارد کنید.'
        )

    def test_conversation_create_form_text_required(self):
        form = ConversationCreateForm({
            'type': 'request',
            'title': 'عنوان تست',
            'text': '',
        })
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors['text'][0],
            'لطفاً متن بازخورد را وارد کنید.'
        )

    def test_conversation_create_form_invalid_type(self):
        form = ConversationCreateForm({
            'type': 'invalid_type',
            'title': 'عنوان تست',
            'text': 'متن تست',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('type', form.errors)

    def test_conversation_create_form_title_max_length(self):
        form = ConversationCreateForm({
            'type': 'request',
            'title': 'a' * 201,
            'text': 'متن تست',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)

    def test_feedback_form_alias(self):
        self.assertIs(FeedbackForm, ConversationCreateForm)

    def test_conversation_update_form_valid(self):
        form = ConversationUpdateForm({
            'type': 'suggestion',
            'title': 'عنوان ویرایش‌شده',
        })
        self.assertTrue(form.is_valid())

    def test_conversation_update_form_title_required(self):
        form = ConversationUpdateForm({
            'type': 'suggestion',
            'title': '',
        })
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors['title'][0],
            'لطفاً عنوان را وارد کنید.'
        )

    def test_message_form_valid(self):
        form = MessageForm({'content': 'متن پیام جدید'})
        self.assertTrue(form.is_valid())

    def test_message_form_content_required(self):
        form = MessageForm({'content': ''})
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors['content'][0],
            'لطفاً متن پیام را وارد کنید.'
        )


class ConversationModelTest(TestCase):

    def test_create_conversation(self):
        conv = Conversation.objects.create(
            type='request',
            title='عنوان گفتگو',
        )
        self.assertEqual(conv.title, 'عنوان گفتگو')
        self.assertEqual(conv.type, 'request')
        self.assertIsNotNone(conv.created_at)
        self.assertIsNotNone(conv.updated_at)
        self.assertEqual(str(conv), 'درخواست: عنوان گفتگو')

    def test_cascade_delete(self):
        conv = Conversation.objects.create(type='request', title='تست حذف آبشاری')
        Message.objects.create(conversation=conv, role=Message.Role.USER, content='پیام ۱')
        Message.objects.create(
            conversation=conv,
            role=Message.Role.ASSISTANT,
            content='پیام ۲',
            ai_status=Message.AIStatus.OK,
        )
        self.assertEqual(Message.objects.filter(conversation=conv).count(), 2)

        conv.delete()
        self.assertEqual(Message.objects.filter(conversation_id=conv.id).count(), 0)

    def test_as_messages_excludes_failed_replies(self):
        conv = Conversation.objects.create(type='request', title='تست تاریخچه')
        Message.objects.create(conversation=conv, role=Message.Role.USER, content='سلام')
        Message.objects.create(
            conversation=conv,
            role=Message.Role.ASSISTANT,
            content='سلام! چطور کمکتون کنم؟',
            ai_status=Message.AIStatus.OK,
        )
        Message.objects.create(conversation=conv, role=Message.Role.USER, content='سؤال من این است')
        Message.objects.create(
            conversation=conv,
            role=Message.Role.ASSISTANT,
            content='',
            ai_status=Message.AIStatus.FAILED,
            ai_error='Timeout',
        )
        Message.objects.create(
            conversation=conv,
            role=Message.Role.ASSISTANT,
            content='پاسخ دوم موفق',
            ai_status=Message.AIStatus.OK,
        )

        history = conv.as_messages()
        self.assertEqual(len(history), 4)
        self.assertEqual(history[0], {'role': 'user', 'content': 'سلام'})
        self.assertEqual(history[1], {'role': 'assistant', 'content': 'سلام! چطور کمکتون کنم؟'})
        self.assertEqual(history[2], {'role': 'user', 'content': 'سؤال من این است'})
        self.assertEqual(history[3], {'role': 'assistant', 'content': 'پاسخ دوم موفق'})

    def test_as_messages_returns_history_only_and_context_separate(self):
        conv = Conversation.objects.create(type='criticism', title='انتقاد تستی')
        Message.objects.create(conversation=conv, role=Message.Role.USER, content='متن کاربر')
        msgs = conv.as_messages()
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0], {'role': 'user', 'content': 'متن کاربر'})
        context = conv.get_context_prompt()
        self.assertIn('انتقاد', context)
        self.assertIn('انتقاد تستی', context)


class MessageModelTest(TestCase):

    def test_message_ordering_same_timestamp_ordered_by_id(self):
        conv = Conversation.objects.create(type='request', title='تست ترتیب')
        now = timezone.now()
        m1 = Message.objects.create(conversation=conv, role=Message.Role.USER, content='پیام اول')
        m2 = Message.objects.create(
            conversation=conv,
            role=Message.Role.ASSISTANT,
            content='پیام دوم',
            ai_status=Message.AIStatus.OK,
        )
        m3 = Message.objects.create(conversation=conv, role=Message.Role.USER, content='پیام سوم')

        # Force same timestamp on all messages
        Message.objects.filter(pk__in=[m1.pk, m2.pk, m3.pk]).update(created_at=now)

        msgs = list(conv.messages.all())
        self.assertEqual([m.id for m in msgs], [m1.id, m2.id, m3.id])

    def test_user_message_token_fields_check_constraint(self):
        conv = Conversation.objects.create(type='request', title='تست قید')
        # Creating user message with non-null token field should fail constraint
        with self.assertRaises(IntegrityError):
            Message.objects.create(
                conversation=conv,
                role=Message.Role.USER,
                content='متن کاربر',
                prompt_tokens=10,
            )

    def test_assistant_message_with_tokens_succeeds(self):
        conv = Conversation.objects.create(type='request', title='تست قید دستیار')
        msg = Message.objects.create(
            conversation=conv,
            role=Message.Role.ASSISTANT,
            content='متن دستیار',
            prompt_tokens=10,
            completion_tokens=20,
            cached_tokens=5,
            total_tokens=30,
            ai_status=Message.AIStatus.OK,
        )
        self.assertEqual(msg.prompt_tokens, 10)


class FeedbackListViewTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.client.force_login(self.user)

    def test_feedback_list_empty(self):
        response = self.client.get(reverse('feedback_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'هنوز موردی ثبت نشده است.')

    def test_feedback_list_displays_conversations(self):
        conv = Conversation.objects.create(
            owner=self.user,
            type='request',
            title='عنوان تستی گفتگو',
        )
        Message.objects.create(conversation=conv, role=Message.Role.USER, content='متن پیام اول')
        response = self.client.get(reverse('feedback_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'عنوان تستی گفتگو')
        self.assertContains(response, reverse('conversation_detail', args=[conv.pk]))

    def test_feedback_list_num_queries(self):
        for i in range(5):
            conv = Conversation.objects.create(
                owner=self.user,
                type='request',
                title=f'گفتگو {i}',
            )
            Message.objects.create(
                conversation=conv,
                role=Message.Role.USER,
                content=f'پیام {i}',
            )
            Message.objects.create(
                conversation=conv,
                role=Message.Role.ASSISTANT,
                content=f'پاسخ {i}',
                ai_status=Message.AIStatus.OK,
            )

        # 3 queries total: session, auth_user, and annotated conversation query (no N+1 queries for message counts)
        with self.assertNumQueries(3):
            response = self.client.get(reverse('feedback_list'))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.context['conversations']), 5)
            self.assertEqual(response.context['conversations'][0].message_count, 2)


class FeedbackCreateViewTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.client.force_login(self.user)

    def test_feedback_create_get(self):
        response = self.client.get(reverse('feedback_create'))
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.context['form'], ConversationCreateForm)

    @patch('feedbacks.services.replies.AIService.generate')
    def test_feedback_create_post_success(self, mock_generate):
        mock_generate.return_value = AIResult(
            content='پاسخ تست هوش مصنوعی',
            model='test-model',
            prompt_tokens=15,
            completion_tokens=25,
            cached_tokens=5,
            total_tokens=40,
            raw_usage={'prompt_tokens': 15, 'completion_tokens': 25, 'total_tokens': 40},
        )

        response = self.client.post(
            reverse('feedback_create'),
            {
                'type': 'request',
                'title': 'Feedback جدید',
                'text': 'متن feedback جدید',
            },
            follow=True,
        )

        self.assertRedirects(response, reverse('feedback_list'))

        conv = Conversation.objects.get(title='Feedback جدید')
        self.assertEqual(conv.owner, self.user)
        self.assertEqual(conv.type, 'request')

        msgs = list(conv.messages.all())
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0].role, Message.Role.USER)
        self.assertEqual(msgs[0].content, 'متن feedback جدید')

        self.assertEqual(msgs[1].role, Message.Role.ASSISTANT)
        self.assertEqual(msgs[1].content, 'پاسخ تست هوش مصنوعی')
        self.assertEqual(msgs[1].ai_status, Message.AIStatus.OK)
        self.assertEqual(msgs[1].ai_model, 'test-model')
        self.assertEqual(msgs[1].prompt_tokens, 15)
        self.assertEqual(msgs[1].completion_tokens, 25)
        self.assertEqual(msgs[1].cached_tokens, 5)
        self.assertEqual(msgs[1].total_tokens, 40)

        mock_generate.assert_called_once()
        self.assertContains(response, 'پاسخ تست هوش مصنوعی')

    @patch('feedbacks.services.replies.AIService.generate')
    def test_feedback_create_post_ai_failure_stores_failure_and_redirects(self, mock_generate):
        mock_generate.side_effect = AIServiceError('LM Studio is down')

        response = self.client.post(
            reverse('feedback_create'),
            {
                'type': 'criticism',
                'title': 'Feedback همراه با خطای AI',
                'text': 'متن انتقاد',
            }
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('feedback_list'))

        conv = Conversation.objects.get(title='Feedback همراه با خطای AI')
        self.assertEqual(conv.owner, self.user)
        msgs = list(conv.messages.all())
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0].role, Message.Role.USER)
        self.assertEqual(msgs[0].content, 'متن انتقاد')

        self.assertEqual(msgs[1].role, Message.Role.ASSISTANT)
        self.assertEqual(msgs[1].ai_status, Message.AIStatus.FAILED)
        self.assertIn('LM Studio is down', msgs[1].ai_error)

    def test_feedback_create_invalid_post(self):
        response = self.client.post(
            reverse('feedback_create'),
            {
                'type': 'request',
                'title': '',
                'text': 'متن تست',
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Conversation.objects.count(), 0)
        self.assertIn('title', response.context['form'].errors)


class FeedbackUpdateViewTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.client.force_login(self.user)
        self.conv = Conversation.objects.create(
            owner=self.user,
            type='request',
            title='عنوان تست',
        )

    def test_feedback_update_get(self):
        response = self.client.get(
            reverse('feedback_update', args=[self.conv.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.context['form'], ConversationUpdateForm)

    def test_feedback_update_post(self):
        response = self.client.post(
            reverse('feedback_update', args=[self.conv.pk]),
            {
                'type': 'suggestion',
                'title': 'عنوان جدید',
            }
        )
        self.assertRedirects(response, reverse('feedback_list'))

        self.conv.refresh_from_db()
        self.assertEqual(self.conv.type, 'suggestion')
        self.assertEqual(self.conv.title, 'عنوان جدید')


class FeedbackDeleteViewTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.client.force_login(self.user)
        self.conv = Conversation.objects.create(
            owner=self.user,
            type='request',
            title='عنوان تست',
        )
        Message.objects.create(conversation=self.conv, role=Message.Role.USER, content='پیام تست')

    def test_feedback_delete_get(self):
        response = self.client.get(
            reverse('feedback_delete', args=[self.conv.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_feedback_delete_post(self):
        response = self.client.post(
            reverse('feedback_delete', args=[self.conv.pk])
        )
        self.assertRedirects(response, reverse('feedback_list'))
        self.assertFalse(Conversation.objects.filter(pk=self.conv.pk).exists())
        self.assertFalse(Message.objects.filter(conversation_id=self.conv.pk).exists())


class ConversationDetailViewTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.client.force_login(self.user)
        self.conv = Conversation.objects.create(
            owner=self.user,
            type='request',
            title='گفتگوی من',
        )
        self.initial_msg = Message.objects.create(
            conversation=self.conv,
            role=Message.Role.USER,
            content='پیام اول کاربر',
        )

    def test_conversation_detail_get(self):
        response = self.client.get(
            reverse('conversation_detail', args=[self.conv.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'گفتگوی من')
        self.assertContains(response, 'پیام اول کاربر')
        self.assertIsInstance(response.context['form'], MessageForm)

    @patch('feedbacks.services.replies.AIService.generate')
    def test_conversation_detail_post_user_message_and_ai_reply(self, mock_generate):
        mock_generate.return_value = AIResult(
            content='پاسخ دستیار به پیام دوم',
            model='qwen-test',
            prompt_tokens=30,
            completion_tokens=40,
            cached_tokens=10,
            total_tokens=70,
            raw_usage={'prompt_tokens': 30, 'completion_tokens': 40, 'total_tokens': 70},
        )

        response = self.client.post(
            reverse('conversation_detail', args=[self.conv.pk]),
            {'content': 'پیام دوم کاربر'},
            follow=True,
        )

        self.assertRedirects(response, reverse('conversation_detail', args=[self.conv.pk]))

        msgs = list(self.conv.messages.all())
        self.assertEqual(len(msgs), 3)
        self.assertEqual(msgs[1].role, Message.Role.USER)
        self.assertEqual(msgs[1].content, 'پیام دوم کاربر')

        self.assertEqual(msgs[2].role, Message.Role.ASSISTANT)
        self.assertEqual(msgs[2].content, 'پاسخ دستیار به پیام دوم')
        self.assertEqual(msgs[2].ai_status, Message.AIStatus.OK)
        self.assertEqual(msgs[2].total_tokens, 70)

        # Ensure full history and context was passed to AI
        mock_generate.assert_called_once()
        sent_messages = mock_generate.call_args[0][0]
        sent_context = mock_generate.call_args[1].get('context', '')
        self.assertEqual(len(sent_messages), 2)
        self.assertIn('گفتگوی من', sent_context)
        self.assertEqual(sent_messages[0]['content'], 'پیام اول کاربر')
        self.assertEqual(sent_messages[1]['content'], 'پیام دوم کاربر')

    @patch('feedbacks.services.replies.AIService.generate')
    def test_conversation_detail_post_ai_failure_stores_failed_and_redirects(self, mock_generate):
        mock_generate.side_effect = AIServiceError('LM Studio unavailable')

        response = self.client.post(
            reverse('conversation_detail', args=[self.conv.pk]),
            {'content': 'پیام کاربر قبل از خطا'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('conversation_detail', args=[self.conv.pk]))

        msgs = list(self.conv.messages.all())
        self.assertEqual(len(msgs), 3)
        self.assertEqual(msgs[1].role, Message.Role.USER)
        self.assertEqual(msgs[1].content, 'پیام کاربر قبل از خطا')

        self.assertEqual(msgs[2].role, Message.Role.ASSISTANT)
        self.assertEqual(msgs[2].ai_status, Message.AIStatus.FAILED)
        self.assertIn('LM Studio unavailable', msgs[2].ai_error)


class AIUsageViewTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.client.force_login(self.user)

    def test_usage_page_totals_correct(self):
        conv1 = Conversation.objects.create(owner=self.user, type='request', title='گفتگو ۱')
        conv2 = Conversation.objects.create(owner=self.user, type='criticism', title='گفتگو ۲')

        # User messages (must NOT be counted in usage)
        Message.objects.create(conversation=conv1, role=Message.Role.USER, content='متن ۱')
        Message.objects.create(conversation=conv2, role=Message.Role.USER, content='متن ۲')

        # Assistant messages
        Message.objects.create(
            conversation=conv1,
            role=Message.Role.ASSISTANT,
            content='پاسخ ۱',
            ai_status=Message.AIStatus.OK,
            prompt_tokens=100,
            completion_tokens=50,
            cached_tokens=20,
            total_tokens=150,
        )
        Message.objects.create(
            conversation=conv1,
            role=Message.Role.ASSISTANT,
            content='پاسخ ۲',
            ai_status=Message.AIStatus.OK,
            prompt_tokens=200,
            completion_tokens=80,
            cached_tokens=None,
            total_tokens=280,
        )
        Message.objects.create(
            conversation=conv2,
            role=Message.Role.ASSISTANT,
            content='',
            ai_status=Message.AIStatus.FAILED,
            ai_error='Connection timeout',
        )

        response = self.client.get(reverse('ai_usage'))

        self.assertEqual(response.status_code, 200)
        usage = response.context['usage']
        self.assertEqual(usage['prompt_tokens'], 300)
        self.assertEqual(usage['completion_tokens'], 130)
        self.assertEqual(usage['cached_tokens'], 20)
        self.assertEqual(usage['total_tokens'], 430)
        self.assertEqual(usage['ok_count'], 2)
        self.assertEqual(usage['failed_count'], 1)

        self.assertContains(response, '300')
        self.assertContains(response, '130')
        self.assertContains(response, '430')

    def test_usage_page_empty(self):
        response = self.client.get(reverse('ai_usage'))
        self.assertEqual(response.status_code, 200)
        usage = response.context['usage']
        self.assertEqual(usage['ok_count'], 0)
        self.assertEqual(usage['failed_count'], 0)


class AIServiceTest(TestCase):

    def setUp(self):
        self.env_patcher = patch.dict('os.environ', {
            'LM_STUDIO_URL': 'http://localhost:1234/v1/chat/completions',
            'LM_MODEL': 'qwen2.5-7b',
            'LM_TIMEOUT': '45',
        })
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def test_load_prompt_missing_file_raises_ai_service_error(self):
        with patch('builtins.open', side_effect=OSError('File not found')):
            with self.assertRaises(AIServiceError) as ctx:
                AIService()
            self.assertIn('System prompt file not found', str(ctx.exception))

    @patch('feedbacks.services.ai_service.requests.post')
    def test_generate_returns_ai_response(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [
                {
                    'message': {
                        'content': 'پاسخ تستی AI'
                    }
                }
            ],
            'model': 'qwen2.5-7b',
            'usage': {
                'prompt_tokens': 10,
                'completion_tokens': 20,
                'total_tokens': 30,
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        ai = AIService()
        result = ai.generate([{'role': 'user', 'content': 'متن تست'}])

        self.assertIsInstance(result, AIResult)
        self.assertEqual(result.content, 'پاسخ تستی AI')
        self.assertEqual(result.model, 'qwen2.5-7b')
        self.assertEqual(result.prompt_tokens, 10)
        self.assertEqual(result.completion_tokens, 20)
        self.assertEqual(result.total_tokens, 30)

    @patch('feedbacks.services.ai_service.requests.post')
    def test_generate_sends_correct_request(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [
                {
                    'message': {
                        'content': 'پاسخ تستی AI'
                    }
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        ai = AIService()
        result = ai.generate([{'role': 'user', 'content': 'متن تست'}])

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args

        self.assertEqual(args[0], ai.url)
        self.assertEqual(kwargs['timeout'], 45.0)
        self.assertEqual(kwargs['json']['model'], ai.model)
        self.assertEqual(kwargs['json']['messages'][-1], {
            'role': 'user',
            'content': 'متن تست',
        })
        self.assertEqual(kwargs['json']['messages'][0]['role'], 'system')
        self.assertEqual(result.content, 'پاسخ تستی AI')

    @patch('feedbacks.services.ai_service.requests.post')
    def test_generate_usage_parsed_including_cached(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'پاسخ کش‌شده'}}],
            'model': 'qwen2.5-7b-instruct',
            'usage': {
                'prompt_tokens': 150,
                'completion_tokens': 60,
                'total_tokens': 210,
                'prompt_tokens_details': {
                    'cached_tokens': 45
                }
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        ai = AIService()
        result = ai.generate([{'role': 'user', 'content': 'متن تست'}])

        self.assertEqual(result.content, 'پاسخ کش‌شده')
        self.assertEqual(result.model, 'qwen2.5-7b-instruct')
        self.assertEqual(result.prompt_tokens, 150)
        self.assertEqual(result.completion_tokens, 60)
        self.assertEqual(result.cached_tokens, 45)
        self.assertEqual(result.total_tokens, 210)
        self.assertIsNotNone(result.raw_usage)

    @patch('feedbacks.services.ai_service.requests.post')
    def test_generate_usage_missing_results_in_none_fields(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'پاسخ بدون مصرف'}}],
            'model': 'test-model',
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        ai = AIService()
        result = ai.generate([{'role': 'user', 'content': 'متن تست'}])

        self.assertIsNone(result.prompt_tokens)
        self.assertIsNone(result.completion_tokens)
        self.assertIsNone(result.cached_tokens)
        self.assertIsNone(result.total_tokens)
        self.assertIsNone(result.raw_usage)

    @patch('feedbacks.services.ai_service.requests.post')
    def test_generate_malformed_json_raises_ai_service_error(self, mock_post):
        mock_response = Mock()
        mock_response.json.side_effect = ValueError('Invalid JSON')
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        ai = AIService()
        with self.assertRaises(AIServiceError):
            ai.generate([{'role': 'user', 'content': 'متن تست'}])

        mock_response.json.side_effect = None
        mock_response.json.return_value = {'choices': []}
        with self.assertRaises(AIServiceError):
            ai.generate([{'role': 'user', 'content': 'متن تست'}])

        mock_response.json.return_value = {'choices': [{}]}
        with self.assertRaises(AIServiceError):
            ai.generate([{'role': 'user', 'content': 'متن تست'}])

    @patch('feedbacks.services.ai_service.requests.post')
    def test_generate_connection_error_raises_ai_service_error(self, mock_post):
        mock_post.side_effect = ConnectionError('LM Studio is not available')

        ai = AIService()
        with self.assertRaises(AIServiceError):
            ai.generate([{'role': 'user', 'content': 'متن تست'}])

    @patch('feedbacks.services.ai_service.requests.post')
    def test_generate_timeout_raises_ai_service_error(self, mock_post):
        mock_post.side_effect = Timeout('LM Studio request timed out')

        ai = AIService()
        with self.assertRaises(AIServiceError):
            ai.generate([{'role': 'user', 'content': 'متن تست'}])

    @patch('feedbacks.services.ai_service.requests.post')
    def test_generate_http_error_raises_ai_service_error(self, mock_post):
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = HTTPError('500 Server Error')
        mock_post.return_value = mock_response

        ai = AIService()
        with self.assertRaises(AIServiceError):
            ai.generate([{'role': 'user', 'content': 'متن تست'}])

    def test_generate_missing_config_raises_ai_service_error(self):
        ai = AIService()
        ai.url = None
        with self.assertRaises(AIServiceError):
            ai.generate([{'role': 'user', 'content': 'متن تست'}])

        ai.url = 'http://localhost:1234'
        ai.model = None
        with self.assertRaises(AIServiceError):
            ai.generate([{'role': 'user', 'content': 'متن تست'}])


class DataMigrationTest(TransactionTestCase):

    def test_migrate_feedback_to_conversation(self):
        executor = MigrationExecutor(connection)
        try:
            # Migrate back to 0002
            executor.migrate([('feedbacks', '0002_feedback_ai_fields')])
            old_state = executor.loader.project_state(('feedbacks', '0002_feedback_ai_fields'))
            Feedback = old_state.apps.get_model('feedbacks', 'Feedback')

            Feedback.objects.create(
                type='request',
                title='درخواست قدیمی ۱',
                text='متن درخواست قدیمی ۱',
                ai_response='پاسخ قدیمی ۱',
                ai_model='qwen-old',
                prompt_tokens=12,
                completion_tokens=24,
                cached_tokens=4,
                total_tokens=36,
                ai_status='ok',
            )
            Feedback.objects.create(
                type='criticism',
                title='انتقاد قدیمی ۲',
                text='متن انتقاد قدیمی ۲',
                ai_response=None,
                ai_status='pending',
            )

            # Migrate forward through 0005
            executor.loader.build_graph()
            executor.migrate([('feedbacks', '0005_delete_feedback')])
            new_state = executor.loader.project_state(('feedbacks', '0005_delete_feedback'))
            Conversation = new_state.apps.get_model('feedbacks', 'Conversation')
            Message = new_state.apps.get_model('feedbacks', 'Message')

            self.assertEqual(Conversation.objects.count(), 2)

            conv1 = Conversation.objects.get(title='درخواست قدیمی ۱')
            self.assertEqual(conv1.type, 'request')
            conv1_msgs = list(Message.objects.filter(conversation=conv1).order_by('id'))
            self.assertEqual(len(conv1_msgs), 2)
            self.assertEqual(conv1_msgs[0].role, 'user')
            self.assertEqual(conv1_msgs[0].content, 'متن درخواست قدیمی ۱')
            self.assertEqual(conv1_msgs[1].role, 'assistant')
            self.assertEqual(conv1_msgs[1].content, 'پاسخ قدیمی ۱')
            self.assertEqual(conv1_msgs[1].ai_model, 'qwen-old')
            self.assertEqual(conv1_msgs[1].prompt_tokens, 12)
            self.assertEqual(conv1_msgs[1].completion_tokens, 24)
            self.assertEqual(conv1_msgs[1].cached_tokens, 4)
            self.assertEqual(conv1_msgs[1].total_tokens, 36)
            self.assertEqual(conv1_msgs[1].ai_status, 'ok')

            conv2 = Conversation.objects.get(title='انتقاد قدیمی ۲')
            self.assertEqual(conv2.type, 'criticism')
            conv2_msgs = list(Message.objects.filter(conversation=conv2).order_by('id'))
            self.assertEqual(len(conv2_msgs), 1)
            self.assertEqual(conv2_msgs[0].role, 'user')
            self.assertEqual(conv2_msgs[0].content, 'متن انتقاد قدیمی ۲')

        finally:
            # Restore latest migration state for test database
            executor.loader.build_graph()
            executor.migrate(executor.loader.graph.leaf_nodes())


class AuthenticationAndAuthorizationTest(TestCase):

    def setUp(self):
        self.user_a = User.objects.create_user(username='user_a', password='password_a')
        self.user_b = User.objects.create_user(username='user_b', password='password_b')
        self.conv_a = Conversation.objects.create(
            owner=self.user_a,
            type='request',
            title='گفتگوی کاربر الف',
        )
        self.msg_a = Message.objects.create(
            conversation=self.conv_a,
            role=Message.Role.USER,
            content='پیام کاربر الف',
        )

    def test_anonymous_redirected_to_login_on_all_views(self):
        routes = [
            reverse('feedback_list'),
            reverse('feedback_create'),
            reverse('feedback_update', args=[self.conv_a.pk]),
            reverse('feedback_delete', args=[self.conv_a.pk]),
            reverse('conversation_detail', args=[self.conv_a.pk]),
            reverse('ai_usage'),
        ]
        for url in routes:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse('login'), response.url)

    def test_user_b_gets_404_on_user_a_detail(self):
        self.client.force_login(self.user_b)
        response = self.client.get(reverse('conversation_detail', args=[self.conv_a.pk]))
        self.assertEqual(response.status_code, 404)

    def test_user_b_gets_404_on_user_a_post_message(self):
        self.client.force_login(self.user_b)
        response = self.client.post(
            reverse('conversation_detail', args=[self.conv_a.pk]),
            {'content': 'تلاش برای ارسال پیام غیرمجاز'},
        )
        self.assertEqual(response.status_code, 404)

    def test_user_b_gets_404_on_user_a_update(self):
        self.client.force_login(self.user_b)
        response_get = self.client.get(reverse('feedback_update', args=[self.conv_a.pk]))
        self.assertEqual(response_get.status_code, 404)

        response_post = self.client.post(
            reverse('feedback_update', args=[self.conv_a.pk]),
            {'type': 'suggestion', 'title': 'تغییر غیرمجاز'},
        )
        self.assertEqual(response_post.status_code, 404)

    def test_user_b_gets_404_on_user_a_delete(self):
        self.client.force_login(self.user_b)
        response_get = self.client.get(reverse('feedback_delete', args=[self.conv_a.pk]))
        self.assertEqual(response_get.status_code, 404)

        response_post = self.client.post(
            reverse('feedback_delete', args=[self.conv_a.pk])
        )
        self.assertEqual(response_post.status_code, 404)
        self.assertTrue(Conversation.objects.filter(pk=self.conv_a.pk).exists())

    def test_list_shows_only_own_conversations(self):
        conv_b = Conversation.objects.create(
            owner=self.user_b,
            type='criticism',
            title='گفتگوی کاربر ب',
        )

        self.client.force_login(self.user_a)
        response_a = self.client.get(reverse('feedback_list'))
        self.assertContains(response_a, 'گفتگوی کاربر الف')
        self.assertNotContains(response_a, 'گفتگوی کاربر ب')

        self.client.force_login(self.user_b)
        response_b = self.client.get(reverse('feedback_list'))
        self.assertContains(response_b, 'گفتگوی کاربر ب')
        self.assertNotContains(response_b, 'گفتگوی کاربر الف')

    @patch('feedbacks.services.replies.AIService.generate')
    def test_create_sets_owner(self, mock_generate):
        mock_generate.return_value = AIResult(
            content='پاسخ هوش مصنوعی',
            model='test',
            prompt_tokens=10,
            completion_tokens=10,
            cached_tokens=None,
            total_tokens=20,
            raw_usage=None,
        )
        self.client.force_login(self.user_a)
        response = self.client.post(
            reverse('feedback_create'),
            {'type': 'request', 'title': 'موضوع متعلق به الف', 'text': 'متن کاربر الف'},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        new_conv = Conversation.objects.get(title='موضوع متعلق به الف')
        self.assertEqual(new_conv.owner, self.user_a)

    def test_usage_totals_per_user(self):
        Message.objects.create(
            conversation=self.conv_a,
            role=Message.Role.ASSISTANT,
            content='پاسخ الف',
            total_tokens=120,
            prompt_tokens=80,
            completion_tokens=40,
            ai_status=Message.AIStatus.OK,
        )

        conv_b = Conversation.objects.create(owner=self.user_b, type='suggestion', title='گفتگو ب')
        Message.objects.create(
            conversation=conv_b,
            role=Message.Role.ASSISTANT,
            content='پاسخ ب',
            total_tokens=300,
            prompt_tokens=200,
            completion_tokens=100,
            ai_status=Message.AIStatus.OK,
        )

        self.client.force_login(self.user_a)
        resp_a = self.client.get(reverse('ai_usage'))
        self.assertEqual(resp_a.context['usage']['total_tokens'], 120)

        self.client.force_login(self.user_b)
        resp_b = self.client.get(reverse('ai_usage'))
        self.assertEqual(resp_b.context['usage']['total_tokens'], 300)

    def test_signup_creates_user_and_logs_in(self):
        response = self.client.post(
            reverse('signup'),
            {
                'username': 'newuser123',
                'password1': 'SecretPass999!',
                'password2': 'SecretPass999!',
            },
        )
        self.assertRedirects(response, reverse('feedback_list'))
        self.assertTrue(User.objects.filter(username='newuser123').exists())
        user = User.objects.get(username='newuser123')
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_logout_via_post(self):
        self.client.force_login(self.user_a)
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('login'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_ai_context_includes_type_and_title(self):
        conv = Conversation.objects.create(
            type='suggestion',
            title='پیشنهاد برای سامانه',
        )
        Message.objects.create(conversation=conv, role=Message.Role.USER, content='پیام اولیه')
        context = conv.get_context_prompt()
        self.assertIn('پیشنهاد', context)
        self.assertIn('پیشنهاد برای سامانه', context)


class SingleLeadingSystemMessageTests(TestCase):

    @patch('feedbacks.services.ai_service.requests.post')
    def test_generate_merges_prompt_and_context_into_single_system_message(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'پاسخ هوش مصنوعی'}}],
            'model': 'qwen-test',
            'usage': {'prompt_tokens': 10, 'completion_tokens': 10, 'total_tokens': 20},
        }
        mock_post.return_value = mock_response

        ai = AIService()
        ai.url = 'http://localhost:1234/v1/chat/completions'
        ai.model = 'qwen-test'
        history = [
            {'role': 'user', 'content': 'سلام'},
            {'role': 'assistant', 'content': 'درود'},
            {'role': 'user', 'content': 'سوال بعدی'},
        ]
        context = "نوع پیام: درخواست\nعنوان: عنوان تستی"

        ai.generate(history, context=context)

        self.assertTrue(mock_post.called)
        sent_payload = mock_post.call_args[1]['json']
        sent_messages = sent_payload['messages']

        # Total messages: 1 system + 3 history
        self.assertEqual(len(sent_messages), 4)

        # Leading message is system and contains both prompt and conversation context
        self.assertEqual(sent_messages[0]['role'], 'system')
        self.assertIn("نوع پیام: درخواست", sent_messages[0]['content'])
        self.assertIn("عنوان: عنوان تستی", sent_messages[0]['content'])

        # No subsequent messages are system messages
        system_msgs = [m for m in sent_messages if m['role'] == 'system']
        self.assertEqual(len(system_msgs), 1)

        # History messages retain role and content
        self.assertEqual(sent_messages[1], {'role': 'user', 'content': 'سلام'})
        self.assertEqual(sent_messages[2], {'role': 'assistant', 'content': 'درود'})
        self.assertEqual(sent_messages[3], {'role': 'user', 'content': 'سوال بعدی'})


class ProdSettingsTests(TestCase):

    def test_prod_settings_raise_without_secret_key(self):
        cmd = [
            sys.executable,
            '-c',
            (
                'import os; '
                'os.environ.pop("DJANGO_SECRET_KEY", None); '
                'os.environ["DJANGO_SETTINGS_MODULE"] = "feedback_system.settings.prod"; '
                'import django; '
                'django.setup()'
            )
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("ImproperlyConfigured", proc.stderr)
        self.assertIn("DJANGO_SECRET_KEY", proc.stderr)

    def test_prod_settings_with_secret_key_and_allowed_hosts(self):
        cmd = [
            sys.executable,
            '-c',
            (
                'import os; '
                'os.environ["DJANGO_SECRET_KEY"] = "dummy-secret-key-for-test-xyz"; '
                'os.environ["DJANGO_ALLOWED_HOSTS"] = "example.com,app.example.com"; '
                'os.environ["DJANGO_SETTINGS_MODULE"] = "feedback_system.settings.prod"; '
                'from django.conf import settings; '
                'print(settings.DEBUG, settings.SESSION_COOKIE_SECURE, settings.CSRF_COOKIE_SECURE, settings.SECURE_HSTS_SECONDS, settings.ALLOWED_HOSTS)'
            )
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("False True True 31536000", proc.stdout)
        self.assertIn("['example.com', 'app.example.com']", proc.stdout)


class LoggingAndFailureVisibilityTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='loguser', password='password')
        self.conv = Conversation.objects.create(
            owner=self.user,
            type='request',
            title='تست لاگ خطا محرمانه',
        )

    @patch('feedbacks.services.replies.AIService.generate')
    def test_ai_service_error_logged_without_pii(self, mock_generate):
        mock_generate.side_effect = AIServiceError("Connection to LM Studio timed out")
        with self.assertLogs('feedbacks.services.replies', level='ERROR') as cm:
            msg = create_ai_reply(self.conv)

        self.assertEqual(msg.ai_status, Message.AIStatus.FAILED)
        self.assertIn("Connection to LM Studio timed out", msg.ai_error)

        # Check log output: contains conversation id and exception class
        expected_msg = f"AI service failed for conversation {self.conv.pk}: AIServiceError"
        self.assertTrue(any(expected_msg in log for log in cm.output))

        # Check no conversation title or prompt content in the log message
        for log in cm.output:
            self.assertNotIn("تست لاگ خطا محرمانه", log)

    @patch('feedbacks.services.replies.AIService.generate')
    def test_unexpected_error_logged(self, mock_generate):
        mock_generate.side_effect = RuntimeError("Fatal crash in parser")
        with self.assertLogs('feedbacks.services.replies', level='ERROR') as cm:
            msg = create_ai_reply(self.conv)

        self.assertEqual(msg.ai_status, Message.AIStatus.FAILED)
        expected_msg = f"AI service failed for conversation {self.conv.pk}: RuntimeError"
        self.assertTrue(any(expected_msg in log for log in cm.output))


class ConversationQuerySetTests(TestCase):

    def setUp(self):
        self.u1 = User.objects.create_user(username='user1', password='p1')
        self.u2 = User.objects.create_user(username='user2', password='p2')
        self.c1 = Conversation.objects.create(owner=self.u1, type='request', title='C1')
        self.c2 = Conversation.objects.create(owner=self.u2, type='criticism', title='C2')
        Message.objects.create(conversation=self.c1, role=Message.Role.USER, content='M1')
        Message.objects.create(conversation=self.c1, role=Message.Role.ASSISTANT, content='M2')

    def test_for_user_filters_correctly(self):
        self.assertEqual(list(Conversation.objects.for_user(self.u1)), [self.c1])
        self.assertEqual(list(Conversation.objects.for_user(self.u2)), [self.c2])

    def test_with_message_count_annotates_correctly(self):
        annotated_c1 = Conversation.objects.with_message_count().get(pk=self.c1.pk)
        annotated_c2 = Conversation.objects.with_message_count().get(pk=self.c2.pk)
        self.assertEqual(annotated_c1.message_count, 2)
        self.assertEqual(annotated_c2.message_count, 0)


class QueryCountTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='qcuser', password='password')
        for i in range(5):
            c = Conversation.objects.create(
                owner=self.user,
                type='request',
                title=f'گفتگو {i}',
            )
            Message.objects.create(conversation=c, role=Message.Role.USER, content=f'پیام {i}')
        self.detail_conv = Conversation.objects.first()
        for j in range(3):
            Message.objects.create(
                conversation=self.detail_conv,
                role=Message.Role.ASSISTANT,
                content=f'پاسخ {j}',
                ai_status=Message.AIStatus.OK,
            )

    def test_feedback_list_query_count(self):
        self.client.force_login(self.user)
        # Expected queries: session lookup, user lookup, 1 annotated conversation query
        with self.assertNumQueries(3):
            response = self.client.get(reverse('feedback_list'))
            self.assertEqual(response.status_code, 200)

    def test_conversation_detail_query_count(self):
        self.client.force_login(self.user)
        # Expected queries: session lookup, user lookup, conversation query, prefetched messages query
        with self.assertNumQueries(4):
            response = self.client.get(reverse('conversation_detail', args=[self.detail_conv.pk]))
            self.assertEqual(response.status_code, 200)


class RoleAndPermissionTests(TestCase):
    def setUp(self):
        self.expert_group, _ = Group.objects.get_or_create(name='experts')
        self.owner = User.objects.create_user(username='owner', password='pw')
        self.other_user = User.objects.create_user(username='other', password='pw')
        self.expert = User.objects.create_user(username='expert1', password='pw')
        self.expert.groups.add(self.expert_group)
        self.expert2 = User.objects.create_user(username='expert2', password='pw')
        self.expert2.groups.add(self.expert_group)
        self.staff = User.objects.create_user(username='staff', password='pw', is_staff=True)

        self.conv_ai = Conversation.objects.create(owner=self.owner, type='request', title='Conv AI', status=Conversation.Status.AI)
        self.conv_waiting = Conversation.objects.create(owner=self.owner, type='request', title='Conv Waiting', status=Conversation.Status.WAITING_EXPERT)
        self.conv_active = Conversation.objects.create(owner=self.owner, expert=self.expert, type='request', title='Conv Active', status=Conversation.Status.EXPERT_ACTIVE)
        self.conv_closed = Conversation.objects.create(owner=self.owner, expert=self.expert, type='request', title='Conv Closed', status=Conversation.Status.CLOSED)

    def test_is_expert(self):
        self.assertTrue(is_expert(self.expert))
        self.assertFalse(is_expert(self.owner))
        self.assertFalse(is_expert(self.staff))
        self.assertFalse(is_expert(None))

    def test_can_view(self):
        # Owner can view all their conversations
        self.assertTrue(can_view(self.owner, self.conv_ai))
        self.assertTrue(can_view(self.owner, self.conv_waiting))
        self.assertTrue(can_view(self.owner, self.conv_active))
        self.assertTrue(can_view(self.owner, self.conv_closed))

        # Staff can view everything
        self.assertTrue(can_view(self.staff, self.conv_ai))
        self.assertTrue(can_view(self.staff, self.conv_waiting))
        self.assertTrue(can_view(self.staff, self.conv_active))
        self.assertTrue(can_view(self.staff, self.conv_closed))

        # Expert can view waiting and assigned
        self.assertTrue(can_view(self.expert, self.conv_waiting))
        self.assertTrue(can_view(self.expert, self.conv_active))
        self.assertTrue(can_view(self.expert, self.conv_closed))
        self.assertFalse(can_view(self.expert, self.conv_ai))
        self.assertFalse(can_view(self.expert2, self.conv_active))

        # Unrelated user cannot view
        self.assertFalse(can_view(self.other_user, self.conv_ai))
        self.assertFalse(can_view(self.other_user, self.conv_waiting))
        self.assertFalse(can_view(self.other_user, self.conv_active))

    def test_can_post(self):
        # Owner can post on open conversations
        self.assertTrue(can_post(self.owner, self.conv_ai))
        self.assertTrue(can_post(self.owner, self.conv_waiting))
        self.assertTrue(can_post(self.owner, self.conv_active))
        self.assertFalse(can_post(self.owner, self.conv_closed))

        # Assigned expert can post on expert_active
        self.assertTrue(can_post(self.expert, self.conv_active))
        self.assertFalse(can_post(self.expert, self.conv_waiting))
        self.assertFalse(can_post(self.expert, self.conv_ai))
        self.assertFalse(can_post(self.expert, self.conv_closed))
        self.assertFalse(can_post(self.expert2, self.conv_active))

        # Staff cannot post unless assigned expert or owner
        self.assertFalse(can_post(self.staff, self.conv_active))

    def test_can_claim(self):
        self.assertTrue(can_claim(self.expert, self.conv_waiting))
        self.assertFalse(can_claim(self.expert, self.conv_ai))
        self.assertFalse(can_claim(self.expert, self.conv_active))
        self.assertFalse(can_claim(self.owner, self.conv_waiting))
        self.assertFalse(can_claim(self.other_user, self.conv_waiting))

        # Owner who is also an expert cannot claim
        self.owner.groups.add(self.expert_group)
        self.assertFalse(can_claim(self.owner, self.conv_waiting))

        # Another expert cannot claim already assigned
        self.assertFalse(can_claim(self.expert2, self.conv_active))

    def test_can_release(self):
        self.assertTrue(can_release(self.expert, self.conv_active))
        self.assertFalse(can_release(self.expert2, self.conv_active))
        self.assertFalse(can_release(self.owner, self.conv_active))
        self.assertFalse(can_release(self.expert, self.conv_waiting))
        self.assertFalse(can_release(self.expert, self.conv_closed))

    def test_can_close(self):
        # Staff can close any open conversation
        self.assertTrue(can_close(self.staff, self.conv_ai))
        self.assertTrue(can_close(self.staff, self.conv_waiting))
        self.assertTrue(can_close(self.staff, self.conv_active))
        self.assertFalse(can_close(self.staff, self.conv_closed))

        # Assigned expert can close assigned
        self.assertTrue(can_close(self.expert, self.conv_active))
        self.assertFalse(can_close(self.expert, self.conv_ai))
        self.assertFalse(can_close(self.expert2, self.conv_active))

        # Owner cannot close
        self.assertFalse(can_close(self.owner, self.conv_active))
        self.assertFalse(can_close(self.owner, self.conv_ai))


class TransitionTests(TestCase):
    def setUp(self):
        self.expert_group, _ = Group.objects.get_or_create(name='experts')
        self.owner = User.objects.create_user(username='towner', password='pw')
        self.other_user = User.objects.create_user(username='tother', password='pw')
        self.expert = User.objects.create_user(username='texpert', password='pw')
        self.expert.groups.add(self.expert_group)
        self.expert2 = User.objects.create_user(username='texpert2', password='pw')
        self.expert2.groups.add(self.expert_group)
        self.staff = User.objects.create_user(username='tstaff', password='pw', is_staff=True)

    def test_allowed_transitions(self):
        # 1. ai -> waiting_expert by owner
        c = Conversation.objects.create(owner=self.owner, type='request', title='T1', status=Conversation.Status.AI)
        c.transition_to(Conversation.Status.WAITING_EXPERT, self.owner)
        self.assertEqual(c.status, Conversation.Status.WAITING_EXPERT)
        self.assertIsNone(c.expert)

        # 2. waiting_expert -> expert_active by expert
        c.transition_to(Conversation.Status.EXPERT_ACTIVE, self.expert)
        self.assertEqual(c.status, Conversation.Status.EXPERT_ACTIVE)
        self.assertEqual(c.expert, self.expert)

        # 3. expert_active -> ai by assigned expert
        c.transition_to(Conversation.Status.AI, self.expert)
        self.assertEqual(c.status, Conversation.Status.AI)
        self.assertIsNone(c.expert)

        # 4. ai -> closed by staff
        c.transition_to(Conversation.Status.CLOSED, self.staff)
        self.assertEqual(c.status, Conversation.Status.CLOSED)

        # 5. waiting_expert -> closed by staff
        c2 = Conversation.objects.create(owner=self.owner, type='request', title='T2', status=Conversation.Status.WAITING_EXPERT)
        c2.transition_to(Conversation.Status.CLOSED, self.staff)
        self.assertEqual(c2.status, Conversation.Status.CLOSED)

        # 6. expert_active -> closed by assigned expert
        c3 = Conversation.objects.create(owner=self.owner, expert=self.expert, type='request', title='T3', status=Conversation.Status.EXPERT_ACTIVE)
        c3.transition_to(Conversation.Status.CLOSED, self.expert)
        self.assertEqual(c3.status, Conversation.Status.CLOSED)

    def test_rejected_transitions_raise_validation_error(self):
        c = Conversation.objects.create(owner=self.owner, type='request', title='T_fail', status=Conversation.Status.AI)

        # Cannot jump ai -> expert_active directly
        with self.assertRaises(ValidationError):
            c.transition_to(Conversation.Status.EXPERT_ACTIVE, self.expert)

        # Non-owner cannot request expert
        with self.assertRaises(ValidationError):
            c.transition_to(Conversation.Status.WAITING_EXPERT, self.other_user)

        # Transition to same status rejected
        with self.assertRaises(ValidationError):
            c.transition_to(Conversation.Status.AI, self.owner)

        # Transition to waiting_expert
        c.transition_to(Conversation.Status.WAITING_EXPERT, self.owner)

        # Non-expert cannot claim
        with self.assertRaises(ValidationError):
            c.transition_to(Conversation.Status.EXPERT_ACTIVE, self.other_user)

        # Owner cannot claim even if in experts group
        self.owner.groups.add(self.expert_group)
        with self.assertRaises(ValidationError):
            c.transition_to(Conversation.Status.EXPERT_ACTIVE, self.owner)

        # Cannot jump waiting_expert -> ai
        with self.assertRaises(ValidationError):
            c.transition_to(Conversation.Status.AI, self.expert)

        # Claim
        c.transition_to(Conversation.Status.EXPERT_ACTIVE, self.expert)

        # Another expert cannot claim already active
        with self.assertRaises(ValidationError):
            c.transition_to(Conversation.Status.EXPERT_ACTIVE, self.expert2)

        # Unassigned expert cannot release
        with self.assertRaises(ValidationError):
            c.transition_to(Conversation.Status.AI, self.expert2)

        # Normal user cannot close
        with self.assertRaises(ValidationError):
            c.transition_to(Conversation.Status.CLOSED, self.owner)

        # Close by assigned expert
        c.transition_to(Conversation.Status.CLOSED, self.expert)

        # Closed is terminal: cannot transition anywhere
        with self.assertRaises(ValidationError):
            c.transition_to(Conversation.Status.AI, self.staff)
        with self.assertRaises(ValidationError):
            c.transition_to(Conversation.Status.WAITING_EXPERT, self.owner)
        with self.assertRaises(ValidationError):
            c.transition_to(Conversation.Status.EXPERT_ACTIVE, self.expert)
        with self.assertRaises(ValidationError):
            c.transition_to(Conversation.Status.CLOSED, self.staff)


class AsMessagesSprint06Tests(TestCase):
    def test_as_messages_maps_expert_to_assistant(self):
        c = Conversation.objects.create(type='request', title='Map Test')
        Message.objects.create(conversation=c, role=Message.Role.USER, content='User msg')
        Message.objects.create(conversation=c, role=Message.Role.EXPERT, content='Expert msg')
        Message.objects.create(conversation=c, role=Message.Role.ASSISTANT, content='AI msg', ai_status=Message.AIStatus.OK)
        Message.objects.create(conversation=c, role=Message.Role.ASSISTANT, content='Failed AI msg', ai_status=Message.AIStatus.FAILED)

        messages = c.as_messages()
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0], {'role': 'user', 'content': 'User msg'})
        self.assertEqual(messages[1], {'role': 'assistant', 'content': 'Expert msg'})
        self.assertEqual(messages[2], {'role': 'assistant', 'content': 'AI msg'})


class ExpertWorkflowAITests(TestCase):
    def setUp(self):
        self.expert_group, _ = Group.objects.get_or_create(name='experts')
        self.user = User.objects.create_user(username='wfuser', password='password')
        self.expert = User.objects.create_user(username='wfexpert', password='password')
        self.expert.groups.add(self.expert_group)

    @patch('feedbacks.views.create_ai_reply')
    def test_create_view_with_at_expert_skips_ai(self, mock_reply):
        self.client.force_login(self.user)
        response = self.client.post(reverse('feedback_create'), {
            'type': 'request',
            'title': 'درخواست با کارشناس',
            'text': '@expert سلام لطفاً کارشناس بررسی نماید',
        })
        self.assertEqual(response.status_code, 302)
        conv = Conversation.objects.get(title='درخواست با کارشناس')
        self.assertEqual(conv.status, Conversation.Status.WAITING_EXPERT)
        self.assertEqual(conv.owner, self.user)
        msg = conv.messages.first()
        self.assertEqual(msg.role, Message.Role.USER)
        self.assertEqual(msg.author, self.user)
        mock_reply.assert_not_called()

    @patch('feedbacks.views.create_ai_reply')
    def test_detail_view_with_at_expert_transitions_and_skips_ai(self, mock_reply):
        conv = Conversation.objects.create(owner=self.user, type='request', title='Conv 1', status=Conversation.Status.AI)
        self.client.force_login(self.user)
        response = self.client.post(reverse('conversation_detail', args=[conv.pk]), {
            'content': '@expert پیام کاربر به کارشناس',
        })
        self.assertEqual(response.status_code, 302)
        conv.refresh_from_db()
        self.assertEqual(conv.status, Conversation.Status.WAITING_EXPERT)
        last_msg = conv.messages.last()
        self.assertEqual(last_msg.role, Message.Role.USER)
        self.assertEqual(last_msg.author, self.user)
        mock_reply.assert_not_called()

    @patch('feedbacks.views.create_ai_reply')
    def test_detail_view_ai_silent_while_waiting_expert(self, mock_reply):
        conv = Conversation.objects.create(owner=self.user, type='request', title='Conv Waiting', status=Conversation.Status.WAITING_EXPERT)
        self.client.force_login(self.user)
        response = self.client.post(reverse('conversation_detail', args=[conv.pk]), {
            'content': 'یک پیام دیگر در حین انتظار',
        })
        self.assertEqual(response.status_code, 302)
        conv.refresh_from_db()
        self.assertEqual(conv.status, Conversation.Status.WAITING_EXPERT)
        mock_reply.assert_not_called()

    @patch('feedbacks.views.create_ai_reply')
    def test_detail_view_ai_silent_while_expert_active(self, mock_reply):
        conv = Conversation.objects.create(
            owner=self.user,
            expert=self.expert,
            type='request',
            title='Conv Active',
            status=Conversation.Status.EXPERT_ACTIVE,
        )
        # Owner post
        self.client.force_login(self.user)
        response = self.client.post(reverse('conversation_detail', args=[conv.pk]), {
            'content': 'پیام کاربر در گفتگوی فعال',
        })
        self.assertEqual(response.status_code, 302)
        mock_reply.assert_not_called()
        self.assertEqual(conv.messages.last().role, Message.Role.USER)

        # Expert post
        self.client.force_login(self.expert)
        response2 = self.client.post(reverse('conversation_detail', args=[conv.pk]), {
            'content': 'پاسخ کارشناس',
        })
        self.assertEqual(response2.status_code, 302)
        mock_reply.assert_not_called()
        expert_msg = conv.messages.last()
        self.assertEqual(expert_msg.role, Message.Role.EXPERT)
        self.assertEqual(expert_msg.author, self.expert)

    @patch('feedbacks.views.create_ai_reply')
    def test_closed_conversation_rejects_new_messages(self, mock_reply):
        conv = Conversation.objects.create(
            owner=self.user,
            expert=self.expert,
            type='request',
            title='Conv Closed',
            status=Conversation.Status.CLOSED,
        )
        self.client.force_login(self.user)
        response = self.client.post(reverse('conversation_detail', args=[conv.pk]), {
            'content': 'تلاش برای ارسال پیام در گفتگوی بسته',
        })
        self.assertEqual(response.status_code, 404)
        mock_reply.assert_not_called()
        self.assertEqual(conv.messages.count(), 0)


class ExpertEndpointsAuthorizationTests(TestCase):
    def setUp(self):
        self.expert_group, _ = Group.objects.get_or_create(name='experts')
        self.owner = User.objects.create_user(username='eowner', password='pw')
        self.other_user = User.objects.create_user(username='eother', password='pw')
        self.expert = User.objects.create_user(username='eexpert1', password='pw')
        self.expert.groups.add(self.expert_group)
        self.expert2 = User.objects.create_user(username='eexpert2', password='pw')
        self.expert2.groups.add(self.expert_group)
        self.staff = User.objects.create_user(username='estaff', password='pw', is_staff=True)

    def test_request_expert_endpoint(self):
        conv = Conversation.objects.create(owner=self.owner, type='request', title='RE Conv', status=Conversation.Status.AI)

        # Other user gets 404
        self.client.force_login(self.other_user)
        r = self.client.post(reverse('conversation_request_expert', args=[conv.pk]))
        self.assertEqual(r.status_code, 404)

        # Owner succeeds
        self.client.force_login(self.owner)
        r2 = self.client.post(reverse('conversation_request_expert', args=[conv.pk]))
        self.assertEqual(r2.status_code, 302)
        conv.refresh_from_db()
        self.assertEqual(conv.status, Conversation.Status.WAITING_EXPERT)

    def test_claim_endpoint_authorizations(self):
        conv = Conversation.objects.create(owner=self.owner, type='request', title='Claim Conv', status=Conversation.Status.WAITING_EXPERT)

        # Owner cannot claim (returns 404)
        self.client.force_login(self.owner)
        r = self.client.post(reverse('conversation_claim', args=[conv.pk]))
        self.assertEqual(r.status_code, 404)

        # Non-expert cannot claim (returns 404)
        self.client.force_login(self.other_user)
        r2 = self.client.post(reverse('conversation_claim', args=[conv.pk]))
        self.assertEqual(r2.status_code, 404)

        # Expert claims successfully
        self.client.force_login(self.expert)
        r3 = self.client.post(reverse('conversation_claim', args=[conv.pk]))
        self.assertEqual(r3.status_code, 302)
        conv.refresh_from_db()
        self.assertEqual(conv.status, Conversation.Status.EXPERT_ACTIVE)
        self.assertEqual(conv.expert, self.expert)

        # Another expert cannot claim already-claimed conversation (returns 404)
        self.client.force_login(self.expert2)
        r4 = self.client.post(reverse('conversation_claim', args=[conv.pk]))
        self.assertEqual(r4.status_code, 404)

    def test_expert_cannot_post_to_unassigned_conversation(self):
        conv = Conversation.objects.create(owner=self.owner, type='request', title='Unassigned', status=Conversation.Status.WAITING_EXPERT)
        self.client.force_login(self.expert)
        r = self.client.post(reverse('conversation_detail', args=[conv.pk]), {'content': 'Expert unsolicited post'})
        self.assertEqual(r.status_code, 404)

    def test_release_endpoint(self):
        conv = Conversation.objects.create(
            owner=self.owner,
            expert=self.expert,
            type='request',
            title='Release Conv',
            status=Conversation.Status.EXPERT_ACTIVE,
        )

        # Another expert gets 404
        self.client.force_login(self.expert2)
        r = self.client.post(reverse('conversation_release', args=[conv.pk]))
        self.assertEqual(r.status_code, 404)

        # Assigned expert succeeds
        self.client.force_login(self.expert)
        r2 = self.client.post(reverse('conversation_release', args=[conv.pk]))
        self.assertEqual(r2.status_code, 302)
        conv.refresh_from_db()
        self.assertEqual(conv.status, Conversation.Status.AI)
        self.assertIsNone(conv.expert)

    def test_close_endpoint(self):
        conv = Conversation.objects.create(
            owner=self.owner,
            expert=self.expert,
            type='request',
            title='Close Conv',
            status=Conversation.Status.EXPERT_ACTIVE,
        )

        # Owner cannot close
        self.client.force_login(self.owner)
        r = self.client.post(reverse('conversation_close', args=[conv.pk]))
        self.assertEqual(r.status_code, 404)

        # Unassigned expert cannot close
        self.client.force_login(self.expert2)
        r2 = self.client.post(reverse('conversation_close', args=[conv.pk]))
        self.assertEqual(r2.status_code, 404)

        # Staff can close
        self.client.force_login(self.staff)
        r3 = self.client.post(reverse('conversation_close', args=[conv.pk]))
        self.assertEqual(r3.status_code, 302)
        conv.refresh_from_db()
        self.assertEqual(conv.status, Conversation.Status.CLOSED)

    def test_expert_queue_view_access(self):
        # Anonymous redirects to login
        r = self.client.get(reverse('expert_queue'))
        self.assertEqual(r.status_code, 302)

        # Regular user gets 404
        self.client.force_login(self.owner)
        r2 = self.client.get(reverse('expert_queue'))
        self.assertEqual(r2.status_code, 404)

        # Expert gets 200
        self.client.force_login(self.expert)
        r3 = self.client.get(reverse('expert_queue'))
        self.assertEqual(r3.status_code, 200)

        # Staff gets 200
        self.client.force_login(self.staff)
        r4 = self.client.get(reverse('expert_queue'))
        self.assertEqual(r4.status_code, 200)


class AdminSprint06Tests(TestCase):
    def test_admin_close_selected_action(self):
        from .admin import ConversationAdmin
        from django.contrib.admin.sites import AdminSite

        admin_site = AdminSite()
        conv_admin = ConversationAdmin(Conversation, admin_site)

        staff = User.objects.create_user(username='adminstaff', password='pw', is_staff=True)
        c1 = Conversation.objects.create(type='request', title='Adm 1', status=Conversation.Status.AI)
        c2 = Conversation.objects.create(type='request', title='Adm 2', status=Conversation.Status.WAITING_EXPERT)
        c3 = Conversation.objects.create(type='request', title='Adm 3', status=Conversation.Status.CLOSED)

        request = Mock()
        request.user = staff

        qs = Conversation.objects.filter(pk__in=[c1.pk, c2.pk, c3.pk])
        conv_admin.close_selected(request, qs)

        c1.refresh_from_db()
        c2.refresh_from_db()
        c3.refresh_from_db()

        self.assertEqual(c1.status, Conversation.Status.CLOSED)
        self.assertEqual(c2.status, Conversation.Status.CLOSED)
        self.assertEqual(c3.status, Conversation.Status.CLOSED)


class TokenConstraintSprint06Tests(TestCase):
    def test_expert_message_token_fields_null_constraint(self):
        c = Conversation.objects.create(type='request', title='Constraint Test')
        # Valid expert message with null tokens
        msg = Message.objects.create(
            conversation=c,
            role=Message.Role.EXPERT,
            content='Expert answer',
        )
        self.assertIsNotNone(msg.pk)

        # Invalid expert message with prompt_tokens violates CheckConstraint
        with self.assertRaises(IntegrityError):
            Message.objects.create(
                conversation=c,
                role=Message.Role.EXPERT,
                content='Invalid tokens',
                prompt_tokens=10,
            )


