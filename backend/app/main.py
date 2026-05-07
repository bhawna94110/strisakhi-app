from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.database.connection import init_db
from app.config import settings
import chromadb
import psutil
import time
import httpx
import os


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting StriSakhi...")
    init_db()
    print("Database initialized")
    yield
    print("Shutting down StriSakhi...")

app = FastAPI(
    title="StriSakhi API",
    description="Voice-first legal, health and scheme AI assistant for Indian women",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
from app.api import legal, medical, session, leads, voice, scheme

app.include_router(legal.router,   prefix="/api/legal",   tags=["Legal"])
app.include_router(medical.router, prefix="/api/medical", tags=["Medical"])
app.include_router(session.router, prefix="/api/session", tags=["Session"])
app.include_router(leads.router,   prefix="/api/leads",   tags=["Leads"])
app.include_router(voice.router,   prefix="/api/voice",   tags=["Voice"])
app.include_router(scheme.router,  prefix="/api/scheme",  tags=["Scheme"])


@app.get("/")
async def root():
    return {
        "app": "StriSakhi",
        "tagline": "Three companions — always by your side",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/api/health"
    }


@app.get("/api/health")
async def health_check():
    health = {
        "status": "ok",
        "app": "StriSakhi",
        "timestamp": time.time(),
        "system": {},
        "services": {},
        "models": {},
        "tts": {}
    }

    # ── System metrics ──────────────────────────────────────────
    try:
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.5)
        disk = psutil.disk_usage('/')
        health["system"] = {
            "cpu_percent": cpu,
            "ram_total_gb": round(mem.total / (1024**3), 2),
            "ram_used_gb": round(mem.used / (1024**3), 2),
            "ram_percent": mem.percent,
            "ram_available_gb": round(mem.available / (1024**3), 2),
            "disk_used_gb": round(disk.used / (1024**3), 2),
            "disk_total_gb": round(disk.total / (1024**3), 2),
        }
    except Exception as e:
        health["system"] = {"error": str(e)}

    # ── llama.cpp server (our main LLM + STT) ──────────────────
    try:
        r = httpx.get(f"{settings.ollama_base_url}/health", timeout=3.0)
        llamacpp_ok = r.status_code == 200

        # Get model info from llama.cpp props endpoint
        try:
            props = httpx.get(f"{settings.ollama_base_url}/props", timeout=3.0).json()
            model_name = props.get("default_generation_settings", {}).get("model", "unknown")
        except:
            model_name = "gemma4:e2b"

        health["services"]["llamacpp"] = {
            "status": "connected" if llamacpp_ok else "error",
            "url": settings.ollama_base_url,
            "model": model_name,
            "thinking_disabled": True,
            "metal_gpu": True,
            "audio_support": True,
        }
        health["models"]["llm"] = {
            "name": "Gemma 4 E2B (Q4_K_M)",
            "size_gb": 3.2,
            "status": "loaded" if llamacpp_ok else "not loaded",
            "capabilities": ["text", "audio_stt", "hindi", "english", "140+ languages"],
            "thinking": "disabled",
            "speed": "~1s response (Metal GPU)"
        }
        health["models"]["mmproj"] = {
            "name": "mmproj-gemma4-e2b (Q8_0)",
            "size_mb": 557,
            "status": "loaded" if llamacpp_ok else "not loaded",
            "purpose": "Audio/Visual understanding"
        }
    except Exception as e:
        health["services"]["llamacpp"] = {"status": "error", "detail": str(e)}
        health["status"] = "degraded"

    # ── ChromaDB ────────────────────────────────────────────────
    try:
        chroma = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        collections = chroma.list_collections()
        col_names = [c.name for c in collections]
        col_counts = {}
        for c in collections:
            try:
                col_counts[c.name] = chroma.get_collection(c.name).count()
            except:
                col_counts[c.name] = 0

        health["services"]["chromadb"] = {
            "status": "connected",
            "collections": col_names,
            "document_counts": col_counts,
            "legal_ready": settings.legal_collection in col_names,
            "medical_ready": settings.medical_collection in col_names,
        }
    except Exception as e:
        health["services"]["chromadb"] = {"status": "error", "detail": str(e)}

    # ── SQLite Database ─────────────────────────────────────────
    try:
        from app.database.connection import SessionLocal
        import sqlalchemy
        db = SessionLocal()
        db.execute(sqlalchemy.text("SELECT 1"))
        # Count sessions and messages
        sessions = db.execute(sqlalchemy.text("SELECT COUNT(*) FROM sessions")).scalar()
        messages = db.execute(sqlalchemy.text("SELECT COUNT(*) FROM messages")).scalar()
        db.close()
        health["services"]["database"] = {
            "status": "connected",
            "type": "sqlite",
            "total_sessions": sessions,
            "total_messages": messages,
        }
    except Exception as e:
        health["services"]["database"] = {"status": "error", "detail": str(e)}

    # ── Piper TTS ───────────────────────────────────────────────
    PIPER_MODELS = {
        "hindi": "/app/strisakhi-models/piper/hi_IN-priyamvada-medium.onnx",
        "english": "/app/strisakhi-models/piper/en_US-amy-medium.onnx",
    }
    piper_binary = "/usr/local/piper"
    health["tts"] = {
        "engine": "Piper TTS (offline binary)",
        "binary": "found" if os.path.exists(piper_binary) else "NOT FOUND",
        "voices": {}
    }
    for lang, path in PIPER_MODELS.items():
        exists = os.path.exists(path)
        size_mb = round(os.path.getsize(path) / (1024**2)) if exists else 0
        health["tts"]["voices"][lang] = {
            "status": "ready" if exists else "missing",
            "model": os.path.basename(path),
            "size_mb": size_mb
        }

    # ── Overall status ──────────────────────────────────────────
    if health["services"].get("llamacpp", {}).get("status") == "error":
        health["status"] = "degraded"

    return health
