"""
Kanoon Sakhi — Legal Expert Agent
5-block response: Empathy → Rights → Action Timeline → Helpline → Follow-up
RAG-grounded: never invents section numbers.
Language-aware: Hindi/English/Bengali.
"""
import requests
import json
from app.config import settings
from app.rag.legal_rag import get_legal_context
from typing import AsyncGenerator

LANGUAGE_INSTRUCTIONS = {
    "hi": "🔴 CRITICAL — LANGUAGE RULE: Sirf Devanagari lipi mein jawab do. Roman script BILKUL nahi. Agar koi Hinglish mein likhti hai, aap Devanagari mein jawab do.",
    "en": "🔴 CRITICAL — LANGUAGE RULE: Respond ONLY in English. Never use Hindi, Devanagari, or any other script.",
    "bn": "🔴 CRITICAL — LANGUAGE RULE: Sudhu Bangla lipi te uttor dao. Roman ba Hindi lipi kokhono byabohar koro na.",
}

# Crime-specific guidance injected into prompt
CRIME_GUIDANCE = {
    "domestic_violence": """
Primary law: DV Act 2005. Key sections: 17 (residence right), 18 (protection order), 19 (residence order), 20 (monetary relief), 12 (application to magistrate).
Always mention: Protection Officer (free help), Magistrate application (no lawyer needed, case heard within 3 days).
Today's action: Call 181, go to nearest police station or Protection Officer.
NEVER say: "talk to husband", "family matter", "try to compromise".
""",
    "dowry": """
Primary law: Dowry Prohibition Act 1961, IPC 498A (cruelty by husband/relatives), IPC 304B (dowry death).
Key fact: Demanding dowry is a CRIMINAL offence. Giving is also illegal.
Always mention: 498A is cognizable — police can arrest without warrant.
Today's action: File FIR at police station, call 181.
""",
    "property": """
Primary law: Hindu Succession Act 1956, amended 2005. Supreme Court: Vineeta Sharma v Rakesh Sharma (2020).
Key right: Daughters have EQUAL coparcenary rights from birth — even if father died before 2005.
Always cite: SC 2020 judgment by name — very powerful and often unknown.
Today's action: Collect birth certificate + father's documents, call DLSA 15100.
""",
    "rape": """
Primary law: IPC 376, Criminal Law Amendment Act 2013.
Key rights: FIR MUST be registered (police cannot refuse). No two-finger test. Free medical examination. Compensation scheme.
Always mention: One Stop Centre (call 181), 1091 women in distress helpline.
Today's action: Call 181 immediately, go to hospital first (free examination).
""",
    "divorce": """
Primary law: Hindu Marriage Act 1955, CrPC Section 125 (maintenance), Muslim Women Protection Act 1986.
Key right: Maintenance can be claimed WITHOUT filing for divorce (CrPC 125). No court fee. Interim relief within 60 days.
Always clarify: Maintenance ≠ divorce. She can ask for maintenance while still married.
Today's action: Apply at Family Court (no fee), call DLSA 15100 for free lawyer.
""",
    "workplace": """
Primary law: POSH Act 2013.
Key rights: ICC mandatory for 10+ employees. Cannot be fired for complaining. Complaint within 3 months (extendable).
Always mention: If no ICC → file with District Officer. Transfer can be requested during inquiry.
Today's action: Written complaint to HR/ICC, document all incidents with dates.
""",
    "stalking": """
Primary law: IPC 354D (stalking), IT Act 66E (privacy), IT Act 67 (obscene content).
Key fact: Online harassment IS a criminal offence. Police can act.
Always mention: National Cyber Crime helpline 1930, screenshot and save all evidence.
Today's action: Call 1930, file complaint at cybercrime.gov.in.
""",
    "acid_attack": """
Primary law: IPC 326A (acid attack), IPC 326B (attempt to throw acid).
Key rights: Hospitals CANNOT refuse treatment. Minimum Rs 3 lakh compensation (NALSA scheme). Fast-track court.
Always mention: Acid Survivors Foundation India (ASFI), NALSA acid attack compensation scheme.
Today's action: Emergency medical care first (any hospital must treat), call 181.
""",
    "custody": """
Primary law: Guardian and Wards Act 1890, Hindu Minority and Guardianship Act 1956.
Key right: Mother gets natural custody of children under 5. Best interest of child is the court's primary consideration.
Always clarify: Father threatening "I will take children" is often legally false.
Today's action: Apply for interim custody at Family Court, call DLSA 15100.
""",
    "trafficking": """
Primary law: IPC 366 (abduction for forced marriage), Immoral Traffic Prevention Act (ITPA), Prohibition of Child Marriage Act 2006.
Key right: Any marriage of girl under 18 is voidable. Forced marriage at any age is criminal.
Always mention: Anti-trafficking helpline 1800-419-8588 (free), CHILDLINE 1098.
Today's action: Call 1800-419-8588 immediately, contact nearest police station.
""",
}

