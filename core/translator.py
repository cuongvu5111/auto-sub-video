"""
Module dịch thuật phụ đề và tối ưu câu thoại lồng tiếng bằng LLM (OpenAI-compatible).
Dịch từ tiếng Trung (hoặc ngôn ngữ gốc) sang tiếng Việt với văn phong tự nhiên, súc tích cho TikTok.
"""

import sys
import json
import re
import time
from typing import Optional, Callable, List, Dict, Any
from config import Config

# Cấu hình encoding UTF-8 nếu chạy trên Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


class TranslationError(Exception):
    """Lỗi xảy ra trong quá trình dịch thuật với LLM."""
    pass


def _sleep_with_cancel(duration: float, cancel_check: Optional[Callable[[], bool]]) -> None:
    slept = 0.0
    while slept < duration:
        if cancel_check and cancel_check():
            raise InterruptedError("The translation was cancelled by the user.")
        step = min(0.1, duration - slept)
        time.sleep(step)
        slept += step


def clean_json_response(raw_text: str) -> str:
    """
    Trích xuất và làm sạch chuỗi JSON từ phản hồi của LLM (loại bỏ markdown fence nếu có).
    """
    text = raw_text.strip()
    
    # Tìm khối mã ```json ... ``` hoặc ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # Nếu text bắt đầu bằng [ và kết thúc bằng ]
    first_bracket = text.find("[")
    last_bracket = text.rfind("]")
    if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
        return text[first_bracket:last_bracket + 1].strip()

    return text


def build_system_prompt(source_lang: str, target_lang: str, genre: str, custom_terms: str) -> str:
    """
    Tạo system prompt kỹ thuật chuyên sâu cho tác vụ lồng tiếng video ngắn.
    """
    prompt = f"""Bạn là chuyên gia dịch thuật và biên kịch lồng tiếng cho video ngắn TikTok/Douyin từ {source_lang} sang {target_lang}.
Thể loại video: {genre}.

YÊU CẦU QUAN TRỌNG NHẤT (CHO TÁC VỤ LỒNG TIẾNG - DUBBING):
1. ĐỘ DÀI CÂU THOẠI: Câu tiếng Việt dịch ra BẮT BUỘC PHẢI NGẮN GỌN, súc tích, số lượng âm tiết tương đương câu gốc để người đọc/máy đọc kịp thời gian khung hình.
2. VĂN PHONG: Tự nhiên, dí dỏm, bắt trend mạng xã hội TikTok, tránh dịch thô cứng kiểu từ điển hay Hán Việt lỗi thời.
3. BẢO TOÀN THỜI GIAN: Giữ nguyên index, start, end của từng phân đoạn câu.
"""
    if custom_terms.strip():
        prompt += f"\nQUY TẮC DỊCH THUẬT RIÊNG (TỪ KHÓA / TÊN RIÊNG):\n{custom_terms.strip()}\n"

    prompt += """
ĐỊNH DẠNG ĐẦU RA BẮT BUỘC:
Trả về duy nhất một mảng JSON hợp lệ, KHÔNG thêm bất kỳ lời chào hay giải thích nào ngoài chuỗi JSON.
Mẫu JSON:
[
  {
    "index": 0,
    "start": 0.0,
    "end": 2.1,
    "text": "Câu gốc",
    "translated_text": "Câu tiếng Việt ngắn gọn"
  }
]
"""
    return prompt


