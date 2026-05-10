"""
Sehat Sakhi — Medical Expert Agent
Never diagnoses. Never prescribes by name.
5-block structure: Empathy → What it means → Home care → Warning signs → Scheme
"""
import requests
import json
from app.config import settings
from app.rag.medical_rag import get_medical_context
from typing import AsyncGenerator

LANGUAGE_INSTRUCTIONS = {
    "hi": "🔴 CRITICAL — LANGUAGE RULE: Sirf Devanagari lipi mein jawab do. Roman script BILKUL nahi.",
    "en": "🔴 CRITICAL — LANGUAGE RULE: Respond ONLY in English. Never use Hindi or Devanagari.",
    "bn": "🔴 CRITICAL — LANGUAGE RULE: Sudhu Bangla lipi te uttor dao. Roman ba Hindi lipi noy.",
}

ISSUE_GUIDANCE = {
    "pregnancy": """
Key conditions to know:
- Pre-eclampsia warning signs: severe headache + blurred vision + swelling of hands/face → HOSPITAL IMMEDIATELY
- Danger in pregnancy: heavy bleeding, baby not moving >12 hrs after 28 weeks, fits, high fever, severe abdominal pain
- Normal discomforts: morning sickness, mild back pain, frequent urination, mild foot swelling in evenings
Government scheme: Janani Suraksha Yojana (JSY) — cash assistance for institutional delivery. Free delivery at govt hospital.
Always recommend: Nearest ASHA worker or ANM for antenatal care (free).
""",
    "child_illness": """
Danger signs requiring immediate hospital:
- Cannot drink/breastfeed, vomits everything, convulsions, unconscious, rapid/difficult breathing
- Severe dehydration (sunken eyes, dry mouth, no tears in a crying baby)
- High fever in child under 3 months — ALWAYS go to hospital
Home management for mild diarrhoea: ORS after every loose stool, continue breastfeeding, do NOT stop food.
Key fact: Zinc tablets (10-14 days) free at govt health centres.
Universal Immunisation Programme: all vaccines FREE at govt hospitals.
""",
    "mental_health": """
Depression is a medical condition — NOT weakness. It can be treated.
Signs: persistent sadness >2 weeks, loss of interest, sleep problems, fatigue, worthlessness, thoughts of death.
Common triggers in Indian women: DV, loss, marital problems, financial stress, postpartum.
NEVER minimize: "Everyone feels sad" or "pray more" type responses are harmful.
Free counselling: iCall 9152987821 (Mon-Sat), Vandrevala Foundation 1860-2662-345 (24x7), NIMHANS 080-46110007.
Key message: Treatment exists. Recovery is possible. Seeking help is strength, not weakness.
""",
    "anaemia": """
Very common: 59.1% of Indian women aged 15-49 are anaemic (NFHS-5).
Signs: fatigue, weakness, pale skin, dizziness, shortness of breath.
Iron-rich foods: palak/methi, dal, gud (jaggery), til (sesame), raisins, dates. Eat with Vitamin C (lemon/amla) to absorb better.
Government: Free iron + folic acid tablets at Anganwadi and PHC. Pregnant women: 1 tablet daily (180 days) — FREE.
""",
    "reproductive": """
Contraception (all free at PHC/ASHA): condoms, Mala-N pills, Antara injection (3-monthly), Copper-T IUD.
Emergency contraception: available at chemist without prescription, within 72 hours.
Irregular periods / PCOD: go to PHC, doctor can help — do not ignore.
Menstrual hygiene: free sanitary pads at Anganwadi under Surakshit Matritva scheme in many states.
""",
    "postpartum": """
Postpartum depression is COMMON and TREATABLE — not a failure as a mother.
Signs: persistent sadness after delivery, inability to bond with baby, extreme anxiety, not eating/sleeping.
Physical: engorgement, cracked nipples (breastfeeding support), postpartum bleeding (lochia — normal for 4-6 weeks).
Danger: very heavy bleeding, fever, foul smell, signs of infection → HOSPITAL IMMEDIATELY.
Scheme: PM Matru Vandana Yojana — Rs 5000 for first pregnancy (conditions apply).
""",
}

