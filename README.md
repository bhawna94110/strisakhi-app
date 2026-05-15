# StriSakhi — स्त्री सखी
### Voice-first AI companion for rural Indian women

**Legal rights · Health guidance · Government schemes · Fully offline · Hindi / English / Bengali**

> *"Every woman deserves to know her rights. Justice is not a privilege — it's yours."*

---

## What Is StriSakhi?

68% of Indian women have faced domestic violence (NCRB 2022). Most don't know their rights.

StriSakhi is a voice-first AI that speaks to a woman in Hindi, in a warm voice, like a trusted older sister who knows the law. No internet required. No account needed. No data sent to any cloud.

### Three Companions

| | Agent | What it does |
|---|-------|-------------|
| ⚖️ | **Kanoon Sakhi** | Legal rights — DV Act, property, workplace harassment, maintenance |
| 🌿 | **Sehat Sakhi** | Health guidance — pregnancy, child health, mental health |
| 📜 | **Yojana Sakhi** | Government schemes — PM Awas, Ayushman Bharat, MGNREGS |

---

## Architecture

```
Browser (React + Vite, port 5173)
    ↓ HTTP / SSE
FastAPI Backend (Docker, port 8000)
    ├── SQLite — sessions + messages
    ├── ChromaDB — 293 legal document chunks
    └── Piper TTS — offline Indian voice (61MB)
    ↓ HTTP to host.docker.internal:8080
llama-server (Mac native, Metal GPU)
    ├── Gemma 4 E2B Q4_K_M (3.2GB) — LLM + audio STT
    └── mmproj Q8_0 (532MB) — multimodal projector
```

**Why llama.cpp runs outside Docker:** Docker adds ~2-3ms per token overhead and Ollama doesn't expose the `enable_thinking` flag. Without `--chat-template-kwargs '{"enable_thinking":false}'`, Gemma 4 returns empty responses for 20-55 seconds. Running natively on Metal gives ~1 second response time at 41 tokens/sec.

---

## Fine-tuned Model

The expert agent uses a fine-tuned Gemma 4 E2B, trained on 549 legal conversation examples using Unsloth LoRA.

| Metric | Base Model | Fine-tuned | Improvement |
|--------|-----------|------------|-------------|
| Pass rate | 60% | **93%** | +33% |
| Structure compliance | 66.7% | **91.7%** | +25% |
| Law citation accuracy | 40% | **90%** | +50% |
| Overall score | 0.710 | **0.889** | +0.179 |

