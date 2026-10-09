"""
Module lồng tiếng AI (Text-to-Speech) và đồng bộ thời lượng âm thanh.
Sử dụng edge-tts tạo giọng đọc tiếng Việt truyền cảm và FFmpeg atempo để nén/giãn tốc độ.
"""

import sys
import os
import re
import time
import asyncio
import math
import subprocess
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any
from config import Config
from core.audio_extractor import find_ffmpeg
from core.process import run_process

# Cấu hình encoding UTF-8 nếu chạy trên Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


class TTSError(Exception):
    """Lỗi xảy ra trong quá trình tạo giọng đọc hoặc đồng bộ thời lượng."""
    pass


def get_audio_duration(
    file_path: Path | str,
    cancel_check: Optional[Callable[[], bool]] = None,
    timing_callback: Optional[Callable[[str, float], None]] = None,
) -> float:
    """
    Đo thời lượng âm thanh bằng PyAV trước, dùng FFmpeg làm fallback.
    """
    file_obj = Path(file_path).resolve()
    if not file_obj.exists():
        raise FileNotFoundError(f"Không tìm thấy file để đo thời lượng: {file_path}")
    if file_obj.stat().st_size == 0:
        return 0.0

    if cancel_check and cancel_check():
        raise InterruptedError("The audio duration probe was cancelled by the user.")

    probe_started = time.perf_counter()
    duration = _get_audio_duration_from_pyav(file_obj)
    if timing_callback:
        timing_callback("PyAV duration probe", time.perf_counter() - probe_started)
    if cancel_check and cancel_check():
        raise InterruptedError("The audio duration probe was cancelled by the user.")
    if duration is not None and math.isfinite(duration) and duration > 0:
        return duration

    ffmpeg_bin = find_ffmpeg()
    cmd = [ffmpeg_bin, "-i", str(file_obj)]

    # FFmpeg in thông tin media ra stderr
    probe_started = time.perf_counter()
    try:
        result = run_process(
            cmd,
            timeout=30.0,
            cancel_check=cancel_check,
            check=False,
            capture_stdout=True,
        )
    finally:
        if timing_callback:
            timing_callback("FFmpeg duration fallback", time.perf_counter() - probe_started)
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", result.stderr)
    if match:
        hours = float(match.group(1))
        minutes = float(match.group(2))
        seconds = float(match.group(3))
        return hours * 3600 + minutes * 60 + seconds

    return 0.0


def _get_audio_duration_from_pyav(file_path: Path) -> Optional[float]:
    """Read audio stream timing without spawning a new FFmpeg process."""
    try:
        import av
    except ImportError:
        return None

    try:
        with av.open(str(file_path)) as container:
            durations = []
            for stream in container.streams.audio:
                if stream.duration is not None and stream.time_base is not None:
                    duration = float(stream.duration * stream.time_base)
                    if math.isfinite(duration) and duration > 0:
                        durations.append(duration)
                elif stream.frames and stream.average_rate:
                    duration = float(stream.frames / stream.average_rate)
                    if math.isfinite(duration) and duration > 0:
                        durations.append(duration)

            if durations:
                return max(durations)
            if container.duration is not None:
                duration = float(container.duration / av.time_base)
                if math.isfinite(duration) and duration > 0:
                    return duration
    except (av.error.FFmpegError, OSError, ValueError, TypeError, ZeroDivisionError):
        # Keep FFmpeg as a compatibility fallback for codecs PyAV cannot inspect.
        return None

    return None


