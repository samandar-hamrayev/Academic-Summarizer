"""Test settings: deterministic, offline, and independent of any local .env."""

import os
import tempfile

os.environ.setdefault('SECRET_KEY', 'test-secret-key-not-for-production')
os.environ.setdefault('DEBUG', 'False')
os.environ['GROQ_API_KEY'] = 'test-groq-key'

from academic_summarizer.settings import *  # noqa: F403

MEDIA_ROOT = tempfile.mkdtemp(prefix='acsum-test-media-')
STATIC_ROOT = tempfile.mkdtemp(prefix='acsum-test-static-')
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
GROQ_MODEL = 'test-model'
GROQ_MAX_RETRIES = 0
