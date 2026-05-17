# StriSakhi — स्त्री सखी

### Voice-first offline AI companion for rural Indian women

**Legal rights · Health guidance · Government schemes · Fully offline · Hindi / English / Bengali**

> *"Every woman deserves to know her rights. Justice is not a privilege — it's yours."*

🎥 **Demo:** https://www.youtube.com/watch?v=xvn72y3w22Y  
🤗 **Model:** https://huggingface.co/snake4u1/strisakhi-gemma4-lora  
📦 **GitHub:** https://github.com/bhawna94110/strisakhi-app

---

## The Problem

300 million rural Indian women cannot access a lawyer. 68% don't know their legal rights. Domestic violence, land theft, abandonment — they suffer because the system that protects them is inaccessible. No internet. No English. No help.

StriSakhi fixes this.

---

## Three Companions

| | Sakhi | What it does | Architecture |
|---|-------|-------------|-------------|
| ⚖️ | **Kanoon Sakhi** | Legal rights — DV Act, property, maintenance, workplace | LangGraph v2 state machine |
| 🌿 | **Sehat Sakhi** | Health — pregnancy, child illness, mental health | Direct LLM + RAG |
| 📜 | **Yojana Sakhi** | 13 govt schemes — PM Awas, Ayushman, MGNREGS | Direct LLM + scheme DB |

---

## Resource Usage

Verified live in admin dashboard:
- **CPU:** ~1%
- **RAM:** under 2GB
- **Speed:** 41 tokens/second on M2 Mac (Metal GPU)
- **Model size:** 3.2GB (Q4_K_M)

**Runs on any edge device** — laptop, Raspberry Pi 5, village kiosk, NGO tablet.

---

## Architecture

```
Browser (React + Vite :5173)
    ↓ HTTP / SSE streaming
FastAPI Backend (Docker :8000)
    ├── SQLite — sessions + messages
    ├── ChromaDB — 197 legal + 6 medical document chunks
    └── Piper TTS — offline Hindi/English voices
    ↓ HTTP → host.docker.internal:8080
llama-server (Mac native, Metal GPU)
    ├── strisakhi-Q4_K_M.gguf (3.2GB) — fine-tuned LLM + native STT
    └── mmproj-gemma4-e2b.gguf (557MB) — audio projector
```

**Why llama.cpp runs outside Docker:**
Without `--chat-template-kwargs '{"enable_thinking":false}'`, Gemma 4 returns empty responses for 55 seconds. This flag is not exposed by Ollama. Running natively on Metal gives 41 tok/s.

---

## Fine-tuned Model

**HuggingFace:** `snake4u1/strisakhi-gemma4-lora`

Trained on Kaggle (Tesla T4, free tier) using Unsloth LoRA on 549 hand-crafted legal conversation examples.

| Metric | Base Gemma 4 | Fine-tuned LoRA | LangGraph v2 |
|--------|-------------|----------------|-------------|
| Pass Rate | 60% | 93% | 3/3 ✓ |
| Structure (5 blocks) | 0.67 | 0.92 | 1.00 |
| Section Accuracy | 0.40 | 0.90 | 1.00 |
| Hindi Purity | 1.00 | 0.87 | 0.87 |
| **Overall Score** | **0.71** | **0.89** | **0.94** |

---

## Reproduce — Step by Step

### Requirements

- macOS Apple Silicon (M1/M2/M3) — or any Linux with CUDA
- Docker Desktop
- 8GB+ RAM
- `brew install llama.cpp`

---

### Step 1 — Clone the repo

```bash
git clone https://github.com/bhawna94110/strisakhi-app
cd strisakhi-app
cp backend/.env.example backend/.env
```

---

### Step 2 — Get the fine-tuned GGUF model

The HuggingFace repo contains raw LoRA adapters (`adapter_model.safetensors`).  
Your options:

**Option A — Download pre-built GGUF (fastest, recommended)**

The merged + quantized GGUF is available directly:

```bash
mkdir -p ~/Downloads/fine_tuned_final_model

# Download merged Q4_K_M GGUF (~3.2GB)
huggingface-cli download snake4u1/strisakhi-gemma4-lora \
  strisakhi-Q4_K_M.gguf \
  --local-dir ~/Downloads/fine_tuned_final_model/

# Download mmproj (~557MB)  
huggingface-cli download snake4u1/strisakhi-gemma4-lora \
  mmproj-gemma4-e2b.gguf \
  --local-dir ~/Downloads/fine_tuned_final_model/
```

