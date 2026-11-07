"""Gunicorn settings (auto-loaded from the working directory)."""

import os

bind = os.environ.get('GUNICORN_BIND', '0.0.0.0:8000')
workers = int(os.environ.get('GUNICORN_WORKERS', '3'))
# Summarization waits on the Groq API (I/O bound), so threads let one worker
# keep serving other requests while a summary is in flight.
worker_class = 'gthread'
threads = int(os.environ.get('GUNICORN_THREADS', '4'))
# Must exceed GROQ_TIMEOUT x (GROQ_MAX_RETRIES + 1) plus PDF parsing time.
timeout = int(os.environ.get('GUNICORN_TIMEOUT', '180'))
graceful_timeout = 30
accesslog = '-'
errorlog = '-'
# The runtime control socket is unused and would need a writable $HOME.
control_socket_disable = True