def translate_segments(
    segments: List[Dict[str, Any]],
    source_lang: str = "Tiếng Trung",
    target_lang: str = "Tiếng Việt",
    genre: str = "Đời sống / Mạng xã hội",
    custom_terms: str = "",
    progress_callback: Optional[Callable[[str, float], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    batch_size: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Gửi danh sách câu thoại sang mô hình LLM để dịch thuật và tối ưu câu thoại lồng tiếng.

    Args:
        segments: Danh sách phân đoạn từ Whisper ([{"index", "start", "end", "text"}]).
        source_lang: Ngôn ngữ gốc.
        target_lang: Ngôn ngữ đích.
        genre: Thể loại nội dung (Cổ trang, Hài hước, Công nghệ,...).
        custom_terms: Danh sách tên riêng hoặc thuật ngữ cố định.
        progress_callback: Hàm nhận (thông điệp, phần trăm tiến độ).
        cancel_check: Hàm kiểm tra xem người dùng có yêu cầu dừng tiến trình hay không.
        batch_size: Số câu tối đa gửi trong một request; mặc định lấy từ Config.

    Returns:
        List[Dict[str, Any]]: Danh sách câu thoại đã được bổ sung trường "translated_text".
    """
    if not segments:
        return []

    configured_batch_size = batch_size if batch_size is not None else getattr(Config, "LLM_TRANSLATION_BATCH_SIZE", 4)
    if isinstance(configured_batch_size, bool) or not isinstance(configured_batch_size, (int, str)):
        raise ValueError("LLM translation batch size must be an integer between 1 and 32.")
    try:
        chunk_size = int(configured_batch_size)
    except (TypeError, ValueError) as exc:
        raise ValueError("LLM translation batch size must be an integer between 1 and 32.") from exc
    if isinstance(configured_batch_size, str) and not configured_batch_size.strip().lstrip("+").isdigit():
        raise ValueError("LLM translation batch size must be an integer between 1 and 32.")
    if not 1 <= chunk_size <= 32:
        raise ValueError("LLM translation batch size must be an integer between 1 and 32.")

    try:
        from openai import OpenAI
    except ImportError:
        raise TranslationError("Thư viện openai chưa được cài đặt. Vui lòng chạy: pip install openai")

    # Cấu hình danh sách providers (hỗ trợ chuyển đổi tự động sang Backup khi chạm Rate Limit 429)
    providers = [
        {
            "name": "Primary",
            "base_url": Config.LLM_BASE_URL,
            "api_key": Config.LLM_API_KEY,
            "model": Config.LLM_MODEL
        }
    ]

    if getattr(Config, "LLM_BACKUP_ENABLED", False) and getattr(Config, "LLM_BACKUP_BASE_URL", "") and getattr(Config, "LLM_BACKUP_MODEL", ""):
        providers.append({
            "name": "Backup",
            "base_url": Config.LLM_BACKUP_BASE_URL,
            "api_key": getattr(Config, "LLM_BACKUP_API_KEY", "") or "no-key-required",
            "model": Config.LLM_BACKUP_MODEL
        })

    clients = {}
    for p in providers:
        clients[p["name"]] = OpenAI(
            base_url=p["base_url"],
            api_key=p["api_key"] or "no-key-required",
            timeout=getattr(Config, "LLM_TIMEOUT", 60.0),
            max_retries=1
        )

    current_p_idx = 0
    init_p = providers[current_p_idx]
    if progress_callback:
        if len(providers) > 1:
            progress_callback(f"Khởi động dịch thuật: Primary ({init_p['model']}) + Backup ({providers[1]['model']})...", 10.0)
        else:
            progress_callback(f"Kết nối tới mô hình LLM: {init_p['model']}...", 10.0)

    system_prompt = build_system_prompt(source_lang, target_lang, genre, custom_terms)
    total_segments = len(segments)
    pending_chunks = [segments[i:i + chunk_size] for i in range(0, total_segments, chunk_size)]
    translation_map = {}
    source_fallback_indexes = set()
    completed_segments = 0
    batch_number = 0

    while pending_chunks:
        if cancel_check and cancel_check():
            raise InterruptedError("Tiến trình dịch thuật đã bị dừng bởi người dùng.")

        chunk = pending_chunks.pop(0)
        batch_number += 1
        percent = (completed_segments / total_segments) * 100.0
        if progress_callback:
            active_name = providers[current_p_idx]["name"]
            progress_callback(f"Translating batch {batch_number} ({len(chunk)} dialogues via {active_name})...", percent)

        input_data = [
            {
                "index": seg["index"],
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"]
            }
            for seg in chunk
        ]

        user_prompt = f"Dưới đây là danh sách {len(input_data)} câu thoại cần dịch:\n" + json.dumps(input_data, ensure_ascii=False, indent=2)

        max_attempts = len(providers) * 2
        for attempt in range(max_attempts):
            if cancel_check and cancel_check():
                raise InterruptedError("Tiến trình dịch thuật đã bị dừng bởi người dùng.")

            active_p = providers[current_p_idx]
            active_client = clients[active_p["name"]]

            try:
                response = active_client.chat.completions.create(
                    model=active_p["model"],
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,
                )
                if cancel_check and cancel_check():
                    raise InterruptedError("The translation was cancelled by the user.")

                raw_output = response.choices[0].message.content or ""
                cleaned_json = clean_json_response(raw_output)
                parsed_results = json.loads(cleaned_json)

                if not isinstance(parsed_results, list):
                    raise ValueError("LLM response must be a JSON list.")

                expected_indexes = {seg["index"] for seg in chunk}
                chunk_translations = {}
                for item in parsed_results:
                    if not isinstance(item, dict) or "index" not in item:
                        raise ValueError("LLM response contains an invalid segment entry.")
                    seg_index = item["index"]
                    translated_text = item.get("translated_text")
                    if seg_index not in expected_indexes:
                        raise ValueError(f"LLM returned an unknown segment index: {seg_index}.")
                    if seg_index in chunk_translations:
                        raise ValueError(f"LLM returned duplicate segment index: {seg_index}.")
                    if not isinstance(translated_text, str) or not translated_text.strip():
                        raise ValueError(f"LLM returned empty text for segment {seg_index}.")
                    chunk_translations[seg_index] = translated_text.strip()

                missing_indexes = expected_indexes.difference(chunk_translations)
                if missing_indexes:
                    raise ValueError(f"LLM response is missing segment indexes: {sorted(missing_indexes)}.")

                if pending_chunks:
                    # Keep a short pause between requests to reduce provider rate-limit pressure.
                    _sleep_with_cancel(0.5, cancel_check)
                translation_map.update(chunk_translations)
                completed_segments += len(chunk)
                break

            except InterruptedError:
                raise
            except Exception as e:
                err_msg = str(e).replace("\n", " ")
                normalized_error = err_msg.lower()
                is_batch_size_error = any(term in normalized_error for term in (
                    "too large", "context length", "context_length", "maximum context",
                    "prompt is too long", "too many tokens", "413",
                ))
                is_timeout_error = "timeout" in normalized_error or "timed out" in normalized_error
                is_rate_limit = any(term in normalized_error for term in ("429", "rate limit", "rate_limit", "tpm"))

                # Nếu có cấu hình Backup Provider: tự động switch sang Provider tiếp theo
                if len(providers) > 1 and attempt < max_attempts - 1:
                    next_p_idx = (current_p_idx + 1) % len(providers)
                    next_p = providers[next_p_idx]
                    reason = "429 Rate Limit" if is_rate_limit else "Lỗi API"
                    if progress_callback:
                        progress_callback(
                            f"⚠️ {active_p['name']} ({active_p['model']}) gặp {reason}. Tự động switch sang {next_p['name']} ({next_p['model']})...",
                            percent
                        )
                    current_p_idx = next_p_idx
                    _sleep_with_cancel(1.0, cancel_check)
                    continue

                # Nếu chỉ có 1 provider và bị rate limit: chờ thử lại theo nhịp
                if is_rate_limit and attempt < max_attempts - 1:
                    wait_sec = 6.0 * (attempt + 1)
                    match_time = re.search(r"(?:try again in|retry after)\s+([\d\.]+)\s*s", err_msg, re.IGNORECASE)
                    if match_time:
                        wait_sec = min(60.0, max(wait_sec, float(match_time.group(1)) + 1.0))

                    if progress_callback:
                        progress_callback(
                            f"⏳ Chạm giới hạn token (429 Rate Limit), tự động chờ {wait_sec:.1f}s trước khi thử lại batch {batch_number}...",
                            percent
                        )

                    slept = 0.0
                    while slept < wait_sec:
                        if cancel_check and cancel_check():
                            raise InterruptedError("Tiến trình dịch thuật đã bị dừng bởi người dùng.")
                        time.sleep(0.1)
                        slept += 0.1
                    continue

                # Retry an invalid/oversized response with smaller chunks before falling back.
                if len(chunk) > 1 and (
                    is_batch_size_error
                    or is_timeout_error
                    or isinstance(e, (ValueError, IndexError))
                ):
                    midpoint = len(chunk) // 2
                    pending_chunks[0:0] = [chunk[:midpoint], chunk[midpoint:]]
                    if progress_callback:
                        progress_callback(
                            f"⚠️ LLM could not return a valid response for {len(chunk)} dialogues; retrying as smaller batches.",
                            percent,
                        )
                    break

                # If this chunk cannot be recovered, keep its source speech visible in the result.
                if progress_callback:
                    progress_callback(f"⚠️ LLM translation error ({err_msg[:80]}). Using original text.", percent)
                for seg in chunk:
                    if seg["index"] not in translation_map:
                        translation_map[seg["index"]] = seg["text"]
                        source_fallback_indexes.add(seg["index"])
                completed_segments += len(chunk)
                break

    enriched_segments = []
    for seg in segments:
        seg_copy = dict(seg)
        if seg["index"] not in translation_map:
            translation_map[seg["index"]] = seg["text"]
            source_fallback_indexes.add(seg["index"])
        seg_copy["translated_text"] = translation_map[seg["index"]].strip()
        seg_copy["translation_status"] = "source_fallback" if seg["index"] in source_fallback_indexes else "translated"
        enriched_segments.append(seg_copy)

    if source_fallback_indexes and progress_callback:
        progress_callback(
            f"⚠️ {len(source_fallback_indexes)} dialogue(s) kept in the source language because translation did not return a valid result.",
            99.0
        )

    if progress_callback:
        progress_callback(f"Translation completed: {len(enriched_segments)} dialogues ready for dubbing.", 100.0)

    return enriched_segments


def test_llm_connection(base_url: str, api_key: str, model: str) -> tuple[bool, str]:
    """
    Kiểm tra kết nối và tính khả dụng của mô hình LLM với một yêu cầu ping ngắn.
    Trả về: (thành_công: bool, thông_điệp: str)
    """
    try:
        from openai import OpenAI
    except ImportError:
        return False, "Library 'openai' is not installed."

    base_url = base_url.strip()
    if base_url.endswith("/chat/completions"):
        base_url = base_url[:-len("/chat/completions")]

    api_key = api_key.strip() or "EMPTY"
    model = model.strip()

    if not base_url:
        return False, "Base URL cannot be empty."
    if not model:
        return False, "Model name cannot be empty."

    try:
        client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=15.0,
            max_retries=1
        )
        # Gửi ping test siêu ngắn
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5
        )
        if response and response.choices:
            return True, f"✓ Connected successfully to {model}!"
        return False, "Model returned an empty response."
    except Exception as e:
        err_msg = str(e)
        if "AuthenticationError" in err_msg or "401" in err_msg:
            return False, "Authentication failed (401): Invalid API Key."
        elif "NotFoundError" in err_msg or "404" in err_msg:
            clean_err = err_msg.replace("\n", " ").strip()
            return False, f"Model '{model}' not found (404) or invalid endpoint URL. ({clean_err[:120]})"
        elif "ConnectionError" in err_msg or "ConnectError" in err_msg:
            return False, "Failed to connect to host. Check your Base URL or network."
        return False, f"Connection error: {err_msg[:80]}"
