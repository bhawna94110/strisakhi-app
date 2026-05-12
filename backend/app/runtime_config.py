"""
Runtime config — backend/app/runtime_config.py
Simple JSON file that admin can update without restart.
"""
import json
import os
from pathlib import Path

CONFIG_FILE = Path("/app/config_runtime.json")

DEFAULTS = {
    "tts_speed_hi": 1.2,
    "tts_speed_en": 1.0,
    "intake_max_turns": 10,
    "intake_min_score": 60,
    "temperature": 0.2,
    "expert_max_tokens": 700,
}

def get_config() -> dict:
    try:
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text())
            return {**DEFAULTS, **data}
    except Exception:
        pass
    return DEFAULTS.copy()

def save_config(updates: dict) -> dict:
    current = get_config()
    current.update({k: v for k, v in updates.items() if k in DEFAULTS})
    CONFIG_FILE.write_text(json.dumps(current, indent=2))
    return current