def _detect_audio_content_window(
    file_path: Path,
    *,
    threshold_db: float = -45.0,
    leading_padding: float = 0.02,
    trailing_padding: float = 0.05,
) -> Optional[tuple[float, float]]:
    """Find the voiced window in short TTS clips while preserving small edge padding."""
    try:
        import av
        import numpy as np
    except ImportError:
        return None

    try:
        with av.open(str(file_path)) as container:
            stream = next(iter(container.streams.audio), None)
            if stream is None:
                return None
            sample_rate = int(stream.rate or 0)
            if sample_rate <= 0:
                return None
            frames = list(container.decode(stream))
            arrays = [frame.to_ndarray() for frame in frames if frame.samples]
            if not arrays:
                return None
            samples = np.concatenate(arrays, axis=-1).astype(np.float32, copy=False)
            if np.issubdtype(arrays[0].dtype, np.integer):
                sample_info = np.iinfo(arrays[0].dtype)
                scale = float(max(abs(sample_info.min), sample_info.max))
                samples = samples / scale
            mono_rms = (
                np.sqrt(np.mean(samples * samples, axis=0))
                if samples.ndim > 1
                else np.abs(samples)
            )
            total_duration = len(mono_rms) / sample_rate
            window_samples = max(1, int(sample_rate * 0.02))
            energies = np.asarray([
                np.sqrt(np.mean(mono_rms[offset:offset + window_samples] ** 2))
                for offset in range(0, len(mono_rms), window_samples)
            ])
            if not len(energies) or float(energies.max()) <= 0:
                return None

            absolute_threshold = 10 ** (threshold_db / 20.0)
            threshold = max(absolute_threshold, float(energies.max()) * 0.02)
            active = np.flatnonzero(energies >= threshold)
            if not len(active):
                return None

            active_start = float(active[0] * window_samples / sample_rate)
            active_end = float(min(len(mono_rms), (active[-1] + 1) * window_samples) / sample_rate)
            start = max(0.0, active_start - leading_padding)
            end = min(total_duration, active_end + trailing_padding)
            if end <= start:
                return None
            return start, end
    except (av.error.FFmpegError, OSError, ValueError, TypeError, ZeroDivisionError):
        return None


def generate_silence_audio(
    output_file: Path,
    duration: float,
    cancel_check: Optional[Callable[[], bool]] = None
) -> Path:
    """
    Tạo tệp âm thanh im lặng (silent audio) bằng FFmpeg khi TTS gặp sự cố hoặc câu không có lời.
    """
    output_file = Path(output_file).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = find_ffmpeg()
    cmd = [
        ffmpeg_bin, "-y",
        "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
        "-t", f"{max(0.2, duration):.2f}",
        "-c:a", "libmp3lame", "-b:a", "48k",
        str(output_file)
    ]
    run_process(
        cmd,
        timeout=30.0,
        cancel_check=cancel_check,
        check=True,
    )
    return output_file


def sanitize_tts_text(text: str) -> str:
    """
    Chuẩn hóa câu văn để tránh các cụm từ gây lỗi NoAudioReceived trên dịch vụ Edge TTS tiếng Việt.
    """
    if not text:
        return ""
    cleaned = text.strip().strip('"').strip("'")
    replacements = {
        "soi tuổi": "đoán tuổi",
        "tuổi tác của tôi": "tuổi của tôi",
        "tuổi tác tôi": "tuổi của tôi",
        "tuổi tác": "tuổi",
    }
    for old, new in replacements.items():
        cleaned = re.sub(re.escape(old), new, cleaned, flags=re.IGNORECASE)
    return cleaned


