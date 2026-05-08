# StriSakhi — System Architecture

## What Is StriSakhi

StriSakhi ("Woman's Companion") is a voice-first AI assistant for rural Indian women. It provides legal rights guidance, health information, and government scheme discovery in Hindi, English, and Bengali. Designed to run fully offline on commodity hardware (tested on M2 MacBook Pro, 16GB RAM), deployed via Docker Compose.

The name replaced the original "Nyay Vani" (Justice Voice) during development. You will see `nyay_vani` in database filenames and older config keys — same system.

---

## High-Level Architecture

```
User Browser (localhost:5173)
    │
    │  React SPA (Vite, single App.jsx file ~1200 lines)
    │  - Language picker (Hindi / English / Bengali, locked per session)
    │  - Voice recording → WebM → WAV conversion (Web Audio API)
    │  - Streaming token display (SSE)
    │  - TTS 🔊 Listen button (Hindi/English only)
    │
    ▼
Docker: nyay-vani-frontend (port 5173)
    │
    │  HTTP/SSE to port 8000
    │
    ▼
Docker: nyay-vani-backend (FastAPI, port 8000)
    │
    ├── /api/legal/chat      → Legal Agent Pipeline
    ├── /api/medical/chat    → Medical Agent Pipeline
    ├── /api/scheme/chat     → Scheme Agent (reuses legal pipeline)
    ├── /api/voice/tts       → Piper TTS
    ├── /api/session/*       → Session management
    ├── /api/admin/settings  → Runtime config
    └── /api/health          → System health + model status
    │
    ├── ChromaDB (embedded, ./chroma_db/ volume)
    ├── SQLite (nyay_vani.db)
    └── Piper binary (/usr/local/piper, baked into Docker image)
    │
    │  HTTP to host.docker.internal:8080
    │
    ▼
Mac Native: llama-server (port 8080, Metal GPU)
    └── Model: Gemma 4 E2B Q4_K_M (3.2GB)
    └── mmproj: mmproj-gemma4-e2b Q8_0 (532MB) ← enables audio STT
```

---

## Why This Architecture (Key Decisions)

### llama.cpp on Mac Native (NOT in Docker)

The single most important architectural decision. llama.cpp runs outside Docker directly on the Mac, using Apple Metal GPU.

**Why not Ollama in Docker (original approach):**
- Docker networking: ~2-3ms per token overhead
- Ollama's thinking mode could not be disabled via Docker
- Result: 55+ second responses (unusable)
- Tested and abandoned on Day 1

**Why not Ollama on Mac:**
- Ollama does not expose `--chat-template-kwargs` for thinking mode control
- Thinking mode causes empty `content` field for 20-55 seconds

**llama.cpp result:** ~1 second responses on M2 Metal GPU (41 tokens/sec measured)

### Gemma 4 E2B — Why This Specific Model

- **Native audio STT**: Accepts `input_audio` block in OpenAI-compatible API — no Whisper needed
- **Single model for text + speech**: Reduces memory footprint vs running separate STT model
- **140+ languages**: Hindi, Bengali, Tamil, Telugu all work for transcription
- **4B params Q4_K_M**: 3.2GB fits in 16GB RAM alongside Docker
- **Thinking mode**: Has reasoning capability but MUST be disabled (see below)
- **Alternative considered**: Whisper (faster STT but separate model, no multilingual generation)

### Why Thinking Mode Must Be Disabled

Gemma 4 has Chain-of-Thought reasoning built in. When enabled:
- Model writes a `<think>...</think>` block before answering
- The API `content` field is EMPTY until thinking completes
- Thinking takes 20-55 seconds
- No streaming tokens visible to user during this time
- Users see blank screen with no feedback

**Fix**: `--chat-template-kwargs '{"enable_thinking":false}'` in llama-server flags.
Without this flag, the application appears broken.

### Why Piper TTS (not edge-tts, not Kokoro, not Parler)

Evaluated in order:
1. **edge-tts (SwaraNeural)**: Best Hindi quality, but requires internet — rejected for offline requirement
2. **Kokoro-ONNX**: Offline, 300MB, but `hf_alpha`/`hf_beta` Hindi voices have Western accent — rejected after listening test
3. **Indic Parler-TTS (AI4Bharat)**: Real Indian accent, controllable style, but 1.5GB model + `fairseq` dependency fails on Python 3.12 — rejected
4. **Piper**: 61MB model, runs as binary (no Python deps), genuine Indian accent (priyamvada), ~0.1-0.3s generation — SELECTED

**Piper pip package rejected**: `pip install piper-tts` pulls PyTorch (800MB) + CUDA (500MB) = 2GB+. Using standalone binary instead.

---

## Request Lifecycle

### Text Message

