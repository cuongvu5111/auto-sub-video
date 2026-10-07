# 🎬 AutoDub Studio v1.0.1 — Windows Release

**AutoDub Studio** is an all-in-one desktop application for automated short video downloading, high-accuracy Speech-to-Text, contextual LLM dialogue translation, natural Vietnamese AI voice dubbing, smart audio ducking, and animated subtitle burning — all running locally on your Windows PC.

This release is a **fully portable standalone Windows executable** bundled with **FFmpeg v7.1**, **CTranslate2**, and **PySide6**. **No Python or additional software installation required.**

---

## 🚀 Key Features

- 📥 **Watermark-Free Downloader** — High-speed video fetching from TikTok, Douyin, and other major platforms via `yt-dlp`.
- 🎙️ **High-Accuracy Speech-to-Text** — Powered by `faster-whisper` (CTranslate2) with INT8 CPU quantization and automatic NVIDIA CUDA acceleration detection.
- 🧠 **Contextual LLM Translation** — Supports any OpenAI-compatible endpoint: VNPT LLM Gateway, Ollama (local), Groq, or official OpenAI.
- 🗣️ **Natural AI Voice Dubbing** — Free, unlimited Microsoft Edge Neural TTS with expressive Vietnamese voices (`vi-VN-NamMinhNeural` / `vi-VN-HoaiMyNeural`).
- ⏱️ **Audio Speed Synchronization** — Dynamic tempo adjustment (`0.85x` – `1.30x`) via FFmpeg `atempo` filter without any pitch distortion.
- 🎧 **Intelligent Audio Ducking** — Preserves original background music and ambient audio at 10% while elevating the dubbed speech track to 100%.
- ✨ **TikTok-Style Animated Subtitles** — Fully customizable `.ass` subtitle rendering with adjustable font, outline, shadow, box padding, and screen position.
- 🖥️ **Native Desktop Studio** — Sleek `PySide6` GUI with a multi-video batch queue, two-column settings panel, real-time terminal logs, and a smooth progress bar.

---

## 🔧 What's Changed in v1.0.1

### Bug Fixes

- **PyAV Compatibility** — Fixed `TypeError: open() got an unexpected keyword argument 'metadata_errors'` that caused Speech-to-Text to fail completely. Root cause: PyAV `19.x` removed the `metadata_errors` argument. Pinned `av<19` (`18.1.0`) in `requirements.txt` to prevent this breaking change from affecting fresh installs.

- **UI Button State Recovery** — Fixed a bug where the **▶ Start** and **■ Stop** buttons would remain permanently disabled after any video processing error. The `DubbingWorker.run()` thread is now wrapped in a `try...finally` block that guarantees `sig_finished` is always emitted — regardless of whether processing succeeded, failed, or was cancelled.

### Improvements

- **Smart Queue Resumption** — The **▶ Start** button now automatically re-enables whenever new videos are added to the queue. On re-run, the application intelligently skips already completed (`✓ Done`) items and only re-processes videos that are pending or previously failed.

- **Portable Build Reliability** — Updated `config.py` to correctly resolve the application root directory when running as a PyInstaller frozen executable. The `.env` config file, `bin/ffmpeg.exe`, `output/`, and `temp/` directories are now always located next to `AutoDubStudio.exe`, exactly where the user expects them.

- **Dual-Layer Worker Safety** — Added a secondary safety net via `QThread.finished` signal connection. Regardless of why the worker thread ends (cancellation, crash, or unhandled exception), the UI will always restore button states correctly.

---

## 📦 Download & Quick Start

1. Download **`AutoDubStudio-v1.0.1-windows-x64.zip`** from the assets below.
2. Extract the `.zip` to any folder on your computer.
3. Double-click **`AutoDubStudio.exe`** to launch.
4. *(Optional)* Configure your LLM API in the **Settings** tab, or copy `.env.example` → `.env` and fill in your credentials.

> **No installation required.** Everything is bundled. Extract and run.

---

## 📋 Release Assets

| Asset | OS | Architecture | Type |
| :--- | :--- | :--- | :--- |
| `AutoDubStudio-v1.0.1-windows-x64.zip` | Windows 10 / 11 | x86_64 (64-bit) | Portable ZIP |

---

*Built with ❤️ for content creators and video editors.*
