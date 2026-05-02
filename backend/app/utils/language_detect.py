from langdetect import detect, DetectorFactory
DetectorFactory.seed = 0  # consistent results

SUPPORTED_LANGUAGES = {
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "bn": "Bengali",
    "mr": "Marathi",
    "gu": "Gujarati",
    "pa": "Punjabi",
    "kn": "Kannada",
    "ml": "Malayalam",
    "en": "English",
}

def detect_language(text: str) -> str:
    """Detect language code from text. Returns 'hi' as default."""
    try:
        lang = detect(text)
        return lang if lang in SUPPORTED_LANGUAGES else "hi"
    except Exception:
        return "hi"

def get_language_name(code: str) -> str:
    return SUPPORTED_LANGUAGES.get(code, "Hindi")
