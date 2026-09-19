"""Unit tests for core data models (SpeechSegment and VideoJob)."""

import pytest
from pathlib import Path
from src.models import SpeechSegment, VideoJob


def test_speech_segment_duration():
    """Verify segment duration calculation and properties."""
    seg = SpeechSegment(
        index=1,
        start=1.5,
        end=4.2,
        source_text="Hallo Welt",
        translated_text="Hello World"
    )
    assert seg.duration == pytest.approx(2.7, 0.001)
    assert seg.index == 1
    assert seg.source_text == "Hallo Welt"
    assert seg.translated_text == "Hello World"


def test_speech_segment_serialization():
    """Verify to_dict and from_dict roundtrip."""
    original = SpeechSegment(
        index=2,
        start=5.0,
        end=7.8,
        source_text="Comment allez-vous?",
        translated_text="How are you?",
        audio_path="outputs/job/segments/segment_0002.mp3",
        speaker_id="speaker_1"
    )
    data = original.to_dict()
    assert data["index"] == 2
    assert data["start"] == 5.0
    assert data["end"] == 7.8
    assert data["duration"] == 2.8
    assert data["source_text"] == "Comment allez-vous?"
    assert data["speaker_id"] == "speaker_1"

    restored = SpeechSegment.from_dict(data)
    assert restored.index == original.index
    assert restored.start == original.start
    assert restored.end == original.end
    assert restored.source_text == original.source_text
    assert restored.translated_text == original.translated_text
    assert restored.audio_path == original.audio_path
    assert restored.speaker_id == "speaker_1"


def test_video_job_elapsed_formatting():
    """Verify time formatting helper."""
    job = VideoJob(
        job_id="test_job",
        source_url="https://youtube.com/watch?v=12345",
        output_dir=Path("/tmp/outputs"),
        started_at=100.0,
        completed_at=174.0  # 74 seconds elapsed = 00:01:14
    )
    assert job.elapsed_seconds == 74.0
    assert job.elapsed_formatted == "00:01:14"


def test_video_job_serialization():
    """Verify VideoJob dictionary serialization."""
    job = VideoJob(
        job_id="job_001",
        source_url="local_test.mp4",
        output_dir=Path("/tmp/test"),
        source_language="es",
        status="completed"
    )
    d = job.to_dict()
    assert d["job_id"] == "job_001"
    assert d["source_language"] == "es"
    assert d["status"] == "completed"
    assert "elapsed_formatted" in d
