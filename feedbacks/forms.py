from django import forms

from .models import Conversation, Message


class ConversationCreateForm(forms.ModelForm):
    text = forms.CharField(
        widget=forms.Textarea,
        label='متن بازخورد',
        error_messages={'required': 'لطفاً متن بازخورد را وارد کنید.'},
    )

    class Meta:
        model = Conversation
        fields = ['type', 'title', 'text']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].error_messages['required'] = (
            'لطفاً عنوان را وارد کنید.'
        )


FeedbackForm = ConversationCreateForm


class ConversationUpdateForm(forms.ModelForm):
    class Meta:
        model = Conversation
        fields = ['type', 'title']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].error_messages['required'] = (
            'لطفاً عنوان را وارد کنید.'
        )


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['content']
        widgets = {
            'content': forms.Textarea(
                attrs={'rows': 3, 'placeholder': 'پیام خود را بنویسید...'}
            ),
        }
        labels = {
            'content': 'متن پیام',
        }
        error_messages = {
            'content': {
                'required': 'لطفاً متن پیام را وارد کنید.',
            },
        }
