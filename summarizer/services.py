"""
AI summarization service using the Groq API (model configurable via GROQ_MODEL).

Supports English, Russian, and Uzbek papers.
Extracts structured summary + top citations in a single API call.
"""

import json
import logging
import re

from django.conf import settings
from django.db import transaction
from groq import APIConnectionError, APIStatusError, APITimeoutError, Groq, RateLimitError

logger = logging.getLogger(__name__)

MAX_TEXT_CHARS = 100_000
SUMMARY_TEXT_FIELDS = ('abstract', 'methodology', 'results', 'conclusion')


class SummarizationError(Exception):
    """Raised when a summary cannot be produced. The message is safe to show to users."""


# ---- System prompts per language ----------------------------------------

_PROMPT_EN = """You are an expert academic paper analyst. Read the paper and return a single
valid JSON object — no markdown fences, no prose outside the JSON — using exactly these keys:

{
  "abstract":    "<2-3 paragraph summary of the paper's core contribution>",
  "key_points":  ["<concise point>", "..."],
  "methodology": "<how the research was conducted>",
  "results":     "<key quantitative and qualitative findings>",
  "conclusion":  "<main conclusions and future-work implications>",
  "citations":   ["<Full citation string>", "..."]
}

Guidelines:
- Be precise, objective, and academic in tone.
- Capture the novel contribution prominently.
- Include concrete numbers from results where available.
- Write in complete sentences (except key_points and citations).
- For citations: extract up to 10 of the most significant references from the paper's
  reference list. Format each as: Authors (Year). Title. Venue.
- If a section is absent, write "Not explicitly stated."
- Always respond in ENGLISH regardless of the paper language."""

_PROMPT_RU = """Вы эксперт по реферированию научных статей. Прочитайте статью и верните
единственный валидный JSON-объект — без разметки markdown, без текста вне JSON — используя
ровно эти ключи:

{
  "abstract":    "<краткое изложение основного вклада статьи в 2–3 абзаца>",
  "key_points":  ["<краткий тезис>", "..."],
  "methodology": "<как было проведено исследование>",
  "results":     "<ключевые количественные и качественные результаты>",
  "conclusion":  "<основные выводы и перспективы>",
  "citations":   ["<полная строка цитирования>", "..."]
}

Инструкции:
- Точный, объективный, академический стиль.
- Включите конкретные числа из результатов.
- Для citations: до 10 наиболее значимых ссылок из списка литературы.
  Формат: Авторы (Год). Название. Журнал/Конференция.
- Если раздел отсутствует, напишите "Явно не указано."
- Отвечайте на РУССКОМ языке."""

_PROMPT_UZ = """Siz ilmiy maqolalarni xulosalash bo'yicha mutaxasssissiz. Maqolani o'qib,
faqat bitta to'g'ri JSON ob'ektini qaytaring — markdown belgilarsiz,
JSON tashqarisida matn bo'lmagan holda —
quyidagi kalitlardan foydalanib:

{
  "abstract":    "<maqolaning asosiy hissasini 2–3 paragrafda xulosa qiling>",
  "key_points":  ["<qisqa tezis>", "..."],
  "methodology": "<tadqiqot qanday olib borilgan>",
  "results":     "<asosiy miqdoriy va sifat natijalari>",
  "conclusion":  "<asosiy xulosalar va kelajakdagi yo'nalishlar>",
  "citations":   ["<to'liq iqtibos qatori>", "..."]
}

Ko'rsatmalar:
- Aniq, ob'ektiv, akademik uslub.
- Natijalardan aniq raqamlarni kiriting.
- Citations: maqolaning adabiyotlar ro'yxatidan eng muhim 10 tagacha iqtibos.
  Format: Mualliflar (Yil). Sarlavha. Jurnal/Konferensiya.
- Qism mavjud bo'lmasa, "Aniq ko'rsatilmagan." yozing.
- O'ZBEK tilida javob bering."""

SYSTEM_PROMPTS = {'en': _PROMPT_EN, 'ru': _PROMPT_RU, 'uz': _PROMPT_UZ}


# ---- Language detection --------------------------------------------------


