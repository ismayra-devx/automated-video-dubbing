"""Unit tests for translation adapter and English pass-through."""

import pytest
from src.models import SpeechSegment
from src.translator import translate_segments, _resolve_source_locale


def test_english_passthrough():
    """Verify English inputs bypass external translation completely."""
    segments = [
        SpeechSegment(index=1, start=0.0, end=3.0, source_text="This is already English."),
        SpeechSegment(index=2, start=3.5, end=6.0, source_text="It should not be modified.")
    ]
    res = translate_segments(segments, source_language="en")
    assert res[0].translated_text == "This is already English."
    assert res[1].translated_text == "It should not be modified."


def test_locale_resolution():
    """Verify ISO 639-1 to standard national locale mapping."""
    assert _resolve_source_locale("es") == "es-ES"
    assert _resolve_source_locale("de") == "de-DE"
    assert _resolve_source_locale("hi") == "hi-IN"
    assert _resolve_source_locale("fr") == "fr-FR"
    assert _resolve_source_locale("it") == "it-IT"


def test_empty_segment_translation():
    """Verify empty or whitespace segments do not cause failures."""
    segments = [
        SpeechSegment(index=1, start=0.0, end=1.0, source_text="   "),
        SpeechSegment(index=2, start=1.5, end=2.5, source_text="")
    ]
    res = translate_segments(segments, source_language="es")
    assert res[0].translated_text == ""
    assert res[1].translated_text == ""