async def synthesize_speech_async(
    text: str,
    output_file: Path,
    voice: str,
    max_retries: int = 3,
    request_timeout: float = 20.0,
    total_timeout: float = 60.0,
    cancel_check: Optional[Callable[[], bool]] = None
) -> bool:
    """
    Hàm bất đồng bộ gọi Microsoft Edge TTS tạo giọng đọc tiếng Việt.
    Có cơ chế tự sửa từ ngữ nhạy cảm, đa dạng hóa biến thể dấu câu,
    luân chuyển giọng đọc Nam/Nữ và exponential backoff khi gặp NoAudioReceived/RateLimit.
    Trả về True nếu thành công, False nếu thất bại.
    """
    try:
        import edge_tts
    except ImportError:
        raise TTSError("Thư viện edge-tts chưa được cài đặt. Vui lòng chạy: pip install edge-tts")

    out_path = Path(output_file).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    clean_text = sanitize_tts_text(text)
    if not clean_text:
        return False

    voices_to_try = [voice]
    alt_voice = "vi-VN-HoaiMyNeural" if "NamMinh" in voice else "vi-VN-NamMinhNeural"
    if alt_voice not in voices_to_try:
        voices_to_try.append(alt_voice)

    # Tập các biến thể văn bản giúp vượt qua lỗi NoAudioReceived trên dịch vụ Edge-TTS tiếng Việt
    candidate_texts = [clean_text]
    if not clean_text.endswith((".", "!", "?")):
        candidate_texts.append(f"{clean_text}.")
    else:
        candidate_texts.append(clean_text.rstrip(".!?"))
    candidate_texts.append(f'"{clean_text}"')

    loop = asyncio.get_running_loop()
    deadline = loop.time() + total_timeout

    async def save_with_controls(communicate, remaining: float):
        task = asyncio.create_task(communicate.save(str(out_path)))
        request_deadline = loop.time() + min(request_timeout, remaining)
        while not task.done():
            if cancel_check and cancel_check():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                raise InterruptedError("The TTS request was cancelled by the user.")
            wait_for = min(0.2, request_deadline - loop.time())
            if wait_for <= 0:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                raise asyncio.TimeoutError("TTS request timed out.")
            await asyncio.wait({task}, timeout=wait_for)
        return await task

    for attempt in range(max_retries):
        for v in voices_to_try:
            for cand in candidate_texts:
                if cancel_check and cancel_check():
                    raise InterruptedError("The TTS request was cancelled by the user.")
                remaining = deadline - loop.time()
                if remaining <= 0:
                    return False
                try:
                    out_path.unlink(missing_ok=True)
                    communicate = edge_tts.Communicate(cand, v)
                    await save_with_controls(communicate, remaining)
                    if out_path.exists() and out_path.stat().st_size > 0:
                        return True
                except InterruptedError:
                    raise
                except Exception:
                    out_path.unlink(missing_ok=True)
                    # Chờ ngắn trước khi thử biến thể tiếp theo
                    await asyncio.sleep(0.2)
                    continue

        # Nếu thất bại toàn bộ biến thể trong lượt thử này, backoff trước khi sang lượt kế tiếp
        if attempt < max_retries - 1:
            await asyncio.sleep(0.6 * (attempt + 1))

    return False


def adjust_audio_speed(
    input_audio: Path,
    output_audio: Path,
    target_duration: float,
    min_speed: float = 0.85,
    max_speed: float = 1.30,
    cancel_check: Optional[Callable[[], bool]] = None,
    timing_callback: Optional[Callable[[str, float], None]] = None,
) -> Path:
    """
    Căn chỉnh tốc độ của tệp âm thanh bằng filter atempo của FFmpeg để khớp target_duration.

    Args:
        input_audio: Đường dẫn file âm thanh gốc.
        output_audio: Đường dẫn file âm thanh sau khi chỉnh tốc độ.
        target_duration: Thời lượng mong muốn (giây).
        min_speed: Giới hạn làm chậm tối đa (tránh giọng bị rề rà).
        max_speed: Giới hạn tăng tốc tối đa (tránh giọng bị như chipmunk).

    Returns:
        Path: Đường dẫn file audio đã qua căn chỉnh tốc độ.
    """
    input_file = Path(input_audio).resolve()
    output_file = Path(output_audio).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    current_duration = get_audio_duration(
        input_file,
        cancel_check=cancel_check,
        timing_callback=timing_callback,
    )
    if cancel_check and cancel_check():
        raise InterruptedError("The audio synchronization was cancelled by the user.")
    if current_duration <= 0 or target_duration <= 0:
        # Nếu thời lượng quá ngắn hoặc lỗi, copy nguyên file
        import shutil
        shutil.copy2(input_file, output_file)
        return output_file

    # Edge TTS MP3s may contain long silent tails. Fit the voiced window, not container padding.
    scan_started = time.perf_counter()
    content_window = _detect_audio_content_window(input_file)
    if timing_callback:
        timing_callback("PyAV active-audio scan", time.perf_counter() - scan_started)
    trim_start, trim_end = content_window or (0.0, current_duration)
    content_duration = max(0.0, trim_end - trim_start)
    has_trim = trim_start > 0.01 or trim_end < current_duration - 0.03
    if content_duration <= 0:
        content_duration = current_duration
        trim_start, trim_end = 0.0, current_duration
        has_trim = False

    # Calculate tempo using audible content after trimming edge silence.
    raw_factor = content_duration / target_duration
    # Kẹp giá trị trong dải an toàn để giữ nguyên độ tự nhiên của giọng đọc
    speed_factor = max(min_speed, min(max_speed, raw_factor))

    # Nếu tốc độ chênh lệch rất nhỏ (dưới 3%), giữ nguyên file không cần re-encode
    if abs(speed_factor - 1.0) < 0.03 and not has_trim:
        import shutil
        shutil.copy2(input_file, output_file)
        return output_file

    ffmpeg_bin = find_ffmpeg()
    # atempo chỉ thay đổi tốc độ (tempo), giữ nguyên cao độ (pitch) của giọng người
    filters = []
    if has_trim:
        filters.extend([
            f"atrim=start={trim_start:.4f}:end={trim_end:.4f}",
            "asetpts=PTS-STARTPTS",
        ])
    if abs(speed_factor - 1.0) >= 0.03:
        filters.append(f"atempo={speed_factor:.3f}")

    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", str(input_file),
        "-filter:a", ",".join(filters),
        "-vn",
        str(output_file)
    ]

    try:
        encode_started = time.perf_counter()
        run_process(
            cmd,
            timeout=Config.FFMPEG_TIMEOUT,
            cancel_check=cancel_check,
            check=True,
        )
        return output_file
    except InterruptedError:
        raise
    except TimeoutError as e:
        raise TTSError(str(e)) from e
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr[-300:] if e.stderr else str(e)
        raise TTSError(f"Lỗi khi căn chỉnh tốc độ âm thanh với atempo: {error_msg}") from e
    finally:
        if timing_callback and "encode_started" in locals():
            timing_callback("FFmpeg atempo encoding", time.perf_counter() - encode_started)