**Option B — Merge LoRA yourself from scratch**

```bash
# Step 1: Download base Gemma 4 E2B
huggingface-cli download google/gemma-4-E2B-it \
  --local-dir ~/gemma4-base/

# Step 2: Download LoRA adapters
huggingface-cli download snake4u1/strisakhi-gemma4-lora \
  adapter_model.safetensors adapter_config.json \
  tokenizer.json tokenizer_config.json \
  --local-dir ~/strisakhi-lora/

# Step 3: Merge LoRA into base model (Python)
pip install peft transformers torch

python3 << 'PYEOF'
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

base = AutoModelForCausalLM.from_pretrained(
    "~/gemma4-base", torch_dtype=torch.bfloat16
)
model = PeftModel.from_pretrained(base, "~/strisakhi-lora")
merged = model.merge_and_unload()
merged.save_pretrained("~/strisakhi-merged")
AutoTokenizer.from_pretrained("~/gemma4-base").save_pretrained("~/strisakhi-merged")
print("Merged saved to ~/strisakhi-merged")
PYEOF

# Step 4: Convert to GGUF
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
pip install -r requirements.txt

python3 convert_hf_to_gguf.py ~/strisakhi-merged \
  --outfile ~/Downloads/fine_tuned_final_model/strisakhi-F16.gguf \
  --outtype f16

# Step 5: Quantize to Q4_K_M (saves ~60% size, minimal quality loss)
./llama-quantize \
  ~/Downloads/fine_tuned_final_model/strisakhi-F16.gguf \
  ~/Downloads/fine_tuned_final_model/strisakhi-Q4_K_M.gguf \
  Q4_K_M

echo "Done: strisakhi-Q4_K_M.gguf ready"
```

---

### Step 3 — Download Piper TTS voices

```bash
mkdir -p ~/strisakhi-models/piper

# Hindi voice (61MB)
curl -L -o ~/strisakhi-models/piper/hi_IN-priyamvada-medium.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/priyamvada/medium/hi_IN-priyamvada-medium.onnx"
curl -L -o ~/strisakhi-models/piper/hi_IN-priyamvada-medium.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/priyamvada/medium/hi_IN-priyamvada-medium.onnx.json"

# English voice (60MB)
curl -L -o ~/strisakhi-models/piper/en_US-amy-medium.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx"
curl -L -o ~/strisakhi-models/piper/en_US-amy-medium.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json"
```

---

### Step 4 — Start llama-server

```bash
llama-server \
  -m ~/Downloads/fine_tuned_final_model/strisakhi-Q4_K_M.gguf \
  --mmproj ~/Downloads/fine_tuned_final_model/mmproj-gemma4-e2b.gguf \
  --port 8080 \
  --chat-template-kwargs '{"enable_thinking":false}' \
  -ngl 99 \
  -c 4096 \
  --host 0.0.0.0
```

⚠️ **Critical:** `enable_thinking:false` is mandatory. Without it, Gemma 4 returns empty responses for 55 seconds.

Wait for: `llama server listening on 0.0.0.0:8080`

---

### Step 5 — Start backend + frontend

```bash
docker compose up
```

First run (~2-3 min):
- Downloads ChromaDB embedding model (80MB)
- Ingests 197 legal + 6 medical documents automatically
- Builds frontend

---

### Step 6 — Open

| URL | What |
|-----|------|
| http://localhost:5173 | Main app |
| http://localhost:5173/admin.html | Admin dashboard (PIN: 1234) |
| http://localhost:8000/docs | API docs |
| http://localhost:8000/api/health | Health check |

---

## Run the Evaluation / Benchmark

```bash
cd backend

# Test 3 reproducible demo use cases end-to-end
# Requires: Docker running + llama-server running
python3 tests/test_kanoon.py

# Expected output:
# RESULTS: 3/3 passed
# final_score: 0.92
# section_accuracy: 1.00
# structure_score: 1.00
# hindi_purity: 0.87

# Results saved to:
# tests/results/kanoon_test_TIMESTAMP.json
```

