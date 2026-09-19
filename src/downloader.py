"""Video and audio downloader module using yt-dlp and FFmpeg.

Downloads YouTube videos locally, extracts audio in 16kHz mono WAV format
optimized for speech transcription, and supports local video paths for offline testing.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple
import yt_dlp

from src.utils import get_ffmpeg_path, get_media_duration


class DownloadError(Exception):
    """Raised when video acquisition or audio extraction fails."""
    pass


def is_url(path_or_url: str) -> bool:
    """Determine whether the input string is a web URL."""
    return path_or_url.startswith("http://") or path_or_url.startswith("https://")


def download_media(source_input: str, output_dir: Path) -> Tuple[Path, Path, Dict[str, Any]]:
    """Download or ingest source video and extract 16kHz WAV audio.
    
    Args:
        source_input: YouTube URL or path to a local video file.
        output_dir: Target directory where artifacts will be saved.
        
    Returns:
        Tuple of (video_path, audio_path, metadata_dict).
        
    Raises:
        DownloadError: If download, validation, or audio extraction fails.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    video_target = output_dir / "source.mp4"
    audio_target = output_dir / "source_audio.wav"
    metadata: Dict[str, Any] = {}

    if not is_url(source_input):
        # Handle local video file input
        local_path = Path(source_input)
        if not local_path.exists() or not local_path.is_file():
            raise DownloadError(f"Local file not found: {source_input}")
        
        # Copy to destination if not already there
        if local_path.resolve() != video_target.resolve():
            shutil.copy2(local_path, video_target)
            
        metadata = {
            "title": local_path.stem,
            "duration": get_media_duration(video_target),
            "uploader": "Local Source",
        }
    else:
        # Download from YouTube via yt-dlp
        ydl_opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": str(output_dir / "source.%(ext)s"),
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(source_input, download=True)
                if info is None:
                    raise DownloadError(f"Could not retrieve video information from {source_input}")
                
                metadata = {
                    "title": info.get("title", "Unknown Title"),
                    "duration": float(info.get("duration", 0.0)),
                    "uploader": info.get("uploader", "Unknown Uploader"),
                }
        except yt_dlp.utils.DownloadError as exc:
            raise DownloadError(f"Failed to download video from YouTube: {exc}") from exc
        except Exception as exc:
            raise DownloadError(f"Unexpected error during download: {exc}") from exc

        # Locate resulting video file (in case extension differed)
        if not video_target.exists():
            downloaded = list(output_dir.glob("source.*"))
            valid_videos = [f for f in downloaded if f.suffix.lower() in [".mp4", ".mkv", ".webm"]]
            if valid_videos:
                if valid_videos[0].suffix.lower() != ".mp4":
                    # Convert to MP4 container using stream copy
                    ffmpeg_bin = get_ffmpeg_path()
                    subprocess.run(
                        [ffmpeg_bin, "-y", "-i", str(valid_videos[0]), "-c", "copy", str(video_target)],
                        capture_output=True,
                        check=True
                    )
                else:
                    video_target = valid_videos[0]
            else:
                raise DownloadError("Download completed but output video file was not found.")

    # Extract 16kHz mono WAV audio track for Whisper
    extract_audio_for_transcription(video_target, audio_target)

    return video_target, audio_target, metadata


def extract_audio_for_transcription(video_path: Path, output_audio_path: Path) -> Path:
    """Extract 16kHz mono WAV from video using FFmpeg.
    
    Whisper models achieve optimal accuracy with single-channel 16,000 Hz PCM audio.
    """
    ffmpeg_bin = get_ffmpeg_path()
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", str(video_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(output_audio_path)
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        err_msg = exc.stderr.strip() if exc.stderr else str(exc)
        raise DownloadError(f"Failed to extract audio using FFmpeg: {err_msg}") from exc
    except FileNotFoundError:
        raise DownloadError(f"FFmpeg binary not found at '{ffmpeg_bin}'. Please install FFmpeg.")

    if not output_audio_path.exists() or output_audio_path.stat().st_size == 0:
        raise DownloadError("Extracted audio file is missing or empty.")

    return output_audio_path
