"""
StriSakhi TTS — backend/app/voice/tts.py
Language is passed explicitly from session — no auto-detection needed.
Hindi → Piper priyamvada (Devanagari only)
English → Piper Amy
Bengali/others → no audio (204)
Fallback: if Hindi session but response is not Devanagari → LLM converts first
"""
import subprocess
import tempfile
import os
import re
import logging
import asyncio
import httpx
from app.runtime_config import get_config

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

TTS_SUPPORTED = {"hi", "en"}


def clean_text(text: str) -> str:
    # Remove emojis
    emoji_re = re.compile(
        "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F9FF\U00002702-\U000027B0"
        "\U0001f926-\U0001f937\U00010000-\U0010ffff"
        "\u2640-\u2642\u2600-\u2B55\u200d\u23cf\u23e9"
        "\u231a\ufe0f\u3030]+", flags=re.UNICODE)
    text = emoji_re.sub('', text)
    text = re.sub(r'\[Source:[^\]]+\]', '', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'^\d+\.\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\*\-•]\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'#+ ', '', text)
    return ' '.join(text.split()).strip()


def is_devanagari(text: str) -> bool:
    deva = len(re.findall(r'[\u0900-\u097F]', text))
    total = len(re.findall(r'[a-zA-Z\u0900-\u097F]', text))
    return total > 0 and (deva / total) > 0.5


async def convert_to_devanagari(text: str, llama_url: str) -> str:
    """Fallback: use Gemma 4 to convert Roman Hindi to Devanagari"""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                f"{llama_url}/v1/chat/completions",
                json={
                    "model": "gemma4",
                    "messages": [{"role": "user", "content":
                        f"Convert this Hindi text to Devanagari script. "
                        f"Output ONLY the Devanagari text, nothing else.\n\nInput: {text}"
                    }],
                    "stream": False, "max_tokens": 400, "temperature": 0.1,
                }
            )
            result = r.json()["choices"][0]["message"]["content"].strip()
            if is_devanagari(result):
                return result
    except Exception as e:
        logger.error(f"Devanagari conversion failed: {e}")
    return text


async def run_piper(text: str, lang: str, speed_override: float = None) -> bytes:
    voice = MODELS[lang]
    speed = speed_override if speed_override else voice["speed"]
    safe_text = text.replace('"', "'").replace('`', "'").replace('$', '').replace('\n', ' ')

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        output_path = f.name

    cmd = f'echo "{safe_text}" | {PIPER} -m {voice["model"]} -f {output_path} --length_scale {speed}'
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
    )

    if result.returncode != 0:
        logger.error(f"Piper error: {result.stderr}")
        if os.path.exists(output_path): os.unlink(output_path)
        return b""

    if not os.path.exists(output_path):
        return b""

    with open(output_path, "rb") as f:
        audio = f.read()
    os.unlink(output_path)
    return audio if len(audio) > 44 else b""


async def synthesize(
    text: str,
    lang: str = "hi",
    llama_url: str = "http://host.docker.internal:8080",
    speed: float = None
) -> bytes:
    """
    Convert text to speech using session language.
    lang: "hi" | "en" | "bn" | others
    Returns WAV bytes or empty bytes if not supported.
    Speed is read from runtime config if not passed explicitly.
    """
    if lang not in TTS_SUPPORTED:
        return b""

    clean = clean_text(text)
    if not clean or len(clean) < 3:
        return b""

    # Limit length (~30 seconds of speech)
    clean = clean[:450]

    # Read speed from runtime config (admin can change without restart)
    if speed is None:
        cfg = get_config()
        speed = cfg.get(f"tts_speed_{lang}", MODELS.get(lang, {}).get("speed", 1.0))

    logger.info(f"TTS: lang={lang} speed={speed}")

    if lang == "hi":
        if not is_devanagari(clean):
            logger.info("Hindi session but Roman text — converting to Devanagari")
            clean = await convert_to_devanagari(clean, llama_url)
        return await run_piper(clean, "hi", speed)

    elif lang == "en":
        return await run_piper(clean, "en", speed)

    return b""
