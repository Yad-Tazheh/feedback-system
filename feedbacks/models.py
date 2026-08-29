from django.db import models

# Create your models here.

''''
A model is the single, definitive source of information about your data. It contains the essential fields and behaviors of the data you’re storing. Generally, each model maps to a single database table.
'''
class Feedback(models.Model):
    TYPE_CHOICES = [
        ('request', 'درخواست'),
        ('criticism', 'انتقاد'),
        ('suggestion', 'پیشنهاد'),
    ]
    # CharField for small texts and TextField for long text
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    text = models.TextField()
    ai_response = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

