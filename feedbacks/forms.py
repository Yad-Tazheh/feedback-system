from django import forms

from .models import Feedback


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['type', 'title', 'text']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['title'].error_messages['required'] = (
            'لطفاً عنوان را وارد کنید.'
        )

        self.fields['text'].error_messages['required'] = (
            'لطفاً متن بازخورد را وارد کنید.'
        )