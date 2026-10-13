import hashlib
import hmac
import io
import json
import os
import time
from urllib.parse import parse_qsl

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__, template_folder="templates")
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
TRANSCRIPTION_MODEL = "whisper-large-v3"
CHAT_MODEL = "openai/gpt-oss-20b"


def verify_telegram_init_data(init_data):
    if not BOT_TOKEN or not init_data:
        return False

    try:
        values = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = values.pop("hash", "")
        if not received_hash:
            return False

        auth_date = int(values.get("auth_date", "0"))
        now = int(time.time())
        if auth_date > now + 30 or now - auth_date > 86400:
            return False

        data_check_string = "\n".join(
            f"{key}={value}" for key, value in sorted(values.items())
        )
        secret_key = hmac.new(
            BOT_TOKEN.encode(), b"WebAppData", hashlib.sha256
        ).digest()
        calculated_hash = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(calculated_hash, received_hash)
    except (TypeError, ValueError):
        return False


def authorized_request():
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    return verify_telegram_init_data(init_data)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify(status="ok", app="Nabz Mini App")


@app.post("/api/voice")
def voice():
    if not authorized_request():
        return jsonify(error="لطفاً نبض را از داخل تلگرام باز کن."), 401

    if not GROQ_API_KEY:
        return jsonify(error="تنظیم سرویس هوش مصنوعی کامل نیست."), 503

    audio = request.files.get("audio")
    if audio is None:
        return jsonify(error="فایل صوتی دریافت نشد."), 400

    audio_bytes = audio.read(app.config["MAX_CONTENT_LENGTH"] + 1)
    if not audio_bytes:
        return jsonify(error="فایل صوتی خالی است."), 400
    if len(audio_bytes) > app.config["MAX_CONTENT_LENGTH"]:
        return jsonify(error="حجم فایل صوتی بیش از حد مجاز است."), 413

    filename = os.path.basename(audio.filename or "recording.webm")
    mime_type = audio.mimetype or "audio/webm"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}

    try:
        transcription_response = requests.post(
            f"{GROQ_BASE_URL}/audio/transcriptions",
            headers=headers,
            files={"file": (filename, io.BytesIO(audio_bytes), mime_type)},
            data={
                "model": TRANSCRIPTION_MODEL,
                "response_format": "json",
            },
            timeout=90,
        )
        transcription_response.raise_for_status()
        transcript = transcription_response.json().get("text", "").strip()
        if not transcript:
            return jsonify(error="صدایی قابل تشخیص نبود."), 422

        chat_response = requests.post(
            f"{GROQ_BASE_URL}/chat/completions",
            headers={**headers, "Content-Type": "application/json"},
            json={
                "model": CHAT_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are Nabz, a helpful multilingual voice assistant. "
                            "Reply in the same language as the user's message. "
                            "Be natural, warm, clear, and concise."
                        ),
                    },
                    {"role": "user", "content": transcript},
                ],
                "temperature": 0.7,
                "max_tokens": 700,
            },
            timeout=60,
        )
        chat_response.raise_for_status()
        answer = (
            chat_response.json()["choices"][0]["message"]["content"].strip()
        )
        return jsonify(transcript=transcript, answer=answer)

    except requests.Timeout:
        return jsonify(error="پاسخ‌گویی طول کشید؛ دوباره امتحان کن."), 504
    except requests.RequestException:
        app.logger.warning("Groq request failed")
        return jsonify(error="اتصال به سرویس هوش مصنوعی ناموفق بود."), 502
    except (ValueError, KeyError, IndexError, TypeError):
        app.logger.exception("Unexpected response from AI service")
        return jsonify(error="پاسخ نامعتبر از سرویس دریافت شد."), 502


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify(error="حجم درخواست بیش از حد مجاز است."), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
