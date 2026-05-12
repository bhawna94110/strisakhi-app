# StriSakhi — Kanoon Sakhi AI Flow
## For Developers: Complete Request Lifecycle

---

## One Paragraph Summary

Every user message in Kanoon Sakhi flows through a strict pipeline starting in `backend/app/api/legal.py`. First, `legal.py` calls `detect_emergency_llm()` in `app/emergency/detector.py` — a fast LLM call (temperature=0, max_tokens=10) that asks the model YES/NO whether the message describes violence happening RIGHT NOW; if YES and severity=critical, an emergency response streams immediately using hardcoded helpline text and the request ends. If not an emergency, the message is saved to SQLite via `app/session/session_manager.py`, the session metadata is re-read fresh from the `metadata_json` column, and `route()` in `app/agents/model_router.py` decides which agent handles the response based on the current `agent_phase` (intake/expert/follow_up), the readiness score (0-100 calculated from collected parameters), and the turn count. If the score is below 60 or it is turn 1, the INTAKE decision is returned and `run_intake_stream()` in `app/agents/intake_agent.py` is called — this makes a single non-streaming LLM call with `response_format: json_object` and a system prompt that instructs the model to extract case parameters (crime_type, urgency, relationship_to_accused, state, has_children, other_context) and return them in JSON along with a warm one-question message for the user; the JSON is extracted with a regex `{.*}` (robust to model wrapping text), merged into session metadata, and the readiness score is recalculated — if score reaches 60+ AND turn >= 2, or turn >= max_turns (admin-configurable, default 10), a `phase_change` event fires and the session moves to expert phase. When the EXPERT decision is returned, `run_legal_expert_stream()` in `app/agents/legal_agent.py` first calls `get_legal_context()` in `app/rag/legal_rag.py` which builds a crime-specific query (using `crime_type` from the case file, not the old `issue_type`) and retrieves 5 chunks from ChromaDB's `legal_documents` collection via `app/rag/retriever.py`; the frozen v1.1 expert system prompt (language instruction first AND last, 5 mandatory blocks with ━━━ headers) is assembled with the RAG context and case file injected, the model streams tokens back with `reasoning_content` filtered out, and after streaming a second quick LLM call generates 5 contextual follow-up question chips. After expert responds, the session phase is moved to `follow_up` in SQLite, and all subsequent messages route to FOLLOW_UP where `_is_followup()` detects the short message and the expert agent gives a 2-4 sentence answer instead of the full 5-block response. Throughout this flow, every routing decision, parameter extraction, RAG retrieval, phase change, and completion is logged to stdout via `log_event()` in `legal.py` and stored in an in-memory `deque(maxlen=200)` readable at `GET /api/admin/logs` — making the full pipeline inspectable in real time from the admin dashboard at `/admin.html`.

---

## File-by-File Breakdown

