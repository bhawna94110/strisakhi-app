"""
StriSakhi Voice API — backend/app/api/voice.py
TTS endpoint — language passed explicitly from frontend session
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
from app.voice.tts import synthesize
from app.config import settings

router = APIRouter()

class TTSRequest(BaseModel):
    text: str
    lang: str = "hi"          # session language
    speed: Optional[float] = None  # optional override from admin settings

@router.post("/tts")
async def text_to_speech(req: TTSRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(400, "Text is required")
    if req.lang not in ("hi", "en", "bn", "ta", "te", "ml", "gu", "pa", "mr"):
        raise HTTPException(400, "Invalid language code")

    audio = await synthesize(
        text=req.text.strip(),
        lang=req.lang,
        llama_url=settings.ollama_base_url,
        speed=req.speed
    )

    if not audio:
        return Response(status_code=204)

    return Response(
        content=audio,
        media_type="audio/wav",
        headers={"X-Language": req.lang}
    )

@router.get("/languages")
async def tts_languages():
    return {
        "supported": [
            {"code": "hi", "name": "हिंदी", "voice": "Priyamvada (female)", "tts": True},
            {"code": "en", "name": "English", "voice": "Amy (female)", "tts": True},
            {"code": "bn", "name": "বাংলা", "voice": None, "tts": False},
        ],
        "coming_soon": ["ta", "te", "ml", "gu", "pa", "mr"]
    }
