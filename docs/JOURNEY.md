# StriSakhi — Build Journey
## From Nyay Vani to StriSakhi: Challenges, Decisions, and Lessons

---

## The Problem We Started With

68% of Indian women have faced domestic violence (NCRB 2022). Most don't know their rights. A woman in a village in Uttar Pradesh being beaten by her husband doesn't know she has a legal right to stay in her home, get a Protection Order within 3 days, and receive free legal aid via NALSA 15100. She can't read legal documents. She's scared to ask for help. And she likely has low literacy.

**The goal:** An AI that speaks to her in Hindi, in a warm voice, like a trusted older sister who knows the law.

---

## Phase 1 — First Architecture (Abandoned)

**Stack:** React + FastAPI + Ollama (Docker) + Whisper STT + edge-tts

**What failed:**

**Thinking mode killed response time.** Gemma 4 with thinking mode enabled returns an empty `content` field for 20-55 seconds while it reasons internally. Users saw a blank screen. We spent 2 days debugging before realizing this was an architecture-level issue with how Docker routes to Ollama — Ollama doesn't expose `--chat-template-kwargs` for disabling thinking.

**Lesson:** The model flag `--chat-template-kwargs '{"enable_thinking":false}'` is not optional. Without it the app appears broken.

**Solution:** Moved llama.cpp outside Docker entirely. Run it natively on Mac Metal. Latency dropped from 55+ seconds to ~1 second.

**TTS was wrong.** edge-tts SwaraNeural sounded good but requires internet — violates offline requirement. Kokoro-ONNX had a Western accent on Hindi. Parler-TTS AI4Bharat had the right Indian accent but fairseq dependency fails on Python 3.12. Evaluated 4 TTS options before landing on Piper binary (61MB, offline, genuine Indian accent).

**STT was wrong.** Whisper required a separate 150MB model. When we discovered Gemma 4 E2B natively accepts `input_audio` blocks (WAV format), we removed Whisper entirely. One model for everything.

**`pip install piper-tts` trap.** This package pulls PyTorch (800MB) + CUDA (500MB) even on Mac. Used the standalone Piper binary instead — same quality, no dependencies.

---

## Phase 2 — Name Change

Original name: **Nyay Vani** (Justice Voice)