def detect_language(text: str) -> str:
    """Heuristic language detection from character frequencies."""
    sample = text[:8000]
    total_alpha = sum(1 for c in sample if c.isalpha())
    if total_alpha == 0:
        return 'en'

    cyrillic = sum(1 for c in sample if 'Ѐ' <= c <= 'ӿ')
    ratio = cyrillic / total_alpha

    if ratio > 0.25:
        # Distinguish Uzbek Cyrillic from Russian by unique characters
        uzbek_cyrillic = set('ғқҳ')
        if any(c in uzbek_cyrillic for c in sample.lower()):
            return 'uz'
        return 'ru'

    return 'en'


# ---- Groq client ---------------------------------------------------------


def _get_client() -> Groq:
    if not settings.GROQ_API_KEY:
        raise SummarizationError(
            'GROQ_API_KEY is not set. '
            'Get a free key at https://console.groq.com and add it to your .env file.'
        )
    return Groq(
        api_key=settings.GROQ_API_KEY,
        timeout=settings.GROQ_TIMEOUT,
        max_retries=settings.GROQ_MAX_RETRIES,
    )


def _complete(client: Groq, messages: list[dict], **kwargs) -> str:
    """Run a chat completion and map SDK errors to SummarizationError."""
    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=messages,
            **kwargs,
        )
    except RateLimitError as exc:
        logger.warning('Groq rate limit hit: %s', exc)
        raise SummarizationError(
            'Groq rate limit reached. Please wait a moment and try again.'
        ) from exc
    except APITimeoutError as exc:
        logger.error('Groq request timed out: %s', exc)
        raise SummarizationError('The AI service timed out. Please try again.') from exc
    except APIConnectionError as exc:
        logger.error('Groq connection error: %s', exc)
        raise SummarizationError('Could not connect to the AI service.') from exc
    except APIStatusError as exc:
        logger.error('Groq API status error %s: %s', exc.status_code, exc.message)
        raise SummarizationError(
            f'The AI service returned an error (HTTP {exc.status_code}).'
        ) from exc

    if not response.choices or not response.choices[0].message.content:
        raise SummarizationError('The AI service returned an empty response.')
    return response.choices[0].message.content.strip()


# ---- Main summarization --------------------------------------------------


def summarize_paper_text(text: str, title: str = '', language: str | None = None) -> dict:
    """
    Summarize an academic paper with the configured Groq model.

    Returns dict with keys: abstract, key_points (list), methodology,
    results, conclusion, citations (list), language (str).

    Raises SummarizationError on any API or parsing failure.
    """
    client = _get_client()

    detected = language or detect_language(text)
    system_prompt = SYSTEM_PROMPTS.get(detected, _PROMPT_EN)

    truncated = text[:MAX_TEXT_CHARS]
    if len(text) > MAX_TEXT_CHARS:
        logger.info('Paper text truncated from %d to %d chars.', len(text), MAX_TEXT_CHARS)

    user_message = (
        f'Title: {title or "Unknown"}\n\n'
        f'Full paper text:\n{truncated}\n\n'
        'Provide a structured summary in the JSON format described in your instructions.'
    )

    response_text = _complete(
        client,
        [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_message},
        ],
        temperature=0.3,
        max_tokens=2500,
        response_format={'type': 'json_object'},
    )
    logger.debug('Groq response (first 500 chars): %s', response_text[:500])

    result = _parse_response(response_text)
    result['language'] = detected
    return result


def _strip_fences(raw: str) -> str:
    cleaned = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.IGNORECASE)
    return re.sub(r'\s*```$', '', cleaned).strip()


def _as_text(value) -> str:
    """Coerce a model-provided field to a clean string."""
    if value is None:
        return ''
    if isinstance(value, list):
        return '\n\n'.join(_as_text(v) for v in value if v)
    return str(value).strip()


def _as_list(value) -> list[str]:
    """Coerce a model-provided field to a list of non-empty strings."""
    if value is None:
        return []
    if isinstance(value, str):
        items = value.split('\n')
    elif isinstance(value, list):
        items = value
    else:
        items = [value]
    return [s for s in (_as_text(item) for item in items) if s]