```
1.  User types → React Enter key
2.  POST /api/{sakhi}/chat { session_id, message, language: "hi" }
3.  legal.py: loads session from SQLite via session_manager.py
4.  legal.py: runs emergency keyword detection (emergency/detector.py)
5.  legal.py: saves user message to SQLite
6.  model_router.py: counts user turns → INTAKE (turns < 3) or EXPERT (turns >= 3)
7a. INTAKE: intake_agent.py → POST http://host.docker.internal:8080/v1/chat/completions (stream=true)
7b. EXPERT: legal_rag.py → ChromaDB query → legal_agent.py → POST to llama.cpp
8.  Each token: SSE event: data: {"type": "token", "token": "..."}
9.  React: appends token to message bubble in real time
10. Final: SSE data: {"type": "done", "full_response": "...", "citations": [...], "agent": "expert"}
11. legal.py: saves assistant response to SQLite
12. Frontend: shows 🔊 button (if sessionLang === "hi" || "en")
```

### Voice Message

```
1.  User presses 🎤 → MediaRecorder starts (WebM/Opus, 250ms chunks)
2.  User presses ⏹ → recording stops (max 25 seconds via timerRef)
3.  blobToWav(): Web Audio API decodes WebM → Float32 PCM → 16kHz mono WAV
4.  WAV bytes → base64 string
5.  POST localhost:8080/v1/chat/completions:
    content: [
      { type: "input_audio", input_audio: { data: base64, format: "wav" } },
      { type: "text", text: "Transcribe exactly..." }
    ]
6.  Gemma 4 returns transcript text
7.  Audio bubble shown in chat with <audio> player + transcript italic below
8.  transcript → sendMessage() → same as text flow above
```

**Critical**: Audio format MUST be "wav" — llama.cpp rejects webm/mp3 with HTTP 400.

### TTS

```
1.  User taps 🔊 Listen
2.  POST /api/voice/tts { text: "...", lang: "hi" }
3.  tts.py: clean_text() — strip emoji, markdown, citations, numbered lists
4.  tts.py: read tts_speed_hi from config_runtime.json
5.  If lang="hi": is_devanagari() check
    - If not Devanagari (Hinglish): POST to llama.cpp "Convert to Devanagari" (0.5s)
    - If Devanagari: use directly
6.  echo "text" | /usr/local/piper -m hi_IN-priyamvada-medium.onnx -f /tmp/out.wav --length_scale 1.2
7.  Return WAV bytes as audio/wav response
8.  Frontend: URL.createObjectURL(blob) → new Audio(url).play()
```

---

## Three Sakhis — Agent Pipelines

### Kanoon Sakhi (Legal) — Most Complete

```
API:    backend/app/api/legal.py
Agents: backend/app/agents/intake_agent.py → backend/app/agents/legal_agent.py
RAG:    backend/app/rag/legal_rag.py
Docs:   backend/rag_documents/legal/ (3 PDFs)
        - dv_act_2005.pdf (Protection of Women from Domestic Violence Act)
        - hindu_succession_act.pdf
        - posh_act_2013.pdf (Prevention of Sexual Harassment)
Status: FULLY WORKING — RAG ingested, 293 chunks in ChromaDB
```

### Sehat Sakhi (Medical) — Partially Working

```
API:    backend/app/api/medical.py
Agents: backend/app/agents/intake_agent.py → backend/app/agents/medical_agent.py
RAG:    backend/app/rag/medical_rag.py
Docs:   backend/rag_documents/medical/ (EMPTY)
Status: INTAKE WORKS, EXPERT gives generic advice (no RAG documents ingested)
Known:  language passthrough in medical.py may not be fully implemented
```

### Yojana Sakhi (Scheme) — Hardcoded Knowledge

```
API:    backend/app/api/scheme.py
Agent:  backend/app/agents/scheme_agent.py
RAG:    NONE — hardcoded dictionary of 18 government schemes
DB:     Sessions stored as tab_type="legal" (scheme maps to legal in DB)
Status: WORKING but limited to hardcoded schemes
Schemes: PM Awas Yojana, Ayushman Bharat, Janani Suraksha, MGNREGS, etc.
```

---

## Routing Logic (model_router.py)

```python
INTAKE_MAX_TURNS = 3  # hardcoded constant

if user_turn_count >= INTAKE_MAX_TURNS:
    force → EXPERT phase

elif confidence_score >= threshold:
    switch → EXPERT phase early

else:
    stay → INTAKE phase
```

Confidence score is calculated from metadata completeness:
- Has location_state? +points
- Has issue_type? +points
- Has urgency? +points
- Has religion? +points (relevant for succession law)

INTAKE_MAX_TURNS is NOT currently wired to admin dashboard slider. This is a pending item.

---

