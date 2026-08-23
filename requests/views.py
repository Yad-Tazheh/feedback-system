from django.shortcuts import render, redirect

from .forms import RequestForm
from .models import Request

# Create your views here.


def request_list(request):
    requests = Request.objects.all().order_by('-created_at')

    return render(request, 'requests/request_list.html', {
        'requests': requests
    })


def request_create(request):
    if request.method == 'POST':
        form = RequestForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect('request_list')
    else:
        form = RequestForm()

    return render(request, 'requests/request_form.html', {
        'form': form
    })

def request_update(request, pk):
    item = Request.objects.get(pk=pk)

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
    item = Request.objects.get(pk=pk)

    if request.method == 'POST':
        item.delete()
        return redirect('request_list')

    return render(request, 'requests/request_confirm_delete.html', {
        'item': item
    })