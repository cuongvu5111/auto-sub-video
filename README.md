# AutoSub Dubbing Studio - AI Video Dubbing & Subtitles

An all-in-one automated desktop suite for downloading short videos from TikTok, Douyin, and other platforms, performing precise Speech-to-Text, contextual LLM translation, natural AI voice dubbing (via Microsoft Edge Neural TTS), audio tempo synchronization, smart background ducking, and video rendering with animated subtitles.

---

## ✨ Key Features

* 🚀 **Watermark-Free Video Downloads**: High-resolution video extraction from TikTok and Douyin powered by `yt-dlp`.
* 🎙️ **High-Accuracy Speech-to-Text**: Powered by `faster-whisper` (CTranslate2) with INT8 quantization, optimized for fast CPU processing without a dedicated GPU.
* 🧠 **Smart LLM Translation**: Leverages instruction-tuned models (Gemma, GPT-4o-mini, Ollama) with syllable-count constraints tailored for fast-paced video dubbing.
* 🗣️ **Natural AI Voice Dubbing**: Free, unlimited neural voice synthesis via `edge-tts` with expressive Vietnamese and multi-language voices.
* ⏱️ **Audio Speed Synchronization**: Dynamic tempo adjustments (`0.85x` - `1.30x`) using FFmpeg's `atempo` filter to match original video lip movements without pitch distortion.
* 🎧 **Intelligent Audio Ducking**: Drops original background audio volume to 10% to preserve laughter, music, and ambient noise while elevating the dubbed voice track.
* 🖥️ **Native Desktop Studio**: Built with `PySide6` (Qt), featuring a batch processing queue, two-column settings grid, progress tracking, and a real-time console log viewer.

---

## 🛠️ System Requirements

* **Operating System**: Windows 10 or Windows 11 (64-bit)
* **Python**: Version 3.10 or higher
* **FFmpeg**: Pre-bundled portable binary included in `bin/ffmpeg.exe` (no separate system installation required).

---

## 🚀 Installation & Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Create your `.env` configuration file from the template:
```bash
cp .env.example .env
```
Edit `.env` to configure your preferred LLM provider (Ollama local, OpenAI, Groq, or custom proxy):
```env
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=gemma3:4b
LLM_API_KEY=your_api_key_here
```

### 3. Launch Application

**Option A: 1-Click Windows Launcher (Recommended)**
Double-click the launcher script:
```text
run_gui.bat
```

**Option B: Python Desktop GUI**
```bash
python gui.py
```

**Option C: Command Line Interface (CLI)**
```bash
python pipeline.py --source "https://www.tiktok.com/@user/video/..." --voice "vi-VN-NamMinhNeural"
```

---

## 📦 Standalone Executable Packaging (.exe)

Package the entire application into a standalone Windows executable (bundled with portable FFmpeg):
```bash
python build_exe.py
```
The compiled distribution will be created at:
`dist/AutoDubStudio/AutoDubStudio.exe` (runs on any Windows PC without Python installed).

---

## 🧪 Comprehensive Test Suite

Run the full end-to-end automated test suite (Phases 2 through 7):
```bash
python tests/run_all_tests.py
```

---

## 📂 Architecture & Documentation

For in-depth architecture details and implementation roadmaps, consult:
* [`PROJECT.md`](file:///d:/www/auto-sub-video/PROJECT.md): Full technical specifications, tech stack, and conventions.
* [`AGENTS.md`](file:///d:/www/auto-sub-video/AGENTS.md): Development principles and coding agent guidelines.
* [`docs/implementation_plan.md`](file:///d:/www/auto-sub-video/docs/implementation_plan.md): 8-Phase implementation roadmap and checklist.
