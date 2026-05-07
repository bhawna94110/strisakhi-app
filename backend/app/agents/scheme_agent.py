"""
Scheme Expert Agent — Gemma 4 E2B via llama.cpp
Government schemes guidance for Indian women.
RAG-powered with scheme documents.
"""
import requests
import json
from app.config import settings
from app.rag.legal_rag import get_legal_context
from typing import AsyncGenerator

# Scheme-specific system prompt
SCHEME_SYSTEM = """You are Yojana Sakhi, a compassionate guide helping Indian women access government schemes and benefits.
Respond in simple Hindi. Be warm, clear, and practical.
Cite scheme sources: [Source: Scheme Name, Ministry]

Structure:
1) One empathy sentence
2) 2-3 relevant government schemes for her situation (with eligibility)
3) How to apply today — 3 numbered steps
4) One free helpline

End with: "Kya aap aur schemes ke baare mein jaanna chahti hain?"

RULES:
- Only mention real Indian government schemes
- Always include eligibility criteria
- Give specific documents needed
- Mention nearest Jan Seva Kendra or Common Service Centre"""

SCHEME_KEYWORDS = {
    "domestic_violence": ["PM Awas Yojana", "Ujjwala Yojana", "One Stop Centre Scheme",
                          "NMEW - National Mission for Empowerment of Women"],
    "health": ["Ayushman Bharat", "Janani Suraksha Yojana", "PMJAY", "PM Matru Vandana Yojana"],
    "education": ["Beti Bachao Beti Padhao", "National Scholarship Portal", "CBSE Merit Scholarship"],
    "financial": ["PM Jan Dhan Yojana", "Mudra Loan", "Stand Up India", "Sukanya Samriddhi Yojana"],
    "housing": ["PM Awas Yojana (Gramin)", "PM Awas Yojana (Urban)", "Indira Awaas Yojana"],
    "employment": ["MGNREGS", "NRLM - Deendayal Antyodaya Yojana", "PM Kaushal Vikas Yojana"],
    "widow": ["Indira Gandhi National Widow Pension Scheme", "Rashtriya Parivar Sahayata Yojana"],
    "old_age": ["Indira Gandhi National Old Age Pension", "Atal Pension Yojana"],
}

def get_scheme_context(case_file: dict) -> tuple:
    """Build scheme context from case file and keyword matching."""
    issue_type = case_file.get("issue_type", "")
    state = case_file.get("location_state", "")

    # Find relevant schemes
    relevant_schemes = []
    for category, schemes in SCHEME_KEYWORDS.items():
        if any(kw in issue_type.lower() for kw in [category, issue_type]):
            relevant_schemes.extend(schemes)

    # Always include universal schemes
    universal = ["PM Jan Dhan Yojana", "Ayushman Bharat", "Ujjwala Yojana"]
    relevant_schemes = list(set(relevant_schemes + universal))[:6]

    context = f"""RELEVANT GOVERNMENT SCHEMES FOR {state.upper() if state else 'INDIA'}:

"""
    scheme_docs = {
        "PM Awas Yojana": "Provides housing to homeless families. Eligibility: Annual income < 3 lakh. Apply at: pmaymis.gov.in or nearest CSC",
        "Ayushman Bharat": "Free health insurance up to 5 lakh per family. Eligibility: BPL families. Apply: pmjay.gov.in",
        "Janani Suraksha Yojana": "Cash assistance for pregnant women. Eligibility: BPL pregnant women. Apply: nearest ASHA worker or ANM",
        "PM Matru Vandana Yojana": "Rs 5000 maternity benefit. Eligibility: First pregnancy. Apply: Anganwadi or Health Centre",
        "PM Jan Dhan Yojana": "Free bank account + RuPay card + insurance. Eligibility: Any Indian adult. Apply: Any bank branch",
        "Mudra Loan": "Loans 50k-10 lakh for small business. Eligibility: Women entrepreneurs. Apply: Bank or mudra.org.in",
        "Beti Bachao Beti Padhao": "Scholarship and welfare for girl child. Eligibility: Girl children. Apply: District office or school",
        "MGNREGS": "100 days guaranteed employment. Eligibility: Rural household adults. Apply: Gram Panchayat",
        "Ujjwala Yojana": "Free LPG connection. Eligibility: BPL women. Apply: Nearest LPG distributor",
        "Sukanya Samriddhi Yojana": "Savings scheme for girl child. Eligibility: Girls under 10. Apply: Post office or bank",
        "One Stop Centre Scheme": "Free shelter, legal, medical, police help for women in distress. Eligibility: Any woman in crisis. Call: 181",
        "NMEW": "National Mission for Empowerment of Women — legal aid, training, support. Apply: District office",
        "Indira Gandhi National Widow Pension Scheme": "Monthly pension for widows. Eligibility: BPL widows aged 40-79. Apply: Gram Panchayat",
        "PM Kaushal Vikas Yojana": "Free skill training + certification. Eligibility: Any Indian 15+. Register: pmkvyofficial.org",
        "Rashtriya Parivar Sahayata Yojana": "Rs 20,000 to BPL family on death of breadwinner. Apply: District Social Welfare Office",
        "National Scholarship Portal": "Scholarships for students. Apply: scholarships.gov.in",
        "Stand Up India": "Loans 10 lakh-1 crore for SC/ST/Women entrepreneurs. Apply: Bank branch",
        "Atal Pension Yojana": "Pension scheme for unorganised workers. Eligibility: 18-40 years. Apply: Bank",
    }

    citations = []
    for scheme in relevant_schemes:
        if scheme in scheme_docs:
            context += f"• {scheme}: {scheme_docs[scheme]}\n\n"
            citations.append({"source": scheme, "section": "Government Scheme"})

    return context, citations


