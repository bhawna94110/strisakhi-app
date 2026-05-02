from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.database.connection import init_db
from app.config import settings
import ollama as ollama_client
import chromadb
import psutil
import time

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting Nyay Vani...")
    init_db()
    print("Database initialized")
    yield
    print("Shutting down Nyay Vani...")

app = FastAPI(
    title="Nyay Vani API",
    description="Voice-first legal and medical AI assistant for rural Indian women",
    version="1.0.0",
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

# Import and register routers
from app.api import legal, medical, session, leads, voice
app.include_router(legal.router,   prefix="/api/legal",   tags=["Legal"])
app.include_router(medical.router, prefix="/api/medical", tags=["Medical"])
app.include_router(session.router, prefix="/api/session", tags=["Session"])
app.include_router(leads.router,   prefix="/api/leads",   tags=["Leads"])
app.include_router(voice.router,   prefix="/api/voice",   tags=["Voice"])

@app.get("/")
async def root():
    return {
        "app": "Nyay Vani",
        "tagline": "Justice Voice — AI legal & medical aid for rural Indian women",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health"
    }

@app.get("/api/health")
async def health_check():
    health = {
        "status": "ok",
        "app": "Nyay Vani",
        "timestamp": time.time(),
        "system": {},
        "services": {}
    }

    # System metrics (compute consumption display)
    try:
        mem = psutil.virtual_memory()
        health["system"] = {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "ram_total_gb": round(mem.total / (1024**3), 2),
            "ram_used_gb": round(mem.used / (1024**3), 2),
            "ram_percent": mem.percent,
        }
    except Exception as e:
        health["system"] = {"error": str(e)}


    # Check Ollama
    try:
        import httpx
        response = httpx.get(
            f"{settings.ollama_base_url}/api/tags",
            timeout=5.0
        )
        data = response.json()
        available = [m.get("name", "") for m in data.get("models", [])]
        health["services"]["ollama"] = {
            "status": "connected",
            "available_models": available,
            "intake_model": settings.intake_model,
            "expert_model": settings.expert_model,
            "intake_ready": any(settings.intake_model in m for m in available),
            "expert_ready": any(settings.expert_model in m for m in available),
        }
    except Exception as e:
        health["services"]["ollama"] = {"status": "error", "detail": str(e)}
        health["status"] = "degraded"

    # ChromaDB check
    try:
        chroma = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        collections = [c.name for c in chroma.list_collections()]
        health["services"]["chromadb"] = {
            "status": "connected",
            "collections": collections,
            "legal_ready": settings.legal_collection in collections,
            "medical_ready": settings.medical_collection in collections,
        }
    except Exception as e:
        health["services"]["chromadb"] = {"status": "error", "detail": str(e)}

    # Database check
    try:
        from app.database.connection import SessionLocal
        db = SessionLocal()
        db.execute(__import__('sqlalchemy').text("SELECT 1"))
        db.close()
        health["services"]["database"] = {"status": "connected", "type": "sqlite"}
    except Exception as e:
        health["services"]["database"] = {"status": "error", "detail": str(e)}

    return health