def process_dubbing_segments(
    segments: List[Dict[str, Any]],
    voice: Optional[str] = None,
    output_dir: Optional[Path] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None
) -> List[Dict[str, Any]]:
    """Run a synchronous TTS batch while reusing one event loop for all cues."""
    if not segments:
        return []

    tts_loop = asyncio.new_event_loop()
    try:
        return _process_dubbing_segments(
            segments,
            voice=voice,
            output_dir=output_dir,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
            tts_loop=tts_loop,
        )
    finally:
        try:
            tts_loop.run_until_complete(tts_loop.shutdown_asyncgens())
        finally:
            tts_loop.close()


def _process_dubbing_segments(
    segments: List[Dict[str, Any]],
    voice: Optional[str],
    output_dir: Optional[Path],
    progress_callback: Optional[Callable[[str, float], None]],
    cancel_check: Optional[Callable[[], bool]],
    tts_loop: asyncio.AbstractEventLoop,
) -> List[Dict[str, Any]]:
    """
    Generate TTS audio with bounded concurrency, then sync and validate in source order.

    Args:
        segments: Danh sách phân đoạn đã có translated_text.
        voice: Giọng đọc (mặc định lấy từ Config.DEFAULT_VOICE).
        output_dir: Thư mục lưu các file audio thành phẩm.
        progress_callback: Hàm nhận (thông điệp, phần trăm tiến độ).
        cancel_check: Hàm kiểm tra xem người dùng có yêu cầu dừng tiến trình hay không.

    Returns:
        List[Dict[str, Any]]: Danh sách phân đoạn được bổ sung "dubbed_audio_path" và "dubbed_duration".
    """
    if not segments:
        return []

    target_voice = voice or Config.DEFAULT_VOICE
    target_dir = output_dir or (Config.TEMP_DIR / "dubbing_segments")
    target_dir.mkdir(parents=True, exist_ok=True)

    total_segments = len(segments)
    concurrency = getattr(Config, "TTS_MAX_CONCURRENCY", 1)
    if not isinstance(concurrency, int) or isinstance(concurrency, bool) or not 1 <= concurrency <= 4:
        raise TTSError("TTS_MAX_CONCURRENCY must be an integer between 1 and 4.")

    request_pacing = getattr(Config, "TTS_REQUEST_PACING_SECONDS", 0.2)
    if not isinstance(request_pacing, (int, float)) or isinstance(request_pacing, bool):
        raise TTSError("TTS_REQUEST_PACING_SECONDS must be a number between 0 and 2.")
    if not math.isfinite(request_pacing) or not 0 <= request_pacing <= 2:
        raise TTSError("TTS_REQUEST_PACING_SECONDS must be a number between 0 and 2.")

    stage_timings = {}
    stage_counts = {}

    def record_timing(stage: str, elapsed: float):
        stage_timings[stage] = stage_timings.get(stage, 0.0) + elapsed
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

    plans = []
    for idx, seg in enumerate(segments):
        text = seg.get("translated_text", "").strip() or seg.get("text", "").strip()
        start = seg.get("start", 0.0)
        end = seg.get("end", 0.0)
        target_duration = max(0.25, end - start)
        next_start = segments[idx + 1].get("start") if idx + 1 < total_segments else None
        if next_start is not None and float(next_start) > float(start):
            target_duration = max(0.25, min(target_duration, float(next_start) - float(start)))
        seg_index = seg.get("index", idx)
        plans.append({
            "ordinal": idx,
            "segment": seg,
            "text": text,
            "start": start,
            "next_start": next_start,
            "target_duration": target_duration,
            "raw_mp3": target_dir / f"raw_seg_{seg_index}.mp3",
            "synced_mp3": target_dir / f"synced_seg_{seg_index}.mp3",
            "source_fallback": seg.get("translation_status") == "source_fallback",
        })

    tts_results = [None] * total_segments
    completed_requests = 0

    async def synthesize_batch():
        nonlocal completed_requests
        semaphore = asyncio.Semaphore(concurrency)
        request_start_lock = asyncio.Lock()
        last_request_started = [None]
        loop = asyncio.get_running_loop()

        async def synthesize_one(plan):
            nonlocal completed_requests
            idx = plan["ordinal"]
            if plan["source_fallback"] or not plan["text"]:
                completed_requests += 1
                if progress_callback:
                    progress_callback(
                        f"TTS audio ready for {completed_requests}/{total_segments} segments.",
                        (completed_requests / total_segments) * 65.0,
                    )
                return None

            async with semaphore:
                if cancel_check and cancel_check():
                    raise InterruptedError("The TTS request was cancelled by the user.")

                async with request_start_lock:
                    if last_request_started[0] is not None and request_pacing:
                        wait_seconds = request_pacing - (loop.time() - last_request_started[0])
                        if wait_seconds > 0:
                            await asyncio.sleep(wait_seconds)
                    if cancel_check and cancel_check():
                        raise InterruptedError("The TTS request was cancelled by the user.")
                    last_request_started[0] = loop.time()

                if progress_callback:
                    progress_callback(
                        f"Đang sinh giọng đọc câu {idx + 1}/{total_segments}: {plan['text'][:30]}...",
                        (completed_requests / total_segments) * 65.0,
                    )

                tts_started = time.perf_counter()
                try:
                    success = await synthesize_speech_async(
                        plan["text"],
                        plan["raw_mp3"],
                        target_voice,
                        request_timeout=Config.TTS_REQUEST_TIMEOUT,
                        total_timeout=Config.TTS_SEGMENT_TIMEOUT,
                        cancel_check=cancel_check,
                    )
                    completed_requests += 1
                    if progress_callback:
                        progress_callback(
                            f"TTS audio ready for {completed_requests}/{total_segments} segments.",
                            (completed_requests / total_segments) * 65.0,
                        )
                    return bool(success)
                finally:
                    record_timing("TTS requests incl. retries", time.perf_counter() - tts_started)

        tasks = [asyncio.create_task(synthesize_one(plan)) for plan in plans]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        for plan, outcome in zip(plans, outcomes):
            if isinstance(outcome, InterruptedError):
                raise outcome
            if isinstance(outcome, BaseException):
                raise outcome
            tts_results[plan["ordinal"]] = outcome

    request_wall_started = time.perf_counter()
    try:
        tts_loop.run_until_complete(synthesize_batch())
    finally:
        record_timing("TTS request wall time", time.perf_counter() - request_wall_started)

    enriched_segments = []
    for plan in plans:
        if cancel_check and cancel_check():
            raise InterruptedError("Tiến trình lồng tiếng đã bị dừng bởi người dùng.")

        idx = plan["ordinal"]
        seg = plan["segment"]
        text = plan["text"]
        start = plan["start"]
        next_start = plan["next_start"]
        target_duration = plan["target_duration"]
        raw_mp3 = plan["raw_mp3"]
        synced_mp3 = plan["synced_mp3"]
        percent = 65.0 + ((idx + 1) / total_segments) * 35.0

        # Preserve the existing source/silence fallback policy for skipped or failed requests.
        tts_status = "success"
        sync_status = "success"
        if plan["source_fallback"]:
            generate_silence_audio(raw_mp3, target_duration, cancel_check=cancel_check)
            tts_status = "translation_fallback_source_audio"
        elif not text:
            generate_silence_audio(raw_mp3, target_duration, cancel_check=cancel_check)
            tts_status = "empty_text"
        elif not tts_results[idx]:
            generate_silence_audio(raw_mp3, target_duration, cancel_check=cancel_check)
            if progress_callback:
                progress_callback(
                    f"⚠️ [CẢNH BÁO] Không lấy được audio TTS cho câu {idx + 1}/{total_segments} (lỗi mạng/Edge-TTS timeout): '{text[:30]}...'. Sẽ khôi phục audio gốc nếu có, nếu không sẽ dùng đoạn im lặng.",
                    percent
                )
            tts_status = "failed_silence_fallback"

        # 2. Căn chỉnh tốc độ khớp thời lượng mục tiêu
        try:
            adjust_audio_speed(
                raw_mp3,
                synced_mp3,
                target_duration,
                cancel_check=cancel_check,
                timing_callback=record_timing,
            )
        except InterruptedError:
            raise
        except (TTSError, OSError, subprocess.SubprocessError, TimeoutError) as exc:
            generate_silence_audio(synced_mp3, target_duration, cancel_check=cancel_check)
            sync_status = "failed_silence_fallback"
            if progress_callback:
                progress_callback(
                    f"⚠️ Audio synchronization failed for segment {idx + 1}/{total_segments}: {str(exc)[:120]}. Original audio will be restored when available; otherwise silence is used.",
                    percent
                )

        # 3. Đo lại thời lượng thực tế của file âm thanh sau khi đồng bộ
        actual_duration = get_audio_duration(
            synced_mp3,
            cancel_check=cancel_check,
            timing_callback=record_timing,
        )
        if actual_duration <= 0:
            raise TTSError(f"Generated audio for segment {idx + 1} is empty or unreadable.")

        seg_copy = dict(seg)
        seg_copy["dubbed_audio_path"] = str(synced_mp3)
        seg_copy["dubbed_duration"] = actual_duration
        seg_copy["tts_status"] = tts_status
        seg_copy["sync_status"] = sync_status
        if actual_duration > target_duration + 0.10 and progress_callback:
            progress_callback(
                f"⚠️ Dubbed segment {idx + 1}/{total_segments} exceeds its subtitle interval by "
                f"{actual_duration - target_duration:.2f}s; the full generated speech is preserved.",
                percent
            )
        if (
            next_start is not None
            and start + actual_duration > float(next_start) + 0.10
            and progress_callback
        ):
            overlap_seconds = start + actual_duration - float(next_start)
            progress_callback(
                f"⚠️ Dubbed segment {idx + 1}/{total_segments} overlaps the next line by "
                f"{overlap_seconds:.2f}s; the full generated speech is preserved.",
                percent,
            )
        if progress_callback:
            progress_callback(
                f"Synchronized audio for {idx + 1}/{total_segments} segments.",
                percent,
            )
        enriched_segments.append(seg_copy)

    if progress_callback:
        if stage_timings:
            timing_summary = ", ".join(
                f"{stage}={elapsed:.2f}s/{stage_counts[stage]} probe(s)"
                if "probe" in stage.lower()
                else f"{stage}={elapsed:.2f}s"
                for stage, elapsed in stage_timings.items()
            )
            progress_callback(f"TTS performance timings: {timing_summary}", 100.0)
        progress_callback(f"Lồng tiếng hoàn tất toàn bộ {total_segments} câu thoại.", 100.0)

    return enriched_segments