async def run_scheme_expert_stream(
    case_file: dict,
    conversation_history: list,
    language: str = "hi"
) -> AsyncGenerator[dict, None]:

    rag_context, citations = get_scheme_context(case_file)
    yield {"type": "rag_retrieved", "citations": citations, "chunk_count": len(citations)}

    # Get last user message
    last_user_msg = ""
    for msg in reversed(conversation_history):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    # Detect follow-up
    followup_words = ["han", "haan", "yes", "okay", "ok", "aur", "batao", "kaise", "kya"]
    is_followup = any(w in last_user_msg.lower() for w in followup_words) and len(last_user_msg.strip()) < 40

    if is_followup:
        system = f"""You are Yojana Sakhi, a guide for Indian government schemes.
The user is asking a follow-up. Answer briefly in Hindi (2-4 sentences only).
Do NOT repeat the full list of schemes.

CONVERSATION:
{chr(10).join([f"{m['role'].upper()}: {m['content']}" for m in conversation_history[-6:]])}"""
    else:
        system = f"""{SCHEME_SYSTEM}

GOVERNMENT SCHEMES DATABASE:
{rag_context}

WOMAN'S SITUATION:
{json.dumps(case_file, ensure_ascii=False)}

CONVERSATION:
{chr(10).join([f"{m['role'].upper()}: {m['content']}" for m in conversation_history[-4:]])}"""

    payload = {
        "model": "gemma4",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": last_user_msg}
        ],
        "stream": True,
        "temperature": 0.2,
        "max_tokens": 150 if is_followup else 500,
        "top_p": 0.95,
    }

    full_response = ""
    try:
        r = requests.post(
            f"{settings.ollama_base_url}/v1/chat/completions",
            json=payload, stream=True, timeout=120
        )
        for line in r.iter_lines():
            if not line: continue
            line_str = line.decode() if isinstance(line, bytes) else line
            if not line_str.startswith("data: "): continue
            data_str = line_str[6:]
            if data_str == "[DONE]": break
            try:
                token = json.loads(data_str)["choices"][0]["delta"].get("content", "") or ""
                if token:
                    full_response += token
                    yield {"type": "token", "token": token, "agent": "expert"}
            except: continue
    except Exception as e:
        yield {"type": "error", "message": str(e)}
        return

    if not full_response.strip():
        full_response = "Maafi chahti hoon, dobara try karein."
        yield {"type": "token", "token": full_response, "agent": "expert"}

    yield {"type": "done", "full_response": full_response, "citations": citations, "agent": "expert"}