WARNING_SIGNS_TEMPLATE = {
    "hi": "⚠️ **इन लक्षणों में तुरंत अस्पताल जाएं:**",
    "en": "⚠️ **Go to hospital IMMEDIATELY if you see:**",
    "bn": "⚠️ **এই লক্ষণে সাথে সাথে হাসপাতাল যান:**",
}

FOLLOWUP_WORDS = ["han", "haan", "yes", "okay", "ok", "aur", "batao", "kaise", "phir", "more", "details"]


async def run_medical_expert_stream(
    case_file: dict,
    conversation_history: list,
    language: str = "hi"
) -> AsyncGenerator[dict, None]:

    rag_context, citations = get_medical_context(case_file)
    yield {"type": "rag_retrieved", "citations": citations, "chunk_count": len(citations)}

    lang_instruction = LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS["en"])
    health_issue = case_file.get("health_issue", "general")
    issue_guidance = ISSUE_GUIDANCE.get(health_issue, "")
    warning_header = WARNING_SIGNS_TEMPLATE.get(language, WARNING_SIGNS_TEMPLATE["en"])

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

You are Sehat Sakhi — health guide for Indian women.
Answer ONLY the follow-up question in 2-4 sentences.
Do NOT repeat full health advice.
Case: {json.dumps(case_file, ensure_ascii=False)}
Conversation: {history_text}

FINAL REMINDER: {lang_instruction}"""
        max_tokens = 250
    else:
        system = f"""{lang_instruction}

You are Sehat Sakhi — a caring, knowledgeable health guide for Indian women.
Think like a well-trained ASHA worker with medical knowledge.

ISSUE-SPECIFIC KNOWLEDGE:
{issue_guidance}

RESPONSE STRUCTURE (follow exactly):
1. ONE empathy sentence — acknowledge her worry
2. WHAT THIS LIKELY MEANS — plain language (NOT a diagnosis, NOT medicine names)
3. WHAT TO DO RIGHT NOW AT HOME — practical steps
4. {warning_header}
   [2-3 specific danger signs that require immediate hospital visit]
5. FREE GOVERNMENT RESOURCE — scheme or helpline relevant to her situation

CRITICAL RULES:
- NEVER diagnose (say "this could be..." not "you have...")
- NEVER prescribe specific medicines by name
- If healthcare is far: give BOTH home management AND emergency transport advice
- Under 350 words
- Always end with: offer to explain more or find nearest health centre

MEDICAL GUIDELINES FROM RAG:
{rag_context}

CASE: {json.dumps(case_file, ensure_ascii=False)}
CONVERSATION: {history_text}

FINAL REMINDER: {lang_instruction}"""
        max_tokens = 700

    # Generate follow-up questions
    followup_prompt = f"""Health case: {health_issue}, patient: {case_file.get('patient', 'self')}, language: {language}
Generate 5 short follow-up questions a woman might ask after getting health guidance.
Write in {language}. Output JSON array only: ["q1","q2","q3","q4","q5"]"""

    payload = {
        "model": "gemma4",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": last_user}
        ],
        "stream": True,
        "temperature": 0.25,
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
                    "Kya main ghar par treat kar sakti hoon?",
                    "Kab hospital jaana zaroori hai?",
                    "Konsi free government scheme milegi?",
                    "Yeh dobara kaise roke?",
                    "Bacche ke liye kya karein?",
                ]
            else:
                followup_questions = [
                    "Can I treat this at home?",
                    "When must I go to hospital?",
                    "What free government scheme is available?",
                    "How to prevent this again?",
                    "What about my child's health?",
                ]

    yield {
        "type": "done",
        "full_response": full_response,
        "citations": citations,
        "agent": "expert",
        "follow_up_questions": followup_questions,
    }
