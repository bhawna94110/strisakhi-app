"""
Yojana Sakhi — Scheme Expert Agent
Finds the 3 most relevant government schemes.
Gives exact eligibility + where to apply + documents needed.
Uses both RAG (scheme_documents) and hardcoded scheme knowledge.
"""
import requests
import json
from app.config import settings
from typing import AsyncGenerator
import chromadb
from chromadb.utils import embedding_functions

LANGUAGE_INSTRUCTIONS = {
    "hi": "Sirf Devanagari Hindi mein jawab do. Bilkul simple bhasha — jaise ek dost batati hai.",
    "en": "Respond ONLY in English. Be warm and practical — like a helpful neighbour.",
    "bn": "Sudhu Bangla te uttor dao. Sorol o bhalobasha diye bolte hobe.",
}

SCHEME_COLLECTION = "scheme_documents"

SITUATION_SCHEMES = {
    "pregnant": ["Janani Suraksha Yojana", "PM Matru Vandana Yojana", "Ayushman Bharat", "JSSK"],
    "widow": ["Indira Gandhi National Widow Pension Scheme", "PM Awas Yojana", "PM Jan Dhan Yojana", "Rashtriya Parivar Sahayata Yojana"],
    "domestic_violence": ["One Stop Centre Sakhi", "PM Awas Yojana", "PM Jan Dhan Yojana", "Ujjwala Yojana"],
    "homeless": ["PM Awas Yojana", "PM Jan Dhan Yojana", "Ujjwala Yojana"],
    "unemployed": ["MGNREGS", "PM Kaushal Vikas Yojana", "Mudra Loan", "NRLM SHG"],
    "student": ["Beti Bachao Beti Padhao", "National Scholarship Portal", "PM Jan Dhan Yojana"],
    "elderly": ["Indira Gandhi National Old Age Pension", "Ayushman Bharat", "Atal Pension Yojana"],
    "entrepreneur": ["Mudra Loan", "Stand Up India", "NRLM SHG", "PM Jan Dhan Yojana"],
    "farmer": ["MGNREGS", "PM Kisan Samman", "Ujjwala Yojana", "PM Jan Dhan Yojana"],
    "general": ["PM Jan Dhan Yojana", "Ayushman Bharat", "Ujjwala Yojana", "PM Awas Yojana"],
}

