from django.db import models

# Create your models here.


class Request(models.Model):
    TYPE_CHOICES = [
        ('request', 'درخواست'),
        ('criticism', 'انتقاد'),
        ('suggestion', 'پیشنهاد'),
    ]

    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    text = models.TextField()
    ai_response = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

