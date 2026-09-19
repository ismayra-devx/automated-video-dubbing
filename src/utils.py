"""Shared utility functions for media inspection, process execution, and formatting."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple


def get_ffmpeg_path() -> str:
    """Resolve the path to the ffmpeg executable.
    
    Checks environment variable FFMPEG_PATH, standard system PATH,
    and common Windows installation directories (WinGet/Gyan).
    """
    env_path = os.environ.get("FFMPEG_PATH")
    if env_path and Path(env_path).exists():
        _ensure_in_path(Path(env_path).parent)
        return env_path

    in_path = shutil.which("ffmpeg")
    if in_path:
        return in_path

    # Common Windows winget package paths
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        winget_root = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if winget_root.exists():
            for p in winget_root.rglob("ffmpeg.exe"):
                _ensure_in_path(p.parent)
                return str(p)

    return "ffmpeg"


def _ensure_in_path(directory: Path) -> None:
    """Ensure directory is present in process PATH."""
    dir_str = str(directory)
    paths = os.environ.get("PATH", "").split(os.pathsep)
    if dir_str not in paths:
        os.environ["PATH"] = dir_str + os.pathsep + os.environ.get("PATH", "")


def get_ffprobe_path() -> str:
    """Resolve the path to the ffprobe executable."""
    env_path = os.environ.get("FFPROBE_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    in_path = shutil.which("ffprobe")
    if in_path:
        return in_path

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        winget_root = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if winget_root.exists():
            for p in winget_root.rglob("ffprobe.exe"):
                return str(p)

    return "ffprobe"


def check_ffmpeg_available() -> Tuple[bool, str]:
    """Verify that FFmpeg is callable and return its version string or error."""
    ffmpeg_bin = get_ffmpeg_path()
    try:
        proc = subprocess.run(
            [ffmpeg_bin, "-version"],
            capture_output=True,
            text=True,
            check=True
        )
        first_line = proc.stdout.splitlines()[0] if proc.stdout else "FFmpeg available"
        return True, first_line
    except Exception as exc:
        return False, str(exc)


def get_media_duration(file_path: Path) -> float:
    """Retrieve media duration in seconds using ffprobe.
    
    Returns 0.0 if ffprobe fails or duration cannot be extracted.
    """
    ffprobe_bin = get_ffprobe_path()
    cmd = [
        ffprobe_bin,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path)
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(proc.stdout.strip())
    except Exception:
        return 0.0
