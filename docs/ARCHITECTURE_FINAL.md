# StriSakhi — Final Architecture Document
## Version 2.0 | Last Updated: May 2026

---

## Overview

StriSakhi ("Woman's Companion") is a voice-first AI assistant for rural Indian women providing legal rights guidance, health information, and government scheme discovery in Hindi, English, and Bengali. Fully offline after setup. Runs on commodity hardware (tested: M2 MacBook Pro 16GB RAM).

**Three agents:**
- ⚖️ **Kanoon Sakhi** — Legal rights (DV Act, Property, POSH, Maintenance)
- 🌿 **Sehat Sakhi** — Health guidance (pregnancy, child health, mental health)
- 📜 **Yojana Sakhi** — Government schemes (PM Awas, Ayushman, MGNREGS etc.)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│  User Browser (http://localhost:5173)                    │
│  React SPA (single App.jsx ~1200 lines)                 │
│  - Language picker (hi/en/bn) — locked per session     │
│  - Voice recording → WebM → WAV (Web Audio API)        │
│  - SSE streaming token display                          │
│  - TTS 🔊 button (hi/en only)                          │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP / SSE (port 5173→8000)
┌──────────────────────▼──────────────────────────────────┐
│  Docker: nyay-vani-frontend (Vite dev server, port 5173) │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  Docker: nyay-vani-backend (FastAPI, port 8000)          │
│                                                          │
│  /api/legal/chat    → Kanoon Sakhi pipeline             │
│  /api/medical/chat  → Sehat Sakhi pipeline              │
│  /api/scheme/chat   → Yojana Sakhi pipeline             │
│  /api/voice/tts     → Piper TTS                         │
│  /api/session/*     → Session CRUD                      │
│  /api/admin/*       → Settings + live logs              │
│  /api/health        → System health check               │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   SQLite      │  │  ChromaDB    │  │  Piper TTS   │  │
│  │  nyay_vani.db│  │  (embedded)  │  │  (binary)    │  │
│  │  sessions    │  │  293 legal   │  │  hi: priya   │  │
│  │  messages    │  │  chunks      │  │  en: amy     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP to host.docker.internal:8080
┌──────────────────────▼──────────────────────────────────┐
│  Mac Native: llama-server (port 8080, Metal GPU)         │
│  Model:   Gemma 4 E2B Q4_K_M (3.2GB, ~41 tok/sec)      │
│  mmproj:  mmproj-gemma4-e2b Q8_0 (532MB, audio STT)    │
│  CRITICAL FLAG: --chat-template-kwargs                   │
│                 '{"enable_thinking":false}'              │
└─────────────────────────────────────────────────────────┘
```

---

## Why This Architecture (Key Decisions)

### llama.cpp on Mac Native (NOT in Docker)

**Problem:** Docker adds ~2-3ms per token overhead. Ollama's thinking mode cannot be disabled via Docker flags. Result: 55+ second responses.

**Solution:** llama.cpp runs outside Docker directly on Mac Metal GPU.

**Result:** ~1 second first token, ~41 tokens/sec on M2.

### Why Thinking Mode Must Be Disabled

Gemma 4 has Chain-of-Thought reasoning. When enabled:
- API `content` field is **EMPTY** until thinking completes
- Thinking takes 20-55 seconds
- Users see blank screen

**Fix:** `--chat-template-kwargs '{"enable_thinking":false}'`

**This flag is not optional. The app appears broken without it.**

### Why Gemma 4 E2B (Not Whisper, Not Other Models)

- Native audio STT via `input_audio` block — no separate Whisper model needed
- 140+ languages for transcription including Hindi, Bengali, Tamil
- 3.2GB fits in 16GB RAM alongside Docker
- Fast inference on Apple Silicon Metal

### Why Piper TTS (Not edge-tts, Not Kokoro)

| Option | Verdict | Reason |
|--------|---------|--------|
| edge-tts SwaraNeural | ❌ | Requires internet |
| Kokoro-ONNX | ❌ | Western accent on Hindi voices |
| Parler-TTS AI4Bharat | ❌ | 1.5GB + fairseq fails Python 3.12 |
| **Piper** | ✅ | 61MB, offline binary, genuine Indian accent |

`pip install piper-tts` rejected — pulls PyTorch (800MB) + CUDA (500MB). Using standalone binary.

### Why ChromaDB DefaultEmbeddingFunction

`sentence-transformers` pulls PyTorch (2GB). ChromaDB's built-in function uses the same underlying model (all-MiniLM-L6-v2) via a different entry point with no heavy deps.

---

## Kanoon Sakhi State Machine

```
Every message:
    ↓
EMERGENCY CHECK (LLM, 200ms, YES/NO)
    ↓ YES → stream hardcoded helplines → continue
    ↓ NO
    ↓
INTAKE STATE (turns 1-10, admin configurable)
    LLM extracts: crime_type, urgency, relationship_to_accused,
                  state, has_children, duration, other_context
    Readiness score: crime_type=30 + urgency=30 + relationship=30 + optional=5each
    Route to EXPERT when:
        score >= 90 immediately
        score >= 60 AND turn >= 2
        turn >= max_turns (admin: default 10)
        frustration detected
        crime = rape/acid_attack/trafficking (after turn 1)
    ↓
EXPERT STATE
    RAG retrieval (crime_type → ChromaDB query → 5 chunks)
    LLM: frozen v1.1 prompt (5 mandatory blocks)
    max_tokens: 900 (Devanagari needs ~1.5x tokens vs English)
    Separate call generates 5 follow-up chips
    ↓
FOLLOW_UP STATE (stays here for rest of session)
    Same expert agent, _is_followup() detects short messages
    max_tokens: 250 (2-4 sentence answer only)
```

---

## Request Lifecycle — Text Message

```
1.  User types → React Enter key
2.  POST /api/legal/chat {session_id, message, language: "hi"}
3.  legal.py: load session from SQLite (get_session_with_history)
4.  legal.py: LLM emergency check → detect_emergency_llm()
              YES+critical → stream EMERGENCY_MESSAGES → return
5.  legal.py: save user message to SQLite
6.  legal.py: re-read fresh metadata from DB (gets score from previous turn)
7.  model_router.py: route() → INTAKE or EXPERT or FOLLOW_UP
8a. INTAKE: intake_agent.run_intake() → LLM call (json_object format)
            → regex extract JSON → update metadata → recalculate score
            → if ready: emit phase_change event
8b. EXPERT: legal_rag.get_legal_context(case_file) → 5 ChromaDB chunks
            → legal_agent._build_system() → frozen v1.1 prompt
            → streaming LLM call → filter reasoning_content tokens
            → separate follow-up questions call
9.  Each token: SSE event: data: {"type": "token", "token": "..."}
10. Final: SSE data: {"type": "done", "full_response": "...", "citations": [...]}
11. legal.py: save assistant response to SQLite
12. Frontend: shows 🔊 button for hi/en
```

## Request Lifecycle — Voice Message

```
1.  User presses 🎤 → MediaRecorder starts (WebM/Opus)
2.  User presses ⏹ → max 25 seconds via timerRef
3.  blobToWav(): Web Audio API → Float32 PCM → 16kHz mono WAV
4.  WAV → base64 string
5.  POST localhost:8080/v1/chat/completions:
    content: [
      {type: "input_audio", input_audio: {data: base64, format: "wav"}},
      {type: "text", text: "Transcribe exactly..."}
    ]
6.  Gemma 4 returns transcript text
7.  transcript → sendMessage() → same as text flow
CRITICAL: Audio format MUST be "wav" — llama.cpp rejects webm/mp3 with HTTP 400
```

---

## Database Schema

### SQLite — nyay_vani.db

```sql
-- sessions
CREATE TABLE sessions (
    id                VARCHAR PRIMARY KEY,    -- UUID
    tab_type          VARCHAR NOT NULL,       -- legal | medical
    language          VARCHAR,               -- hi | en | bn (NOT persisted yet — known limitation)
    agent_phase       VARCHAR DEFAULT 'intake', -- intake | expert | follow_up
    confidence_score  INTEGER DEFAULT 0,     -- readiness score 0-100
    emergency_flagged BOOLEAN DEFAULT FALSE,
    metadata_json     TEXT,                  -- JSON: {crime_type, urgency, relationship_to_accused,
                                             --        state, has_children, duration, other_context, ...}
    lead_submitted    BOOLEAN DEFAULT FALSE,
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_active       DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- messages
CREATE TABLE messages (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     VARCHAR REFERENCES sessions(id),
    role           VARCHAR NOT NULL,         -- user | assistant
    content        TEXT NOT NULL,
    input_type     VARCHAR DEFAULT 'text',   -- text | audio
    citations_json TEXT,                     -- JSON array of {source, section, relevance}
    agent_used     VARCHAR,                  -- intake | expert | emergency
    tokens_used    INTEGER,
    response_ms    INTEGER,
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- legal_leads (for lawyer callback feature)
CREATE TABLE legal_leads (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id           VARCHAR,
    name                 VARCHAR,
    phone                VARCHAR NOT NULL,
    district             VARCHAR,
    state                VARCHAR,
    issue_type           VARCHAR,
    urgency_level        VARCHAR,
    conversation_summary TEXT,
    status               VARCHAR DEFAULT 'pending',  -- pending | assigned | resolved
    assigned_lawyer      VARCHAR,
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Known limitation:** `language` column exists in schema but session_manager.py doesn't populate it. Session resume always defaults to Hindi. Fix: add `language` to `create_new_session()`.

### ChromaDB Collections

```
legal_documents:    293 chunks
  - DV Act 2005 (Sections 12, 17, 18, 19, 20)
  - Hindu Succession Act 1956 Amendment 2005
  - POSH Act 2013 (Sections 4, 9, 11, 13)
  - IPC Women Protection (354, 376, 406, 498A)
  - Legal Aid Act 1987
  - Baseline legal knowledge (6 documents)
  - PDFs from rag_documents/legal/

medical_documents:  4 chunks (baseline only, no PDFs)
scheme_documents:   10 chunks (baseline only)

Embedding: ChromaDB DefaultEmbeddingFunction (all-MiniLM-L6-v2, ~80MB download on first run)
```

---

## API Reference

### Chat Endpoints

```
POST /api/legal/chat
POST /api/medical/chat
POST /api/scheme/chat

Request:
{
  "session_id": "uuid-string",
  "message": "mere pati mujhe marte hain",
  "language": "hi",           // hi | en | bn
  "input_type": "text"        // text | audio
}

Response: text/event-stream (SSE)
Events emitted in order:
  {"type": "routing", "decision": "intake|expert|follow_up", "reason": "...", "turn": 2, "score": 60}
  {"type": "metrics", "ram_used_gb": 8.2, "ram_percent": 51}
  {"type": "emergency", "data": {"message": "...", "helplines": [...]}}  // only if emergency
  {"type": "token", "token": "मैं", "agent": "intake|expert"}           // repeated N times
  {"type": "citations", "citations": [{"source": "DV Act 2005", "section": "Section 17", "relevance": 0.92}]}
  {"type": "metadata_update", "confidence_score": 60, "metadata": {...}}
  {"type": "phase_change", "from": "intake", "to": "expert"}
  {"type": "done", "full_response": "...", "citations": [...], "agent": "expert",
   "follow_up_questions": ["Protection order कैसे मिलेगा?", ...], "response_ms": 4312}
  {"type": "error", "message": "..."}
```

### Session Endpoints

```
POST /api/session/new
  Request:  {"tab_type": "legal|medical|scheme"}
  Response: {"session_id": "uuid", "agent_phase": "intake", "tab_type": "legal", ...}

GET  /api/session/{session_id}
  Response: full session object + message history

DELETE /api/session/{session_id}
  Response: {"message": "Session deleted", "session_id": "..."}
```

### Voice Endpoints

```
POST /api/voice/tts
  Request:  {"text": "आपके पास...", "lang": "hi"}
  Response: audio/wav binary (204 if language not supported)

GET /api/voice/languages
  Response: {"supported": [{"code": "hi", "tts": true}, ...]}
```

### Admin Endpoints

```
GET  /api/admin/settings
  Response: current config_runtime.json contents

POST /api/admin/settings
  Request:  {"pin": "1234", "intake_max_turns": 10, "tts_speed_hi": 1.2, ...}
  Response: updated config

GET  /api/admin/logs?limit=50
  Response: {"events": [...last N events from in-memory deque...], "total": 200}

GET  /api/admin/session/{session_id}
  Response: {"phase": "expert", "metadata": {...}, "confidence_score": 90, ...}
```

---

## Expert Response Format (Frozen v1.1)

Every expert response MUST contain all 5 blocks:

```
━━━ BLOCK 1: EMPATHY (1 sentence) ━━━
[Personal reference to her case file]

━━━ BLOCK 2: HER RIGHTS (2-3 rights) ━━━
[Source: DV Act 2005, Section 17] explanation
[Source: DV Act 2005, Section 18] explanation

━━━ BLOCK 3: ACTION TIMELINE (all 3 required) ━━━
**अभी (Right Now):** [immediate step]
**आज (Today):** [within 24 hours]
**इस हफ्ते (This Week):** [within 7 days]

━━━ BLOCK 4: FREE HELPLINE (exactly 1) ━━━
📞 181 — महिला हेल्पलाइन (24 घंटे, FREE)

━━━ BLOCK 5: FOLLOW-UP QUESTION (exactly 1) ━━━
[Specific question about her case]?
```

Citation format: `[Source: Act Name YYYY, Section X]` — year required, "Source:" prefix required.

---

## Project Structure

```
nyay-vani-backend/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── intake_agent.py      ← JSON parameter extraction, readiness scoring
│   │   │   ├── legal_agent.py       ← Expert 5-block response, follow-up questions
│   │   │   ├── medical_agent.py     ← Health guidance, warning signs
│   │   │   ├── scheme_agent.py      ← Government scheme lookup
│   │   │   ├── model_router.py      ← State machine, routing rules, readiness score
│   │   │   └── prompt_builder.py    ← DEPRECATED — stub only, safe to delete
│   │   ├── api/
│   │   │   ├── legal.py             ← Main legal endpoint, SSE streaming, logging
│   │   │   ├── medical.py           ← Medical endpoint
│   │   │   ├── scheme.py            ← Scheme endpoint
│   │   │   ├── session.py           ← Session CRUD
│   │   │   ├── voice.py             ← TTS endpoint
│   │   │   ├── admin.py             ← Settings + live logs
│   │   │   └── leads.py             ← Lawyer/doctor callback feature
│   │   ├── database/
│   │   │   ├── models.py            ← SQLAlchemy models (Session, Message, Leads)
│   │   │   ├── crud.py              ← DB operations
│   │   │   └── connection.py        ← SQLite engine, init_db()
│   │   ├── emergency/
│   │   │   └── detector.py          ← LLM-based YES/NO detection, helpline responses
│   │   ├── rag/
│   │   │   ├── legal_rag.py         ← crime_type → ChromaDB query → 5 chunks
│   │   │   ├── medical_rag.py       ← symptom → ChromaDB query
│   │   │   ├── retriever.py         ← ChromaDB client, embedding, format context
│   │   │   └── embedder.py          ← DefaultEmbeddingFunction wrapper
│   │   ├── session/
│   │   │   └── session_manager.py   ← create/get/update/delete sessions + messages
│   │   ├── voice/
│   │   │   ├── tts.py               ← Piper subprocess, Devanagari conversion fallback
│   │   │   └── stt.py               ← DEAD CODE — Whisper replaced by Gemma 4 audio
│   │   ├── utils/
│   │   │   ├── language_detect.py   ← langdetect wrapper (used by medical/scheme only)
│   │   │   ├── prompt_builder.py    ← DEAD CODE — duplicate, safe to delete
│   │   │   └── __init__.py
│   │   ├── main.py                  ← FastAPI app, CORS, routers, lifespan, health check
│   │   ├── config.py                ← Pydantic settings (reads .env)
│   │   └── runtime_config.py        ← config_runtime.json read/write (no restart needed)
│   ├── scripts/
│   │   ├── ingest_legal_docs.py     ← One-time ChromaDB population
│   │   ├── ingest_medical_docs.py
│   │   └── ingest_scheme_docs.py
│   ├── benchmark_v2/
│   │   ├── evaluate_v3.py           ← RAGAS-style evaluation (run on Mac, not Docker)
│   │   ├── test_cases_v2.json       ← 15 test cases (10 expert + 5 intake)
│   │   └── results/                 ← Saved eval JSON files
│   ├── rag_documents/legal/         ← PDFs: dv_act_2005.pdf, posh_act_2013.pdf, etc.
│   ├── config_runtime.json          ← Live settings (tts_speed, intake_max_turns, etc.)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/App.jsx                  ← Entire React app (single file ~1200 lines)
│   ├── public/admin.html            ← Admin dashboard (standalone, no React)
│   └── Dockerfile
└── docker-compose.yml
```

---

## Dead Code

Remove these files — they serve no purpose:

```
backend/app/voice/stt.py            faster-whisper not in requirements.txt
                                     STT done via Gemma 4 audio input now
backend/app/utils/prompt_builder.py  Duplicate of agents/prompt_builder.py
backend/app/agents/prompt_builder.py Already stubbed with NotImplementedError
```

Stale config keys in `backend/app/config.py` (never read by any current code):
```python
intake_model: str = "gemma3n:e2b"
expert_model: str = "gemma3n:e4b"
whisper_model_size: str = "tiny"
tts_voice_hindi: str = "hi-IN-SwaraNeural"
tts_voice_english: str = "en-IN-NeerjaNeural"
```

---

## Known Limitations / Technical Debt

| # | Issue | Impact | Fix |
|---|-------|--------|-----|
| 1 | Medical RAG empty | Sehat Sakhi gives generic advice | Add PDFs to rag_documents/medical/ |
| 2 | Session language not persisted | Resume defaults to Hindi | Add language to create_new_session() |
| 3 | intake_max_turns in config_runtime.json stuck at 3 | Admin slider has no effect | Update config_runtime.json manually |
| 4 | Hindi purity 0.87 (fine-tuned) vs 1.0 (base) | English terms leak into Hindi | Add Hindi legal term glossary to prompt |
| 5 | Admin PIN hardcoded "1234" | Not production-safe | Move to .env |
| 6 | No HTTPS | Fine for local demo | Nginx reverse proxy for production |
| 7 | Single user at a time | llama.cpp sequential | Expected for demo hardware |
| 8 | scheme.py uses tab_type="legal" in DB | Can't separate scheme analytics | Add scheme to tab_type enum |

---

## Daily Startup

```bash
# Terminal 1 — llama-server (start first, wait for "llama server listening")
llama-server \
  -m ~/.ollama/models/blobs/sha256-e6d47b7c... \
  --mmproj ~/strisakhi-models/mmproj/mmproj-gemma4-e2b.gguf \
  --port 8080 \
  --chat-template-kwargs '{"enable_thinking":false}' \
  -ngl 99 -c 4096 --host 0.0.0.0

# Terminal 2 — Docker
cd ~/Desktop/nyay-vani-backend
docker compose up

# URLs
App:      http://localhost:5173
Admin:    http://localhost:5173/admin.html   PIN: 1234
API docs: http://localhost:8000/docs
Health:   http://localhost:8000/api/health
Logs:     http://localhost:8000/api/admin/logs
```
