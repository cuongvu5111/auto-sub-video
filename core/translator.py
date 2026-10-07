"""
Module dịch thuật phụ đề và tối ưu câu thoại lồng tiếng bằng LLM (OpenAI-compatible).
Dịch từ tiếng Trung (hoặc ngôn ngữ gốc) sang tiếng Việt với văn phong tự nhiên, súc tích cho TikTok.
"""

import sys
import json
import re
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
    progress_callback: Optional[Callable[[str, float], None]] = None
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

    Returns:
        List[Dict[str, Any]]: Danh sách câu thoại đã được bổ sung trường "translated_text".
    """
    if not segments:
        return []

    try:
        from openai import OpenAI
    except ImportError:
        raise TranslationError("Thư viện openai chưa được cài đặt. Vui lòng chạy: pip install openai")

    if progress_callback:
        progress_callback(f"Kết nối tới mô hình LLM: {Config.LLM_MODEL}...", 10.0)

    client = OpenAI(
        base_url=Config.LLM_BASE_URL,
        api_key=Config.LLM_API_KEY,
        timeout=30.0,
        max_retries=2
    )

    # Chuẩn bị dữ liệu đầu vào gọn nhẹ cho prompt
    input_data = [
        {
            "index": seg["index"],
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"]
        }
        for seg in segments
    ]

    system_prompt = build_system_prompt(source_lang, target_lang, genre, custom_terms)
    chunk_size = 6
    total_segments = len(segments)
    chunks = [segments[i:i + chunk_size] for i in range(0, total_segments, chunk_size)]
    translation_map = {}

    for c_idx, chunk in enumerate(chunks):
        if progress_callback:
            percent = (c_idx / len(chunks)) * 100.0
            progress_callback(f"Translating batch {c_idx + 1}/{len(chunks)} ({len(chunk)} dialogues)...", percent)

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

        try:
            response = client.chat.completions.create(
                model=Config.LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
            )

            raw_output = response.choices[0].message.content or ""
            cleaned_json = clean_json_response(raw_output)
            parsed_results = json.loads(cleaned_json)

            for item in parsed_results:
                if isinstance(item, dict) and "index" in item:
                    translation_map[item["index"]] = item.get("translated_text", "").strip()

        except Exception as e:
            # Thông báo cảnh báo lỗi LLM qua callback để hiển thị trên UI console
            err_msg = str(e).replace("\n", " ")
            if progress_callback:
                progress_callback(f"⚠️ LLM translation error ({err_msg[:80]}). Using original text.", percent)
            # Nếu 1 batch gặp lỗi phân tích JSON hoặc timeout thì fallback về câu gốc
            for seg in chunk:
                if seg["index"] not in translation_map:
                    translation_map[seg["index"]] = seg["text"]

    enriched_segments = []
    for seg in segments:
        seg_copy = dict(seg)
        seg_copy["translated_text"] = translation_map.get(seg["index"], seg["text"]).strip()
        enriched_segments.append(seg_copy)

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
            timeout=8.0,
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
            return False, f"Model '{model}' not found (404) or invalid endpoint URL."
        elif "ConnectionError" in err_msg or "ConnectError" in err_msg:
            return False, "Failed to connect to host. Check your Base URL or network."
        return False, f"Connection error: {err_msg[:80]}"
