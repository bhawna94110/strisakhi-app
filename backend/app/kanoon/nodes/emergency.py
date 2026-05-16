"""
Emergency Check Node
LLM: YES/NO, temp=0, max_tokens=5
Skipped entirely if emergency_enabled=False (admin toggle)
"""
import httpx
from app.kanoon.state import KanoonState
from app.kanoon.prompts import LANG_INSTRUCTION
from app.config import settings

EMERGENCY_SYSTEM = (
    "You are a safety classifier for a women's crisis helpline in India. "
    "Determine if this message describes IMMEDIATE physical danger happening RIGHT NOW.\n\n"
    "Mark YES only if: violence actively happening at this moment, "
    "weapon present right now, person cannot escape right now, bleeding/injured right now.\n\n"
    "Mark NO if: describing past violence, asking for legal advice, "
    "general distress, 'pati mujhe maarta hai' (habit/ongoing, not right now).\n\n"
    "YES examples: 'abhi maar raha hai', 'help me he is hitting me now', 'khoon aa raha hai'\n"
    "NO examples: 'pati mujhe maarta hai', 'mujhe madad chahiye', 'mera pati mujhe marta hai'\n\n"
    "Reply with ONLY one word: YES or NO"
)


async def emergency_check_node(state: KanoonState) -> dict:
    """
    Check for immediate danger.
    Returns state updates only — does not stream.
    Streaming happens in legal.py based on emergency_detected flag.
    """
    if not state.get("emergency_enabled", True):
        return {"emergency_detected": False}

    message = state.get("user_message_processed", "")

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(
                f"{settings.ollama_base_url}/v1/chat/completions",
                json={
                    "model": "gemma4",
                    "messages": [
                        {"role": "system", "content": EMERGENCY_SYSTEM},
                        {"role": "user", "content": f"Message: {message}"},
                    ],
                    "stream": False,
                    "temperature": 0.0,
                    "max_tokens": 5,
                    "chat_template_kwargs": {"enable_thinking": False},
                }
            )
        raw = r.json()["choices"][0]["message"]["content"].strip().upper()
        is_emergency = raw.startswith("YES")
        return {"emergency_detected": is_emergency}

    except Exception as e:
        # Fail safe — never crash on emergency check failure
        return {"emergency_detected": False, "error": f"emergency_check failed: {e}"}
