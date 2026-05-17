"""
AI summarization service using Groq API (llama-3.3-70b-versatile).

Supports English, Russian, and Uzbek papers.
Extracts structured summary + top citations in a single API call.
"""
import json
import logging
import re

from groq import Groq, APIStatusError, APIConnectionError
from django.conf import settings

logger = logging.getLogger(__name__)

MAX_TEXT_CHARS = 100_000

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
faqat bitta to'g'ri JSON ob'ektini qaytaring — markdown belgilarsiz, JSON tashqarisida matn bo'lmagan holda —
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

# Uzbek-Latin "smoking gun" markers — words and digraphs that almost never
# appear together in English, Turkish, Azerbaijani or other Latin scripts.
_UZBEK_LATIN_WORDS = {
    'va', 'uchun', 'bilan', 'lekin', 'ammo', 'ham', 'yoki', 'qilish',
    "bo'lib", "bo'yicha", "bo'lgan", 'ushbu', 'mazkur', 'qilingan',
    'tadqiqot', 'ishlab', 'natijalar', 'maqola', 'kerak', 'kerakli',
    'maxsus', "ko'rib", 'birinchi', 'asosiy', 'haqida', 'orqali',
    'tomonidan', 'ekanligini', 'foydalanib', "o'rganish",
}
# o' and g' apostrophe digraphs are unique to Uzbek-Latin orthography
_UZBEK_LATIN_DIGRAPHS = ("o'", "g'", "o‘", "g‘", "o’", "g’")

# Uzbek-Cyrillic characters that don't appear in standard Russian
_UZBEK_CYRILLIC = set('ғқҳў')

_TOKEN_RE = re.compile(r"[A-Za-zÀ-ſЀ-ӿ'’‘]+", re.UNICODE)


def _uzbek_latin_score(sample: str) -> float:
    """
    Return 0.0–1.0 likelihood that a Latin-script sample is Uzbek.
    Combines apostrophe digraph density with stop-word coverage.
    """
    lower = sample.lower()
    digraph_hits = sum(lower.count(d) for d in _UZBEK_LATIN_DIGRAPHS)
    tokens = _TOKEN_RE.findall(lower)
    if not tokens:
        return 0.0
    word_hits = sum(1 for t in tokens if t in _UZBEK_LATIN_WORDS)
    # Each signal is normalized then combined (heuristic but resilient)
    digraph_density = min(digraph_hits / max(len(tokens), 1) * 8, 1.0)
    word_density    = min(word_hits / max(len(tokens), 1) * 12, 1.0)
    return 0.6 * digraph_density + 0.4 * word_density


def detect_language(text: str) -> tuple[str, float]:
    """
    Detect document language. Returns (code, confidence) where code ∈
    {'en','ru','uz'} and confidence ∈ [0.0, 1.0].

    Pipeline:
      1. Reject empty / tiny inputs → ('en', 0.0).
      2. Cyrillic majority → Russian vs Uzbek-Cyrillic by distinguishing letters.
      3. Latin majority → run Uzbek-Latin heuristic first (langdetect has no
         Uzbek model and tends to misfire as Somali/Turkish/Azerbaijani).
      4. Otherwise fall back to langdetect for English vs anything else.
    """
    if not text or not text.strip():
        return ('en', 0.0)

    sample = text[:8000]
    total_alpha = sum(1 for c in sample if c.isalpha())
    if total_alpha < 20:
        return ('en', 0.0)

    cyrillic = sum(1 for c in sample if 'Ѐ' <= c <= 'ӿ')
    cyr_ratio = cyrillic / total_alpha

    # ── Cyrillic-dominant ────────────────────────────────────────────────
    if cyr_ratio > 0.25:
        if any(c in _UZBEK_CYRILLIC for c in sample.lower()):
            return ('uz', round(min(0.6 + cyr_ratio * 0.4, 0.95), 2))
        return ('ru', round(min(0.7 + cyr_ratio * 0.3, 0.99), 2))

    # ── Latin-dominant: Uzbek heuristic before langdetect ────────────────
    uz_score = _uzbek_latin_score(sample)
    if uz_score >= 0.35:
        return ('uz', round(min(0.55 + uz_score * 0.4, 0.95), 2))

    # ── Default: langdetect for English (or anything Latin) ──────────────
    try:
        from langdetect import detect_langs, DetectorFactory, LangDetectException
        DetectorFactory.seed = 0
        results = detect_langs(sample)
    except Exception as exc:
        logger.warning('langdetect failed: %s — defaulting to English.', exc)
        return ('en', 0.3)

    top = results[0] if results else None
    if top and top.lang == 'en':
        return ('en', round(top.prob, 2))
    if top and top.lang == 'ru':
        return ('ru', round(top.prob, 2))
    # Anything else (so/sq/tr/az) — Uzbek-Latin with low text density is
    # plausible, but without supporting signals we honestly don't know,
    # so report English with low confidence and let the user override.
    return ('en', 0.3)


