from unittest.mock import Mock, patch
from requests.exceptions import ConnectionError, HTTPError, Timeout

from django.contrib.messages import get_messages
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

    def test_feedback_list_empty(self):
        response = self.client.get(reverse('feedback_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'هنوز موردی ثبت نشده است.')

    def test_feedback_list_displays_conversations(self):
        conv = Conversation.objects.create(type='request', title='عنوان تستی گفتگو')
        Message.objects.create(conversation=conv, role=Message.Role.USER, content='متن پیام اول')
        response = self.client.get(reverse('feedback_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'عنوان تستی گفتگو')
        self.assertContains(response, reverse('conversation_detail', args=[conv.pk]))

    def test_feedback_list_num_queries(self):
        for i in range(5):
            conv = Conversation.objects.create(
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

        with self.assertNumQueries(1):
            response = self.client.get(reverse('feedback_list'))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.context['conversations']), 5)
            self.assertEqual(response.context['conversations'][0].message_count, 2)


class FeedbackCreateViewTest(TestCase):

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
        self.conv = Conversation.objects.create(
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
        self.conv = Conversation.objects.create(
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
        self.conv = Conversation.objects.create(
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

        # Ensure full history was passed to AI
        mock_generate.assert_called_once()
        sent_messages = mock_generate.call_args[0][0]
        self.assertEqual(len(sent_messages), 2)
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

    def test_usage_page_totals_correct(self):
        conv1 = Conversation.objects.create(type='request', title='گفتگو ۱')
        conv2 = Conversation.objects.create(type='criticism', title='گفتگو ۲')

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
