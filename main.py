"""Automated Video Dubbing System - Command Line Interface.

Accepts a YouTube URL or local video path, transcribes the speech,
translates it to English, synthesizes speech with neural voices,
and produces a dubbed MP4 video with the original visuals.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Initialize utilities and ensure FFmpeg is in PATH before other media imports
from src.utils import get_ffmpeg_path
get_ffmpeg_path()

from src.pipeline import run_dubbing_pipeline, PipelineError
from src.synthesizer import DEFAULT_VOICE


def print_banner() -> None:
    """Print clean CLI project header."""
    print("=" * 50)
    print("        Automated Video Dubbing System")
    print("    Idealabs Digital Internship Assignment")
    print("=" * 50)
    print()


def cli_progress_callback(stage_num: int, stage_name: str, status: str, details: Optional[str] = None) -> None:
    """Display real-time stage progress according to the UI/UX Brief specification."""
    if status == "start":
        print(f"[{stage_num}/6] {stage_name}")
    elif status == "success":
        detail_str = f" ({details})" if details else ""
        # Use safe checkmark supported by UTF-8 or ASCII fallback
        mark = "✓" if sys.stdout.encoding and "utf" in sys.stdout.encoding.lower() else "[OK]"
        print(f"  {mark} {stage_name}{detail_str}\n")


def parse_arguments() -> argparse.Namespace:
    """Configure and parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Automated Video Dubbing System: Dub YouTube or local videos into English.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=None,
        help="YouTube URL or path to a local video file."
    )
    parser.add_argument(
        "--model",
        default="base",
        choices=["tiny", "base", "small", "medium"],
        help="Whisper model size (optimized for CPU INT8 execution)."
    )
    parser.add_argument(
        "--voice",
        default=DEFAULT_VOICE,
        help="Edge-TTS neural English voice."
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Base directory to save outputs and intermediate artifacts."
    )
    parser.add_argument(
        "--acoustic-translation",
        action="store_true",
        default=False,
        help="Enable optional secondary Whisper acoustic translation pass for non-English audio."
    )
    return parser.parse_args()


def main() -> int:
    """Main program entry point."""
    print_banner()
    args = parse_arguments()

    source_url = args.url
    if not source_url:
        try:
            source_url = input("Enter YouTube URL or video path: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nOperation cancelled by user.")
            return 1

    if not source_url:
        print("Error: No YouTube URL or video path provided.", file=sys.stderr)
        return 1

    output_base_dir = Path(args.output_dir).resolve()

    try:
        job = run_dubbing_pipeline(
            source_input=source_url,
            output_base_dir=output_base_dir,
            whisper_model=args.model,
            voice=args.voice,
            enable_acoustic_translation=args.acoustic_translation,
            progress_callback=cli_progress_callback
        )

        print("-" * 50)
        print(f"Model:             {args.model}")
        print(f"Detected Language: {job.source_language.upper()}")
        print(f"Voice:             {args.voice}")
        print(f"Processing time:   {job.elapsed_formatted}")
        print()
        print("Output Video:")
        print(f"  {job.final_video_path}")
        print("-" * 50)
        return 0

    except PipelineError as exc:
        print(f"\n[PIPELINE FAILURE] {exc}", file=sys.stderr)
        print("Suggestion: Verify that the YouTube URL is public, network is accessible, and FFmpeg is installed.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Processing cancelled by user.", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"\n[UNEXPECTED ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
