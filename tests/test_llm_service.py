import json

import groq
import httpx
import pytest

from summarizer import services
from summarizer.models import Summary
from summarizer.services import (
    SummarizationError,
    _parse_response,
    detect_language,
    extract_tags_from_text,
    summarize_paper_task,
    summarize_paper_text,
)
from tests.conftest import SAMPLE_TEXT, VALID_SUMMARY, completion

REQUEST = httpx.Request('POST', 'https://api.groq.com/openai/v1/chat/completions')


def status_error(cls, code: int):
    return cls(f'HTTP {code}', response=httpx.Response(code, request=REQUEST), body=None)


class TestDetectLanguage:
    def test_english(self):
        assert detect_language('Plain English research text') == 'en'

    def test_russian(self):
        assert detect_language('Это научная статья о машинном обучении') == 'ru'

    def test_uzbek_cyrillic(self):
        assert detect_language('Бу илмий мақола ҳақида ғоя') == 'uz'

    def test_empty_defaults_to_english(self):
        assert detect_language('12345 !!!') == 'en'


class TestParseResponse:
    def test_valid_json(self):
        result = _parse_response(json.dumps(VALID_SUMMARY))
        assert result['abstract'] == VALID_SUMMARY['abstract']
        assert result['key_points'] == VALID_SUMMARY['key_points']
        assert result['citations'] == VALID_SUMMARY['citations']

    def test_strips_markdown_fences(self):
        result = _parse_response(f'```json\n{json.dumps(VALID_SUMMARY)}\n```')
        assert result['conclusion'] == 'Attention suffices.'

    def test_newline_separated_strings_become_lists(self):
        data = {**VALID_SUMMARY, 'key_points': 'one\n\n two \nthree', 'citations': 'a\nb'}
        result = _parse_response(json.dumps(data))
        assert result['key_points'] == ['one', 'two', 'three']
        assert result['citations'] == ['a', 'b']

    def test_null_and_non_string_fields_are_coerced(self):
        data = {**VALID_SUMMARY, 'methodology': None, 'results': 42, 'key_points': ['x', None, 3]}
        result = _parse_response(json.dumps(data))
        assert result['methodology'] == ''
        assert result['results'] == '42'
        assert result['key_points'] == ['x', '3']

    def test_missing_fields_default_to_empty(self):
        result = _parse_response(json.dumps({'abstract': 'Only abstract'}))
        assert result['key_points'] == []
        assert result['methodology'] == ''

    @pytest.mark.parametrize(
        'raw',
        ['no json here', '{"abstract": "unterminated', '{}', '{"abstract": "", "key_points": []}'],
    )
    def test_invalid_payloads_raise(self, raw):
        with pytest.raises(SummarizationError):
            _parse_response(raw)


