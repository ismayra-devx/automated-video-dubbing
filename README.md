# Automated Video Dubbing System

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![FFmpeg Powered](https://img.shields.io/badge/FFmpeg-9.0-orange.svg)](https://ffmpeg.org/)
[![Faster-Whisper](https://img.shields.io/badge/ASR-Faster--Whisper-purple.svg)](https://github.com/SYSTRAN/faster-whisper)
[![Edge-TTS](https://img.shields.io/badge/TTS-Edge--TTS-cyan.svg)](https://github.com/rany2/edge-tts)

An automated, local Python command-line system that accepts a YouTube URL (or local video) in a non-English language and produces a new MP4 video with the original visuals and natural, time-synchronized English dubbed audio—without unnecessary video re-encoding.

Built for the **Idealabs Digital Internship Assignment** following strict clean-code and modular design principles.

---

## Architecture & Processing Flow

The system runs a 6-stage linear pipeline:

```
[1/6] YouTube URL / Local Video
      │
      ▼
   yt-dlp ──────► Downloads video (source.mp4) & extracts 16kHz mono audio (source_audio.wav)
      │
      ▼
[2/6] Faster-Whisper (INT8 CPU) ──► Automatic language detection & timestamped segments (transcript.json)
      │
      ▼
[3/6] Translation Adapter ────────► Contextual, natural English phrasing (translation.json)
      │
      ▼
[4/6] Edge-TTS (Neural Voices) ───► High-fidelity English speech clips (segments/segment_xxxx.mp3)
      │
      ▼
[5/6] Audio Processor & Timing ───► Timeline alignment, overrun tempo fitting & pause preservation (dubbed_audio.wav)
      │
      ▼
[6/6] FFmpeg Stream Muxer ────────► Muxes original video stream + dubbed audio (dubbed_video.mp4)
```

---

## Technology Choices & Rationale

| Component | Technology | Rationale |
| :--- | :--- | :--- |
| **Video Ingestion** | `yt-dlp` | Industry standard for reliable YouTube and web video downloads. Also accepts local MP4/MKV video files. |
| **Speech-to-Text (ASR)** | `faster-whisper` | Powered by CTranslate2. Features **INT8 quantization**, optimized for high CPU efficiency with lower memory footprint than standard PyTorch Whisper models—critical for laptops without a dedicated NVIDIA GPU. |
| **Translation** | `deep-translator` | Produces natural conversational English phrasing rather than crude word-for-word translation, supporting 100+ languages including Indian and European languages. |
| **Speech Synthesis (TTS)** | `edge-tts` | Accesses Microsoft Azure's neural speech synthesis models for free. Delivers remarkably natural, expressive human voices without robotic artifacts or heavy local GPU models. |
| **Audio Processing** | `pydub` + `scipy` | Frame-accurate audio slicing, padding, and multi-track overlay. |
| **Media Muxing** | `FFmpeg` | Stream-copies original video (`-c:v copy`) to avoid visual quality degradation and eliminate long video re-encoding times. |

---

## Hardware & System Requirements

- **Operating System**: Windows 10/11, macOS, or Linux.
- **CPU**: Intel Core i5 / AMD Ryzen 5 or higher (optimized for multi-threaded CPU execution).
- **RAM**: Minimum 8 GB (16 GB recommended).
- **GPU**: No GPU required (runs 100% locally on CPU).
- **Disk Space**: ~2 GB for virtual environment and model cache, plus storage for downloaded videos.
- **Python**: Python 3.12 (Python 3.12.10 recommended; Python 3.13+ removed the standard library `audioop` module required by `pydub`).
- **FFmpeg**: Version 6.0+ installed and available in PATH.

---

## Installation & Setup

### 1. Clone or Open the Repository
```powershell
cd automated-video-dubbing
```

### 2. Verify FFmpeg
Ensure FFmpeg and FFprobe are accessible:
```powershell
ffmpeg -version
ffprobe -version
```
> *If FFmpeg is not installed on Windows, install via WinGet: `winget install Gyan.FFmpeg.Essentials` or download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/).*

### 3. Create Virtual Environment
Using Python 3.12:
```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
```

### 4. Install Dependencies
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## Usage

### Basic Command
Run the dubbing pipeline with a YouTube URL:
```powershell
python main.py "https://www.youtube.com/watch?v=YOUR_VIDEO_ID"
```

Or pass a local video file directly:
```powershell
python main.py "C:\path\to\input_video.mp4"
```

If run without arguments, `main.py` will prompt interactively:
```powershell
python main.py
# Enter YouTube URL or video path: <paste URL here>
```

### Advanced Options & Flags

```
usage: main.py [-h] [--model {tiny,base,small,medium}] [--voice VOICE] [--output-dir OUTPUT_DIR] [--acoustic-translation] [url]

positional arguments:
  url                   YouTube URL or path to a local video file.

options:
  -h, --help            Show this help message and exit.
  --model {tiny,base,small,medium}
                        Whisper model size (default: base).
  --voice VOICE         Edge-TTS neural voice (default: en-US-ChristopherNeural).
  --output-dir OUTPUT_DIR
                        Directory for job outputs (default: outputs).
  --acoustic-translation
                        Enable optional secondary Whisper acoustic translation pass for non-English audio.
```

#### Example with Custom Voice and Model:
```powershell
# Female narrator with base Whisper model
python main.py "https://youtu.be/..." --model base --voice en-US-AriaNeural
```

---

## Terminal Output Example

Following the UI/UX Brief specification, terminal logs are structured, clean, and informative:

```text
==================================================
        Automated Video Dubbing System
    Idealabs Digital Internship Assignment
==================================================

[1/6] Downloading video...
  ✓ Download complete (German Science Primer)

[2/6] Transcribing speech...
  ✓ Transcription complete (Detected: DE (14 segments))

[3/6] Translating to English...
  ✓ Translation complete

[4/6] Generating English speech...
  ✓ Speech generated (Voice: en-US-ChristopherNeural)

[5/6] Building dubbed audio...
  ✓ Audio ready (14 segments placed)

[6/6] Creating final video...
  ✓ Done

--------------------------------------------------
Output:
  C:\...\outputs\job_20260918_213000\dubbed_video.mp4

Detected Language:
  DE

Processing time:
  00:01:18
--------------------------------------------------
```

---

## Output Artifacts & Layout

Every run creates a uniquely stamped job directory under `outputs/job_<timestamp>/`:

```
outputs/job_20260918_213000/
├── source.mp4             # Original downloaded video
├── source_audio.wav       # Extracted 16kHz mono audio
├── transcript.json        # Speech segments with start/end timestamps & source text
├── translation.json       # Segment-aligned natural English translations
├── segments/              # Individual synthesized audio clips
│   ├── segment_0001.mp3
│   ├── segment_0002.mp3
│   └── ...
├── dubbed_audio.wav       # Assembled, time-synchronized master audio track
├── dubbed_video.mp4       # Final dubbed MP4 (original visuals + English audio)
└── job_summary.json       # Execution telemetry, language, and elapsed time
```

---

## Timing Strategy & Audio Synchronization

A major technical challenge in automated dubbing is that English phrasing often requires a different duration than the original language:

1. **Baseline Alignment**: Whisper timestamps (`start`, `end`) serve as the primary timeline anchor.
2. **Natural Pause Preservation**: When the synthesized English speech is shorter than the source segment, the remaining duration is left as natural silence, keeping dialogue cadence aligned with visual cues.
3. **Overrun Handling (Adaptive Tempo Adjustment)**: If the translated English speech is longer than the source segment:
   - If the gap before the next segment allows it, speech naturally finishes.
   - If speech threatens to overlap into the next segment, FFmpeg's `atempo` filter dynamically compresses the segment duration (up to 1.30x speedup) **without pitch shifting**, ensuring crystal-clear, non-overlapping speech.
4. **Collision Prevention**: An active timeline cursor with a 40ms safety buffer guarantees that no two consecutive dialogue clips ever overlap.
5. **Exact Duration Matching**: The final master audio track is padded or bounded to precisely match the source video length.

### Honest Limitations
- **No Lip Sync**: The system replaces the audio track and synchronizes segment start/end timings, but does not modify facial geometry or mouth movements.
- **Ambient Audio Separation**: In the current single-track core implementation, background music/effects present on the original audio track are replaced by the clean English dubbed voice. (Audio stem separation via Demucs is an optional extension).
- **Pacing**: Rapid foreign speech translated into lengthy English idioms may sound briskly paced due to the timing compression.

---

## Running Automated Tests

To execute the unit test suite:

```powershell
.venv\Scripts\python -m pytest tests/ -v
```

Tests cover:
- Data contract validation and JSON serialization (`test_models.py`)
- Timeline overlap prevention and speed-clamping algorithms (`test_timing.py`)
- CLI parameter parsing, options, and URL validation (`test_cli.py`)
- Translation adapter, English pass-through, and locale resolution (`test_translation.py`)

---

## Benchmarks & Verification

The assignment requires testing on approximately 30-minute and 2-hour videos.

### Verified Test Run (Real YouTube Dialogue)
- **URL**: `https://www.youtube.com/watch?v=IoUqOToXe-4`
- **Video Title**: *Short film Spanish A2 | Ep. 2: Challenges for Spanish students*
- **Source Duration**: 108.88 seconds (1m 49s)
- **Detected Language**: Spanish (`ES`, 12 segments)
- **Model**: `base` (INT8 CPU)
- **Processing Time**: 54 seconds
- **Verification**: Output video verified with FFmpeg/FFprobe null decode (0 errors, stream copy intact).

### Benchmark Submission Table
Run the pipeline on your chosen 30-minute and 2-hour videos and record the measured metrics below:

| Metric | 30-Minute Benchmark | 2-Hour Benchmark |
| :--- | :--- | :--- |
| **YouTube URL** | *Pending execution* | *Pending execution* |
| **Source Duration** | *Pending execution* | *Pending execution* |
| **Detected Language** | *Pending execution* | *Pending execution* |
| **Model Size** | `base` | `base` |
| **Elapsed Processing Time** | *Pending execution* | *Pending execution* |
| **Output File Location** | *outputs/job_.../dubbed_video.mp4* | *outputs/job_.../dubbed_video.mp4* |
| **Output File Size** | *Pending execution* | *Pending execution* |
| **Playability Verification** | *Pending execution* | *Pending execution* |

**off campus code: SBY9A3**

```powershell
# Execute 30-minute run:
python main.py "<30_MIN_YOUTUBE_URL>" --model base

# Execute 2-hour run:
python main.py "<2_HOUR_YOUTUBE_URL>" --model base
```

---

## Project Structure

```
automated-video-dubbing/
│
├── main.py                   # CLI entry point, banner, argument handling, UX
├── src/
│   ├── __init__.py           # Package marker
│   ├── models.py             # VideoJob and SpeechSegment dataclasses
│   ├── utils.py              # FFmpeg path resolution & duration inspection
│   ├── downloader.py         # yt-dlp video fetcher & 16kHz audio extractor
│   ├── transcriber.py        # Faster-Whisper ASR & language detector
│   ├── translator.py         # Segment-preserving English translator
│   ├── synthesizer.py        # Edge-TTS neural speech synthesizer
│   ├── audio_processor.py    # Timing fitting, tempo scaling & timeline assembly
│   └── pipeline.py           # End-to-end pipeline coordinator & FFmpeg muxer
│
├── tests/
│   ├── __init__.py
│   ├── test_models.py        # Model serialization tests
│   ├── test_timing.py        # Audio alignment & overlap prevention tests
│   ├── test_cli.py           # CLI argument parsing tests
│   └── test_translation.py   # Translation adapter & locale tests
│
├── samples/                  # Sample test video clips
├── outputs/                  # Generated video and JSON artifacts
├── requirements.txt          # Pinned project dependencies
├── .env.example              # Sample environment configuration
├── .gitignore                # Git exclusions (temp files, videos, venv)
├── LICENSE                   # MIT License
└── README.md                 # Complete documentation
```

---

## License

MIT License. Developed for educational and internship evaluation purposes.
