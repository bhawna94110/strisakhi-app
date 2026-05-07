"""
StriSakhi TTS — backend/app/voice/tts.py
Offline TTS using Piper binary at /usr/local/piper
Supports Hindi (Devanagari) and English only.
Hinglish (Roman Hindi) → convert via LLM → Piper Hindi
"""
import subprocess
import tempfile
import os
import re
import logging
import asyncio
import httpx
from pathlib import Path

logger = logging.getLogger(__name__)

PIPER = "/usr/local/piper"
MODELS = {
    "hi": {
        "model":  "/app/strisakhi-models/piper/hi_IN-priyamvada-medium.onnx",
        "config": "/app/strisakhi-models/piper/hi_IN-priyamvada-medium.onnx.json",
        "speed":  1.2,
    },
    "en": {
        "model":  "/app/strisakhi-models/piper/en_US-amy-medium.onnx",
        "config": "/app/strisakhi-models/piper/en_US-amy-medium.onnx.json",
        "speed":  1.0,
    },
}

# These scripts have no Piper voice — return no audio
NO_TTS_SCRIPTS = [
    r'[\u0980-\u09FF]',  # Bengali
    r'[\u0B80-\u0BFF]',  # Tamil
    r'[\u0C00-\u0C7F]',  # Telugu
    r'[\u0C80-\u0CFF]',  # Kannada
    r'[\u0D00-\u0D7F]',  # Malayalam
    r'[\u0A80-\u0AFF]',  # Gujarati
    r'[\u0A00-\u0A7F]',  # Punjabi
    r'[\u0900-\u094F\u0950-\u097F]',  # Devanagari (handled separately as "hi")
]


def remove_emojis(text: str) -> str:
    # Remove all emoji and symbol unicode ranges
    emoji_pattern = re.compile(
        "[\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F9FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "\u2640-\u2642"
        "\u2600-\u2B55"
        "\u200d\u23cf\u23e9\u231a\ufe0f\u3030]+",
        flags=re.UNICODE
    )
    return emoji_pattern.sub('', text)


