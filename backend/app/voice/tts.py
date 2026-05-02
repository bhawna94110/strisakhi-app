"""
Text to Speech — edge-tts
Uses hi-IN-SwaraNeural — warm, natural Indian female voice
"""
import edge_tts
import tempfile
import os
import re
from app.config import settings

VOICE_MAP = {
    "hi": "hi-IN-SwaraNeural",
    "en": "en-IN-NeerjaNeural",
    "ta": "ta-IN-PallaviNeural",
    "te": "te-IN-ShrutiNeural",
    "mr": "mr-IN-AarohiNeural",
    "bn": "bn-IN-TanishaaNeural",
    "gu": "gu-IN-DhwaniNeural",
    "kn": "kn-IN-SapnaNeural",
    "ml": "ml-IN-SobhanaNeural",
}

def clean_text_for_tts(text: str) -> str:
    """Remove markdown, citations, and format for natural speech"""
    # Remove citation tags [Source: ...]
    text = re.sub(r'\[Source:[^\]]+\]', '', text)
    # Remove markdown bold/italic
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    # Remove bullet points
    text = re.sub(r'^[→•\-\*]\s*', '', text, flags=re.MULTILINE)
    # Clean extra whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    return text

async def synthesize_speech(text: str, language: str = "hi") -> bytes:
    """
    Convert text to speech using edge-tts.
    Returns MP3 audio bytes.
    """
    voice = VOICE_MAP.get(language, VOICE_MAP["hi"])
    clean = clean_text_for_tts(text)

    if not clean:
        return b""

    communicate = edge_tts.Communicate(
        text=clean,
        voice=voice,
        rate="-10%",    # slightly slower for clarity
        pitch="+0Hz",
    )

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        await communicate.save(tmp_path)
        with open(tmp_path, "rb") as f:
            audio_bytes = f.read()
        return audio_bytes
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
