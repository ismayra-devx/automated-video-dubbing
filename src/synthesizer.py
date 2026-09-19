"""Text-to-speech synthesis module using edge-tts.

Generates natural, high-fidelity neural English speech for each translated segment.
"""

import asyncio
from pathlib import Path
from typing import List, Optional
import edge_tts

from src.models import SpeechSegment


class SynthesisError(Exception):
    """Raised when text-to-speech synthesis fails."""
    pass


DEFAULT_VOICE = "en-US-ChristopherNeural"
MAX_CONCURRENT_TTS = 3  # Conservative concurrency to prevent rate-limiting by Edge-TTS


async def _synthesize_single_segment(
    seg: SpeechSegment,
    voice: str,
    output_path: Path,
    semaphore: asyncio.Semaphore
) -> None:
    """Asynchronously synthesize text into an audio file using edge-tts with retry."""
    text = seg.translated_text.strip()
    if not text:
        seg.audio_path = ""
        return

    async with semaphore:
        for attempt in range(2):
            try:
                communicate = edge_tts.Communicate(text=text, voice=voice)
                await communicate.save(str(output_path))
                if output_path.exists() and output_path.stat().st_size > 0:
                    seg.audio_path = str(output_path)
                    return
            except Exception:
                if attempt == 0:
                    await asyncio.sleep(0.5)  # brief backoff before retry
        seg.audio_path = ""


async def _synthesize_all_segments(
    segments: List[SpeechSegment],
    output_dir: Path,
    voice: str,
    max_concurrency: int = MAX_CONCURRENT_TTS
) -> None:
    """Synthesize all segments concurrently within a single async event loop."""
    semaphore = asyncio.Semaphore(max_concurrency)
    tasks = []
    for seg in segments:
        segment_file = output_dir / f"segment_{seg.index:04d}.mp3"
        tasks.append(_synthesize_single_segment(seg, voice, segment_file, semaphore))
    await asyncio.gather(*tasks)


def synthesize_segments(
    segments: List[SpeechSegment],
    output_segments_dir: Path,
    voice: str = DEFAULT_VOICE,
    max_concurrency: int = MAX_CONCURRENT_TTS
) -> List[SpeechSegment]:
    """Generate audio files for all translated speech segments.
    
    Uses a single async event loop with controlled concurrency (semaphore)
    to balance speed with server rate-limit safety.
    
    Args:
        segments: List of SpeechSegments containing translated_text.
        output_segments_dir: Directory where segment audio files will be stored.
        voice: edge-tts neural voice identifier.
        max_concurrency: Maximum simultaneous TTS HTTP requests.
        
    Returns:
        List of SpeechSegments with audio_path set.
        
    Raises:
        SynthesisError: If synthesis fails across segments.
    """
    if not segments:
        return []

    output_segments_dir.mkdir(parents=True, exist_ok=True)
    asyncio.run(_synthesize_all_segments(segments, output_segments_dir, voice, max_concurrency))

    non_empty = [s for s in segments if s.translated_text.strip()]
    success_count = sum(1 for s in non_empty if s.audio_path and Path(s.audio_path).exists())

    if non_empty and success_count == 0:
        raise SynthesisError(
            f"Failed to synthesize audio for segments using voice '{voice}'. "
            "Please check network connection or try another voice."
        )

    return segments
