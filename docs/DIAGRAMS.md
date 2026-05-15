# StriSakhi — Architecture Diagrams
## Mermaid code for all diagrams

---

## 1. System Architecture

```mermaid
graph TB
    User["👤 User Browser\nhttp://localhost:5173"]
    
    subgraph Docker["Docker Compose"]
        FE["nyay-vani-frontend\nReact + Vite\nport 5173"]
        BE["nyay-vani-backend\nFastAPI\nport 8000"]
        SQLite["SQLite\nnyay_vani.db\nsessions + messages"]
        ChromaDB["ChromaDB\nembedded\n293 legal chunks"]
        Piper["Piper TTS\nbinary\nhi: priyamvada\nen: amy"]
    end
    
    subgraph MacNative["Mac Native (Metal GPU)"]
        LLM["llama-server\nport 8080\nGemma 4 E2B Q4_K_M\n3.2GB | ~41 tok/sec"]
        mmproj["mmproj Q8_0\n532MB\naudio STT"]
    end
    
    User -->|HTTP / SSE| FE
    FE -->|HTTP / SSE| BE
    BE <--> SQLite
    BE <--> ChromaDB
    BE <--> Piper
    BE -->|"HTTP host.docker.internal:8080"| LLM
    LLM --- mmproj
```

---

## 2. Kanoon Sakhi State Machine

```mermaid
stateDiagram-v2
    [*] --> EMERGENCY_CHECK
    
    EMERGENCY_CHECK --> EMERGENCY_STATE : YES + critical
    EMERGENCY_CHECK --> INTAKE : NO
    
    EMERGENCY_STATE --> INTAKE : session continues
    
    INTAKE --> INTAKE : score < 60\nOR turn < 2
    INTAKE --> EXPERT : score ≥ 90\nOR (score ≥ 60 AND turn ≥ 2)\nOR turn ≥ max_turns\nOR frustrated\nOR rape/acid_attack/trafficking
    
    EXPERT --> FOLLOW_UP : after first response
    FOLLOW_UP --> FOLLOW_UP : all subsequent messages
    
    note right of EMERGENCY_CHECK
        LLM call
        YES/NO only
        temp=0, max_tokens=10
        200ms
    end note
    
    note right of INTAKE
        JSON parameter extraction
        crime_type, urgency, relationship
        readiness_score 0-100
        max turns: admin configurable (default 10)
    end note
    
    note right of EXPERT
        RAG: 5 ChromaDB chunks
        Frozen v1.1 prompt
        5 mandatory blocks
        max_tokens: 900
    end note
    
    note right of FOLLOW_UP
        Short answers only
        max_tokens: 250
        2-4 sentences
    end note
```

---

## 3. Request Lifecycle — Full Pipeline

```mermaid
sequenceDiagram
    participant U as User Browser
    participant FE as Frontend (React)
    participant BE as Backend (FastAPI)
    participant DB as SQLite
    participant EM as Emergency Detector
    participant RT as Model Router
    participant IA as Intake Agent
    participant RA as RAG (ChromaDB)
    participant EA as Expert Agent
    participant LLM as llama-server (Mac)

    U->>FE: Type message / voice
    FE->>BE: POST /api/legal/chat
    BE->>DB: load session + metadata
    BE->>EM: detect_emergency_llm(message)
    EM->>LLM: YES/NO call (200ms)
    LLM-->>EM: NO
    EM-->>BE: {is_emergency: false}
    BE->>DB: save user message
    BE->>DB: re-read fresh metadata
    BE->>RT: route(phase, score, metadata)
    RT-->>BE: INTAKE decision

    BE->>IA: run_intake_stream(history, metadata)
    IA->>LLM: json_object call (temp=0.3)
    LLM-->>IA: {message, extracted, ready_for_expert}
    IA-->>BE: token events + metadata_update

    Note over BE,FE: SSE: token events stream to browser
    BE->>DB: update metadata_json
    BE-->>FE: SSE phase_change (intake→expert)
    
    BE->>RA: get_legal_context(case_file)
    RA-->>BE: 5 chunks + citations
    BE->>EA: run_legal_expert_stream(case_file, history)
    EA->>LLM: streaming call (temp=0.2, max_tokens=900)
    
    loop Stream tokens
        LLM-->>EA: token
        EA-->>BE: {"type":"token","token":"..."}
        BE-->>FE: SSE token
        FE-->>U: append to bubble
    end
    
    EA->>LLM: follow-up questions call
    LLM-->>EA: ["q1","q2","q3","q4","q5"]
    BE->>DB: save assistant message + citations
    BE-->>FE: SSE done event
    FE-->>U: show 🔊 button + follow-up chips
    BE->>DB: update phase to follow_up
```

