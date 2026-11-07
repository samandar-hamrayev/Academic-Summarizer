# syntax=docker/dockerfile:1

# ── Stage 1: build a virtualenv with all Python dependencies ─────────────────
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install -r requirements.txt


# ── Stage 2: slim runtime image ──────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# fonts-dejavu-core: Cyrillic-capable font for PDF exports of RU/UZ summaries
RUN apt-get update \
 && apt-get install -y --no-install-recommends fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=academic_summarizer.settings

RUN groupadd --system django \
 && useradd --system --gid django --home-dir /app --shell /usr/sbin/nologin django

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
# Code stays root-owned (read-only for the app user); only media is writable.
COPY . .

# Static files are baked into the image (served by WhiteNoise), so no shared
# volume is needed. A throwaway key is enough for collectstatic.
RUN SECRET_KEY=collectstatic-only python manage.py collectstatic --noinput \
 && mkdir -p /app/media \
 && chown django:django /app/media \
 && chmod +x /app/entrypoint.sh

USER django

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz/', timeout=4).status == 200 else 1)"]

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "academic_summarizer.wsgi:application"]
