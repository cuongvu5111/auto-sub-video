# PROJECT CONTEXT: AutoSub Dubbing Studio

## 1. Project Overview
An end-to-end automated desktop tool designed to download short videos from TikTok, Douyin, and other social platforms (especially Chinese content), extract speech, transcribe audio, translate contextual dialogues using LLMs, generate natural AI dubbing voices (via Edge Neural TTS), synchronize timeline speed, perform smart audio ducking, and render finalized videos with TikTok-style animated subtitles.

Core Principle: **Cost-effective (100% Free & Open-Source), lightweight, and optimized to run smoothly on standard Windows PCs (CPU-friendly, no discrete GPU required).**

---

## 2. Tech Stack & Infrastructure

* **Programming Language**: Python 3.10+
* **Video Downloader**: `yt-dlp` (supports watermark-free downloads from TikTok/Douyin)
* **Speech-to-Text (STT)**: `faster-whisper` (utilizing `base` or `small` models, optimized for CPU execution with INT8 quantization: `compute_type="int8"`)
* **Large Language Model (LLM)**:
  * **Endpoint**: OpenAI-compatible standard (configured via `LLM_BASE_URL`, supports local Ollama `http://localhost:11434/v1`, Groq, or custom gateways).
  * **Model**: Open instruction-tuned models (e.g., `gemma3:4b`, `gemma-4-26B-A4B-it`, `gpt-4o-mini`).
  * **Objective**: Context-aware natural translation, syllable-count constraint matching video pacing, and structured JSON output.
* **Text-to-Speech (TTS)**: `edge-tts` (Microsoft Edge Neural Voice service - free, unlimited)
  * Male Voice: `vi-VN-NamMinhNeural` (expressive, deep)
  * Female Voice: `vi-VN-HoaiMyNeural` (gentle, clear)
* **Audio & Video Processing**: `FFmpeg` (integrated portable binary v7.1 in `bin/ffmpeg.exe` + `pydub`)
  * `atempo` filter: Dynamically stretches/compresses voice tempo (0.85x - 1.30x) without altering pitch to match original video timing.
  * `amix` & `volume` filter: Smart Audio Ducking (drops original audio volume to 10% for ambient/music preservation, overlays 100% dubbing audio).
* **User Interface**: `PySide6` (Native Windows Desktop Studio matching the AutoDub Studio design) with CLI fallback.

---

## 3. Project Directory Structure

```
auto-sub-video/
├── .env.example              # Sample environment variables (LLM_BASE_URL, LLM_MODEL, etc.)
├── requirements.txt          # Python dependencies
├── config.py                 # Centralized configuration management
├── bin/
│   └── ffmpeg.exe            # Pre-bundled portable FFmpeg binary (v7.1)
├── core/
│   ├── __init__.py
│   ├── downloader.py         # Watermark-free video downloader (yt-dlp)
│   ├── audio_extractor.py    # 16kHz mono WAV audio extractor (FFmpeg)
│   ├── transcriber.py        # Speech-to-Text with word timestamps (faster-whisper)
│   ├── translator.py         # LLM translation with strict JSON format
│   ├── tts_engine.py         # AI voice synthesis and atempo speed sync (edge-tts)
│   └── audio_mixer.py        # Audio ducking and video packaging (FFmpeg)
├── pipeline.py               # End-to-end processing pipeline orchestrator & CLI
├── gui.py                    # PySide6 Native Desktop Studio application
├── run_gui.bat               # 1-Click Windows launcher script
├── build_exe.py              # PyInstaller executable builder script (.exe)
├── docs/
│   └── implementation_plan.md# Multi-phase roadmap and checklists
└── tests/                    # Comprehensive unit and integration test suite
```

---

## 4. Development Conventions

1. **Global Readiness**: All user-facing documentation, UI labels, button tooltips, and status messages must be in English.
2. **Exception Handling**: Catch specific exceptions (`DownloadError`, `TranscriptionError`, `TranslationError`, `TTSError`, `AudioMixerError`) rather than generic `Exception`.
3. **Temporary Files**: All intermediate audio/video artifacts must reside in `temp/` and be cleaned up appropriately.
4. **Intermediate Data Schema**: Timeline data exchanged between modules must adhere to standard schemas:
   ```json
   [
     {
       "index": 0,
       "start": 0.0,
       "end": 2.15,
       "text": "Original dialogue",
       "translated_text": "Translated concise sentence",
       "dubbed_audio_path": "temp/synced_seg_0.mp3",
       "dubbed_duration": 2.12
     }
   ]
   ```
5. **Windows Compatibility**: File paths must use `pathlib.Path` or normalized forward slashes for reliable Windows cross-version support.