---

## 4. AI Flow — Kanoon Sakhi Agents

```mermaid
flowchart TD
    MSG["User Message"] --> EC

    EC{"Emergency Check\nLLM: YES/NO\n200ms, temp=0"}
    EC -->|"YES + critical"| EM["🚨 EMERGENCY\nHardcoded helplines\n181 / 100 / 1091\nSession continues after"]
    EC -->|NO| PH{"Current Phase?"}

    PH -->|intake| IA
    PH -->|expert| EA
    PH -->|follow_up| FU

    subgraph INTAKE["Intake Agent — intake_agent.py"]
        IA["run_intake()\njson_object format\ntemp=0.3, max=400"]
        SC["Calculate readiness_score\ncrime_type=30\nurgency=30\nrelationship=30\noptional=5each"]
        RT{"Route?"}
        IA --> SC --> RT
        RT -->|"score≥90\nOR score≥60 AND turn≥2\nOR turn≥max_turns\nOR frustrated"| GOTO_EX["→ EXPERT"]
        RT -->|collecting| ASK["Ask next question\n1 per turn\nwarm + empathetic"]
    end

    subgraph EXPERT["Expert Agent — legal_agent.py"]
        EA["run_legal_expert_stream()"]
        RAG["legal_rag.get_legal_context()\nCrimeType → ChromaDB query\n5 chunks returned"]
        SYS["_build_system()\nFrozen v1.1 prompt\nLanguage instruction ×2\n5 mandatory blocks"]
        STREAM["Streaming LLM call\ntemp=0.2, max=900\nthinking OFF"]
        FQS["Follow-up questions\nSeparate quick call\n5 chips generated"]
        EA --> RAG --> SYS --> STREAM --> FQS
        FQS --> SAVE_EX["Save to DB\nUpdate phase→follow_up"]
    end

    subgraph FOLLOWUP["Follow-up Handler"]
        FU["_is_followup() detects\nshort message + keywords\nmax=250, 2-4 sentences"]
    end

    GOTO_EX --> EA
```

---

## 5. Performance Optimization Architecture

```mermaid
graph LR
    subgraph Problem["❌ Original Architecture (55+ sec)"]
        P1["User message"] --> P2["Docker → Ollama API"]
        P2 --> P3["Thinking mode enabled\n20-55 sec blank screen"]
        P3 --> P4["2-3ms per token\nDocker network overhead"]
    end

    subgraph Solution["✅ Optimized Architecture (~1 sec)"]
        S1["User message"] --> S2["Docker → host.docker.internal:8080"]
        S2 --> S3["llama-server native\nMetal GPU M2"]
        S3 --> S4["enable_thinking=false\nImmediate content stream"]
        S4 --> S5["41 tok/sec\n~1 sec first token"]
    end

    subgraph ModelChoice["Model Selection for Resource Constraints"]
        M1["Gemma 4 E2B Q4_K_M\n3.2GB — main LLM + STT"]
        M2["mmproj Q8_0\n532MB — audio processing"]
        M3["Piper binary\n61MB — Hindi/English TTS"]
        M4["ChromaDB embedded\n~80MB model auto-download"]
        M5["Total: ~4GB models\nFits in 16GB RAM with Docker"]
        M1 --- M2 --- M3 --- M4 --- M5
    end

    subgraph Avoided["Libraries Avoided (size reasons)"]
        A1["sentence-transformers\n2GB+ with torch ❌"]
        A2["piper-tts pip package\n1.5GB with cuda ❌"]
        A3["faster-whisper\n150MB + model ❌"]
        A4["edge-tts\nInternet required ❌"]
    end
```

