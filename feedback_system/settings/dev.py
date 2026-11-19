import os
from .base import *

DEBUG = True

SECRET_KEY = os.getenv(
    'DJANGO_SECRET_KEY',
    'django-insecure-dev-only-secret-key-do-not-use-in-production',
)

ALLOWED_HOSTS = ['localhost', '127.0.0.1']
