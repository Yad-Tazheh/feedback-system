from django import forms

from .models import Feedback


class RequestForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['type', 'title', 'text']