```
User sends message
        │
        ▼
backend/app/api/legal.py  ← Entry point for all Kanoon Sakhi requests
  │  ChatRequest(session_id, message, language)
  │
  ├─► app/emergency/detector.py → detect_emergency_llm()
  │     LLM call: YES/NO, temp=0, max_tokens=10
  │     Returns: {is_emergency, severity, reason}
  │     If CRITICAL → stream hardcoded EMERGENCY_MESSAGES[language]
  │                   + helplines overlay event
  │                   → REQUEST ENDS HERE
  │
  ├─► app/session/session_manager.py → save_message(), get_session_with_history()
  │     SQLite table: sessions (columns: id, agent_phase, metadata_json,
  │                              confidence_score, emergency_flagged)
  │     SQLite table: messages (session_id, role, content, agent_used)
  │
  ├─► app/agents/model_router.py → route()
  │     Reads: agent_phase, confidence_score, metadata, user_turn_count
  │     Returns: RouteDecision (INTAKE | EXPERT | FOLLOW_UP)
  │
  │     Routing rules (in priority order):
  │     1. phase == follow_up → FOLLOW_UP
  │     2. metadata.frustrated == True → EXPERT (skip intake)
  │     3. crime_type in [rape, acid_attack, trafficking] AND turn >= 1 → EXPERT
  │     4. score >= 90 → EXPERT immediately
  │     5. score >= 60 AND turn >= 2 → EXPERT
  │     6. turn >= intake_max_turns (admin config, default 10) → EXPERT
  │     7. Otherwise → INTAKE
  │
  ├── if INTAKE:
  │     app/agents/intake_agent.py → run_intake_stream()
  │       → run_intake() [non-streaming LLM call]
  │         System prompt: build_intake_system()
  │           - Language instruction FIRST line
  │           - 6 universal parameters to collect
  │           - Crime-specific Layer 3 params (injected if crime detected)
  │           - Current case file (already collected)
  │           - Turn count and readiness score
  │           - Language instruction LAST line
  │         LLM call: response_format=json_object, temp=0.3, max_tokens=400
  │         JSON extracted via regex r'\{.*\}' (robust to any wrapping)
  │         Returns: {message, extracted{}, ready_for_expert, frustrated, readiness_score}
  │
  │       Emits SSE events:
  │         token × N  ← streams the message character by character
  │         metadata_update ← updated case file + new readiness score
  │         phase_change ← if ready_for_expert or frustrated
  │         done
  │
  ├── if EXPERT:
  │     app/rag/legal_rag.py → get_legal_context(case_file)
  │       Uses crime_type (NOT issue_type — old bug fixed)
  │       CRIME_QUERY_MAP maps crime_type to specific legal query
  │       Queries ChromaDB collection: legal_documents (293 chunks)
  │       Returns: (formatted_context_string, citations_list)
  │
  │     app/agents/legal_agent.py → run_legal_expert_stream()
  │       _build_system() assembles frozen v1.1 prompt:
  │         [LANGUAGE_INSTRUCTION]          ← first line
  │         Senior advocate persona
  │         CASE FILE (JSON)
  │         CRIME GUIDANCE (crime-specific)
  │         LEGAL CONTEXT (RAG chunks)
  │         5 MANDATORY BLOCKS with ━━━ headers
  │         [LANGUAGE_INSTRUCTION]          ← last line (repeat)
  │       LLM call: streaming, temp=0.2, max_tokens=900
  │         reasoning_content tokens filtered (thinking mode tokens)
  │         content tokens streamed to frontend
  │       After streaming: second quick LLM call generates 5 follow-up chips
  │
  │       Emits SSE events:
  │         rag_retrieved ← citations array
  │         token × N ← expert response words
  │         done ← with follow_up_questions array
  │
  │     Session phase updated to follow_up in SQLite
  │
  └── if FOLLOW_UP:
        app/agents/legal_agent.py → run_legal_expert_stream()
          _is_followup() detects short message (< 60 chars + follow-up keywords)
          _build_system() returns short system (250 tokens max)
          "Answer ONLY what they asked in 2-4 sentences"
          Same RAG context reused
```

---

## SSE Event Types (frontend receives these)

```
routing        → {decision, reason, turn, score}   ← admin logs use this
emergency      → {data: {message, helplines}}       ← triggers overlay
token          → {token, agent}                     ← streams text
metadata_update→ {confidence_score, metadata}       ← updates case file display
phase_change   → {from, to}                         ← intake→expert transition
citations      → {citations: [{source, section}]}   ← shown below response
done           → {full_response, agent, follow_up_questions, response_ms}
metrics        → {ram_used_gb, ram_percent}         ← admin monitoring
error          → {message}                          ← error handling
```

---

## Known Issues / Active Work

```
1. response_format: json_object added back to intake
   — if llama.cpp build still returns empty, falls back to prompt-based JSON
   — regex extraction handles both cases

2. Emergency sensitivity calibrated for "happening NOW" not general violence
   — "मेरा पति मुझे मारता है" → NOT emergency (habit, not active)
   — "मेरा पति अभी मार रहा है" → IS emergency

3. RAG chunks for property/dowry/maintenance/divorce/stalking are thin
   — ChromaDB has 293 chunks but mostly DV Act + POSH Act
   — Need to ingest Hindu Succession Act, CrPC 125, Hindu Marriage Act PDFs
   — Until then, those crime types may cite wrong sections

4. prompt_builder.py is deprecated dead code
   — Replaced with stub that raises NotImplementedError
   — Safe to delete once confirmed no imports

5. max_tokens raised to 900 for Hindi Devanagari tokenization
   — Devanagari ~1.5 tokens/word vs English ~1.0 tokens/word
   — 700 was causing truncation mid-timeline
```

---

## Admin Dashboard

- Live logs: `GET /api/admin/logs` → returns last 200 events from `EVENT_LOG` deque in `legal.py`
- Session debug: `GET /api/admin/session/{id}` → returns phase, metadata, score
- Settings: `POST /api/admin/settings` → writes to `config_runtime.json`, read by `get_runtime_config()` in `model_router.py`
- Admin UI: `frontend/public/admin.html` → polls logs every 5s, shows routing decisions in real time
