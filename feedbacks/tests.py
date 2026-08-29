from unittest.mock import patch, Mock
from requests.exceptions import Timeout

from django.test import TestCase
from django.urls import reverse

from .forms import FeedbackForm
from .models import Feedback
from .services.ai_service import AIService


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

    def test_feedback_create_get(self):
        response = self.client.get(
            reverse('feedback_create')
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(
            response.context['form'],
            FeedbackForm
        )

    @patch('feedbacks.views.generate_ai_response')
    def test_feedback_create_post(self, mock_ai_response):
        mock_ai_response.return_value = 'پاسخ تست هوش مصنوعی'

        response = self.client.post(
            reverse('feedback_create'),
            {
                'type': 'request',
                'title': 'Feedback جدید',
                'text': 'متن feedback جدید',
            }
        )

        self.assertEqual(response.status_code, 200)

        feedback = Feedback.objects.get(
            title='Feedback جدید'
        )

        self.assertEqual(
            feedback.text,
            'متن feedback جدید'
        )

        self.assertEqual(
            feedback.ai_response,
            'پاسخ تست هوش مصنوعی'
        )

        mock_ai_response.assert_called_once()

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



class AIServiceTest(TestCase):

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
            ]
        }

        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        ai = AIService()

        result = ai.generate('متن تست')

        self.assertEqual(
            result,
            'پاسخ تستی AI'
        )

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

        result = ai.generate('متن تست')

        mock_post.assert_called_once()

        args, kwargs = mock_post.call_args

        self.assertEqual(
            args[0],
            ai.url
        )

        self.assertEqual(
            kwargs['json']['model'],
            ai.model
        )

        self.assertEqual(
            kwargs['json']['messages'][-1],
            {
                'role': 'user',
                'content': 'متن تست'
            }
        )

        self.assertEqual(
            result,
            'پاسخ تستی AI'
        )

    @patch('feedbacks.services.ai_service.requests.post')
    def test_generate_raises_http_error(self, mock_post):
        mock_response = Mock()

        mock_response.raise_for_status.side_effect = Exception(
            'LM Studio error'
        )

        mock_post.return_value = mock_response

        ai = AIService()

        with self.assertRaises(Exception):
            ai.generate('متن تست')

    @patch('feedbacks.services.ai_service.requests.post')
    def test_generate_handles_connection_error(self, mock_post):
        mock_post.side_effect = ConnectionError(
            'LM Studio is not available'
        )

        ai = AIService()

        with self.assertRaises(ConnectionError):
            ai.generate('متن تست')

    @patch('feedbacks.services.ai_service.requests.post')
    def test_generate_handles_timeout(self, mock_post):
        mock_post.side_effect = Timeout(
            'LM Studio request timed out'
        )

        ai = AIService()

        with self.assertRaises(Timeout):
            ai.generate('متن تست')