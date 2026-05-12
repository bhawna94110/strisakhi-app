# StriSakhi Benchmark v3.0

**Production-prompt aligned benchmark** for Kanoon Sakhi AI legal assistant.
Uses your actual `legal_agent.py` and `intake_agent.py` prompt builders so the benchmark matches real app behavior.

## 📁 Files

| File | Purpose |
|------|---------|
| `evaluate_v3.py` | Strict regex-based evaluator. Imports your real prompt builders. |
| `test_cases_v2.json` | 15 test cases (10 expert + 5 intake) with controlled RAG context. |
| `generate_report.py` | Generates beautiful HTML reports for hackathon judges. |
| `results/` | Output directory for JSON results and HTML reports. |

## 🚀 Quick Start

### 1. Ensure llama-server is running
```bash
llama-server \
  -m ~/strisakhi-models/finetuned/YOUR_MODEL.gguf \
  --mmproj ~/strisakhi-models/mmproj/mmproj-gemma4-e2b.gguf \
  --port 8080 \
  --chat-template-kwargs '{"enable_thinking":false}' \
  -ngl 99 -c 4096 --host 0.0.0.0
```

### 2. Run benchmark (from `backend/` directory)
```bash
cd /Users/bhawna/Desktop/nyay-vani-backend/backend
python benchmark_v2/evaluate_v3.py
```

This will:
- Build prompts using your actual `_build_system()` and `build_intake_system()` functions
- Send them directly to `localhost:8080/v1/chat/completions`
- Score responses with strict regex (exact citation format, all 3 timeline lines, etc.)
- Save results to `benchmark_v2/results/eval_v3_latest.json`

### 3. Generate HTML report
```bash
python benchmark_v2/generate_report.py benchmark_v2/results/eval_v3_latest.json
```
Open `benchmark_v2/results/eval_v3_latest.html` in your browser.

### 4. Compare Before vs After fine-tuning
```bash
# After you have both baseline and fine-tuned results:
python benchmark_v2/generate_report.py \
  benchmark_v2/results/eval_v3_BASE.json \
  benchmark_v2/results/eval_v3_FT.json
```
This creates `benchmark_v2/results/comparison_report.html` — perfect for judges.

## 📊 What Gets Scored

### Expert Agent
| Check | Rule | Weight |
|-------|------|--------|
| All 5 blocks | Exact English headers: `━━━ BLOCK 1: EMPATHY` etc. | 40% |
| Citation format | Exact: `[Source: DV Act 2005, Section 17]` | 25% |
| Timeline | All 3: `**अभी (Right Now):**`, `**आज (Today):**`, `**इस हफ्ते (This Week):**` | part of structure |
| Hindi purity | Devanagari / (Devanagari + Roman) | 15% |
| Word count | Under 400 words | 5% |
| No hallucination | No fake sections like Section 999 | 5% |
| Helpline | `📞 181` or `📞 15100` present | 5% |
| No bare lawyer advice | Never say "consult a lawyer" without NALSA 15100 | 5% |

### Intake Agent
| Check | Rule | Weight |
|-------|------|--------|
| Valid JSON | Parseable, no markdown fences | 50% |
| All fields | `message`, `extracted`, `ready_for_expert`, `frustrated`, `readiness_score` | part of structure |
| One question | `message` contains exactly 1 `?` | part of structure |
| Extraction accuracy | `extracted` fields match expected | 30% |
| Ready flag | `ready_for_expert` matches expectation | 20% |

## 🎯 Pass Threshold
- **Expert:** `final_score >= 0.65` AND `structure_score >= 0.6`
- **Intake:** `final_score >= 0.65` AND `valid_json == True`

## 📝 Adding More Test Cases

Edit `test_cases_v2.json`. Each case needs:
- `agent_type`: `"expert"` or `"intake"`
- `language`: `"hi"`, `"en"`, or `"bn"`
- For expert: `case_file`, `rag_context`, `history_text`, `user_message`, `is_followup`
- For intake: `metadata`, `turn`, `max_turns`, `user_message`
- `evaluation_rules`: scoring parameters

## 🔗 Integration with Your App

This benchmark bypasses FastAPI/SQLite/RAG and tests the model directly. This is intentional:
- **Isolates model quality** from RAG retrieval errors
- **Isolates format compliance** from session/DB bugs
- **Fair comparison** — same prompt in, same format check out

Your production app still uses the same prompts, so if the model passes this benchmark, it will format correctly in production too.

## 🏆 For Hackathon Judges

Show them:
1. `comparison_report.html` — Before vs After delta table
2. `eval_v3_latest.html` — Detailed per-case breakdown
3. The `eval_v3_*.json` files — Raw machine-readable scores

**Key metric to highlight:** `section_accuracy` and `structure_score` — these directly measure the format compliance that fine-tuning fixes.
