"""
Speech to Text — faster-whisper tiny model
Runs fully offline, supports 99 languages including Hindi
"""
from faster_whisper import WhisperModel
from app.config import settings
import tempfile
import os

_model = None

def get_whisper_model():
    global _model
    if _model is None:
        print(f"Loading Whisper {settings.whisper_model_size} model...")
        _model = WhisperModel(
            settings.whisper_model_size,
            device="cpu",
            compute_type="int8"
        )
        print("Whisper model loaded")
    return _model

async def transcribe_audio(audio_bytes: bytes, language: str = None) -> dict:
    """
    Transcribe audio bytes to text.
    Returns dict with text, language_detected, confidence
    """
    model = get_whisper_model()

    # Write to temp file (faster-whisper needs file path)
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        segments, info = model.transcribe(
            tmp_path,
            language=language,
            beam_size=5,
            vad_filter=True,
        )

        text = " ".join([seg.text.strip() for seg in segments])
        detected_lang = info.language
        confidence = round(info.language_probability, 3)

        return {
            "text": text.strip(),
            "language_detected": detected_lang,
            "confidence": confidence,
            "duration_seconds": round(info.duration, 2)
        }
    finally:
        os.unlink(tmp_path)
