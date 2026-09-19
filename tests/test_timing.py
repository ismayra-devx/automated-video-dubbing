"""Unit tests for audio timing and synchronization logic."""

import pytest
from src.models import SpeechSegment
from src.downloader import is_url


def test_is_url():
    """Verify URL vs local path discrimination."""
    assert is_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") is True
    assert is_url("http://youtu.be/dQw4w9WgXcQ") is True
    assert is_url("sample_video.mp4") is False
    assert is_url("C:\\path\\to\\video.mp4") is False
    assert is_url("/home/user/video.mp4") is False


def test_segment_timing_integrity():
    """Verify segment timing and non-negative duration constraints."""
    seg1 = SpeechSegment(index=1, start=0.0, end=2.5, source_text="First")
    seg2 = SpeechSegment(index=2, start=3.0, end=5.5, source_text="Second")
    
    assert seg1.end <= seg2.start
    assert seg1.duration > 0
    assert seg2.duration > 0


def test_timing_overlap_prevention():
    """Verify simulated timeline sequence avoids overlapping speech."""
    # Simulate three segments where segment 1 speech overruns past segment 2 start
    placed_timeline = []
    current_timeline_ms = 0
    buffer_ms = 40

    simulated_segments = [
        {"start_ms": 1000, "duration_ms": 3000},  # ends at 4000
        {"start_ms": 2500, "duration_ms": 2000},  # requested start 2500, but 1 is still playing!
        {"start_ms": 6000, "duration_ms": 1500},
    ]

    for item in simulated_segments:
        target_start = item["start_ms"]
        duration = item["duration_ms"]
        
        # Placement logic from audio_processor
        actual_placement = max(target_start, current_timeline_ms)
        placed_timeline.append((actual_placement, actual_placement + duration))
        current_timeline_ms = actual_placement + duration + buffer_ms

    # Segment 1 placed at 1000 -> 4000
    assert placed_timeline[0] == (1000, 4000)
    # Segment 2 shifted to 4040 -> 6040 (no overlap with 1!)
    assert placed_timeline[1] == (4040, 6040)
    # Segment 3 placed at 6080 -> 7580
    assert placed_timeline[2] == (6080, 7580)
    
    # Assert absolutely no overlaps
    for i in range(len(placed_timeline) - 1):
        assert placed_timeline[i][1] <= placed_timeline[i + 1][0]