class TestSummarizePaperText:
    def test_happy_path_uses_configured_model_and_json_mode(self, mock_groq, settings):
        settings.GROQ_MODEL = 'llama-3.3-70b-versatile'
        result = summarize_paper_text(SAMPLE_TEXT, title='Attention')

        assert result['language'] == 'en'
        assert result['abstract'] == VALID_SUMMARY['abstract']
        kwargs = mock_groq.chat.completions.create.call_args.kwargs
        assert kwargs['model'] == 'llama-3.3-70b-versatile'
        assert kwargs['response_format'] == {'type': 'json_object'}
        assert 'Title: Attention' in kwargs['messages'][1]['content']

    def test_selects_russian_prompt(self, mock_groq):
        result = summarize_paper_text('Это научная статья о нейронных сетях и обучении')
        assert result['language'] == 'ru'
        system = mock_groq.chat.completions.create.call_args.kwargs['messages'][0]['content']
        assert 'РУССКОМ' in system

    def test_truncates_long_text(self, mock_groq):
        summarize_paper_text('a' * (services.MAX_TEXT_CHARS + 5000))
        user_msg = mock_groq.chat.completions.create.call_args.kwargs['messages'][1]['content']
        assert len(user_msg) < services.MAX_TEXT_CHARS + 500

    def test_missing_api_key(self, settings, mock_groq):
        settings.GROQ_API_KEY = ''
        with pytest.raises(SummarizationError, match='GROQ_API_KEY'):
            summarize_paper_text(SAMPLE_TEXT)
        mock_groq.chat.completions.create.assert_not_called()

    @pytest.mark.parametrize(
        ('error', 'message'),
        [
            (status_error(groq.RateLimitError, 429), 'rate limit'),
            (status_error(groq.InternalServerError, 503), 'HTTP 503'),
            (status_error(groq.NotFoundError, 404), 'HTTP 404'),
            (groq.APITimeoutError(request=REQUEST), 'timed out'),
            (groq.APIConnectionError(request=REQUEST), 'connect'),
        ],
    )
    def test_api_errors_become_friendly_errors(self, mock_groq, error, message):
        mock_groq.chat.completions.create.side_effect = error
        with pytest.raises(SummarizationError, match=message):
            summarize_paper_text(SAMPLE_TEXT)

    def test_empty_completion(self, mock_groq):
        mock_groq.chat.completions.create.return_value = completion(None)
        with pytest.raises(SummarizationError, match='empty'):
            summarize_paper_text(SAMPLE_TEXT)

    def test_client_gets_timeout_and_retries(self, mock_groq, settings, monkeypatch):
        settings.GROQ_TIMEOUT = 12
        settings.GROQ_MAX_RETRIES = 1
        summarize_paper_text(SAMPLE_TEXT)
        services.Groq.assert_called_once_with(api_key='test-groq-key', timeout=12, max_retries=1)


class TestExtractTags:
    def test_returns_deduplicated_tags(self, mock_groq):
        mock_groq.chat.completions.create.return_value = completion(
            '```json\n["Deep Learning", "deep learning", "NLP", "", "Transformers"]\n```'
        )
        assert extract_tags_from_text(SAMPLE_TEXT, max_tags=5) == [
            'Deep Learning',
            'NLP',
            'Transformers',
        ]

    def test_respects_max_tags(self, mock_groq):
        mock_groq.chat.completions.create.return_value = completion('["a", "b", "c"]')
        assert extract_tags_from_text(SAMPLE_TEXT, max_tags=2) == ['a', 'b']

    @pytest.mark.parametrize('raw', ['no array', '[broken', '{"tags": 1}'])
    def test_bad_output_returns_empty(self, mock_groq, raw):
        mock_groq.chat.completions.create.return_value = completion(raw)
        assert extract_tags_from_text(SAMPLE_TEXT) == []

    def test_api_failure_never_raises(self, mock_groq):
        mock_groq.chat.completions.create.side_effect = groq.APIConnectionError(request=REQUEST)
        assert extract_tags_from_text(SAMPLE_TEXT) == []

    def test_missing_key_never_raises(self, settings, mock_groq):
        settings.GROQ_API_KEY = ''
        assert extract_tags_from_text(SAMPLE_TEXT) == []


class TestSummarizePaperTask:
    def test_persists_summary_and_marks_processed(self, mock_groq, paper):
        summary = summarize_paper_task(paper, SAMPLE_TEXT)

        paper.refresh_from_db()
        assert paper.processed is True
        assert summary.get_key_points_list() == VALID_SUMMARY['key_points']
        assert summary.get_citations_list() == VALID_SUMMARY['citations']

    def test_rerun_updates_existing_summary(self, mock_groq, paper, summary):
        new = {**VALID_SUMMARY, 'abstract': 'Updated abstract'}
        mock_groq.chat.completions.create.return_value = completion(json.dumps(new))
        summarize_paper_task(paper, SAMPLE_TEXT)
        assert Summary.objects.count() == 1
        assert Summary.objects.get().abstract == 'Updated abstract'

    def test_failure_leaves_paper_unprocessed(self, mock_groq, paper):
        mock_groq.chat.completions.create.return_value = completion('not json')
        with pytest.raises(SummarizationError):
            summarize_paper_task(paper, SAMPLE_TEXT)
        paper.refresh_from_db()
        assert paper.processed is False
        assert not Summary.objects.exists()
