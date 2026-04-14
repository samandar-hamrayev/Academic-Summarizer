"""
AI summarization service using Groq API (llama-3.1-70b-versatile).

Groq runs inference on custom LPU hardware — responses are extremely fast
(typically 2–5 s for a full academic summary) compared to GPU-based APIs.

Free tier: ~14 400 requests/day, 6 000 tokens/min per model.
"""
import json
import logging
import re

from groq import Groq, APIStatusError, APIConnectionError
from django.conf import settings

logger = logging.getLogger(__name__)

# Maximum characters of paper text sent to the API.
# At ~4 chars/token ≈ 25 000 tokens — fits within the 128K context window.
MAX_TEXT_CHARS = 100_000

SYSTEM_PROMPT = """You are an expert academic paper analyst. Your task is to read
academic papers and produce concise, accurate, structured summaries.

Always respond with a single valid JSON object — no markdown fences, no prose
outside the JSON — using exactly these keys:

{
  "abstract":     "<2-3 paragraph summary of the paper's core contribution>",
  "key_points":   ["<concise point>", "..."],
  "methodology":  "<how the research was conducted>",
  "results":      "<key quantitative and qualitative findings>",
  "conclusion":   "<main conclusions and future-work implications>"
}

Guidelines:
- Be precise, objective, and academic in tone.
- Capture the paper's novel contribution prominently.
- Include concrete numbers from results where they exist.
- Write in complete sentences (except key_points, which may be fragments).
- If a section is not present in the paper, write "Not explicitly stated."
"""


def _get_client() -> Groq:
    if not settings.GROQ_API_KEY:
        raise ValueError(
            'GROQ_API_KEY is not set. '
            'Get your free key at https://console.groq.com '
            'and add it to your .env file, then restart the server.'
        )
    return Groq(api_key=settings.GROQ_API_KEY)


def summarize_paper_text(text: str, title: str = '') -> dict:
    """
    Summarize an academic paper using Groq / Llama 3.1.

    Returns a dict with keys: abstract, key_points (list), methodology,
    results, conclusion.
    """
    client = _get_client()

    truncated = text[:MAX_TEXT_CHARS]
    if len(text) > MAX_TEXT_CHARS:
        logger.info(
            'Paper text truncated from %d to %d chars for summarization.',
            len(text), MAX_TEXT_CHARS,
        )

    user_message = (
        f'Title: {title or "Unknown"}\n\n'
        f'Full paper text:\n{truncated}\n\n'
        'Please provide a structured summary of this paper in the JSON format '
        'described in your instructions.'
    )

    try:
        response = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': user_message},
            ],
            temperature=0.3,
            max_tokens=2000,
        )

        response_text = response.choices[0].message.content.strip()
        logger.debug('Raw Groq response (first 500 chars): %s', response_text[:500])

    except APIStatusError as exc:
        logger.error('Groq API status error %s: %s', exc.status_code, exc.message)
        if exc.status_code == 429:
            raise ValueError(
                'Groq API rate limit reached. Please wait a moment and try again.'
            ) from exc
        raise ValueError(f'Groq API error ({exc.status_code}): {exc.message}') from exc
    except APIConnectionError as exc:
        logger.error('Groq connection error: %s', exc)
        raise ValueError(f'Could not connect to Groq API: {exc}') from exc

    return _parse_response(response_text)


def _parse_response(response_text: str) -> dict:
    """Extract the JSON object from the model's response."""
    cleaned = re.sub(r'^```(?:json)?\s*', '', response_text, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*```$', '', cleaned).strip()

    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if not match:
        logger.error('No JSON object found in Groq response: %s', response_text[:300])
        raise ValueError('Model did not return a valid JSON object.')

    try:
        data = json.loads(match.group())
    except json.JSONDecodeError as exc:
        logger.error('JSON decode error: %s\nRaw: %s', exc, response_text[:300])
        raise ValueError(f'Could not parse response as JSON: {exc}') from exc

    key_points = data.get('key_points', [])
    if isinstance(key_points, str):
        key_points = [kp.strip() for kp in key_points.split('\n') if kp.strip()]

    return {
        'abstract': data.get('abstract', '').strip(),
        'key_points': key_points,
        'methodology': data.get('methodology', '').strip(),
        'results': data.get('results', '').strip(),
        'conclusion': data.get('conclusion', '').strip(),
    }


def summarize_paper_task(paper, text: str) -> None:
    """Orchestrate summarization → persistence for a Paper instance."""
    from .models import Summary

    result = summarize_paper_text(text, title=paper.title)

    summary, _ = Summary.objects.get_or_create(paper=paper)
    summary.abstract = result['abstract']
    summary.set_key_points_list(result['key_points'])
    summary.methodology = result['methodology']
    summary.results = result['results']
    summary.conclusion = result['conclusion']
    summary.save()

    paper.processed = True
    paper.save(update_fields=['processed'])

    logger.info('Summary saved for paper pk=%s "%s"', paper.pk, paper.title)
