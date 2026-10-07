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
        api_key=Config.LLM_API_KEY
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
    user_prompt = f"Dưới đây là danh sách {len(input_data)} câu thoại cần dịch:\n" + json.dumps(input_data, ensure_ascii=False, indent=2)

    if progress_callback:
        progress_callback(f"Đang gửi {len(input_data)} câu thoại sang LLM xử lý...", 30.0)

    try:
        response = client.chat.completions.create(
            model=Config.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3, # Giữ nhiệt độ thấp để bản dịch ổn định và tuân thủ JSON
        )

        raw_output = response.choices[0].message.content or ""
        cleaned_json = clean_json_response(raw_output)

        parsed_results = json.loads(cleaned_json)

        # Mapping bản dịch ngược lại vào segments gốc
        translation_map = {item["index"]: item.get("translated_text", "") for item in parsed_results if "index" in item}

        enriched_segments = []
        for seg in segments:
            seg_copy = dict(seg)
            # Nếu LLM dịch thành công thì lấy, nếu không fallback về câu gốc
            seg_copy["translated_text"] = translation_map.get(seg["index"], seg["text"]).strip()
            enriched_segments.append(seg_copy)

        if progress_callback:
            progress_callback(f"Dịch hoàn tất: {len(enriched_segments)} câu thoại sẵn sàng lồng tiếng.", 100.0)

        return enriched_segments

    except json.JSONDecodeError as e:
        raise TranslationError(f"Phản hồi từ LLM không phải là JSON hợp lệ: {str(e)}\nNội dung thô: {raw_output[:300]}") from e
    except Exception as e:
        raise TranslationError(f"Lỗi khi gọi API LLM ({Config.LLM_BASE_URL}): {str(e)}") from e
