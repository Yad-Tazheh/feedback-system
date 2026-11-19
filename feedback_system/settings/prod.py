import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from .base import *

DEBUG = False

# Secret Key
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured("The DJANGO_SECRET_KEY environment variable must be set in production.")

# Allowed Hosts
allowed_hosts_raw = os.getenv('DJANGO_ALLOWED_HOSTS', '')
ALLOWED_HOSTS = [host.strip() for host in allowed_hosts_raw.split(',') if host.strip()]

# CSRF Trusted Origins
csrf_trusted_raw = os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', '')
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_trusted_raw.split(',') if origin.strip()]

# Security & HTTPS Settings
SECURE_SSL_REDIRECT = os.getenv('DJANGO_SECURE_SSL_REDIRECT', 'True').lower() in ('true', '1', 'yes')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(os.getenv('DJANGO_SECURE_HSTS_SECONDS', '31536000'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Reverse proxy SSL header (assumes upstream reverse proxy terminates TLS and sets X-Forwarded-Proto)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Email
MAILERS = {
    'default': {
        'BACKEND': os.getenv(
            'DJANGO_EMAIL_BACKEND',
            'django.core.mail.backends.smtp.EmailBackend',
        ),
    },
}

# Database
# Production defaults to SQLite at DJANGO_DB_PATH (or BASE_DIR/db.sqlite3).
# PostgreSQL migration requires driver dependency (psycopg) and is documented for future phase.
db_path = os.getenv('DJANGO_DB_PATH')
if db_path:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': Path(db_path),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