---

## 6. Fine-tuning Pipeline

```mermaid
flowchart LR
    subgraph Data["Training Data"]
        D1["OpenAI API\ngenerates 549 examples"]
        D2["ShareGPT format\nsystem + user + assistant"]
        D3["5 crime types\nHindi + English\nvaried states/scenarios"]
        D1 --> D2 --> D3
    end

    subgraph Training["Fine-tuning on Kaggle"]
        T1["Base: unsloth/gemma-4-E2B-it-unsloth-bnb-4bit"]
        T2["LoRA r=8, alpha=8\nlanguage layers only\nT4 GPU free tier"]
        T3["3 epochs\n~2-3 hours\nloss: 13-15 normal"]
        T1 --> T2 --> T3
    end

    subgraph Export["Export + Deploy"]
        E1["save_pretrained_gguf\nQ4_K_M quantization"]
        E2["Upload to HuggingFace\nsnake4u1/strisakhi-gemma4-lora"]
        E3["llama-server\nsame flags as base model"]
        E1 --> E2 --> E3
    end

    subgraph Results["Benchmark Results"]
        R1["Pass rate: 60% → 93%\n+33%"]
        R2["Structure: 0.667 → 0.917\n+25%"]
        R3["Citations: 0.400 → 0.900\n+50%"]
        R4["Scorer bug fixed:\n[DV Act 2005, Section 17]\nvs [Source: DV Act 2005, Section 17]"]
    end

    Data --> Training --> Export --> Results
```

---

## 7. Admin Dashboard Flow

```mermaid
flowchart TD
    AD["Admin Dashboard\nadmin.html"] --> AUTH{"PIN: 1234"}
    AUTH -->|wrong| DENY["Access Denied"]
    AUTH -->|correct| TABS

    subgraph TABS["Four Tabs"]
        T1["⚙️ System\nRAM / CPU / Model status\nChromaDB counts\nPiper voice status"]
        T2["🧠 AI Flow\nLive routing decisions\nCurrent session state\nParameter collection progress\nScore display"]
        T3["📋 Logs\nReal-time event stream\nPolls /api/admin/logs\nevery 5 seconds\n200 events in memory"]
        T4["🔧 Settings\nintake_max_turns slider\ntts_speed_hi / tts_speed_en\ntemperature\nNo restart required"]
    end

    T3 --> EB["In-memory deque\nEVENT_LOG maxlen=200\nin legal.py"]
    T4 --> CF["config_runtime.json\nRead on every request\nWrite via POST /api/admin/settings"]

    EB --> ICONS["Log icons:\n🔍 INTAKE\n⚡ EXPERT\n🚨 EMERGENCY\n📚 RAG retrieval\n🔀 ROUTING\n→  PHASE CHANGE\n✅ DONE\n❌ ERROR"]
```

---

## 8. Dynamic Prompt Engineering

