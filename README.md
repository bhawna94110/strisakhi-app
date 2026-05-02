# 🎙️ Nyay Vani — न्याय वाणी
### Justice Voice — AI Legal & Medical Assistant for Rural Indian Women

> Voice-first AI that provides instant legal and medical guidance in Hindi and regional languages.
> Works offline via RAG. Connects to free lawyers and doctors when online.

---

## 🚀 Quick Start (Docker)

```bash
# 1. Clone repo
git clone https://github.com/yourusername/nyay-vani.git
cd nyay-vani

# 2. Start everything
docker compose up --build

# 3. Ingest documents (run once)
docker exec nyay-vani-backend python scripts/ingest_legal_docs.py
docker exec nyay-vani-backend python scripts/ingest_medical_docs.py

# 4. Open app
open http://localhost:5173
```

App will be live at `http://localhost:5173`
API docs at `http://localhost:8000/docs`

---

## 🏗️ Architecture

```
User Voice/Text Input
        ↓
ModelRouter (Cactus Prize)
  ├── Gemma 4 E2B → Intake Agent (gather case info)
  └── Gemma 4 E4B → Expert Agent (legal/medical guidance + RAG)
        ↓
ChromaDB RAG → Retrieved from Indian legal corpus
        ↓
Streaming SSE response with citations
        ↓
edge-tts (hi-IN-SwaraNeural) → Female Hindi voice output
```

## 🎯 Prize Tracks Targeted

| Prize | How |
|---|---|
| Main Track $100K | Full product |
| Digital Equity $10K | Voice-first, 9 Indian languages |
| Health & Sciences $10K | Medical tab with clinical RAG |
| Safety & Trust $10K | RAG citations on every answer |
| Ollama $10K | Local inference via Ollama |
| Unsloth $10K | Fine-tuned on Indian legal corpus |
| Cactus $10K | ModelRouter — E2B/E4B routing |

## 📁 Structure
```
nyay-vani/
├── backend/          FastAPI + Gemma 4 + RAG
├── frontend/         React JS
├── docs/             Postman collection + API specs
└── docker-compose.yml
```
