from django.shortcuts import render, redirect, get_object_or_404

from .forms import FeedbackForm
from .models import Feedback
from .services.ai_service import AIService


def generate_ai_response(item):
    ai = AIService()

    prompt = f"""
نوع پیام:
{item.get_type_display()}

عنوان:
{item.title}

متن کاربر:
{item.text}
"""

    return ai.generate(prompt)


def feedback_list(request):
    feedbacks = Feedback.objects.all().order_by('-created_at')

    return render(request, 'feedbacks/feedback_list.html', {
        'feedbacks': feedbacks
    })


def feedback_create(request):
    if request.method == 'POST':
        form = FeedbackForm(request.POST)

        if form.is_valid():
            item = form.save()

            item.ai_response = generate_ai_response(item)
            item.save()

            return render(request, 'feedbacks/feedback_list.html', {
                'feedbacks': Feedback.objects.all().order_by('-created_at'),
                'ai_response': item.ai_response,
            })

    else:
        form = FeedbackForm()

    return render(request, 'feedbacks/feedback_form.html', {
        'form': form
    })


def feedback_update(request, pk):
    item = get_object_or_404(Feedback, pk=pk)

    if request.method == 'POST':
        form = FeedbackForm(
            request.POST,
            instance=item
        )

        if form.is_valid():
            form.save()
            return redirect('feedback_list')

    else:
        form = FeedbackForm(instance=item)

    return render(request, 'feedbacks/feedback_form.html', {
        'form': form
    })


def feedback_delete(request, pk):
    item = get_object_or_404(Feedback, pk=pk)

    if request.method == 'POST':
        item.delete()
        return redirect('feedback_list')

    return render(request, 'feedbacks/feedback_confirm_delete.html', {
        'item': item
    })