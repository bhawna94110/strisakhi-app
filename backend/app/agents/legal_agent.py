"""
Kanoon Sakhi — Legal Expert Agent (frozen prompt v1.1)
5-block response: Empathy → Rights → Timeline → Helpline → Follow-up
RAG-grounded: never invents section numbers.
Thinking OFF (faster, consistent formatting).
"""
import json
import re
import requests
from app.config import settings
from app.rag.legal_rag import get_legal_context
from typing import AsyncGenerator

# ─── Language Instructions ────────────────────────────────────────────────────
LANGUAGE_INSTRUCTIONS = {
    "hi": (
        "🔴 CRITICAL LANGUAGE RULE: "
        "Sirf Devanagari lipi mein jawab do. "
        "KABHI BHI Roman/English script mat use karo Hindi shabdon ke liye."
    ),
    "en": (
        "🔴 CRITICAL LANGUAGE RULE: "
        "Respond ONLY in English. "
        "Never use Hindi, Devanagari, or any other script."
    ),
    "bn": (
        "🔴 CRITICAL LANGUAGE RULE: "
        "Sudhu Bangla lipi te uttor dao. "
        "Roman ba Hindi lipi kokhono byabohar koro na."
    ),
}

# ─── Timeline format per language ─────────────────────────────────────────────
TIMELINE_FORMAT = {
    "hi": "**अभी (Right Now):** [1 step]\n**आज (Today):** [1-2 steps]\n**इस हफ्ते (This Week):** [1 step]",
    "en": "**Right Now:** [1 step]\n**Today:** [1-2 steps]\n**This Week:** [1 step]",
    "bn": "**এখনই (Right Now):** [1 step]\n**আজ (Today):** [1-2 steps]\n**এই সপ্তাহে (This Week):** [1 step]",
}

# ─── Crime-specific guidance blocks ──────────────────────────────────────────
CRIME_GUIDANCE = {
    "domestic_violence": """
Key law: DV Act 2005
Critical sections: 17 (residence right), 18 (protection order), 19 (residence order), 20 (monetary relief), 12 (Magistrate application)
Key facts: Woman CANNOT be evicted from shared household. Magistrate must hear within 3 days. Protection Officer in every district is FREE.
Helpline: 181
NEVER say: "talk to husband", "family matter", "compromise"
""",
    "property": """
Key law: Hindu Succession Act 1956 (Amendment 2005)
Critical case: Vineeta Sharma v. Rakesh Sharma, Supreme Court 2020
Key facts: Daughters have EQUAL coparcenary rights from birth (Section 6). Applies even if father died before 2005. Applies to agricultural land in most states.
Helpline: 15100
""",
    "dowry": """
Key law: Dowry Prohibition Act 1961, IPC 498A, IPC 304B
Key facts: Demanding dowry is CRIMINAL (Dowry Prohibition Act Section 3). IPC 498A cognizable — police can arrest without warrant. Dowry death = IPC 304B minimum 7 years.
Helpline: 181, 100
""",
    "maintenance": """
Key law: CrPC Section 125
Key facts: Maintenance WITHOUT divorce is possible. No court fee. Interim maintenance within 60 days. Amount based on husband's income.
Helpline: 15100
""",
    "divorce": """
Key law: Hindu Marriage Act 1955 (Section 13), CrPC Section 125
Key facts: Grounds include cruelty, desertion, adultery. Maintenance can be claimed separately via CrPC 125 without divorce.
Helpline: 15100
""",
    "workplace": """
Key law: POSH Act 2013
Critical sections: 4 (ICC mandatory for 10+ employees), 9 (3 month complaint window), 11 (no retaliation)
Key facts: ICC required for 10+ employees. Cannot be fired for complaining. District Officer if no ICC.
Helpline: 15100
""",
    "stalking": """
Key law: IPC 354D (stalking), IT Act 66E (privacy), IT Act 67 (obscene content)
Key facts: Online harassment IS criminal. Screenshot all evidence. Police can act immediately.
Helpline: 1930 (cyber crime)
""",
    "rape": """
Key law: IPC 376, Criminal Law Amendment Act 2013
Key facts: FIR MUST be registered — police cannot refuse. No two-finger test. Free medical examination. Compensation available.
Helpline: 181, 1091
""",
    "acid_attack": """
Key law: IPC 326A, IPC 326B
Key facts: Hospitals CANNOT refuse treatment. Minimum Rs 3 lakh compensation (NALSA scheme). Fast-track court.
Helpline: 181
""",
    "custody": """
Key law: Guardian and Wards Act 1890, Hindu Minority and Guardianship Act 1956
Key facts: Mother gets natural custody of children under 5. Best interest of child is paramount.
Helpline: 15100
""",
    "trafficking": """
Key law: IPC 366, Immoral Traffic Prevention Act (ITPA), Prohibition of Child Marriage Act 2006
Key facts: Any marriage of girl under 18 is voidable. Anti-trafficking helpline 1800-419-8588.
Helpline: 1800-419-8588, 1098
""",
}

# ─── Follow-up words (detect short follow-up questions) ─────────────────────
FOLLOWUP_WORDS = [
    "han", "haan", "yes", "okay", "ok", "theek", "acha", "sure",
    "kaise", "aur", "phir", "batao", "explain", "matlab",
    "samjha nai", "more", "aage", "then", "next", "details",
    "NALSA", "vakeel", "kahan", "kitna", "how long", "what if",
]


def _is_followup(last_user: str) -> bool:
    text = last_user.lower().strip()
    if len(text) < 60:
        return any(w in text for w in FOLLOWUP_WORDS)
    return False


