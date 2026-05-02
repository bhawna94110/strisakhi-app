"""
Intake Agent — Uses Gemma 4 E2B (lightweight)
Conversationally gathers case information from user.
Builds metadata JSON turn by turn.
"""
import json
import re
import ollama
from app.config import settings
from app.utils.prompt_builder import build_intake_prompt
from app.agents.model_router import calculate_confidence
from typing import AsyncGenerator

client = ollama.AsyncClient(host=settings.ollama_base_url)

async def run_intake_stream(
    conversation_history: list,
    metadata: dict,
    tab_type: str,
    language: str = "hi"
) -> AsyncGenerator[dict, None]:
    """
    Stream intake agent response token by token.
    Also yields metadata_update events when new info extracted.
    """
    prompt = build_intake_prompt(
        conversation_history, metadata, tab_type, language
    )

    full_response = ""

    try:
        stream = await client.chat(
            model=settings.intake_model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            options={"temperature": 0.3, "num_predict": 256}
        )

        async for chunk in stream:
            token = chunk.message.content or ""
            full_response += token
            yield {"type": "token", "token": token, "agent": "intake"}

    except Exception as e:
        yield {"type": "error", "message": str(e)}
        return

    # Check for special signals in response
    if "EMERGENCY_DETECTED" in full_response:
        yield {"type": "emergency", "flag": True}
        return

    if "READY_FOR_EXPERT" in full_response:
        yield {"type": "phase_change", "from": "intake", "to": "expert"}
        return

    # Extract any new metadata from the full response
    new_metadata = extract_metadata_from_response(full_response, metadata, tab_type)
    if new_metadata != metadata:
        new_confidence = calculate_confidence(new_metadata, tab_type)
        yield {
            "type": "metadata_update",
            "metadata": new_metadata,
            "confidence_score": new_confidence
        }

    yield {"type": "done", "full_response": full_response, "agent": "intake"}

def extract_metadata_from_response(response: str, existing: dict, tab_type: str) -> dict:
    """
    Simple heuristic extraction — in production this would use
    a structured output from the model.
    For now extracts common Indian states, religions, issues.
    """
    updated = existing.copy()
    text = response.lower()

    # Extract Indian states
    states = [
        "uttar pradesh", "up", "maharashtra", "rajasthan", "bihar",
        "madhya pradesh", "mp", "west bengal", "karnataka", "gujarat",
        "andhra pradesh", "tamil nadu", "telangana", "kerala", "punjab",
        "haryana", "odisha", "jharkhand", "assam", "delhi"
    ]
    for state in states:
        if state in text and not updated.get("location_state"):
            updated["location_state"] = state.title()
            break

    # Extract religion
    religions = ["hindu", "muslim", "christian", "sikh", "buddhist", "jain"]
    for religion in religions:
        if religion in text and not updated.get("religion"):
            updated["religion"] = religion
            break

    return updated
