"""Unit tests for CLI argument parsing and options."""

import pytest
import sys
from main import parse_arguments


def test_cli_defaults(monkeypatch):
    """Verify default CLI arguments."""
    monkeypatch.setattr(sys, "argv", ["main.py", "https://youtu.be/test123"])
    args = parse_arguments()
    assert args.url == "https://youtu.be/test123"
    assert args.model == "base"
    assert args.voice == "en-US-ChristopherNeural"
    assert args.output_dir == "outputs"
    assert args.acoustic_translation is False


def test_cli_custom_flags(monkeypatch):
    """Verify custom flags override defaults correctly."""
    monkeypatch.setattr(
        sys, "argv",
        [
            "main.py",
            "https://youtu.be/demo",
            "--model", "small",
            "--voice", "en-US-AriaNeural",
            "--output-dir", "custom_outputs",
            "--acoustic-translation"
        ]
    )
    args = parse_arguments()
    assert args.url == "https://youtu.be/demo"
    assert args.model == "small"
    assert args.voice == "en-US-AriaNeural"
    assert args.output_dir == "custom_outputs"
    assert args.acoustic_translation is True