def _build_system(
    case_file: dict,
    rag_context: str,
    history_text: str,
    language: str,
    is_followup: bool,
) -> tuple[str, int]:
    lang_instruction = LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS["en"])
    crime_type = case_file.get("crime_type", "general")
    guidance = CRIME_GUIDANCE.get(crime_type, "")
    timeline = TIMELINE_FORMAT.get(language, TIMELINE_FORMAT["en"])

    if is_followup:
        system = f"""{lang_instruction}

You are Kanoon Sakhi — answering a follow-up question.
The user already received full legal advice. Answer ONLY their specific question in 2-4 sentences.
Do NOT repeat the full legal advice. If they ask about free lawyer → give NALSA 15100 + 3 steps.

CASE FILE: {json.dumps(case_file, ensure_ascii=False)}
CONVERSATION: {history_text}

FINAL REMINDER: {lang_instruction}"""
        return system, 250

    system = f"""{lang_instruction}

You are a senior Indian legal advocate with 20 years of experience
in district courts across India, specializing in women's rights.
You speak like a knowledgeable older sister — warm but authoritative.

CASE FILE: {json.dumps(case_file, ensure_ascii=False)}

CRIME-SPECIFIC GUIDANCE:
{guidance}

LEGAL CONTEXT (USE ONLY THIS — never invent section numbers):
{rag_context}

CONVERSATION HISTORY:
{history_text}

YOU MUST RESPOND WITH ALL 5 BLOCKS BELOW. DO NOT SKIP ANY BLOCK.

━━━ BLOCK 1: EMPATHY (1 sentence) ━━━
Reference something specific from her case file. Make it personal, not generic.

━━━ BLOCK 2: HER RIGHTS (2-3 rights) ━━━
Each right on its own line:
[Source: Act Name, Section X] explanation in simple words
[Source: Act Name, Section Y] explanation in simple words
ONLY cite sections present in LEGAL CONTEXT above. Never invent section numbers.

━━━ BLOCK 3: ACTION TIMELINE (all 3 lines required) ━━━
{timeline}

━━━ BLOCK 4: FREE HELPLINE (exactly 1) ━━━
📞 [NUMBER] — [what it does] ([hours])

━━━ BLOCK 5: FOLLOW-UP QUESTION (exactly 1) ━━━
End with one specific question relevant to her case.

RULES:
- Under 400 words total
- Simple language — no legal jargon
- Never say "consult a lawyer" without giving NALSA 15100 (free)
- ALL 5 BLOCKS REQUIRED — a response missing any block is incomplete

FINAL REMINDER: {lang_instruction}"""
    return system, 900


async def run_legal_expert_stream(
    case_file: dict,
    conversation_history: list,
    language: str = "hi",
) -> AsyncGenerator[dict, None]:

    # RAG retrieval
    rag_context, citations = get_legal_context(case_file)
    yield {"type": "rag_retrieved", "citations": citations, "chunk_count": len(citations)}

    last_user = next(
        (m["content"] for m in reversed(conversation_history) if m.get("role") == "user"),
        ""
    )
    is_followup = _is_followup(last_user)

    history_text = "\n".join([
        f"{'User' if m['role'] == 'user' else 'Sakhi'}: {m['content']}"
        for m in conversation_history[-8:]
        if m.get("content")
    ])

    system, max_tokens = _build_system(
        case_file, rag_context, history_text, language, is_followup
    )

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
        "chat_template_kwargs": {"enable_thinking": False},
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
                # Filter reasoning_content (thinking tokens)
                token = delta.get("content", "") or ""
                if token:
                    full_response += token
                    yield {"type": "token", "token": token, "agent": "expert"}
            except Exception:
                continue
    except Exception as e:
        yield {"type": "error", "message": str(e)}
        return

    if not full_response.strip():
        fallback = {
            "hi": "माफ करें, फिर से कोशिश करें।",
            "en": "Sorry, please try again.",
            "bn": "দুঃখিত, আবার চেষ্টা করুন।"
        }.get(language, "Please try again.")
        full_response = fallback
        yield {"type": "token", "token": full_response, "agent": "expert"}

    # Generate follow-up questions
    follow_up_questions = []
    if not is_followup:
        crime_type = case_file.get("crime_type", "general")
        lang_instruction = LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS["en"])
        fq_prompt = (
            f"{lang_instruction}\n"
            f"Based on this legal case: {crime_type} ({language} session)\n"
            f"Generate 5 short follow-up questions this woman might ask next.\n"
            f"Write in {'Devanagari Hindi' if language == 'hi' else language}.\n"
            f"Output JSON array only: [\"q1\",\"q2\",\"q3\",\"q4\",\"q5\"]"
        )
        try:
            fq_r = requests.post(
                f"{settings.ollama_base_url}/v1/chat/completions",
                json={
                    "model": "gemma4",
                    "messages": [{"role": "user", "content": fq_prompt}],
                    "stream": False,
                    "temperature": 0.4,
                    "max_tokens": 200,
                    "chat_template_kwargs": {"enable_thinking": False},
                },
                timeout=30
            )
            fq_text = fq_r.json()["choices"][0]["message"]["content"].strip()
            match = re.search(r'\[.*?\]', fq_text, re.DOTALL)
            if match:
                follow_up_questions = json.loads(match.group())[:5]
        except Exception:
            pass

        if not follow_up_questions:
            # Hardcoded fallbacks
            if language == "hi":
                follow_up_questions = [
                    "Protection order कैसे मिलेगा?",
                    "FIR कैसे file करें?",
                    "मुफ्त वकील कहाँ मिलेगा?",
                    "क्या मैं घर में रह सकती हूँ?",
                    "बच्चों की custody के बारे में?",
                ]
            else:
                follow_up_questions = [
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
        "follow_up_questions": follow_up_questions,
    }
