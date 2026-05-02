from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "nyay-vani"
    app_env: str = "development"
    debug: bool = True
    ollama_base_url: str = "http://ollama:11434"
    intake_model: str = "gemma3n:e2b"
    expert_model: str = "gemma3n:e4b"
    database_url: str = "sqlite:////app/nyay_vani.db"
    chroma_persist_dir: str = "/app/chroma_db"
    legal_collection: str = "legal_documents"
    medical_collection: str = "medical_documents"
    embedding_model: str = "all-MiniLM-L6-v2"
    whisper_model_size: str = "tiny"
    tts_voice_hindi: str = "hi-IN-SwaraNeural"
    tts_voice_english: str = "en-IN-NeerjaNeural"
    session_expiry_hours: int = 24
    admin_username: str = "admin"
    admin_password: str = "nyayvani2024"
    frontend_url: str = "http://localhost:5173"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