Changed to: **StriSakhi** (Woman's Companion)

Why: "Nyay Vani" felt formal and legal. "StriSakhi" is warmer — a companion, not an authority. The three agents were renamed to match: Kanoon Sakhi (Legal), Sehat Sakhi (Health), Yojana Sakhi (Schemes).

Legacy: The database file is still named `nyay_vani.db`. Old config keys reference `nyay-vani`. This is intentional — we didn't want to break a working system mid-development.

---

## Phase 3 — RAG and State Machine

**The intake problem.** Early versions dumped users directly to the expert agent without collecting context. Expert responses were generic ("consult a lawyer") because they had no case information. We added an intake agent — but early intake was unreliable because `response_format: json_schema` returned empty responses on our specific llama.cpp build.

**Finding:** `response_format: json_schema` causes empty `content` on certain llama.cpp builds. Fallback: `response_format: json_object` + robust JSON extraction via `re.search(r'\{.*\}', raw, re.DOTALL)`. This handles any model wrapping: plain JSON, markdown fences, preamble text.

**RAG wrong query.** For weeks, the RAG was using `issue_type` to query ChromaDB but the intake agent stored data under `crime_type`. Every RAG query returned generic women's rights content instead of DV Act specifics. The fix was one line: `crime_type = case_file.get("crime_type") or case_file.get("issue_type")`.

**Emergency detection too sensitive.** Initial keyword-based detector flagged "mere pati mujhe marte hain" as emergency. Switched to LLM-based YES/NO detection with explicit examples. The model correctly distinguishes "maarta hai" (habit, not emergency) from "abhi maar raha hai" (active danger).

**Session stuck after emergency.** After emergency fired, `emergency_flagged=True` was saved to DB. The router then permanently blocked the session with "Emergency flagged" reason. Fix: pass `emergency_flagged=False` to router (emergency is handled upstream before routing, so it's already resolved by the time routing happens).

---

## Phase 4 — Fine-Tuning

**The finding:** Base Gemma 4 E2B knows Indian law but doesn't format responses correctly. Only 40% of expert responses had proper citations and structure.

**Fine-tuning approach:**
- Base: `unsloth/gemma-4-E2B-it-unsloth-bnb-4bit`
- Method: LoRA r=8, alpha=8, language layers only
- Training data: 549 examples generated via OpenAI API
- Platform: Kaggle free GPU (T4)
- Training time: ~2-3 hours

**Results:**
```
Metric              Base    Fine-tuned  Delta
Pass rate           60%     93%         +33%
Structure score     0.667   0.917       +0.250
Section accuracy    0.400   0.900       +0.500
Hindi purity        1.000   0.869       -0.131
```

**The scorer bug that hid the improvement.** Initial evaluation showed fine-tuned model section_accuracy dropped from 0.40 to 0.10. The model was actually citing correctly but dropped the `Source: ` prefix: `[DV Act 2005, Section 17]` instead of `[Source: DV Act 2005, Section 17]`. Scorer regex required `Source: ` prefix. Fixed scorer to search full response text instead.

**Hindi purity regression.** Training on 549 English-session examples caused English legal terms (Protection Order, ICC, FIR) to leak into Hindi responses. Fix for next training run: separate Hindi and English examples in batches.

---

## Phase 5 — Evaluation Framework

**Challenge:** How do you measure if a legal AI is actually giving correct advice? Especially in Hindi?

**Solution:** Multi-layer scoring:
1. Structural compliance (do all 5 blocks exist?)
2. Section accuracy (are the right laws cited?)
3. Hindi purity (is Devanagari ratio > 90%?)
4. Helpline presence (correct numbers?)
5. RAGAS-style LLM judge (faithfulness, relevancy, correctness)

**Key insight:** Rule-based scoring is more interpretable for judges than pure LLM scoring. When section_accuracy = 0%, you immediately know why (missing citation format) rather than getting a vague LLM judgment score.

**RAGAS runs on Mac, not Docker.** Keeps Docker image lean. Results saved to `benchmark_v2/results/latest.json`. Admin dashboard reads this static file.

---

## Current State (May 2026)

**Working:**
- Full Kanoon Sakhi pipeline (intake → expert → follow-up)
- Emergency detection (LLM-based, calibrated)
- Hindi/English/Bengali language sessions
- Voice input (Gemma 4 audio STT) and output (Piper TTS)
- Admin dashboard with live routing logs
- Fine-tuned model (93% pass rate, 0.89 score)
- Benchmark evaluation framework

**Not working / limited:**
- Sehat Sakhi expert gives generic advice (no medical PDFs in RAG)
- Yojana Sakhi uses hardcoded scheme dictionary (no RAG query)
- Session language not persisted across sessions
- Hindi purity regression (0.87 instead of 1.0) in fine-tuned model

**Next priorities:**
1. Add medical PDFs to RAG (maternal health, NIMHANS guidelines)
2. Fix Hindi purity via prompt engineering (add legal term glossary)
3. Persist session language in SQLite
4. Create Kaggle notebook for competition submission
5. Upload training data to HuggingFace

---

## Lessons for Next Developer

1. **The thinking mode flag is everything.** If responses are blank or delayed 20+ seconds, check `--chat-template-kwargs '{"enable_thinking":false}'` first.

2. **`response_format: json_schema` may return empty.** Use `json_object` instead, combined with regex extraction. Always handle the fallback.

3. **RAG key mismatch is the silent killer.** If expert responses are generic despite having PDFs, check that the key used to query ChromaDB matches the key used to store data.

4. **Score stuck at 0 = DB read timing issue.** Re-read metadata from DB after saving user message, not before. The score from the previous turn needs to be included.

5. **Devanagari needs 1.5x max_tokens.** Hindi Devanagari tokenizes slower than English. `max_tokens=700` causes truncation. Use 900+.

6. **One llama-server at a time.** Concurrent requests queue behind each other. The app handles this gracefully but response times add up under load.