ACTION_TIMELINE_INSTRUCTION = {
    "hi": """Har response mein yeh timeline zaroor dein (Devanagari mein):
**अभी (Right Now):** [1 immediate step]
**आज (Today):** [1-2 steps within 24 hours]
**इस हफ्ते (This Week):** [1 longer term step]""",
    "en": """Include this timeline in every response:
**Right Now:** [1 immediate step]
**Today:** [1-2 steps within 24 hours]
**This Week:** [1 longer term step]""",
    "bn": """Protiti response e ei timeline diye dio:
**এখনই (Right Now):** [1 immediate step]
**আজ (Today):** [1-2 steps]
**এই সপ্তাহে (This Week):** [1 step]""",
}

FOLLOWUP_WORDS = [
    "han", "haan", "yes", "okay", "ok", "theek", "acha", "sure", "hmm",
    "kaise", "aur", "phir", "batao", "explain", "matlab", "next",
    "samjha nai", "details", "more", "aage", "then what",
]


async def run_legal_expert_stream(
    case_file: dict,
    conversation_history: list,
    language: str = "hi"
) -> AsyncGenerator[dict, None]:

    rag_context, citations = get_legal_context(case_file)
    yield {"type": "rag_retrieved", "citations": citations, "chunk_count": len(citations)}

    lang_instruction = LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS["en"])
    timeline_instruction = ACTION_TIMELINE_INSTRUCTION.get(language, ACTION_TIMELINE_INSTRUCTION["en"])
    crime_type = case_file.get("crime_type", "general")
    crime_guidance = CRIME_GUIDANCE.get(crime_type, "")

    last_user = ""
    for m in reversed(conversation_history):
        if m.get("role") == "user":
            last_user = m.get("content", "")
            break

    is_followup = (
        any(w in last_user.lower() for w in FOLLOWUP_WORDS)
        and len(last_user.strip()) < 50
    )

    history_text = "\n".join([
        f"{'User' if m['role']=='user' else 'Sakhi'}: {m['content']}"
        for m in conversation_history[-8:]
        if m.get("content")
    ])

    if is_followup:
        system = f"""{lang_instruction}

You are Kanoon Sakhi — legal companion for Indian women.
The user is asking a follow-up question. Answer ONLY what they asked in 2-4 sentences.
Do NOT repeat the full legal advice already given.
If they say yes to free lawyer → give NALSA number 15100 and 3 steps to get it.

Case: {json.dumps(case_file, ensure_ascii=False)}
Conversation: {history_text}

FINAL REMINDER: {lang_instruction}"""
        max_tokens = 250
    else:
        system = f"""{lang_instruction}

You are Kanoon Sakhi — a confident, warm legal advocate for Indian women.

CRIME-SPECIFIC GUIDANCE:
{crime_guidance}

RESPONSE STRUCTURE (follow exactly):
1. ONE empathy sentence — acknowledge her pain first
2. HER RIGHTS — 2-3 most important rights, cite law: [Source: Act Name, Section X]
3. ACTION TIMELINE:
{timeline_instruction}
4. ONE free helpline with number
5. End with: offer of free lawyer

CRITICAL RULES:
- Use ONLY the legal context below — never invent section numbers
- Under 350 words total
- Simple language, NOT legal jargon
- Never say "consult a lawyer" without also giving NALSA 15100 (it's free)

LEGAL CONTEXT FROM RAG:
{rag_context}

CASE FILE: {json.dumps(case_file, ensure_ascii=False)}

CONVERSATION:
{history_text}

FINAL REMINDER: {lang_instruction}"""
        max_tokens = 700

    # Generate follow-up questions via separate call
    followup_prompt = f"""Based on this legal case:
Case type: {crime_type}
Last response was about: {case_file}
Language: {language}

Generate exactly 5 short follow-up questions this woman might ask next.
Write them in {language} language.
Output as JSON array only: ["question1", "question2", "question3", "question4", "question5"]
Make them specific to her situation, not generic."""

    payload = {
        "model": "gemma4",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": last_user}
        ],
        "stream": True,
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "top_p": 0.95,
        # Enable thinking for expert agent — deeper reasoning = better legal advice
        # Capped at ~15 seconds via frontend animation
        "chat_template_kwargs": {"enable_thinking": not is_followup},
    }

    full_response = ""
    try:
        r = requests.post(
            f"{settings.ollama_base_url}/v1/chat/completions",
            json=payload, stream=True, timeout=120
        )
        for line in r.iter_lines():
            if not line:
                continue
            line_str = line.decode() if isinstance(line, bytes) else line
            if not line_str.startswith("data: "):
                continue
            data_str = line_str[6:]
            if data_str == "[DONE]":
                break
            try:
                delta = json.loads(data_str)["choices"][0]["delta"]
                # llama.cpp returns thinking in 'reasoning_content' field
                thinking = delta.get("reasoning_content", "") or ""
                token = delta.get("content", "") or ""
                if thinking:
                    yield {"type": "thinking", "thinking": thinking}
                if token:
                    if "<think>" in token or "</think>" in token:
                        continue
                    full_response += token
                    yield {"type": "token", "token": token, "agent": "expert"}
            except Exception:
                continue
    except Exception as e:
        yield {"type": "error", "message": str(e)}
        return

    if not full_response.strip():
        fallback = {"hi": "Maafi chahti hoon, dobara try karein.", "en": "Sorry, please try again."}.get(language, "Please try again.")
        full_response = fallback
        yield {"type": "token", "token": full_response, "agent": "expert"}

    # Generate follow-up questions (non-streaming, quick call)
    followup_questions = []
    if not is_followup:
        try:
            fq_r = requests.post(
                f"{settings.ollama_base_url}/v1/chat/completions",
                json={
                    "model": "gemma4",
                    "messages": [{"role": "user", "content": followup_prompt}],
                    "stream": False,
                    "temperature": 0.4,
                    "max_tokens": 200,
                },
                timeout=30
            )
            fq_text = fq_r.json()["choices"][0]["message"]["content"].strip()
            # Parse JSON array
            match = __import__("re").search(r'\[.*?\]', fq_text, __import__("re").DOTALL)
            if match:
                followup_questions = json.loads(match.group())[:5]
        except Exception:
            # Hardcoded fallbacks if LLM call fails
            if language == "hi":
                followup_questions = [
                    "Protection order kaise milega?",
                    "FIR kaise file karein?",
                    "Muft vakeel kahan milega?",
                    "Ghar mein rehne ka hak kaise prove karein?",
                    "Bacchon ki custody ke baare mein?",
                ]
            else:
                followup_questions = [
                    "How do I get a protection order?",
                    "How do I file an FIR?",
                    "Where can I get a free lawyer?",
                    "What documents do I need?",
                    "What if police don't help?",
                ]

    yield {
        "type": "done",
        "full_response": full_response,
        "citations": citations,
        "agent": "expert",
        "follow_up_questions": followup_questions,
    }
