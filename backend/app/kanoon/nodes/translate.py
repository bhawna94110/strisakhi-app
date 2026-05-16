"""
Translation Node — Bengali only
Translates user input Bengali → English for processing.
Hindi and English go through unchanged.
Output response translation not needed — Gemma 4 handles Bengali output natively.
"""
import httpx
from app.kanoon.state import KanoonState
from app.config import settings

TRANSLATE_SYSTEM = (
    "You are a translator. Translate the following Bengali text to English. "
    "Output ONLY the English translation — no explanation, no preamble. "
    "Preserve the meaning and emotional tone exactly."
)


async def translate_input_node(state: KanoonState) -> dict:
    """Only runs if language == 'bn'. Otherwise returns unchanged state."""
    if state.get("language") != "bn":
        return {"user_message_processed": state.get("user_message_raw", "")}

    message = state.get("user_message_raw", "")
    if not message.strip():
        return {"user_message_processed": message}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                f"{settings.ollama_base_url}/v1/chat/completions",
                json={
                    "model": "gemma4",
                    "messages": [
                        {"role": "system", "content": TRANSLATE_SYSTEM},
                        {"role": "user", "content": message},
                    ],
                    "stream": False,
                    "temperature": 0.0,
                    "max_tokens": 200,
                    "chat_template_kwargs": {"enable_thinking": False},
                }
            )
        translated = r.json()["choices"][0]["message"]["content"].strip()
        return {"user_message_processed": translated}
    except Exception as e:
        # Fallback: use original message
        return {"user_message_processed": message, "error": f"translation failed: {e}"}