🤗 **Model:** [snake4u1/strisakhi-gemma4-lora](https://huggingface.co/snake4u1/strisakhi-gemma4-lora)

---

## Requirements

- macOS with Apple Silicon (M1/M2/M3)
- Docker Desktop
- 16GB RAM minimum
- ~6GB free disk space
- `brew install llama.cpp`

---

## Setup

### 1. Clone

```bash
git clone https://github.com/bhawna94110/strisakhi-app
cd strisakhi-app
```

### 2. Configure environment

```bash
cp .env.example backend/.env
# Edit backend/.env — set MODELS_PATH to your models directory
```

### 3. Download models

```bash
# Create models directory
mkdir -p ~/strisakhi-models/piper ~/strisakhi-models/mmproj

# Gemma 4 E2B via Ollama (easiest way to get the GGUF)
ollama pull batiai/gemma4-e2b:q4

# Find the model file hash
ls ~/.ollama/models/blobs/ | grep -v manifest | head -5

# mmproj for audio support
huggingface-cli download ggml-org/gemma-4-E2B-it-GGUF \
  --include "mmproj*" \
  --local-dir ~/strisakhi-models/mmproj/

# Piper voices
curl -L -o ~/strisakhi-models/piper/hi_IN-priyamvada-medium.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/priyamvada/medium/hi_IN-priyamvada-medium.onnx"
curl -L -o ~/strisakhi-models/piper/hi_IN-priyamvada-medium.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/priyamvada/medium/hi_IN-priyamvada-medium.onnx.json"
curl -L -o ~/strisakhi-models/piper/en_US-amy-medium.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx"
curl -L -o ~/strisakhi-models/piper/en_US-amy-medium.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json"
```

### 4. Start llama-server

```bash
# Replace SHA256_HASH with your actual model file hash from step 3
llama-server \
  -m ~/.ollama/models/blobs/SHA256_HASH \
  --mmproj ~/strisakhi-models/mmproj/mmproj-gemma4-e2b-f16.gguf \
  --port 8080 \
  --chat-template-kwargs '{"enable_thinking":false}' \
  -ngl 99 -c 4096 --host 0.0.0.0
```

⚠️ Wait for `llama server listening` before proceeding.

### 5. Start Docker

```bash
docker compose up
```

First run downloads the ChromaDB embedding model (~80MB) and ingests legal documents automatically. This takes 2-3 minutes.

### 6. Open the app

| URL | Description |
|-----|-------------|
| http://localhost:5173 | Main app |
| http://localhost:5173/admin.html | Admin dashboard (PIN: 1234) |
| http://localhost:8000/docs | API documentation |
| http://localhost:8000/api/health | System health check |

---

## How It Works

### Intelligent Intake → Expert Pipeline

```
User message
    ↓
Emergency check (LLM, 200ms) — if active danger: show helplines immediately
    ↓
Intake agent (turns 1-10) — collects: crime type, urgency, relationship
    ↓ when enough context collected
Expert agent — RAG retrieval + frozen 5-block legal response
    ↓
Follow-up state — short answers to follow-up questions
```

### Voice Flow

User presses 🎤 → records audio → WAV conversion in browser → sent to Gemma 4 as `input_audio` block → transcript returned → processed as text

**No Whisper needed.** Gemma 4 E2B natively supports audio input.

### TTS Flow

Response text → clean (strip emoji/markdown) → Piper subprocess → WAV bytes → played in browser

For Hindi: if response contains Roman script (Hinglish), Gemma 4 first converts it to Devanagari before TTS.

### Dynamic Prompt Architecture

Every response uses a 5-block frozen structure:

```
━━━ BLOCK 1: EMPATHY — personal reference to her case
━━━ BLOCK 2: HER RIGHTS — 2-3 rights with [Source: Act, Section] citations
━━━ BLOCK 3: ACTION TIMELINE — अभी / आज / इस हफ्ते (Right Now / Today / This Week)
━━━ BLOCK 4: FREE HELPLINE — one relevant number
━━━ BLOCK 5: FOLLOW-UP QUESTION — specific to her situation
```

Language instruction appears both FIRST and LAST in every system prompt — enforces Devanagari output even when user writes in Hinglish (Roman Hindi).

---

## Evaluation

Run benchmarks against your local model:

```bash
cd backend

# Run evaluation (requires llama-server running)
python benchmark_v2/evaluate_v3.py \
  --dataset benchmark_v2/test_cases_v2.json

# Compare base vs fine-tuned
python benchmark_v2/evaluate_v3.py \
  --compare benchmark_v2/results/BASE.json \
            benchmark_v2/results/FINETUNED.json
```

Scores: structure compliance, law citation accuracy, Hindi purity, RAGAS faithfulness/relevancy/correctness.

---

## Admin Dashboard

Live system monitoring at `http://localhost:5173/admin.html`

- **System tab** — RAM, CPU, model status, ChromaDB stats
- **AI Flow tab** — live routing decisions per message (intake/expert/follow_up)
- **Logs tab** — real-time event stream with emoji markers
- **Settings tab** — adjust intake turns, TTS speed, temperature without restart

---

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| LLM + STT | Gemma 4 E2B via llama.cpp | Offline, multilingual, native audio |
| Fine-tuning | Unsloth LoRA | +33% pass rate, runs on free Kaggle GPU |
| TTS | Piper binary | 61MB, offline, genuine Indian accent |
| RAG | ChromaDB embedded | No separate service, no heavy deps |
| Backend | FastAPI + Python 3.11 | Async SSE streaming |
| Frontend | React + Vite | Single file, no build complexity |
| Database | SQLite | Embedded, file-based |
| Container | Docker Compose | Reproducible environment |

---

## Privacy

- No data sent to any cloud service
- No account or login required  
- Voice recordings transcribed and discarded immediately (never stored)
- Fully offline after initial model downloads

---

## Built For

Kaggle GenAI Hackathon 2025. But more than a hackathon project — a tool we want rural women to actually use.

**Fine-tuned model:** [snake4u1/strisakhi-gemma4-lora](https://huggingface.co/snake4u1/strisakhi-gemma4-lora)
**GitHub:** [bhawna94110/strisakhi-app](https://github.com/bhawna94110/strisakhi-app)
