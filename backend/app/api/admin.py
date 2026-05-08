"""
Admin API — backend/app/api/admin.py
Settings endpoints for runtime config.
Simple PIN auth (same as frontend).
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.runtime_config import get_config, save_config

router = APIRouter()

ADMIN_PIN = "1234"

class SettingsRequest(BaseModel):
    pin: str
    tts_speed_hi: Optional[float] = None
    tts_speed_en: Optional[float] = None
    intake_max_turns: Optional[int] = None
    temperature: Optional[float] = None
    expert_max_tokens: Optional[int] = None

@router.get("/settings")
async def get_settings():
    return get_config()

@router.post("/settings")
async def save_settings(req: SettingsRequest):
    if req.pin != ADMIN_PIN:
        raise HTTPException(403, "Wrong PIN")
    updates = {k: v for k, v in req.dict().items()
               if k != "pin" and v is not None}
    return save_config(updates)
