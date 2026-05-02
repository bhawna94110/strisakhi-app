import io
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
from app.voice.stt import transcribe_audio
from app.voice.tts import synthesize_speech

router = APIRouter()

class TTSRequest(BaseModel):
    text: str
    language: Optional[str] = "hi"
    voice: Optional[str] = None  # override voice if needed

@router.post("/transcribe")
async def transcribe(
    audio_file: UploadFile = File(...),
    language: Optional[str] = Form(None)
):
    """
    Convert uploaded audio to text using Whisper tiny.
    Accepts: webm, wav, mp3, ogg, m4a
    Returns: text + detected language + confidence
    """
    allowed = ["audio/webm", "audio/wav", "audio/mpeg",
               "audio/mp3", "audio/ogg", "audio/m4a", "audio/mp4",
               "video/webm", "application/octet-stream"]

    if audio_file.content_type not in allowed:
        raise HTTPException(
            400,
            f"Unsupported audio format: {audio_file.content_type}. Use webm, wav, mp3, ogg"
        )

    audio_bytes = await audio_file.read()
    if len(audio_bytes) < 100:
        raise HTTPException(400, "Audio file is too small or empty")

    result = await transcribe_audio(audio_bytes, language)

    if not result.get("text"):
        raise HTTPException(422, "Could not transcribe audio. Please speak clearly and try again.")

    return result

@router.post("/synthesize")
async def synthesize(req: TTSRequest):
    """
    Convert text to speech using edge-tts.
    Returns MP3 audio binary.
    Voice: hi-IN-SwaraNeural (Hindi female, warm, natural)
    """
    if not req.text or not req.text.strip():
        raise HTTPException(400, "Text cannot be empty")

    if len(req.text) > 3000:
        raise HTTPException(400, "Text too long. Maximum 3000 characters.")

    audio_bytes = await synthesize_speech(req.text, req.language or "hi")

    if not audio_bytes:
        raise HTTPException(500, "Failed to generate audio")

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": "inline; filename=response.mp3",
            "X-Language": req.language or "hi",
        }
    )

@router.get("/voices")
async def list_voices():
    """List all available TTS voices"""
    return {
        "voices": [
            {"code": "hi", "language": "Hindi", "voice": "hi-IN-SwaraNeural", "gender": "Female"},
            {"code": "en", "language": "English (Indian)", "voice": "en-IN-NeerjaNeural", "gender": "Female"},
            {"code": "ta", "language": "Tamil", "voice": "ta-IN-PallaviNeural", "gender": "Female"},
            {"code": "te", "language": "Telugu", "voice": "te-IN-ShrutiNeural", "gender": "Female"},
            {"code": "mr", "language": "Marathi", "voice": "mr-IN-AarohiNeural", "gender": "Female"},
            {"code": "bn", "language": "Bengali", "voice": "bn-IN-TanishaaNeural", "gender": "Female"},
            {"code": "gu", "language": "Gujarati", "voice": "gu-IN-DhwaniNeural", "gender": "Female"},
            {"code": "kn", "language": "Kannada", "voice": "kn-IN-SapnaNeural", "gender": "Female"},
            {"code": "ml", "language": "Malayalam", "voice": "ml-IN-SobhanaNeural", "gender": "Female"},
        ]
    }

@router.get("/test")
async def voice_test():
    return {"status": "Voice router working", "endpoints": ["/transcribe", "/synthesize", "/voices"]}