# Full scheme database with apply details
SCHEME_DATABASE = {
    "PM Awas Yojana": {
        "what": "Free/subsidised house",
        "eligibility": "BPL families, homeless or 0-1 room kutcha house",
        "benefit": "Rs 1.2-1.3 lakh for construction",
        "apply": "Gram Panchayat (rural) or Urban Local Body (urban)",
        "documents": "Aadhaar, bank account, BPL/ration card, land proof",
        "website": "pmayg.nic.in",
    },
    "Ayushman Bharat": {
        "what": "Free health insurance up to Rs 5 lakh per family per year",
        "eligibility": "BPL families as per SECC 2011. Check: pmjay.gov.in or SMS 'PMJAY' to 56167",
        "benefit": "Hospitalisation, surgery, medicines at empanelled hospitals",
        "apply": "Show Aadhaar at any empanelled hospital. Get Ayushman card at CSC.",
        "documents": "Aadhaar card",
        "website": "pmjay.gov.in or call 14555",
    },
    "Janani Suraksha Yojana": {
        "what": "Cash for institutional delivery",
        "eligibility": "BPL pregnant women",
        "benefit": "Rs 1400 (rural) / Rs 1000 (urban) for delivery at government hospital",
        "apply": "ASHA worker or nearest PHC/hospital before delivery",
        "documents": "Aadhaar, BPL card, bank account",
        "website": "nhm.gov.in",
    },
    "PM Matru Vandana Yojana": {
        "what": "Cash benefit for first pregnancy",
        "eligibility": "First pregnancy only. Age 19+.",
        "benefit": "Rs 5000 (paid in 2 installments)",
        "apply": "Anganwadi centre or Women and Child Development office",
        "documents": "Aadhaar, MCP card, bank account",
        "website": "pmmvy.nic.in",
    },
    "PM Jan Dhan Yojana": {
        "what": "Free bank account + RuPay card + free insurance",
        "eligibility": "Any Indian citizen 10 years+. Zero balance.",
        "benefit": "Account + Rs 2 lakh accident insurance + Rs 30000 life insurance",
        "apply": "Any bank branch with Aadhaar + 1 photo",
        "documents": "Aadhaar card, 1 passport photo",
        "website": "pmjdy.gov.in",
    },
    "Ujjwala Yojana": {
        "what": "Free LPG gas connection",
        "eligibility": "Women from BPL households, SC/ST, PMAY beneficiaries",
        "benefit": "Free LPG connection (stove + cylinder). Refill subsidy via DBT.",
        "apply": "Nearest LPG distributor (HP Gas, Indane, Bharat Gas)",
        "documents": "Aadhaar, bank account, BPL ration card or self-declaration",
        "website": "pmuy.gov.in",
    },
    "MGNREGS": {
        "what": "100 days guaranteed paid work per year",
        "eligibility": "Any adult in rural household willing to do manual work",
        "benefit": "Rs 200-300/day (varies by state). Women get 33% reservation.",
        "apply": "Register at Gram Panchayat. Get Job Card (free).",
        "documents": "Aadhaar, photo",
        "website": "nrega.nic.in",
    },
    "PM Kaushal Vikas Yojana": {
        "what": "Free skill training + certification + placement help",
        "eligibility": "Any Indian aged 15-45. No minimum education.",
        "benefit": "Free training + Rs 8000 reward on job placement",
        "apply": "Nearest Skill India / PMKVY centre or online",
        "documents": "Aadhaar, photo",
        "website": "pmkvyofficial.org",
    },
    "Mudra Loan": {
        "what": "Business loan without collateral",
        "eligibility": "Any Indian starting/running small business. Women get priority.",
        "benefit": "Up to Rs 10 lakh loan. No collateral needed.",
        "apply": "Any bank, MFI, or NBFC",
        "documents": "Aadhaar, business plan, bank account",
        "website": "mudra.org.in",
    },
    "Beti Bachao Beti Padhao": {
        "what": "Girl child savings + education support",
        "eligibility": "Girl child under 10 years for Sukanya Samriddhi account",
        "benefit": "Savings account with ~7.6% tax-free interest. Scholarships for education.",
        "apply": "Post office or bank (Sukanya Samriddhi). School for scholarships.",
        "documents": "Girl's birth certificate, parent's Aadhaar",
        "website": "scholarships.gov.in",
    },
    "One Stop Centre Sakhi": {
        "what": "Free shelter, legal aid, medical help, police help for women in distress",
        "eligibility": "Any woman facing violence — domestic, sexual, trafficking, acid attack",
        "benefit": "Emergency shelter (5 days), medical, legal, police, counselling — all FREE",
        "apply": "Call Women Helpline 181 — they will connect you",
        "documents": "No documents required in emergency",
        "website": "Call 181",
    },
    "Indira Gandhi National Widow Pension Scheme": {
        "what": "Monthly pension for widows",
        "eligibility": "BPL widows aged 40-79 years",
        "benefit": "Rs 300/month",
        "apply": "Gram Panchayat or Block Development Office",
        "documents": "Husband's death certificate, BPL card, Aadhaar, bank account",
        "website": "nsap.nic.in",
    },
    "Indira Gandhi National Old Age Pension": {
        "what": "Monthly pension for elderly poor",
        "eligibility": "BPL persons aged 60+",
        "benefit": "Rs 200/month (60-79 yrs), Rs 500/month (80+ yrs)",
        "apply": "Gram Panchayat or Block Development Office",
        "documents": "Age proof, BPL card, Aadhaar, bank account",
        "website": "nsap.nic.in",
    },
    "Rashtriya Parivar Sahayata Yojana": {
        "what": "One-time payment on death of breadwinner",
        "eligibility": "BPL family where breadwinner (18-64) died",
        "benefit": "Rs 20000 one-time payment. Apply within 90 days of death.",
        "apply": "District Social Welfare Office",
        "documents": "Death certificate, BPL card, Aadhaar",
        "website": "State social welfare department",
    },
}

FOLLOWUP_WORDS = ["han", "haan", "yes", "okay", "ok", "aur", "batao", "kaise", "more", "details", "aage"]


