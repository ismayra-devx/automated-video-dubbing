"""End-to-end pipeline orchestrator for the Automated Video Dubbing System.

Coordinates all six pipeline stages:
1. Download video & extract audio
2. Transcribe speech & detect language (Faster-Whisper)
3. Translate to natural English (Google/Translator adapter)
4. Synthesize English speech segments (Edge-TTS)
5. Assemble timeline & synchronize audio (FFmpeg/Pydub)
6. Mux dubbed audio with original video (FFmpeg stream copy)
"""

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Dict, Any

from src.models import VideoJob, SpeechSegment
from src.utils import get_ffmpeg_path, get_media_duration, check_ffmpeg_available
from src.downloader import download_media, DownloadError
from src.transcriber import transcribe_audio, TranscriptionError
from src.translator import translate_segments, TranslationError
from src.synthesizer import synthesize_segments, SynthesisError, DEFAULT_VOICE
from src.audio_processor import assemble_dubbed_audio, AudioProcessingError


class PipelineError(Exception):
    """Raised when an end-to-end dubbing pipeline stage fails."""
    pass


# Callback type for terminal progress reporting: (stage_num, stage_name, status, details)
ProgressCallback = Callable[[int, str, str, Optional[str]], None]


def default_progress_callback(stage_num: int, stage_name: str, status: str, details: Optional[str] = None) -> None:
    """Default logger when no custom CLI callback is provided."""
    pass


