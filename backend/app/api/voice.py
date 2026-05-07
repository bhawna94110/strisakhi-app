from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from app.voice.tts import synthesize
from app.config import settings

router = APIRouter()

class TTSRequest(BaseModel):
    text: str

@router.post("/tts")
async def text_to_speech(req: TTSRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(400, "Text is required")

    audio_bytes, lang = await synthesize(
        req.text.strip(),
        llama_url=settings.ollama_base_url
    )

    if not audio_bytes:
        return Response(status_code=204)

    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers={"X-Language": lang}
    )

@router.get("/languages")
async def tts_languages():
    return {
        "tts_supported": ["hi", "en"],
        "text_only": ["bn", "ta", "te", "kn", "ml", "gu", "pa", "mr", "or"],
        "description": {
            "hi": "Hindi — Priyamvada voice (female, offline)",
            "en": "English — Amy voice (female, offline)",
        },
        "hinglish": "Auto-detected and converted to Hindi via Gemma 4"
    }