## Language System (Session-Locked)

Each session has ONE language locked at start. User picks from:
- **हिंदी (Hindi)**: System prompt forces Devanagari. TTS: Piper priyamvada. STT: hints Hindi.
- **English**: System prompt forces English. TTS: Piper Amy.
- **বাংলা (Bengali)**: System prompt forces Bengali. TTS: none (no Bengali Piper voice exists).

Language is stored in React state only — NOT in SQLite. Session resume defaults to Hindi. This is a known limitation.

Coming soon (shown greyed out in UI): Tamil, Telugu, Marathi, Gujarati, Punjabi.

---

## Data Storage

### SQLite: backend/nyay_vani.db

```
sessions:
  id (UUID), tab_type (legal/medical), agent_phase (intake/expert),
  confidence_score (float), emergency_flagged (bool),
  metadata (JSON: location_state, issue_type, urgency, religion),
  created_at, updated_at

messages:
  id, session_id (FK), role (user/assistant), content (text),
  input_type (text/audio), citations (JSON array),
  agent_used (intake/expert), response_ms (int), created_at
```

### ChromaDB: backend/chroma_db/

- Embedded (no separate process)
- Volume mounted: persists across Docker restarts
- Collections: `legal_documents`, `medical_documents`
- Embeddings: ChromaDB DefaultEmbeddingFunction (downloads ~80MB model on first use)
- **Why DefaultEmbeddingFunction**: Avoids `sentence-transformers` which pulls PyTorch (2GB). Same underlying model (all-MiniLM-L6-v2), different entry point with no heavy deps.

### config_runtime.json: backend/config_runtime.json

```json
{
  "tts_speed_hi": 1.2,
  "tts_speed_en": 1.0,
  "intake_max_turns": 3,
  "temperature": 0.3,
  "expert_max_tokens": 600
}
```

Read on every TTS call. Write via `POST /api/admin/settings`. No restart required.

---

## Docker Services

### nyay-vani-backend

- Base image: `python:3.11-slim`
- Piper binary installed at build time (aarch64 for Apple Silicon)
- Live reload: `./backend` mounted to `/app` — code changes apply without rebuild
- Models volume: `/Users/bhawna/strisakhi-models` → `/app/strisakhi-models`
- Reaches llama.cpp via `host.docker.internal:8080` (extra_hosts config)
- Port: 8000

### nyay-vani-frontend

- Base image: Node (Vite dev server)
- Live reload: `./frontend` mounted
- Port: 5173

### nyay-vani-ollama

- Role: model management only (pull, list models)
- NOT used for inference (all inference goes to Mac native llama-server)
- Kept for potential future use / model management convenience

---

## Known Bottlenecks and Issues

### Critical (blocks features)
1. **Medical RAG empty**: No PDFs in `rag_documents/medical/`. Medical expert gives generic advice.
2. **Scheme RAG empty**: `scheme_agent.py` uses hardcoded list only. Misses state-specific schemes.
3. **INTAKE_MAX_TURNS not wired**: Admin slider has no effect on routing.

### Performance
4. **TTS subprocess overhead**: Piper runs via shell subprocess — ~100-300ms per call. For Hinglish, adds ~500ms LLM conversion call.
5. **ChromaDB cold start**: First query downloads embedding model (~80MB). Takes 30-60 seconds on first run.
6. **Audio STT base64 overhead**: Large recordings create very large HTTP request bodies.

### Architecture Debt
7. **Session language not persisted**: SQLite `sessions` table has no language column. Resume always defaults to Hindi.
8. **medical.py language passthrough**: `language` field may not be fully passed to medical agents.
9. **Scheme uses legal tab_type**: Cannot distinguish scheme vs legal sessions in analytics.
10. **Admin PIN hardcoded**: PIN "1234" in both frontend JS and backend Python. Not suitable for production.
11. **No HTTPS**: All communication is HTTP. Fine for local demo, not for deployment.

---

## Daily Startup

```bash
# Terminal 1 — llama.cpp (start first)
llama-server \
  -m ~/.ollama/models/blobs/sha256-e6d47b7c6316612da747c4e471d10f5f1b87c8bf6051332d80f4810d69196c64 \
  --mmproj ~/strisakhi-models/mmproj/mmproj-gemma4-e2b.gguf \
  --port 8080 \
  --chat-template-kwargs '{"enable_thinking":false}' \
  -ngl 99 -c 4096 --host 0.0.0.0

# Terminal 2 — Docker
cd ~/Desktop/nyay-vani-backend
docker compose up

# URLs
# App:      http://localhost:5173
# Admin:    http://localhost:5173/admin.html   PIN: 1234
# API docs: http://localhost:8000/docs
# Health:   http://localhost:8000/api/health
```