def run_dubbing_pipeline(
    source_input: str,
    output_base_dir: Path,
    whisper_model: str = "base",
    voice: str = DEFAULT_VOICE,
    enable_acoustic_translation: bool = False,
    progress_callback: ProgressCallback = default_progress_callback
) -> VideoJob:
    """Execute the full video dubbing pipeline.
    
    Args:
        source_input: YouTube URL or local video path.
        output_base_dir: Base directory for job artifacts.
        whisper_model: Whisper model size ('tiny', 'base', 'small').
        voice: edge-tts neural voice name.
        enable_acoustic_translation: Whether to run optional secondary Whisper acoustic translation.
        progress_callback: Callback for CLI stage updates.
        
    Returns:
        VideoJob object with complete metadata and artifact paths.
        
    Raises:
        PipelineError: If any pipeline stage fails.
    """
    # Verify FFmpeg availability before starting expensive tasks
    ffmpeg_ok, ffmpeg_info = check_ffmpeg_available()
    if not ffmpeg_ok:
        raise PipelineError(
            f"FFmpeg is not available: {ffmpeg_info}. "
            "Please ensure FFmpeg is installed and added to PATH."
        )

    # Initialize job directory and state
    job_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    job_id = f"job_{job_timestamp}"
    job_dir = output_base_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    job = VideoJob(
        job_id=job_id,
        source_url=source_input,
        output_dir=job_dir,
        started_at=time.time(),
        status="running"
    )

    try:
        # -------------------------------------------------------------
        # Stage 1: Download / Ingest Media
        # -------------------------------------------------------------
        progress_callback(1, "Downloading video...", "start", None)
        video_path, audio_path, dl_meta = download_media(source_input, job_dir)
        job.source_video_path = str(video_path)
        job.source_audio_path = str(audio_path)
        video_duration = dl_meta.get("duration", 0.0) or get_media_duration(video_path)
        progress_callback(1, "Download complete", "success", dl_meta.get("title"))

        # -------------------------------------------------------------
        # Stage 2: Transcribe Speech & Detect Language
        # -------------------------------------------------------------
        progress_callback(2, "Transcribing speech...", "start", None)
        transcript_file = job_dir / "transcript.json"
        segments, detected_lang, trans_meta = transcribe_audio(
            audio_path=audio_path,
            output_transcript_path=transcript_file,
            model_size=whisper_model,
            device="cpu",
            compute_type="int8",
            enable_acoustic_translation=enable_acoustic_translation
        )
        job.segments = segments
        job.source_language = detected_lang
        job.transcript_path = str(transcript_file)
        
        lang_display = f"Detected: {detected_lang.upper()} ({len(segments)} segments)"
        progress_callback(2, "Transcription complete", "success", lang_display)

        if not segments:
            raise PipelineError("No speech was detected in the video audio track.")

        # -------------------------------------------------------------
        # Stage 3: Translate to English
        # -------------------------------------------------------------
        progress_callback(3, "Translating to English...", "start", None)
        translation_file = job_dir / "translation.json"
        segments = translate_segments(
            segments=segments,
            source_language=detected_lang,
            output_translation_path=translation_file
        )
        job.segments = segments
        job.translation_path = str(translation_file)
        progress_callback(3, "Translation complete", "success", None)

        # -------------------------------------------------------------
        # Stage 4: Synthesize English Speech (TTS)
        # -------------------------------------------------------------
        progress_callback(4, "Generating English speech...", "start", None)
        segments_dir = job_dir / "segments"
        segments = synthesize_segments(
            segments=segments,
            output_segments_dir=segments_dir,
            voice=voice
        )
        job.segments = segments
        progress_callback(4, "Speech generated", "success", f"Voice: {voice}")

        # -------------------------------------------------------------
        # Stage 5: Assemble & Synchronize Dubbed Audio
        # -------------------------------------------------------------
        progress_callback(5, "Building dubbed audio...", "start", None)
        dubbed_audio_file = job_dir / "dubbed_audio.wav"
        dubbed_audio_path, audio_stats = assemble_dubbed_audio(
            segments=segments,
            total_duration_seconds=video_duration,
            output_audio_path=dubbed_audio_file
        )
        job.dubbed_audio_path = str(dubbed_audio_path)
        progress_callback(5, "Audio ready", "success", f"{audio_stats['segments_placed']} segments placed")

        # -------------------------------------------------------------
        # Stage 6: Mux Final Video with FFmpeg
        # -------------------------------------------------------------
        progress_callback(6, "Creating final video...", "start", None)
        final_video_file = job_dir / "dubbed_video.mp4"
        _mux_video_and_audio(video_path, dubbed_audio_path, final_video_file)

        # Verify output exists and is valid
        if not final_video_file.exists() or final_video_file.stat().st_size == 0:
            raise PipelineError("Dubbed video creation failed: output file is missing or empty.")

        final_duration = get_media_duration(final_video_file)
        if final_duration <= 0:
            raise PipelineError("Dubbed video verification failed: output file is not a valid playable video.")

        job.final_video_path = str(final_video_file)
        job.status = "completed"
        job.completed_at = time.time()
        progress_callback(6, "Done", "success", None)

        # Persist final job summary
        _save_job_summary(job)

        return job

    except (DownloadError, TranscriptionError, TranslationError, SynthesisError, AudioProcessingError) as exc:
        job.status = "failed"
        job.error = str(exc)
        job.completed_at = time.time()
        _save_job_summary(job)
        raise PipelineError(f"Pipeline failed: {exc}") from exc
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
        job.completed_at = time.time()
        _save_job_summary(job)
        raise PipelineError(f"Unexpected error during dubbing: {exc}") from exc


def _mux_video_and_audio(video_path: Path, audio_path: Path, output_video_path: Path) -> Path:
    """Mux original video stream with new dubbed audio stream.
    
    Prefers video stream copy (-c:v copy) to avoid quality loss and re-encoding latency.
    Encodes audio to standard AAC for maximum player compatibility.
    """
    ffmpeg_bin = get_ffmpeg_path()
    
    # Primary attempt: stream-copy video, encode audio to AAC
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(output_video_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Fallback: if container format requires video transcode
        fallback_cmd = [
            ffmpeg_bin,
            "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(output_video_path)
        ]
        fallback_res = subprocess.run(fallback_cmd, capture_output=True, text=True)
        if fallback_res.returncode != 0:
            err = fallback_res.stderr.strip() if fallback_res.stderr else result.stderr.strip()
            raise PipelineError(f"FFmpeg muxing failed: {err}")

    return output_video_path


def _save_job_summary(job: VideoJob) -> None:
    """Persist final execution summary JSON in job directory."""
    summary_file = job.output_dir / "job_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(job.to_dict(), f, indent=2)
