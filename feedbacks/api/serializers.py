from rest_framework import serializers

from ..models import Feedback


class FeedbackSerializer(serializers.ModelSerializer):

    class Meta:
        model = Feedback
        fields = [
            'id',
            'type',
            'title',
            'text',
            'ai_response',
            'created_at',
        ]