```mermaid
flowchart TD
    REQ["Incoming request\n{session_id, message, language}"]

    REQ --> LANG["Language Config\nSingle source of truth\nhi / en / bn\nInstruction injected FIRST + LAST"]

    LANG --> PHASE{"Current Phase?"}

    PHASE -->|intake| IP
    PHASE -->|expert| EP
    PHASE -->|follow_up| FP

    subgraph IP["Intake Prompt — dynamic"]
        I1["Language instruction ×1"]
        I2["Persona: warm intake specialist"]
        I3["Parameters to collect\n(base: crime_type, urgency, relationship)\n+crime-specific Layer 3\n(injected based on detected crime_type)"]
        I4["Current case file\n(already collected — do NOT ask again)"]
        I5["Turn: X of MAX | Score: Y/100"]
        I6["Ready-for-expert conditions"]
        I7["JSON output schema\n(no markdown, no explanation)"]
        I8["Language instruction ×2"]
        I1 --> I2 --> I3 --> I4 --> I5 --> I6 --> I7 --> I8
    end

    subgraph EP["Expert Prompt — frozen v1.1"]
        E1["Language instruction ×1"]
        E2["Persona: 20yr senior advocate"]
        E3["Case file JSON\n(intake output)"]
        E4["Crime-specific guidance block\n(CRIME_GUIDANCE dict)"]
        E5["RAG context\n(5 ChromaDB chunks)"]
        E6["Conversation history\n(last 8 turns)"]
        E7["5 mandatory blocks\n(━━━ headers enforce structure)"]
        E8["Rules: 400 words max\nno lawyer without 15100"]
        E9["Language instruction ×2"]
        E1 --> E2 --> E3 --> E4 --> E5 --> E6 --> E7 --> E8 --> E9
    end

    subgraph FP["Follow-up Prompt — short"]
        F1["Language instruction ×1"]
        F2["Persona: answering follow-up only"]
        F3["Case file + conversation"]
        F4["Answer in 2-4 sentences\nmax_tokens: 250"]
        F5["Language instruction ×2"]
        F1 --> F2 --> F3 --> F4 --> F5
    end

    subgraph WHY["Why Language Instruction ×2?"]
        W1["Gemma 4 attends to beginning\nAND end of prompt most strongly"]
        W2["Middle gets diluted with long prompts"]
        W3["Repeating at end re-enforces\nDevanagari output rule"]
        W4["Result: 0.87-1.0 Hindi purity\nvs ~0.6 without repetition"]
        W1 --> W2 --> W3 --> W4
    end
```

---

## 9. TTS Pipeline

```mermaid
flowchart TD
    TTS["POST /api/voice/tts\n{text, lang}"]

    TTS --> LANG_CHECK{"Language\nsupported?"}
    LANG_CHECK -->|"bn / others"| NO_TTS["Return 204\nNo audio"]
    LANG_CHECK -->|"hi / en"| CLEAN

    CLEAN["clean_text()\n- Remove emoji\n- Strip [Source: ...] citations\n- Remove markdown bold/italic\n- Remove numbered list prefixes\n- Collapse whitespace\n- Limit to 450 chars (~30 sec audio)"]

    CLEAN --> SPEED["Read tts_speed from\nconfig_runtime.json\n(admin can change without restart)"]

    SPEED --> LANG_ROUTE{"Language?"}

    LANG_ROUTE -->|Hindi| DEVA_CHECK{"is_devanagari()?\nDevanagari chars / total\n> 50%?"}
    LANG_ROUTE -->|English| PIPER_EN["Piper Amy\nen_US-amy-medium.onnx\nspeed: 1.0"]

    DEVA_CHECK -->|"Yes — pure Devanagari"| PIPER_HI
    DEVA_CHECK -->|"No — Hinglish/Roman"| CONVERT["convert_to_devanagari()\nGemma 4 LLM call\n'Convert to Devanagari only'\n~500ms extra"]

    CONVERT --> PIPER_HI["Piper Priyamvada\nhi_IN-priyamvada-medium.onnx\nspeed: 0.85 (20% slower = clearer)"]

    PIPER_HI --> SUBPROCESS["subprocess: echo text | piper -m model -f out.wav\nasyncio.run_in_executor (non-blocking)\n~100-300ms generation"]
    PIPER_EN --> SUBPROCESS

    SUBPROCESS --> WAV["Return audio/wav\nbinary response"]
    WAV --> BROWSER["Frontend: URL.createObjectURL\nnew Audio(url).play()"]

    subgraph WHY_PIPER["Why Piper over alternatives"]
        P1["edge-tts: best quality BUT needs internet ❌"]
        P2["Kokoro-ONNX: offline BUT Western accent ❌"]
        P3["Parler AI4Bharat: Indian accent BUT fairseq\nfails on Python 3.12 ❌"]
        P4["piper-tts pip: pulls PyTorch 800MB ❌"]
        P5["Piper binary: 61MB, offline, Indian accent ✅"]
        P1 --> P5
        P2 --> P5
        P3 --> P5
        P4 --> P5
    end
```
