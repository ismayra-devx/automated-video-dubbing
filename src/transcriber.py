"""Speech-to-text transcription module using Faster-Whisper.

Performs automatic language detection and extracts timestamped speech segments
using CTranslate2 with INT8 quantization, optimized for fast CPU execution.
"""

import json
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from faster_whisper import WhisperModel

from src.models import SpeechSegment


class TranscriptionError(Exception):
    """Raised when speech transcription or model inference fails."""
    pass


def transcribe_audio(
    audio_path: Path,
    output_transcript_path: Optional[Path] = None,
    model_size: str = "base",
    device: str = "cpu",
    compute_type: str = "int8",
    num_threads: int = 4,
    enable_acoustic_translation: bool = False
) -> Tuple[List[SpeechSegment], str, Dict[str, Any]]:
    """Transcribe an audio file into timestamped SpeechSegments.
    
    Performs a single-pass Whisper transcription by default to maximize CPU efficiency.
    Acoustic translation pass (task='translate') is optional and disabled by default.
    
    Args:
        audio_path: Path to the 16kHz WAV audio file.
        output_transcript_path: Optional path to save transcript.json.
        model_size: Whisper model size ('tiny', 'base', 'small', 'medium').
        device: Execution device ('cpu' or 'cuda').
        compute_type: Quantization type ('int8', 'float16', 'float32').
        num_threads: Number of CPU worker threads.
        enable_acoustic_translation: If True, executes an optional second Whisper pass for direct acoustic translation.
        
    Returns:
        Tuple of (list_of_segments, detected_language, metadata_dict).
        
    Raises:
        TranscriptionError: If audio file is invalid or transcription fails.
    """
    if not audio_path.exists():
        raise TranscriptionError(f"Audio file not found: {audio_path}")

    try:
        # Load CTranslate2 Whisper model with INT8 quantization for optimal CPU efficiency
        model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            cpu_threads=num_threads
        )
        
        # Single-pass transcription with Voice Activity Detection (VAD) filter
        segments_gen, info = model.transcribe(
            str(audio_path),
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=400)
        )
        
        detected_language = info.language
        lang_prob = getattr(info, "language_probability", 1.0)
        
        segments: List[SpeechSegment] = []
        for idx, seg in enumerate(segments_gen, start=1):
            text = seg.text.strip()
            if not text:
                continue
            
            speech_seg = SpeechSegment(
                index=idx,
                start=round(seg.start, 3),
                end=round(seg.end, 3),
                source_text=text
            )
            segments.append(speech_seg)

        # Optional acoustic translation pass: disabled by default to keep long benchmark runs fast on CPU
        if enable_acoustic_translation and detected_language != "en" and segments:
            try:
                trans_gen, _ = model.transcribe(
                    str(audio_path),
                    task="translate",
                    beam_size=5,
                    vad_filter=True
                )
                trans_list = [s.text.strip() for s in trans_gen if s.text.strip()]
                if len(trans_list) == len(segments):
                    for i, seg in enumerate(segments):
                        seg.direct_translation = trans_list[i]
                elif trans_list:
                    full_direct = " ".join(trans_list)
                    segments[0].direct_translation = full_direct
            except Exception:
                pass
            
    except Exception as exc:
        raise TranscriptionError(f"Whisper transcription failed: {exc}") from exc

    metadata = {
        "model_size": model_size,
        "device": device,
        "compute_type": compute_type,
        "detected_language": detected_language,
        "language_probability": round(lang_prob, 4),
        "total_segments": len(segments),
        "audio_duration": round(getattr(info, "duration", 0.0), 2)
    }

    # Persist transcript artifact for debugging and inspection
    if output_transcript_path:
        output_transcript_path.parent.mkdir(parents=True, exist_ok=True)
        transcript_data = {
            "metadata": metadata,
            "segments": [seg.to_dict() for seg in segments]
        }
        with open(output_transcript_path, "w", encoding="utf-8") as f:
            json.dump(transcript_data, f, indent=2, ensure_ascii=False)

    return segments, detected_language, metadata
