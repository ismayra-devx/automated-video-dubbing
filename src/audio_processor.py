"""Audio assembly and timing synchronization module.

Places synthesized English speech segments onto the original video timeline,
handles duration differences, prevents overlapping speech, and preserves natural pauses.
"""

import subprocess
from pathlib import Path
from typing import List, Dict, Any, Tuple
from pydub import AudioSegment

from src.models import SpeechSegment
from src.utils import get_ffmpeg_path, get_ffprobe_path, get_media_duration

# Ensure pydub uses the resolved FFmpeg binaries even if not yet inherited in PATH
AudioSegment.converter = get_ffmpeg_path()
AudioSegment.ffprobe = get_ffprobe_path()


class AudioProcessingError(Exception):
    """Raised when audio assembly or timing synchronization fails."""
    pass


def adjust_audio_speed(input_path: Path, output_path: Path, speed_factor: float) -> Path:
    """Adjust audio playback speed using FFmpeg atempo filter without pitch distortion.
    
    Args:
        input_path: Source audio file.
        output_path: Target adjusted audio file.
        speed_factor: Speed multiplier (e.g. 1.15 for 15% faster).
        
    Returns:
        Path to the speed-adjusted audio file.
    """
    speed_factor = max(0.5, min(2.0, speed_factor))
    ffmpeg_bin = get_ffmpeg_path()
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", str(input_path),
        "-filter:a", f"atempo={speed_factor:.3f}",
        "-vn",
        str(output_path)
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path


def assemble_dubbed_audio(
    segments: List[SpeechSegment],
    total_duration_seconds: float,
    output_audio_path: Path,
    max_speedup_factor: float = 1.30
) -> Tuple[Path, Dict[str, Any]]:
    """Assemble all synthesized segments onto a master audio timeline.
    
    Timing strategy:
    - Base timeline is governed by the original segment timestamps (start, end).
    - If English audio duration exceeds the original segment window:
      1. If following silence allows it, let it naturally complete.
      2. If it would overlap into the next segment, apply mild tempo speedup (up to 1.3x).
    - If English audio is shorter, preserve remaining duration as natural silence/pause.
    - Guarantee that no two adjacent speech segments overlap.
    - Final master track duration matches source video duration.
    
    Args:
        segments: Synthesized speech segments with valid audio_path.
        total_duration_seconds: Duration of the original video in seconds.
        output_audio_path: Destination path for dubbed_audio.wav.
        max_speedup_factor: Maximum allowed tempo increase before clipping.
        
    Returns:
        Tuple of (output_audio_path, stats_dict).
        
    Raises:
        AudioProcessingError: If assembly fails or audio files are unreadable.
    """
    if total_duration_seconds <= 0:
        total_duration_seconds = 1.0

    output_audio_path.parent.mkdir(parents=True, exist_ok=True)
    total_ms = int(total_duration_seconds * 1000)
    
    # Initialize silent master track matching video duration exactly (44.1kHz, 16-bit, stereo)
    master_track = AudioSegment.silent(duration=total_ms, frame_rate=44100)
    current_timeline_ms = 0
    adjusted_count = 0
    placed_count = 0

    valid_segments = [s for s in segments if s.audio_path and Path(s.audio_path).exists()]

    for idx, seg in enumerate(valid_segments):
        audio_file = Path(seg.audio_path)
        try:
            clip = AudioSegment.from_file(str(audio_file))
        except Exception as exc:
            # Skip unreadable segment rather than aborting entire video
            continue

        clip_ms = len(clip)
        target_start_ms = int(seg.start * 1000)
        target_end_ms = int(seg.end * 1000)
        orig_window_ms = max(100, target_end_ms - target_start_ms)

        # Determine next segment start time to detect impending overlaps
        next_start_ms = int(valid_segments[idx + 1].start * 1000) if idx + 1 < len(valid_segments) else total_ms
        available_window_ms = max(100, next_start_ms - target_start_ms)

        # Apply mild tempo compression if speech exceeds the available window
        if clip_ms > available_window_ms:
            speed_ratio = clip_ms / available_window_ms
            # Clamp speedup between 1.05 and max_speedup_factor to keep speech natural
            effective_speedup = min(max_speedup_factor, max(1.05, speed_ratio))
            
            temp_adjusted = audio_file.parent / f"adj_{audio_file.stem}.wav"
            try:
                adjust_audio_speed(audio_file, temp_adjusted, effective_speedup)
                clip = AudioSegment.from_file(str(temp_adjusted))
                clip_ms = len(clip)
                adjusted_count += 1
            except Exception:
                # If speed adjustment fails, fall back to original clip
                pass

        # Prevent overlapping with previously placed speech
        placement_ms = max(target_start_ms, current_timeline_ms)

        # Ensure we do not place beyond video end
        if placement_ms < total_ms:
            # Overlay onto master track
            master_track = master_track.overlay(clip, position=placement_ms)
            placed_count += 1
            current_timeline_ms = placement_ms + clip_ms + 40  # 40ms buffer to guarantee separation

    # Export master dubbed track as high-quality WAV
    try:
        master_track.export(
            str(output_audio_path),
            format="wav",
            parameters=["-ar", "44100", "-ac", "2"]
        )
    except Exception as exc:
        raise AudioProcessingError(f"Failed to export assembled audio: {exc}") from exc

    stats = {
        "total_segments_input": len(segments),
        "segments_placed": placed_count,
        "segments_tempo_adjusted": adjusted_count,
        "master_duration_seconds": round(len(master_track) / 1000.0, 2),
        "target_duration_seconds": round(total_duration_seconds, 2)
    }

    return output_audio_path, stats
