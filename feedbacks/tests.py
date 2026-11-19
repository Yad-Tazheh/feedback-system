from unittest.mock import Mock, patch
from requests.exceptions import ConnectionError, HTTPError, Timeout

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from .forms import FeedbackForm
from .models import Feedback
from .services.ai_service import AIService, AIServiceError, AIResult


class FeedbackFormTest(TestCase):

    def test_valid_form(self):
        form = FeedbackForm({
            'type': 'request',
            'title': 'عنوان تست',
            'text': 'متن تست',
        })

        self.assertTrue(form.is_valid())

    def test_title_is_required(self):
        form = FeedbackForm({
            'type': 'request',
            'title': '',
            'text': 'متن تست',
        })

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors['title'][0],
            'لطفاً عنوان را وارد کنید.'
        )

    def test_text_is_required(self):
        form = FeedbackForm({
            'type': 'request',
            'title': 'عنوان تست',
            'text': '',
        })

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors['text'][0],
            'لطفاً متن بازخورد را وارد کنید.'
        )

    def test_invalid_type(self):
        form = FeedbackForm({
            'type': 'invalid_type',
            'title': 'عنوان تست',
            'text': 'متن تست',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('type', form.errors)

    def test_title_max_length(self):
        form = FeedbackForm({
            'type': 'request',
            'title': 'a' * 201,
            'text': 'متن تست',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)


class FeedbackModelTest(TestCase):

    def test_create_feedback(self):
        feedback = Feedback.objects.create(
            type='request',
            title='عنوان تست',
            text='متن تست',
        )

        self.assertEqual(feedback.title, 'عنوان تست')
        self.assertEqual(feedback.text, 'متن تست')
        self.assertEqual(feedback.type, 'request')

    def test_created_at_is_set(self):
        feedback = Feedback.objects.create(
            type='request',
            title='عنوان تست',
            text='متن تست',
        )

        self.assertIsNotNone(feedback.created_at)

    def test_ai_response_is_optional(self):
        feedback = Feedback.objects.create(
            type='request',
            title='عنوان تست',
            text='متن تست',
        )

        self.assertIsNone(feedback.ai_response)

    def test_default_ai_status_is_pending(self):
        feedback = Feedback.objects.create(
            type='request',
            title='عنوان تست',
            text='متن تست',
        )

        self.assertEqual(feedback.ai_status, 'pending')

    def test_as_messages(self):
        feedback = Feedback.objects.create(
            type='request',
            title='عنوان تستی',
            text='متن تستی بازخورد',
        )

        messages = feedback.as_messages()
        self.assertIsInstance(messages, list)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['role'], 'user')
        self.assertIn('عنوان تستی', messages[0]['content'])
        self.assertIn('متن تستی بازخورد', messages[0]['content'])


class FeedbackViewTest(TestCase):

    def setUp(self):
        self.feedback = Feedback.objects.create(
            type='request',
            title='عنوان تست',
            text='متن تست',
        )

    def test_feedback_list(self):
        response = self.client.get(
            reverse('feedback_list')
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'عنوان تست')

    @patch('feedbacks.views.AIService.generate')
    def test_feedback_create_post(self, mock_generate):
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

        feedback = Feedback.objects.get(
            title='Feedback جدید'
        )

        self.assertEqual(feedback.text, 'متن feedback جدید')
        self.assertEqual(feedback.ai_response, 'پاسخ تست هوش مصنوعی')
        self.assertEqual(feedback.ai_status, 'ok')
        self.assertEqual(feedback.ai_model, 'test-model')
        self.assertEqual(feedback.prompt_tokens, 15)
        self.assertEqual(feedback.completion_tokens, 25)
        self.assertEqual(feedback.cached_tokens, 5)
        self.assertEqual(feedback.total_tokens, 40)
        self.assertIsNotNone(feedback.ai_responded_at)

        mock_generate.assert_called_once()
        self.assertContains(response, 'پاسخ تست هوش مصنوعی')

    @patch('feedbacks.views.AIService.generate')
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

        feedback = Feedback.objects.get(
            title='Feedback همراه با خطای AI'
        )

        self.assertEqual(feedback.ai_status, 'failed')
        self.assertIn('LM Studio is down', feedback.ai_error)
        self.assertIsNone(feedback.ai_response)

    def test_feedback_create_get(self):
        response = self.client.get(
            reverse('feedback_create')
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(
            response.context['form'],
            FeedbackForm
        )

    def test_feedback_create_invalid(self):
        response = self.client.post(
            reverse('feedback_create'),
            {
                'type': 'request',
                'title': '',
                'text': 'متن تست',
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Feedback.objects.count(),
            1
        )
        self.assertIn(
            'title',
            response.context['form'].errors
        )

    def test_feedback_update_get(self):
        response = self.client.get(
            reverse(
                'feedback_update',
                args=[self.feedback.pk]
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(
            response.context['form'],
            FeedbackForm
        )

    def test_feedback_update_post(self):
        response = self.client.post(
            reverse(
                'feedback_update',
                args=[self.feedback.pk]
            ),
            {
                'type': 'suggestion',
                'title': 'عنوان جدید',
                'text': 'متن جدید',
            }
        )

        self.assertRedirects(
            response,
            reverse('feedback_list')
        )

        self.feedback.refresh_from_db()

        self.assertEqual(
            self.feedback.type,
            'suggestion'
        )
        self.assertEqual(
            self.feedback.title,
            'عنوان جدید'
        )
        self.assertEqual(
            self.feedback.text,
            'متن جدید'
        )

    def test_feedback_update_invalid_pk(self):
        response = self.client.get(
            reverse(
                'feedback_update',
                args=[9999]
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_feedback_delete_get(self):
        response = self.client.get(
            reverse(
                'feedback_delete',
                args=[self.feedback.pk]
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_feedback_delete_post(self):
        response = self.client.post(
            reverse(
                'feedback_delete',
                args=[self.feedback.pk]
            )
        )

        self.assertRedirects(
            response,
            reverse('feedback_list')
        )

        self.assertFalse(
            Feedback.objects.filter(
                pk=self.feedback.pk
            ).exists()
        )

    def test_feedback_delete_invalid_pk(self):
        response = self.client.get(
            reverse(
                'feedback_delete',
                args=[9999]
            )
        )

        self.assertEqual(response.status_code, 404)


class AIUsageViewTest(TestCase):

    def test_usage_page_totals_correct(self):
        Feedback.objects.create(
            type='request',
            title='درخواست ۱',
            text='متن ۱',
            ai_status='ok',
            prompt_tokens=100,
            completion_tokens=50,
            cached_tokens=20,
            total_tokens=150,
        )
        Feedback.objects.create(
            type='criticism',
            title='انتقاد ۱',
            text='متن ۲',
            ai_status='ok',
            prompt_tokens=200,
            completion_tokens=80,
            cached_tokens=None,
            total_tokens=280,
        )
        Feedback.objects.create(
            type='suggestion',
            title='پیشنهاد ۱',
            text='متن ۳',
            ai_status='failed',
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

        # Test empty choices
        mock_response.json.side_effect = None
        mock_response.json.return_value = {'choices': []}
        with self.assertRaises(AIServiceError):
            ai.generate([{'role': 'user', 'content': 'متن تست'}])

        # Test missing message inside choices
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
