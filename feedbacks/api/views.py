from rest_framework.generics import ListAPIView

from ..models import Feedback
from .serializers import FeedbackSerializer


class FeedbackListAPIView(ListAPIView):

    queryset = Feedback.objects.all()
    serializer_class = FeedbackSerializer