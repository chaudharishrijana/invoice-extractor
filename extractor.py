"""Reads an invoice image and extracts structured data using the Gemini API."""
import json
import os
from pathlib import Path

from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from models import Invoice

# Model can be overridden with the GEMINI_MODEL environment variable.
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # keep uploads small

SYSTEM_PROMPT = (
    "You are an invoice data extraction assistant. You read invoice images "
    "and return structured JSON. You never invent values. If a field is not "
    "visible or unclear, use null."
)

USER_PROMPT = """Extract the following information from the attached invoice image and return ONLY valid JSON. Do not include markdown fences, explanations, or any text outside the JSON.

Schema:
{
  "invoice_number": string | null,
  "invoice_date": string | null,        // ISO format YYYY-MM-DD
  "supplier_name": string | null,
  "currency": string | null,            // e.g. "NPR"
  "items": [
    {
      "description": string,
      "quantity": number,
      "unit": string | null,            // e.g. "pcs", "hrs", "lot"
      "unit_price": number
    }
  ],
  "subtotal": number | null,
  "vat_rate_percent": number | null,
  "vat_amount": number | null,
  "total_amount": number | null
}

Rules:
- Copy values exactly as printed on the invoice. Do NOT calculate, correct, or adjust any numbers.
- Numbers must be plain numbers without currency symbols or thousands separators (e.g. 62500.00, not "62,500.00").
- The supplier is the company that issued the invoice (the letterhead), not the "Bill To" party.
- If a field is missing or unreadable, set it to null. Do not guess.
- If the image is not an invoice, return {"error": "not_an_invoice"}."""


class ExtractionError(Exception):
    """Raised for any expected failure: bad file, API problem, bad model output."""


def _detect_media_type(data: bytes) -> str | None:
    """Identify the image type from its first bytes (more reliable than the extension)."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def load_image(path: str) -> tuple[str, bytes]:
    """Return (media_type, raw_bytes) for the image at `path`."""
    file = Path(path)
    if not file.is_file():
        raise ExtractionError(f"File not found: {file}")

    try:
        data = file.read_bytes()
    except OSError as exc:
        raise ExtractionError(f"Could not read file: {exc}") from exc

    if len(data) > MAX_IMAGE_BYTES:
        raise ExtractionError("Image is larger than 5 MB. Please use a smaller file.")

    media_type = _detect_media_type(data)
    if media_type is None:
        raise ExtractionError(
            "Unreadable or unsupported image. Use a PNG, JPEG, GIF or WEBP file."
        )

    return media_type, data


def call_gemini(media_type: str, image_bytes: bytes) -> str:
    """Send the image to Gemini and return the raw text response."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ExtractionError("GEMINI_API_KEY environment variable is not set.")

    client = genai.Client(api_key=api_key)

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=media_type),
                USER_PROMPT,
            ],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0,
            ),
        )
    except errors.APIError as exc:
        code = getattr(exc, "code", None)
        message = getattr(exc, "message", str(exc))
        if code in (401, 403) or "API key" in str(message):
            raise ExtractionError("Invalid API key (authentication failed).") from exc
        if code == 429:
            raise ExtractionError("Rate limit reached. Please wait a minute and try again.") from exc
        raise ExtractionError(f"API error {code}: {message}") from exc
    except Exception as exc:  # network problems, timeouts, etc.
        raise ExtractionError(f"Could not reach the Gemini API: {exc}") from exc

    text = response.text
    if not text or not text.strip():
        raise ExtractionError("The model returned an empty response.")
    return text


def parse_model_output(text: str) -> Invoice:
    """Turn the model's text into a validated Invoice object."""
    cleaned = text.strip()

    # Be forgiving if the model wrapped the JSON in ``` fences or added text.
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ExtractionError("The model response did not contain a JSON object.")

    try:
        data = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"The model returned invalid JSON: {exc}") from exc

    if isinstance(data, dict) and data.get("error"):
        raise ExtractionError(f"Could not extract invoice data: {data['error']}")

    try:
        return Invoice.model_validate(data)
    except ValidationError as exc:
        raise ExtractionError(f"Extracted data had the wrong shape: {exc}") from exc


def extract_invoice(path: str) -> Invoice:
    """Full pipeline: load image -> call Gemini -> parse output."""
    media_type, image_bytes = load_image(path)
    raw_text = call_gemini_with_retry(media_type, image_bytes)
    return parse_model_output(raw_text)


def call_gemini_with_retry(media_type, image_bytes, attempts=4):
    """Retry on temporary errors (503 overload, 429 rate limit)."""
    import sys
    import time

    delay = 5
    for attempt in range(1, attempts + 1):
        try:
            return call_gemini(media_type, image_bytes)
        except ExtractionError as exc:
            temporary = "API error 503" in str(exc) or "Rate limit" in str(exc)
            if not temporary or attempt == attempts:
                raise
            print(f"Temporary error, retrying in {delay}s ({attempt}/{attempts})...", file=sys.stderr)
            time.sleep(delay)
            delay *= 2