def _parse_response(response_text: str) -> dict:
    cleaned = _strip_fences(response_text)

    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if not match:
        logger.error('No JSON object in Groq response: %s', response_text[:300])
        raise SummarizationError('The AI model did not return a valid JSON object.')

    try:
        data = json.loads(match.group())
    except json.JSONDecodeError as exc:
        logger.error('JSON decode error: %s\nRaw: %s', exc, response_text[:300])
        raise SummarizationError('Could not parse the AI response as JSON.') from exc

    if not isinstance(data, dict):
        raise SummarizationError('The AI model returned an unexpected JSON structure.')

    result = {field: _as_text(data.get(field)) for field in SUMMARY_TEXT_FIELDS}
    result['key_points'] = _as_list(data.get('key_points'))
    result['citations'] = _as_list(data.get('citations'))

    if not result['abstract'] and not result['key_points']:
        raise SummarizationError('The AI response did not contain a summary.')
    return result


# ---- Tag extraction ------------------------------------------------------


def extract_tags_from_text(text: str, max_tags: int = 5) -> list[str]:
    """
    Extract relevant academic tags from paper text using Groq.
    Returns a list of tag strings, e.g. ['Machine Learning', 'NLP', 'BERT'].
    Never raises — returns [] on any failure, since tags are optional.
    """
    sample = text[:8_000]
    prompt = (
        f'Extract exactly {max_tags} concise tags/keywords from this academic paper.\n\n'
        'Rules:\n'
        '- Tags must be research fields, methods, or technologies used in the paper\n'
        '- Use title case (e.g. "Deep Learning", "Graph Neural Networks")\n'
        '- Keep each tag 1–3 words; no generic terms like "Research" or "Study"\n'
        '- Return ONLY a valid JSON array of strings — no prose, no markdown fences\n\n'
        f'Paper text:\n{sample}\n\n'
        f'Return format: ["Tag1", "Tag2", ..., "Tag{max_tags}"]'
    )

    try:
        raw = _complete(
            _get_client(),
            [
                {
                    'role': 'system',
                    'content': (
                        'You extract academic tags. Return only a valid JSON array of strings.'
                    ),
                },
                {'role': 'user', 'content': prompt},
            ],
            temperature=0.2,
            max_tokens=150,
        )
    except SummarizationError as exc:
        logger.warning('Tag extraction skipped: %s', exc)
        return []

    logger.debug('Tag extraction raw: %s', raw[:200])
    match = re.search(r'\[.*\]', _strip_fences(raw), re.DOTALL)
    if not match:
        logger.warning('No JSON array in tag response: %s', raw[:200])
        return []

    try:
        tags = json.loads(match.group())
    except json.JSONDecodeError as exc:
        logger.warning('Tag response is not valid JSON: %s', exc)
        return []
    if not isinstance(tags, list):
        return []

    seen: set[str] = set()
    unique: list[str] = []
    for tag in _as_list(tags):
        tag = tag[:50]
        if tag.lower() not in seen:
            seen.add(tag.lower())
            unique.append(tag)
    return unique[:max_tags]


# ---- Orchestration -------------------------------------------------------


def summarize_paper_task(paper, text: str):
    """Summarize a Paper and persist the result. Returns the saved Summary."""
    from .models import Summary

    # Call the LLM outside the transaction so no DB connection is held open
    # for the duration of a slow network request.
    result = summarize_paper_text(text, title=paper.title)

    with transaction.atomic():
        summary, _ = Summary.objects.get_or_create(paper=paper)
        summary.abstract = result['abstract']
        summary.methodology = result['methodology']
        summary.results = result['results']
        summary.conclusion = result['conclusion']
        summary.language = result.get('language', 'en')
        summary.set_key_points_list(result['key_points'])
        summary.set_citations_list(result.get('citations', []))
        summary.save()

        paper.processed = True
        paper.save(update_fields=['processed'])

    logger.info(
        'Summary saved for paper pk=%s "%s" [lang=%s]', paper.pk, paper.title, summary.language
    )
    return summary