The 3 test cases:
1. **Domestic Violence** — Section 17 DV Act (cannot be evicted)
2. **Property Rights** — Vineeta Sharma v Rakesh Sharma SC 2020
3. **Maintenance** — CrPC 125 (no divorce needed, 60 days)

---

## Retrain the Model (Optional)

The training notebook is on Kaggle (free T4 GPU, ~35 min):

```
Training data:  backend/benchmark_v2/training_data/strisakhi_train.jsonl
Test data:      backend/benchmark_v2/training_data/strisakhi_test.jsonl
Examples:       549 training, 50 test
Base model:     unsloth/gemma-4-E2B-it-unsloth-bnb-4bit
LoRA rank:      r=8, alpha=8
Epochs:         3
Final loss:     0.35
Training time:  34.9 minutes on Tesla T4
```

Key training config:
```python
model = FastModel.get_peft_model(
    model,
    finetune_vision_layers=False,
    finetune_language_layers=True,
    finetune_attention_modules=True,
    finetune_mlp_modules=True,
    r=8, lora_alpha=8, lora_dropout=0,
    random_state=42,
)
```

---

## Kanoon Sakhi — LangGraph v2 Architecture

```
User message
    ↓
[emergency node] — LLM checks: immediate danger? YES → helplines + short response
    ↓ NO
[intake node] — extract crime type, score fields (0-100 confidence)
    ↓
score-based routing:
    score ≥ 85 + turn ≥ 3 → expert
    score ≥ 95 + turn ≥ 2 → expert
    turn ≥ max_turns      → expert (forced)
    otherwise             → intake (next question)
    ↓
[rag node] — ChromaDB top-5 chunks from 197 legal documents
    ↓
[expert node] — 5-block structured response with citations
    ↓
[followup node] — short 2-4 sentence answers for follow-up questions
    ↓
[save node] — persist phase + metadata to SQLite
```

**5-block expert response format:**
```
BLOCK 1: EMPATHY — personal reference to her specific case
BLOCK 2: HER RIGHTS — [Source: Act, Section] citations from RAG
BLOCK 3: ACTION TIMELINE — अभी / आज / इस हफ्ते
BLOCK 4: FREE HELPLINE — crime-specific number (181/15100/1930)
BLOCK 5: FOLLOW-UP QUESTION — specific to her situation
```

---

## RAG Knowledge Base

197 legal chunks in ChromaDB (local, no internet):

| Document | Sections | Crime Type |
|----------|---------|-----------|
| DV Act 2005 | 12, 17, 18, 19, 20, 21, 22 | domestic_violence |
| Vineeta Sharma v Rakesh Sharma SC 2020 | Full judgment | property |
| Hindu Succession Act 1956 (Amended 2005) | Section 6 | property |
| CrPC | Section 125, 125(2) | maintenance |
| POSH Act 2013 | 2, 4, 9, 11, 13 | workplace |
| Dowry Prohibition Act 1961 | 3, IPC 498A, 304B | dowry |
| IPC 354D + IT Act | 354D, 66C, 66E, 67 | stalking |
| NALSA Legal Aid | Free lawyer helpline | general |

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM + STT | Gemma 4 E2B Q4_K_M via llama.cpp |
| Fine-tuning | Unsloth LoRA (Kaggle T4, free) |
| State machine | LangGraph v2 |
| RAG | ChromaDB (local embedded) |
| TTS | Piper binary (offline) |
| Backend | FastAPI + Python 3.11 |
| Frontend | React + Vite |
| Database | SQLite |
| Container | Docker Compose |

---

## Privacy

- Zero data sent to any cloud
- No login or account required
- Voice recordings transcribed locally and discarded immediately
- Fully offline after model downloads

---

## Links

- 🎥 Demo video: https://www.youtube.com/watch?v=xvn72y3w22Y
- 🤗 Fine-tuned model: https://huggingface.co/snake4u1/strisakhi-gemma4-lora
- 📊 Training data: `backend/benchmark_v2/training_data/`
- 📋 Benchmark results: `backend/benchmark_v2/results/`
- 🧪 Test script: `backend/tests/test_kanoon.py`

---

*Built for Kaggle GenAI Hackathon 2025 — but built for the women who need it.*