def clean_text(text: str) -> str:
    """Remove markdown, citations, emojis, numbered lists from LLM output"""
    text = remove_emojis(text)
    text = re.sub(r'\[Source:[^\]]+\]', '', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'^\d+\.\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\*\-•]\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'#+ ', '', text)
    text = ' '.join(text.split())
    return text.strip()


def detect_script(text: str) -> str:
    """
    Detect the dominant script in text.
    Returns: 'devanagari' | 'roman' | 'bengali' | 'tamil' | 'other_indic' | 'mixed'
    """
    deva = len(re.findall(r'[\u0900-\u097F]', text))
    roman = len(re.findall(r'[a-zA-Z]', text))
    bengali = len(re.findall(r'[\u0980-\u09FF]', text))
    tamil = len(re.findall(r'[\u0B80-\u0BFF]', text))
    other_indic = len(re.findall(
        r'[\u0C00-\u0C7F\u0C80-\u0CFF\u0D00-\u0D7F\u0A80-\u0AFF\u0A00-\u0A7F]', text
    ))
    total = deva + roman + bengali + tamil + other_indic
    if total == 0:
        return 'roman'

    # Dominant script check (>50%)
    if deva / total > 0.5:
        return 'devanagari'
    if roman / total > 0.5:
        return 'roman'
    if bengali / total > 0.3:
        return 'bengali'
    if tamil / total > 0.3:
        return 'tamil'
    if other_indic / total > 0.3:
        return 'other_indic'

    # Mixed Devanagari + Roman
    if deva > 0 and roman > 0:
        return 'devanagari' if deva >= roman else 'roman'

    return 'roman'


async def convert_hinglish_to_devanagari(text: str, llama_url: str) -> str:
    """
    Use Gemma 4 to convert Hinglish (Roman Hindi) to Devanagari.
    Fast — just script conversion, no reasoning needed.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            payload = {
                "model": "gemma4",
                "messages": [{
                    "role": "user",
                    "content": (
                        f"Convert this Hindi text written in Roman script to Devanagari script. "
                        f"Output ONLY the Devanagari text, nothing else, no explanation.\n\n"
                        f"Input: {text}"
                    )
                }],
                "stream": False,
                "max_tokens": 300,
                "temperature": 0.1,
            }
            r = await client.post(f"{llama_url}/v1/chat/completions", json=payload)
            result = r.json()["choices"][0]["message"]["content"].strip()
            # Verify result is actually Devanagari
            if re.search(r'[\u0900-\u097F]', result):
                return result
            return text  # fallback if conversion failed
    except Exception as e:
        logger.error(f"Hinglish conversion failed: {e}")
        return text


async def run_piper(text: str, model: str, config: str, speed: float) -> bytes:
    """Run piper binary and return WAV bytes"""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        output_path = f.name

    # Escape quotes in text
    safe_text = text.replace('"', "'").replace('`', "'").replace('$', '')

    cmd = f'echo "{safe_text}" | {PIPER} -m {model} -f {output_path} --length_scale {speed}'

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
    )

    if result.returncode != 0:
        logger.error(f"Piper error: {result.stderr}")
        if os.path.exists(output_path):
            os.unlink(output_path)
        return b""

    if not os.path.exists(output_path):
        return b""

    with open(output_path, "rb") as f:
        audio = f.read()

    os.unlink(output_path)

    if len(audio) <= 44:
        return b""

    return audio


async def synthesize(text: str, llama_url: str = "http://host.docker.internal:8080") -> tuple[bytes, str]:
    """
    Convert text to speech.
    Returns (wav_bytes, lang_code)
    Returns (b"", lang) if not supported.
    """
    if not text or len(text.strip()) < 3:
        return b"", ""

    # Step 1: Clean text
    clean = clean_text(text)
    if not clean:
        return b"", ""

    # Limit to first 400 chars for TTS (about 30 seconds)
    clean = clean[:400]

    # Step 2: Detect script
    script = detect_script(clean)
    logger.info(f"TTS: script={script}, text={clean[:50]}")

    # Step 3: Route based on script
    if script == 'devanagari':
        # Pure Hindi → Piper priyamvada directly
        voice = MODELS["hi"]
        audio = await run_piper(clean, voice["model"], voice["config"], voice["speed"])
        return audio, "hi"

    elif script == 'roman':
        # Could be English or Hinglish
        # Simple heuristic: check for common Hinglish words
        hinglish_words = [
            'aapki', 'aapke', 'aapka', 'mujhe', 'mere', 'mera', 'meri',
            'hoon', 'hain', 'hai', 'tha', 'thi', 'karo', 'karein', 'karna',
            'namaste', 'dhanyavaad', 'theek', 'accha', 'nahin', 'nahi',
            'aaj', 'kal', 'abhi', 'bahut', 'kuch', 'sab', 'aur', 'lekin',
            'ghar', 'pati', 'sakhi', 'adhikar', 'kanoon', 'madad',
        ]
        text_lower = clean.lower()
        hinglish_count = sum(1 for w in hinglish_words if w in text_lower)

        if hinglish_count >= 2:
            # Hinglish → convert to Devanagari → Piper priyamvada
            logger.info(f"TTS: Hinglish detected ({hinglish_count} words) → converting to Devanagari")
            devanagari = await convert_hinglish_to_devanagari(clean, llama_url)
            voice = MODELS["hi"]
            audio = await run_piper(devanagari, voice["model"], voice["config"], voice["speed"])
            return audio, "hi"
        else:
            # English → Piper amy
            voice = MODELS["en"]
            audio = await run_piper(clean, voice["model"], voice["config"], voice["speed"])
            return audio, "en"

    elif script in ('bengali', 'tamil', 'other_indic'):
        # No TTS support
        logger.info(f"TTS: No support for script={script}")
        return b"", script

    else:
        # Mixed or unknown → try English
        voice = MODELS["en"]
        audio = await run_piper(clean, voice["model"], voice["config"], voice["speed"])
        return audio, "en"
