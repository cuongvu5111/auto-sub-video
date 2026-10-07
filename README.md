# AutoDub Studio — AI Video Dubbing & Subtitles

> **v1.0.1** · Windows 10 / 11 (64-bit) · No GPU required · 100% Free & Open Source

An all-in-one automated desktop suite for downloading short videos from TikTok, Douyin, and other platforms — performing precise Speech-to-Text, contextual LLM dialogue translation, natural AI voice dubbing, audio tempo synchronization, smart background ducking, and video rendering with animated TikTok-style subtitles.

---

## ✨ Key Features

* 📥 **Watermark-Free Video Downloads** — High-resolution extraction from TikTok and Douyin powered by `yt-dlp`.
* 🎙️ **High-Accuracy Speech-to-Text** — Powered by `faster-whisper` (CTranslate2) with INT8 quantization, CPU-optimized with automatic NVIDIA CUDA detection.
* 🧠 **Smart LLM Translation** — Contextual dialogue translation using any OpenAI-compatible endpoint (Ollama, Groq, VNPT LLM Gateway, OpenAI).
* 🗣️ **Natural AI Voice Dubbing** — Free, unlimited Microsoft Edge Neural TTS (`vi-VN-NamMinhNeural` / `vi-VN-HoaiMyNeural`).
* ⏱️ **Audio Speed Synchronization** — Dynamic tempo adjustment (`0.85x` – `1.30x`) via FFmpeg `atempo` without pitch distortion.
* 🎧 **Intelligent Audio Ducking** — Preserves background music and ambient audio at 10% while elevating the dubbed voice track to 100%.
* ✨ **TikTok-Style Animated Subtitles** — Fully customizable `.ass` subtitle rendering with font, outline, shadow, padding, and position controls.
* 🖥️ **Native Desktop Studio** — Built with `PySide6` featuring a batch processing queue, two-column settings grid, real-time console log, and smooth progress bar.

---

## 🛠️ System Requirements

| Requirement | Minimum |
| :--- | :--- |
| **OS** | Windows 10 / Windows 11 (64-bit) |
| **Python** | 3.10 or higher |
| **FFmpeg** | Pre-bundled in `bin/ffmpeg.exe` — no separate install needed |
| **GPU** | Optional — NVIDIA CUDA auto-detected for faster transcription |

---

## 🚀 Installation & Quick Start

### Option A — Standalone Executable (No Python required)

Download the latest release from [**GitHub Releases**](../../releases) and extract:
```text
AutoDubStudio-v1.0.1-windows-x64.zip
```
Double-click **`AutoDubStudio.exe`** to launch. Everything is bundled.

---

### Option B — Run from Source

**1. Clone the repository**
```bash
git clone https://github.com/your-username/auto-sub-video.git
cd auto-sub-video
```

**2. Create a virtual environment and install dependencies**
```bash
py -3.10 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

> ⚠️ `requirements.txt` pins `av<19` to maintain compatibility with `faster-whisper`. Do not upgrade `av` to `19.x` or above.

**3. Configure your environment**
```bash
copy .env.example .env
```
Edit `.env` with your LLM provider details:
```env
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=gemma3:4b
LLM_API_KEY=your_api_key_here
```

**4. Launch the application**

```bash
# Option A: 1-Click Windows Launcher
run_gui.bat

# Option B: Python GUI directly
python gui.py

# Option C: Command Line Interface
python pipeline.py --source "https://www.tiktok.com/@user/video/..." --voice "vi-VN-NamMinhNeural"
```

---

## 📦 Build Standalone Executable

Package the entire application into a portable Windows `.exe` (bundled with FFmpeg):
```bash
python build_exe.py
```
Output:
```text
dist/AutoDubStudio/AutoDubStudio.exe         ← Run directly
dist/AutoDubStudio-v1.0.1-windows-x64.zip   ← Upload to GitHub Releases
```

---

## 🧪 Test Suite

Run the full automated test suite (Phases 2 through 7):
```bash
python tests/run_all_tests.py
```
Expected result: **6/6 tests passing**.

---

## 📂 Architecture & Documentation

| Document | Description |
| :--- | :--- |
| [`PROJECT.md`](PROJECT.md) | Full technical specs, tech stack, and conventions |
| [`AGENTS.md`](AGENTS.md) | AI coding agent development guidelines |
| [`docs/RELEASE_NOTES_v1.0.1.md`](docs/RELEASE_NOTES_v1.0.1.md) | Changelog and release details for v1.0.1 |
| [`docs/implementation_plan.md`](docs/implementation_plan.md) | 8-Phase implementation roadmap and checklist |

---

## 📄 License

This project is open-source and free to use. Built with 100% free and open-source components.