def get_scheme_context(case_file: dict) -> tuple[str, list]:
    """Get relevant scheme context from ChromaDB + hardcoded database."""
    situation = case_file.get("life_situation", "general")
    state = case_file.get("state", "")

    # Get relevant scheme names
    relevant_names = SITUATION_SCHEMES.get(situation, SITUATION_SCHEMES["general"])
    # Always include Jan Dhan
    if "PM Jan Dhan Yojana" not in relevant_names:
        relevant_names = list(relevant_names) + ["PM Jan Dhan Yojana"]

    context_parts = []
    citations = []

    for name in relevant_names[:5]:
        if name in SCHEME_DATABASE:
            s = SCHEME_DATABASE[name]
            context_parts.append(
                f"**{name}**\n"
                f"What: {s['what']}\n"
                f"Eligibility: {s['eligibility']}\n"
                f"Benefit: {s['benefit']}\n"
                f"How to apply: {s['apply']}\n"
                f"Documents: {s['documents']}\n"
            )
            citations.append({"source": name, "section": s.get("website", "")})

    # Try RAG for additional context
    try:
        from app.config import settings as cfg
        client = chromadb.PersistentClient(path=cfg.chroma_persist_dir)
        ef = embedding_functions.DefaultEmbeddingFunction()
        try:
            collection = client.get_collection(SCHEME_COLLECTION, embedding_function=ef)
            query = f"{situation} schemes {state} women India"
            results = collection.query(query_texts=[query], n_results=3)
            for doc in results["documents"][0]:
                context_parts.append(doc[:400])
        except Exception:
            pass
    except Exception:
        pass

    return "\n\n".join(context_parts), citations


async def run_scheme_expert_stream(
    case_file: dict,
    conversation_history: list,
    language: str = "hi"
) -> AsyncGenerator[dict, None]:

    rag_context, citations = get_scheme_context(case_file)
    yield {"type": "rag_retrieved", "citations": citations, "chunk_count": len(citations)}

    lang_instruction = LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS["en"])
    situation = case_file.get("life_situation", "general")
    state = case_file.get("state", "aapke rajya mein")

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
        system = f"""You are Yojana Sakhi — government scheme guide for women.
{lang_instruction}
Answer ONLY the follow-up in 2-4 sentences.
Case: {json.dumps(case_file, ensure_ascii=False)}
Conversation: {history_text}"""
        max_tokens = 250
    else:
        system = f"""You are Yojana Sakhi — a friendly guide who helps Indian women access government benefits.
You know every government scheme and exactly how to apply.
{lang_instruction}

RESPONSE STRUCTURE (follow exactly):
1. "Aapke liye yeh schemes hain:" (or equivalent in {language})
2. TOP SCHEME (most relevant for her situation):
   - Name + what she gets
   - Eligibility in 1 sentence
   - Exactly where to apply + what documents to bring today
3. SECOND SCHEME (related benefit)
   Same format
4. UNIVERSAL SCHEME (Jan Dhan or similar — nearly everyone qualifies)
   Same format
5. "Common Service Centre (CSC) aapke nearest gaon mein in sab ke liye help kar sakta hai"

RULES:
- Under 400 words
- Always give EXACT apply location (Gram Panchayat / PHC / CSC / Bank / specific website)
- Always list documents needed
- NEVER say "you don't qualify" — find at least one scheme for everyone
- Jan Dhan account is FIRST step for all other schemes — mention if she doesn't have one

SCHEME DATABASE:
{rag_context}

CASE: {json.dumps(case_file, ensure_ascii=False)}
CONVERSATION: {history_text}"""
        max_tokens = 700

    # Follow-up questions prompt
    followup_prompt = f"""Situation: {situation}, state: {state}, language: {language}
Generate 5 short follow-up questions a woman might ask after learning about government schemes.
Write in {language}. Output JSON array only: ["q1","q2","q3","q4","q5"]"""

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
                token = json.loads(data_str)["choices"][0]["delta"].get("content", "") or ""
                if token:
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

    # Follow-up questions
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
            match = __import__("re").search(r'\[.*?\]', fq_text, __import__("re").DOTALL)
            if match:
                followup_questions = json.loads(match.group())[:5]
        except Exception:
            if language == "hi":
                followup_questions = [
                    "Kya main ek se zyada yojana le sakti hoon?",
                    "Aadhaar nahi hai toh kya karein?",
                    "Yojana ke paise kab tak aayenge?",
                    "CSC kahan milega?",
                    "Mere bacche ke liye koi yojana hai?",
                ]
            else:
                followup_questions = [
                    "Can I apply for multiple schemes?",
                    "What if I don't have Aadhaar?",
                    "How long till I get the money?",
                    "Where is the nearest CSC?",
                    "Is there a scheme for my children?",
                ]

    yield {
        "type": "done",
        "full_response": full_response,
        "citations": citations,
        "agent": "expert",
        "follow_up_questions": followup_questions,
    }
