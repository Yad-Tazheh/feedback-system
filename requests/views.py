import json
from urllib.request import Request as HttpRequest
from urllib.request import urlopen

from django.shortcuts import render, redirect, get_object_or_404

from .forms import RequestForm
from .models import Request


LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
LM_MODEL = "qwen2.5-7b-instruct"


def generate_ai_response(request_type, title, text):
    prompt = f"""
تو دستیار سیستم ثبت درخواست، انتقاد و پیشنهاد هستی.

نوع پیام: {request_type}
عنوان: {title}
متن: {text}

یک پاسخ کوتاه، محترمانه و مرتبط به فارسی بنویس.

قوانین:
- فقط بر اساس اطلاعات موجود در پیام کاربر پاسخ بده.
- هیچ اطلاعاتی از خودت اضافه نکن.
- پاسخ حداکثر 2 یا 3 جمله باشد.
- پاسخ طبیعی و محترمانه باشد.
"""

    payload = {
        "model": LM_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "تو یک دستیار پاسخ‌گوی فارسی هستی."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.4,
        "max_tokens": 150,
    }

    data = json.dumps(payload).encode("utf-8")

    http_request = HttpRequest(
        LM_STUDIO_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urlopen(http_request, timeout=120) as response:
        result = json.loads(response.read().decode("utf-8"))

    return result["choices"][0]["message"]["content"]



def request_list(request):
    requests = Request.objects.all().order_by('-created_at')

    return render(request, 'requests/request_list.html', {
        'requests': requests
    })


def request_create(request):
    if request.method == 'POST':
        form = RequestForm(request.POST)

        if form.is_valid():
            item = form.save()

            item.ai_response = generate_ai_response(
                item.get_type_display(),
                item.title,
                item.text
            )

            item.save()

            return render(request, 'requests/request_list.html', {
                'requests': Request.objects.all().order_by('-created_at'),
                'ai_response': item.ai_response,
            })

    else:
        form = RequestForm()

    return render(request, 'requests/request_form.html', {
        'form': form
    })


def request_update(request, pk):
    item = get_object_or_404(Request, pk=pk)

    if request.method == 'POST':
        form = RequestForm(request.POST, instance=item)

        if form.is_valid():
            form.save()
            return redirect('request_list')
    else:
        form = RequestForm(instance=item)

    return render(request, 'requests/request_form.html', {
        'form': form
    })


def request_delete(request, pk):
    item = get_object_or_404(Request, pk=pk)

    if request.method == 'POST':
        item.delete()
        return redirect('request_list')

    return render(request, 'requests/request_confirm_delete.html', {
        'item': item
    })