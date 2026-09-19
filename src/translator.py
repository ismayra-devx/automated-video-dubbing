"""Translation module to convert transcripts into natural English.

Translates non-English speech segments into natural, fluent English phrasing
while preserving segment boundaries, timestamps, and context.
Supports major European and Indian languages with resilient engine fallback.
"""

import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from deep_translator import MyMemoryTranslator, GoogleTranslator

from src.models import SpeechSegment


class TranslationError(Exception):
    """Raised when segment translation fails."""
    pass


# Map ISO 639-1 language codes to standard MyMemory locale codes
LOCALE_MAP = {
    "es": "es-ES",
    "de": "de-DE",
    "hi": "hi-IN",
    "fr": "fr-FR",
    "it": "it-IT",
    "pt": "pt-PT",
    "ja": "ja-JP",
    "ko": "ko-KR",
    "zh": "zh-CN",
    "ru": "ru-RU",
    "ar": "ar-SA",
    "ta": "ta-IN",
    "te": "te-IN",
    "mr": "mr-IN",
    "bn": "bn-IN",
    "gu": "gu-IN",
    "kn": "kn-IN",
    "ml": "ml-IN",
    "pa": "pa-IN",
    "ur": "ur-PK",
    "nl": "nl-NL",
    "tr": "tr-TR",
    "pl": "pl-PL",
    "uk": "uk-UA",
    "vi": "vi-VN",
}


def _resolve_source_locale(source_lang: str) -> str:
    """Map detected 2-letter language code to standard locale."""
    clean = source_lang.strip().lower()[:2]
    return LOCALE_MAP.get(clean, f"{clean}-{clean.upper()}")


def translate_text(text: str, source_language: str = "auto") -> str:
    """Translate text to natural English using primary and fallback engines.
    
    Tries MyMemory first for natural colloquial phrasing; falls back to Google
    Translator if MyMemory encounters errors or rate limits.
    """
    clean_text = text.strip()
    if not clean_text:
        return ""

    src_locale = _resolve_source_locale(source_language)

    # Primary engine: MyMemory (high quality natural phrase translations)
    try:
        translated = MyMemoryTranslator(source=src_locale, target="en-GB").translate(clean_text)
        if translated and translated.strip():
            return translated.strip()
    except Exception:
        pass

    # Fallback engine: Google Translator
    try:
        clean_code = source_language.lower()[:2] if source_language != "auto" else "auto"
        translated = GoogleTranslator(source=clean_code, target="en").translate(clean_text)
        if translated and translated.strip():
            return translated.strip()
    except Exception:
        pass

    # If both engines fail, return source text as safe fallback
    return clean_text


def _contains_non_latin(text: str) -> bool:
    """Check if text contains untranslated non-Latin script characters.
    
    Used to detect when a translation engine failed to translate non-Latin scripts
    (such as Devanagari, Arabic/Urdu, or CJK) into English.
    """
    import re
    # Matches Arabic, Devanagari, Bengali, Gurmukhi, Gujarati, Oriya, Tamil, Telugu, Kannada, Malayalam, CJK, and Cyrillic
    non_latin_pattern = r'[\u0600-\u06FF\u0900-\u0D7F\u4E00-\u9FFF\u3040-\u30FF\u0400-\u04FF]'
    return bool(re.search(non_latin_pattern, text))


def translate_segments(
    segments: List[SpeechSegment],
    source_language: str = "auto",
    output_translation_path: Optional[Path] = None
) -> List[SpeechSegment]:
    """Translate a list of SpeechSegments into natural English.
    
    Args:
        segments: Timestamped speech segments from the transcriber.
        source_language: Detected source language code or 'auto'.
        output_translation_path: Optional path to save translation.json.
        
    Returns:
        List of SpeechSegments with translated_text populated.
    """
    if not segments:
        return []

    # If already English, pass through without external requests
    if source_language.lower() in ["en", "english"]:
        for seg in segments:
            seg.translated_text = seg.source_text
            
        if output_translation_path:
            _save_translation_artifact(output_translation_path, segments, source_language)
        return segments

    for seg in segments:
        text = seg.source_text.strip()
        if not text:
            seg.translated_text = ""
            continue
        
        translated = translate_text(text, source_language=source_language)
        
        # If translation output still contains non-Latin characters or failed to translate,
        # use the Whisper acoustic direct translation if available
        if (_contains_non_latin(translated) or translated == text) and seg.direct_translation:
            seg.translated_text = seg.direct_translation
        else:
            seg.translated_text = translated

    # Save intermediate translation artifact for auditing and debugging
    if output_translation_path:
        _save_translation_artifact(output_translation_path, segments, source_language)

    return segments


def _save_translation_artifact(
    output_path: Path,
    segments: List[SpeechSegment],
    source_language: str
) -> None:
    """Persist structured translation JSON to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_language": source_language,
        "target_language": "en",
        "segment_count": len(segments),
        "segments": [seg.to_dict() for seg in segments]
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