# ---- Groq client ---------------------------------------------------------

def _get_client() -> Groq:
    if not settings.GROQ_API_KEY:
        raise ValueError(
            'GROQ_API_KEY is not set. '
            'Get your free key at https://console.groq.com and add it to your .env file.'
        )
    return Groq(api_key=settings.GROQ_API_KEY)


# ---- Main summarization --------------------------------------------------

def summarize_paper_text(text: str, title: str = '', language: str | None = None) -> dict:
    """
    Summarize an academic paper using Groq / Llama 3.3.

    Returns dict with keys: abstract, key_points (list), methodology,
    results, conclusion, citations (list), language (str).
    """
    client = _get_client()

    if language:
        detected = language
    else:
        detected, _conf = detect_language(text)
    system_prompt = SYSTEM_PROMPTS.get(detected, _PROMPT_EN)

    truncated = text[:MAX_TEXT_CHARS]
    if len(text) > MAX_TEXT_CHARS:
        logger.info('Paper text truncated from %d to %d chars.', len(text), MAX_TEXT_CHARS)

    user_message = (
        f'Title: {title or "Unknown"}\n\n'
        f'Full paper text:\n{truncated}\n\n'
        'Provide a structured summary in the JSON format described in your instructions.'
    )

    try:
        response = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user',   'content': user_message},
            ],
            temperature=0.3,
            max_tokens=2500,
            response_format={'type': 'json_object'},
        )
        response_text = response.choices[0].message.content.strip()
        logger.debug('Groq response (first 500 chars): %s', response_text[:500])

    except APIStatusError as exc:
        logger.error('Groq API status error %s: %s', exc.status_code, exc.message)
        if exc.status_code == 429:
            raise ValueError('Groq rate limit reached. Please wait a moment and try again.') from exc
        raise ValueError(f'Groq API error ({exc.status_code}): {exc.message}') from exc
    except APIConnectionError as exc:
        logger.error('Groq connection error: %s', exc)
        raise ValueError(f'Could not connect to Groq API: {exc}') from exc

    result = _parse_response(response_text)
    result['language'] = detected
    return result


