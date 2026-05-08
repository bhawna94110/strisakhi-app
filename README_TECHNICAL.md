# StriSakhi — Technical README

> Voice-first AI assistant for rural Indian women. Legal rights, health guidance, and government schemes in Hindi, English, and Bengali. Fully offline. No cloud API keys.

---

## Architecture

```
Browser (React + Vite)
    ↓ HTTP/SSE
FastAPI Backend (Docker, port 8000)
    ↓ HTTP
llama-server (Mac native, Metal GPU, port 8080)
    └── Gemma 4 E2B Q4_K_M (3.2GB) + mmproj (532MB)

Offline TTS: Piper binary + hi_IN-priyamvada + en_US-amy
Storage: SQLite + ChromaDB (embedded)
```

## Prerequisites

- macOS with Apple Silicon (M1/M2/M3)
- Docker Desktop
- 16GB RAM minimum (8GB available for LLM)
- llama.cpp installed (`brew install llama.cpp` or build from source)
- ~5GB free disk space

## Setup

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/strisakhi
cd strisakhi
```

### 2. Download models

```bash
# Gemma 4 E2B via Ollama
ollama pull batiai/gemma4-e2b:q4

# Find the model hash
ls ~/.ollama/models/blobs/ | grep -v manifest

# Download mmproj
mkdir -p ~/strisakhi-models/mmproj ~/strisakhi-models/piper
# mmproj file needs to be obtained from HuggingFace (see ARCHITECTURE.md)
```

### 3. Download Piper voices

```bash
# Hindi (female)
curl -L -o ~/strisakhi-models/piper/hi_IN-priyamvada-medium.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/priyamvada/medium/hi_IN-priyamvada-medium.onnx"
curl -L -o ~/strisakhi-models/piper/hi_IN-priyamvada-medium.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/priyamvada/medium/hi_IN-priyamvada-medium.onnx.json"

# English (female)
curl -L -o ~/strisakhi-models/piper/en_US-amy-medium.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx"
curl -L -o ~/strisakhi-models/piper/en_US-amy-medium.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json"
```

### 4. Update docker-compose.yml

Update the volume mount path for Piper models:
```yaml
volumes:
  - /YOUR_HOME/strisakhi-models:/app/strisakhi-models
```

### 5. Start llama-server

```bash
llama-server \
  -m ~/.ollama/models/blobs/SHA256_HASH_OF_MODEL \
  --mmproj ~/strisakhi-models/mmproj/mmproj-gemma4-e2b.gguf \
  --port 8080 \
  --chat-template-kwargs '{"enable_thinking":false}' \
  -ngl 99 -c 4096 --host 0.0.0.0
```

⚠️ `--chat-template-kwargs '{"enable_thinking":false}'` is **critical**. Without it, responses take 55+ seconds.

### 6. Start Docker

```bash
docker compose up
```

### 7. Ingest legal documents

```bash
docker exec nyay-vani-backend python scripts/ingest_legal_docs.py
```

### 8. Access the app

- App: http://localhost:5173
- Admin: http://localhost:5173/admin.html (PIN: 1234)
- API docs: http://localhost:8000/docs

---

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── agents/          # intake_agent, legal_agent, medical_agent, scheme_agent, model_router
│   │   ├── api/             # FastAPI routers: legal, medical, scheme, session, voice, admin
│   │   ├── database/        # SQLAlchemy models, connection, CRUD
│   │   ├── rag/             # ChromaDB retrieval, embedder, legal_rag, medical_rag
│   │   ├── session/         # session_manager.py
│   │   ├── voice/           # tts.py, stt.py
│   │   ├── emergency/       # detector.py
│   │   ├── utils/           # language_detect, prompt_builder
│   │   ├── main.py          # FastAPI app, all routers registered
│   │   ├── config.py        # env vars
│   │   └── runtime_config.py # live settings from config_runtime.json
│   ├── scripts/
│   │   ├── ingest_legal_docs.py
│   │   └── ingest_medical_docs.py
│   ├── rag_documents/legal/ # PDFs: DV Act, Hindu Succession Act, POSH Act
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/App.jsx          # entire React app (single file ~1200 lines)
│   ├── public/admin.html    # standalone admin dashboard
│   └── Dockerfile
├── docker-compose.yml
└── docs/                    # this documentation
```

---

## API Reference

### Chat

```
POST /api/legal/chat
POST /api/medical/chat
POST /api/scheme/chat

Body: {
  "session_id": "uuid",
  "message": "text",
  "language": "hi" | "en" | "bn"
}

Response: SSE stream
  data: {"type": "token", "token": "..."}
  data: {"type": "done", "full_response": "...", "citations": [...], "agent": "intake|expert"}
  data: {"type": "phase_change", "from": "intake", "to": "expert"}
```

### Session

```
POST /api/session/new      Body: {"tab_type": "legal"|"medical"|"scheme"}
GET  /api/session/{id}     Returns session + message history
DELETE /api/session/{id}   Delete session
```

### Voice

```
POST /api/voice/tts
Body: {"text": "...", "lang": "hi"|"en"}
Response: audio/wav binary (or 204 if language not supported)

GET /api/voice/languages   Returns supported TTS languages
```

### Admin

```
GET  /api/admin/settings          Returns current runtime config
POST /api/admin/settings          Body: {"pin": "1234", "tts_speed_hi": 1.2, ...}
GET  /api/health                  System health, model status, ChromaDB stats
```

---

## Known Limitations

- Medical RAG empty — needs PDFs added to `rag_documents/medical/`
- Session language not persisted — resume defaults to Hindi
- Admin settings (temperature, max_tokens) saved but not wired to agents
- Single user at a time — llama.cpp processes one request sequentially
- Runs only on Mac with Apple Silicon (Metal GPU dependency)

---

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| LLM + STT | Gemma 4 E2B via llama.cpp | Native audio support, multilingual, fits in 16GB |
| TTS | Piper binary | Offline, 61MB, genuine Indian accent |
| RAG | ChromaDB | Embedded, no separate service |
| Backend | FastAPI + Python 3.11 | Async SSE streaming, simple setup |
| Frontend | React + Vite | Single file app, no build complexity |
| Database | SQLite | Embedded, file-based, simple for demo |
| Container | Docker Compose | Reproducible environment |
