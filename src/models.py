"""Data models for the Automated Video Dubbing System.

Defines the core data contracts (VideoJob and SpeechSegment) used
across pipeline stages, ensuring structured state and clean JSON serialization.
"""

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional
import time


@dataclass
class SpeechSegment:
    """Represents a discrete speech segment with timing and transcript data."""
    index: int
    start: float
    end: float
    source_text: str
    translated_text: str = ""
    audio_path: str = ""
    direct_translation: str = ""
    speaker_id: str = "speaker_0"

    @property
    def duration(self) -> float:
        """Original speech segment duration in seconds."""
        return max(0.0, self.end - self.start)

    def to_dict(self) -> Dict[str, Any]:
        """Convert segment to dictionary for JSON persistence."""
        return {
            "index": self.index,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "duration": round(self.duration, 3),
            "source_text": self.source_text,
            "translated_text": self.translated_text,
            "audio_path": self.audio_path,
            "direct_translation": self.direct_translation,
            "speaker_id": self.speaker_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SpeechSegment":
        """Instantiate SpeechSegment from a dictionary."""
        return cls(
            index=data.get("index", 0),
            start=float(data.get("start", 0.0)),
            end=float(data.get("end", 0.0)),
            source_text=data.get("source_text", ""),
            translated_text=data.get("translated_text", ""),
            audio_path=data.get("audio_path", ""),
            direct_translation=data.get("direct_translation", ""),
            speaker_id=data.get("speaker_id", "speaker_0"),
        )


@dataclass
class VideoJob:
    """Tracks state, file artifacts, and timing for a dubbing job."""
    job_id: str
    source_url: str
    output_dir: Path
    source_video_path: str = ""
    source_audio_path: str = ""
    source_language: str = ""
    transcript_path: str = ""
    translation_path: str = ""
    dubbed_audio_path: str = ""
    final_video_path: str = ""
    segments: List[SpeechSegment] = field(default_factory=list)
    status: str = "initialized"
    error: str = ""
    started_at: float = field(default_factory=time.time)
    completed_at: float = 0.0

    @property
    def elapsed_seconds(self) -> float:
        """Calculate total execution time in seconds."""
        if self.completed_at > 0:
            return max(0.0, self.completed_at - self.started_at)
        return max(0.0, time.time() - self.started_at)

    @property
    def elapsed_formatted(self) -> str:
        """Format execution time as HH:MM:SS."""
        total = int(self.elapsed_seconds)
        hours = total // 3600
        minutes = (total % 3600) // 60
        seconds = total % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize job state metadata."""
        return {
            "job_id": self.job_id,
            "source_url": self.source_url,
            "output_dir": str(self.output_dir),
            "source_video_path": self.source_video_path,
            "source_audio_path": self.source_audio_path,
            "source_language": self.source_language,
            "transcript_path": self.transcript_path,
            "translation_path": self.translation_path,
            "dubbed_audio_path": self.dubbed_audio_path,
            "final_video_path": self.final_video_path,
            "segment_count": len(self.segments),
            "status": self.status,
            "error": self.error,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "elapsed_formatted": self.elapsed_formatted,
        }