def _parse_response(response_text: str) -> dict:
    cleaned = re.sub(r'^```(?:json)?\s*', '', response_text, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*```$', '', cleaned).strip()

    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if not match:
        logger.error('No JSON object in Groq response: %s', response_text[:300])
        raise ValueError('Model did not return a valid JSON object.')

    try:
        data = json.loads(match.group())
    except json.JSONDecodeError as exc:
        logger.error('JSON decode error: %s\nRaw: %s', exc, response_text[:300])
        raise ValueError(f'Could not parse response as JSON: {exc}') from exc

    key_points = data.get('key_points', [])
    if isinstance(key_points, str):
        key_points = [kp.strip() for kp in key_points.split('\n') if kp.strip()]

    citations = data.get('citations', [])
    if isinstance(citations, str):
        citations = [c.strip() for c in citations.split('\n') if c.strip()]

    return {
        'abstract':    data.get('abstract', '').strip(),
        'key_points':  key_points,
        'methodology': data.get('methodology', '').strip(),
        'results':     data.get('results', '').strip(),
        'conclusion':  data.get('conclusion', '').strip(),
        'citations':   citations,
    }


# ---- Tag extraction ------------------------------------------------------

def extract_tags_from_text(text: str, max_tags: int = 5) -> list:
    """
    Extract relevant academic tags from paper text using Groq.
    Returns a list of tag strings, e.g. ['Machine Learning', 'NLP', 'BERT'].
    Never raises — returns [] on any failure.
    """
    try:
        client = _get_client()
    except ValueError:
        return []

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
        response = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[
                {'role': 'system',
                 'content': 'You extract academic tags. Return only a valid JSON array of strings.'},
                {'role': 'user', 'content': prompt},
            ],
            temperature=0.2,
            max_tokens=150,
        )
        raw = response.choices[0].message.content.strip()
        logger.debug('Tag extraction raw: %s', raw[:200])

        cleaned = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*```$', '', cleaned).strip()

        match = re.search(r'\[.*?\]', cleaned, re.DOTALL)
        if not match:
            logger.warning('No JSON array in tag response: %s', raw[:200])
            return []

        tags = json.loads(match.group())
        if not isinstance(tags, list):
            return []

        return [str(t).strip()[:50] for t in tags if t and str(t).strip()][:max_tags]

    except (json.JSONDecodeError, APIStatusError, APIConnectionError) as exc:
        logger.error('Tag extraction failed: %s', exc)
        return []
    except Exception as exc:
        logger.error('Unexpected error in extract_tags_from_text: %s', exc)
        return []


# ---- Chat with paper ----------------------------------------------------

def chat_with_paper(paper, summary, history, question: str) -> str:
    """
    Answer a free-form question about a paper, using its structured summary
    as the grounding context plus the last ten turns of conversation.

    Args:
        paper:    papers.models.Paper
        summary:  summarizer.models.Summary (must exist)
        history:  iterable of ChatMessage in chronological order
                  (NOT including the new question)
        question: the new user question

    Returns the assistant reply as a string. Raises ValueError on API errors.
    """
    client = _get_client()

    title  = paper.title
    author = paper.author or 'Unknown'

    sections = []
    if summary.abstract:    sections.append(f'## ABSTRACT\n{summary.abstract}')
    kps = summary.get_key_points_list()
    if kps:                 sections.append('## KEY POINTS\n' + '\n'.join(f'- {kp}' for kp in kps))
    if summary.methodology: sections.append(f'## METHODOLOGY\n{summary.methodology}')
    if summary.results:     sections.append(f'## RESULTS\n{summary.results}')
    if summary.conclusion:  sections.append(f'## CONCLUSION\n{summary.conclusion}')
    cites = summary.get_citations_list()
    if cites:               sections.append('## REFERENCES\n' + '\n'.join(f'[{i}] {c}' for i, c in enumerate(cites, 1)))

    context = '\n\n'.join(sections) if sections else '(no structured summary available)'

    # Reply in the paper's language so the user sees consistent content,
    # regardless of which UI language they have selected.
    paper_lang = getattr(paper, 'language', None) or getattr(summary, 'language', 'en')
    lang_directive = {
        'en': "Respond in clear, academic English.",
        'ru': "Отвечайте на грамотном академическом русском языке.",
        'uz': "Akademik o'zbek tilida (lotin yozuvi, o' va g' apostroflari bilan) javob bering.",
    }.get(paper_lang, "Respond in clear, academic English.")

    system_prompt = (
        "You are an academic research assistant. The user has uploaded the paper "
        f"'{title}' by {author}. Below is the structured summary of the paper:\n\n"
        f"{context}\n\n"
        "Answer the user's questions about this paper based on this context. "
        "Be precise, academic, and helpful. "
        "If asked about content not present in the summary, say so honestly — do not invent details. "
        "Format your response in Markdown when helpful (bullet points, **bold** for key terms, "
        "inline `code` for variable names, blockquotes for direct claims). "
        "Keep answers concise unless the user explicitly asks for more detail. "
        f"{lang_directive}"
    )

    messages = [{'role': 'system', 'content': system_prompt}]
    # Keep the last 10 turns to fit context window comfortably
    for msg in list(history)[-10:]:
        messages.append({'role': msg.role, 'content': msg.content})
    messages.append({'role': 'user', 'content': question})

    try:
        response = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=messages,
            temperature=0.4,
            max_tokens=1500,
        )
    except APIStatusError as exc:
        logger.error('Groq chat status error %s: %s', exc.status_code, exc.message)
        if exc.status_code == 429:
            raise ValueError('Groq rate limit reached. Please wait a moment and try again.') from exc
        raise ValueError(f'Groq API error ({exc.status_code}): {exc.message}') from exc
    except APIConnectionError as exc:
        logger.error('Groq chat connection error: %s', exc)
        raise ValueError(f'Could not connect to Groq API: {exc}') from exc

    reply = (response.choices[0].message.content or '').strip()
    if not reply:
        raise ValueError('Empty response from model.')
    return reply


# ---- Orchestration -------------------------------------------------------

def summarize_paper_task(paper, text: str) -> None:
    """Summarize a Paper and persist the result.

    Generates the summary in `paper.language`, which was set by the upload
    flow (either auto-detected or user-overridden). UI language is irrelevant
    here — the summary always matches the paper's own language.
    """
    from .models import Summary

    lang = paper.language if paper.language in {'en', 'ru', 'uz'} else None
    result = summarize_paper_text(text, title=paper.title, language=lang)

    summary, _ = Summary.objects.get_or_create(paper=paper)
    summary.abstract    = result['abstract']
    summary.methodology = result['methodology']
    summary.results     = result['results']
    summary.conclusion  = result['conclusion']
    summary.language    = result.get('language', 'en')
    summary.set_key_points_list(result['key_points'])
    summary.set_citations_list(result.get('citations', []))
    summary.save()

    paper.processed = True
    paper.save(update_fields=['processed'])

    logger.info('Summary saved for paper pk=%s "%s" [lang=%s]', paper.pk, paper.title, summary.language)
