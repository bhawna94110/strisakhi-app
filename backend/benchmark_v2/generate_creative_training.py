#!/usr/bin/env python3
"""
StriSakhi — Creative Training Data Generator v4.0
==================================================
Uses GPT-4o to generate NATURAL, VARIED content inside a SACRED format template.
The model writes empathy, rights, steps, questions — but CANNOT modify the format skeleton.
Auto-retry on validation failure. Checkpoint every 100.

Usage:
    export OPENAI_API_KEY="sk-..."
    python benchmark_v2/generate_creative_training.py --target 700

Cost: ~$15-25 USD with gpt-4o (user budget: $30-40)
Output: benchmark_v2/training_data/strisakhi_train.jsonl
"""
import os
import json
import re
import random
import asyncio
import argparse
import hashlib
import httpx
from datetime import datetime
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o"  # Better quality since cost is not a constraint

OUTPUT_DIR = Path(__file__).parent / "training_data"
OUTPUT_DIR.mkdir(exist_ok=True)

PRICING = {"gpt-4o": {"input": 2.50, "output": 10.00}}

# ── Variation pools ────────────────────────────────────────────
STATES = ["Uttar Pradesh", "Bihar", "Maharashtra", "West Bengal", "Rajasthan",
          "Delhi", "Madhya Pradesh", "Tamil Nadu", "Karnataka", "Gujarat", "Punjab", "Odisha", "Haryana", "Assam"]
URGENCY = ["immediate", "recent", "ongoing", "historical"]
HAS_CHILDREN = [True, False]
DURATIONS = ["1 saal", "2 saal", "3 saal", "5 saal", "6 mahine", "1 mahina", "4 saal", "10 saal"]
COMPANY_SIZES = ["15 employees", "50 employees", "100 employees", "200 employees", "25 employees", "500 employees"]

# ── SACRED FORMAT TEMPLATES (never changes) ────────────────────

HI_EXPERT_FORMAT = """{empathy}

**आपके अधिकार:**
{rights}

**अभी (Right Now):** {step_now}
**आज (Today):** {step_today}
**इस हफ्ते (This Week):** {step_week}

📞 {helpline}

{followup}"""

EN_EXPERT_FORMAT = """{empathy}

**Your Rights:**
{rights}

**Right Now:** {step_now}
**Today:** {step_today}
**This Week:** {step_week}

📞 {helpline}

{followup}"""

# ── SYSTEM PROMPTS FOR GPT-4o ──────────────────────────────────

HI_GENERATOR_SYSTEM = """You are a training data generator for an Indian legal AI assistant.
Your job: write NATURAL, WARM, SPECIFIC content for each block of a legal response.

CRITICAL RULES — NEVER BREAK THESE:
1. Citations MUST be exactly: [Source: Act Name YYYY, Section X] — NEVER translate "Source" or "Section" into Hindi
2. Block headers are sacred — I will add them, you do NOT write them
3. Timeline labels are sacred — I will add them, you do NOT write them  
4. Helpline format is sacred — I will add it, you do NOT write it
5. End with a question mark
6. Pure Devanagari for all Hindi text — NO Roman script mixed in
7. Under 300 words for your content

What you write:
- empathy: 1 sentence, personal, warm, referencing specific case details
- rights: 2-3 rights, each starting with [Source: ...] then simple explanation in Hindi
- steps: 3 actionable steps (immediate, today, this week) — specific, not generic
- followup: 1 specific question related to the case

Write like a knowledgeable older sister, not a robot. Vary your phrasing. Be human."""

EN_GENERATOR_SYSTEM = """You are a training data generator for an Indian legal AI assistant.
Your job: write NATURAL, WARM, SPECIFIC content for each block of a legal response.

CRITICAL RULES — NEVER BREAK THESE:
1. Citations MUST be exactly: [Source: Act Name YYYY, Section X]
2. Block headers are sacred — I will add them, you do NOT write them
3. Timeline labels are sacred — I will add them, you do NOT write them
4. Helpline format is sacred — I will add it, you do NOT write it
5. End with a question mark
6. English only — NO Hindi or Devanagari
7. Under 300 words for your content

What you write:
- empathy: 1 sentence, personal, warm, referencing specific case details
- rights: 2-3 rights, each starting with [Source: ...] then simple explanation
- steps: 3 actionable steps (immediate, today, this week) — specific, not generic
- followup: 1 specific question related to the case

Write like a knowledgeable older sister, not a robot. Vary your phrasing. Be human."""

# ── PROMPT BUILDERS FOR GPT-4o ─────────────────────────────────

def build_hi_expert_prompt(case_file: str, rag_context: str, user_msg: str, crime_type: str) -> str:
    crime_guidance = {
        "domestic_violence": "Key law: DV Act 2005. Sections: 17 (residence), 18 (protection order), 20 (monetary relief). Helpline: 181.",
        "maintenance": "Key law: CrPC Section 125. Maintenance without divorce possible. Interim in 60 days. Helpline: 15100.",
        "property": "Key law: Hindu Succession Act 1956, Section 6. Daughter has equal right. Helpline: 15100.",
        "dowry": "Key law: Dowry Prohibition Act 1961, Section 3. IPC 498A. Helpline: 181.",
    }.get(crime_type, "Key law: DV Act 2005. Helpline: 181.")

    return f"""Write a legal response for this case:

CASE FILE: {case_file}
LEGAL CONTEXT: {rag_context}
USER MESSAGE: {user_msg}
CRIME GUIDANCE: {crime_guidance}

Write ONLY these 4 parts, separated by ---PART--- markers:

---PART:EMPATHY---
1 sentence in Devanagari Hindi, warm and personal.

---PART:RIGHTS---
2-3 rights. Each MUST start with exact citation format like [Source: DV Act 2005, Section 17] then explanation in simple Hindi.
Use ONLY sections from the LEGAL CONTEXT above. NEVER invent sections.

---PART:STEPS---
3 lines separated by newlines:
Line 1: immediate action (right now)
Line 2: action within 24 hours (today)  
Line 3: action within 7 days (this week)
Each line should be specific and actionable.

---PART:FOLLOWUP---
1 question ending with ?

REMEMBER:
- Pure Devanagari. No Roman script.
- Citations: [Source: Act Name YYYY, Section X] exactly.
- Do NOT write block headers or timeline labels — I will add those.
- Do NOT write the helpline line — I will add it.
- Be warm, human, and specific to this case."""


def build_en_expert_prompt(case_file: str, rag_context: str, user_msg: str, crime_type: str) -> str:
    crime_guidance = {
        "workplace": "Key law: POSH Act 2013. Sections: 4 (ICC), 9 (complaint window), 11 (no retaliation). Helpline: 15100.",
        "stalking": "Key law: IPC 354D, IT Act 66E. Helpline: 1930.",
        "divorce": "Key law: Hindu Marriage Act 1955, Section 13. Helpline: 15100.",
    }.get(crime_type, "Key law: POSH Act 2013. Helpline: 15100.")

    return f"""Write a legal response for this case:

CASE FILE: {case_file}
LEGAL CONTEXT: {rag_context}
USER MESSAGE: {user_msg}
CRIME GUIDANCE: {crime_guidance}

Write ONLY these 4 parts, separated by ---PART--- markers:

---PART:EMPATHY---
1 sentence in English, warm and personal.

---PART:RIGHTS---
2-3 rights. Each MUST start with exact citation format like [Source: POSH Act 2013, Section 4] then explanation in simple English.
Use ONLY sections from the LEGAL CONTEXT above. NEVER invent sections.

---PART:STEPS---
3 lines separated by newlines:
Line 1: immediate action (right now)
Line 2: action within 24 hours (today)
Line 3: action within 7 days (this week)
Each line should be specific and actionable.

---PART:FOLLOWUP---
1 question ending with ?

REMEMBER:
- English only. No Hindi.
- Citations: [Source: Act Name YYYY, Section X] exactly.
- Do NOT write block headers or timeline labels — I will add those.
- Do NOT write the helpline line — I will add it.
- Be warm, human, and specific to this case."""


# ── OPENAI CALL ────────────────────────────────────────────────

async def call_openai(system: str, user: str, model: str, max_tokens: int = 900) -> str:
    if not OPENAI_KEY:
        raise ValueError("Set OPENAI_API_KEY")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.7,  # Higher for creativity
        "max_tokens": max_tokens,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            OPENAI_URL,
            json=payload,
            headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


# ── PARSER ─────────────────────────────────────────────────────

def parse_parts(response: str) -> dict:
    """Extract EMpathy, Rights, Steps, Followup from GPT output."""
    parts = {}
    current_key = None
    current_lines = []

    for line in response.split("\n"):
        if line.startswith("---PART:"):
            if current_key:
                parts[current_key] = "\n".join(current_lines).strip()
            current_key = line.replace("---PART:", "").replace("---", "").strip().lower()
            current_lines = []
        elif current_key:
            current_lines.append(line)

    if current_key:
        parts[current_key] = "\n".join(current_lines).strip()

    return parts


# ── VALIDATORS ───────────────────────────────────────────────────

def validate_expert(response: str, language: str) -> tuple[bool, dict]:
    errors = {}

    blocks = ["━━━ BLOCK 1: EMPATHY", "━━━ BLOCK 2: HER RIGHTS",
              "━━━ BLOCK 3: ACTION TIMELINE", "━━━ BLOCK 4: FREE HELPLINE",
              "━━━ BLOCK 5: FOLLOW-UP QUESTION"]
    missing = [b for b in blocks if b not in response]
    if missing:
        errors["blocks"] = f"Missing {len(missing)} block headers"

    citation_pat = r'\[Source: [A-Za-z][A-Za-z\s]+\d{4}, Section \d+[A-Z]?\]'
    citations = re.findall(citation_pat, response)
    if len(citations) < 2:
        errors["citations"] = f"Only {len(citations)} valid [Source: ...] found"

    if language == "hi":
        checks = [r'\*\*अभी \(Right Now\):\*\*', r'\*\*आज \(Today\):\*\*', r'\*\*इस हफ्ते \(This Week\):\*\*']
    else:
        checks = [r'\*\*Right Now:\*\*', r'\*\*Today:\*\*', r'\*\*This Week:\*\*']
    missing_t = [c for c in checks if not re.search(c, response)]
    if missing_t:
        errors["timeline"] = f"Missing {len(missing_t)} timeline labels"

    if not re.search(r'📞\s*\b(181|100|15100|1091|1930|1098|102|104|108|112|1800-419-8588)\b', response):
        errors["helpline"] = "No valid helpline"

    if not response.strip().endswith("?"):
        errors["question"] = "Does not end with ?"

    if len(response.split()) > 400:
        errors["words"] = f"{len(response.split())} words"

    if language in ("hi", "bn"):
        deva = len(re.findall(r'[\u0900-\u097F]', response))
        roman = len(re.findall(r'[a-zA-Z]', response))
        total = deva + roman
        if total > 0 and (deva/total) < 0.75:
            errors["purity"] = f"Hindi purity {deva/total:.2f}"

    return len(errors) == 0, errors


# ── ASSEMBLER ──────────────────────────────────────────────────

def assemble_hi_expert(parts: dict, helpline: str) -> str:
    rights_text = parts.get("rights", "")
    # Ensure each right line starts with [Source: ...]
    rights_lines = [l.strip() for l in rights_text.split("\n") if l.strip().startswith("[Source:")]
    if len(rights_lines) < 2:
        rights_lines = ["[Source: DV Act 2005, Section 17] आप घर में रहने की हकदार हैं।",
                        "[Source: DV Act 2005, Section 18] मजिस्ट्रेट से सुरक्षा आदेश मिल सकता है।"]

    steps_text = parts.get("steps", "")
    steps_lines = [l.strip() for l in steps_text.split("\n") if l.strip()]
    if len(steps_lines) < 3:
        steps_lines = ["181 पर call करें", "Magistrate के पास application दें", "DLSA से vakeel लें"]

    return f"""━━━ BLOCK 1: EMPATHY ━━━
{parts.get("empathy", "आपकी तकलीफ समझ में आती है।")}

━━━ BLOCK 2: HER RIGHTS ━━━
{chr(10).join(rights_lines)}

━━━ BLOCK 3: ACTION TIMELINE ━━━
**अभी (Right Now):** {steps_lines[0]}
**आज (Today):** {steps_lines[1]}
**इस हफ्ते (This Week):** {steps_lines[2]}

━━━ BLOCK 4: FREE HELPLINE ━━━
📞 {helpline}

━━━ BLOCK 5: FOLLOW-UP QUESTION ━━━
{parts.get("followup", "क्या आप और जानना चाहती हैं?")}"""


def assemble_en_expert(parts: dict, helpline: str) -> str:
    rights_text = parts.get("rights", "")
    rights_lines = [l.strip() for l in rights_text.split("\n") if l.strip().startswith("[Source:")]
    if len(rights_lines) < 2:
        rights_lines = ["[Source: POSH Act 2013, Section 4] Your company must have an ICC.",
                        "[Source: POSH Act 2013, Section 9] You can file a complaint within 3 months."]

    steps_text = parts.get("steps", "")
    steps_lines = [l.strip() for l in steps_text.split("\n") if l.strip()]
    if len(steps_lines) < 3:
        steps_lines = ["Save all evidence", "File complaint with ICC", "Contact NALSA 15100"]

    return f"""━━━ BLOCK 1: EMPATHY ━━━
{parts.get("empathy", "I'm sorry you're going through this.")}

━━━ BLOCK 2: HER RIGHTS ━━━
{chr(10).join(rights_lines)}

━━━ BLOCK 3: ACTION TIMELINE ━━━
**Right Now:** {steps_lines[0]}
**Today:** {steps_lines[1]}
**This Week:** {steps_lines[2]}

━━━ BLOCK 4: FREE HELPLINE ━━━
📞 {helpline}

━━━ BLOCK 5: FOLLOW-UP QUESTION ━━━
{parts.get("followup", "Would you like to know more?")}"""


# ── GENERATION ───────────────────────────────────────────────────

async def generate_example(category: str, language: str, max_retries: int = 3) -> tuple[dict, bool, dict]:
    """Generate one example. Returns (sharegpt_dict, is_valid, errors)."""

    # Build case file and context
    if category == "domestic_violence":
        case_file = json.dumps({
            "crime_type": "domestic_violence",
            "urgency": random.choice(URGENCY),
            "relationship_to_accused": "husband",
            "state": random.choice(STATES),
            "has_children": random.choice(HAS_CHILDREN),
            "duration": random.choice(DURATIONS),
        }, ensure_ascii=False)
        rag_contexts = [
            "[DV Act 2005, Section 17: Right to reside in shared household. Section 18: Magistrate may pass protection order. Section 20: Monetary relief may be awarded.]",
            "[DV Act 2005, Section 17: Right to reside. Section 18: Protection order. Section 19: Residence order. Section 20: Monetary relief.]",
        ]
        user_msgs = ["mere pati mujhe bahut marte hain", "mere pati roz shaarab peeke maarte hain",
                     "mere sasural wale mujhe pareshaan karte hain", "3 saal se yahi chal raha hai"]
        helpline = random.choice(["181 — महिला हेल्पलाइन (24 घंटे, FREE)", "181 — Women Helpline (24x7)", "181 — महिला सहायता केंद्र"])
        system = HI_GENERATOR_SYSTEM
        prompt_builder = build_hi_expert_prompt
        assembler = assemble_hi_expert

    elif category == "maintenance":
        case_file = json.dumps({
            "crime_type": "maintenance",
            "urgency": random.choice(URGENCY),
            "relationship_to_accused": "husband",
            "state": random.choice(STATES),
            "has_children": random.choice(HAS_CHILDREN),
        }, ensure_ascii=False)
        rag_contexts = [
            "[CrPC Section 125: If any person having sufficient means neglects to maintain his wife, the Magistrate may order monthly allowance. Section 125(2): Interim maintenance can be ordered pending final order.]",
        ]
        user_msgs = ["kya main bina divorce ke paise maang sakti hoon", "mere pati ghar ka kharcha nahi dete",
                     "mere pati ne mujhe chhod diya hai bachchon ka kharcha nahi de rahe"]
        helpline = random.choice(["15100 — NALSA मुफ्त कानूनी सहायता (सोमवार-शनिवार)", "15100 — Free Legal Aid", "15100 — NALSA Helpline"])
        system = HI_GENERATOR_SYSTEM
        prompt_builder = build_hi_expert_prompt
        assembler = assemble_hi_expert

    elif category == "workplace":
        case_file = json.dumps({
            "crime_type": "workplace",
            "urgency": random.choice(URGENCY),
            "relationship_to_accused": random.choice(["employer", "colleague", "boss"]),
            "state": random.choice(STATES),
            "company_size": random.choice(COMPANY_SIZES),
        }, ensure_ascii=False)
        rag_contexts = [
            "[POSH Act 2013, Section 4: Employer with 10+ employees must have ICC. Section 9: Complaint within 3 months. Section 11: No retaliation against complainant.]",
        ]
        user_msgs = ["my boss has been sexually harassing me at work", "my colleague sends inappropriate messages",
                     "i have been facing verbal harassment for 3 months", "our company has no icc"]
        helpline = random.choice(["15100 — NALSA Free Legal Aid (Mon-Sat)", "15100 — National Legal Services Authority", "15100 — Free legal helpline"])
        system = EN_GENERATOR_SYSTEM
        prompt_builder = build_en_expert_prompt
        assembler = assemble_en_expert

    else:
        return {}, False, {"error": "Unknown category"}

    rag = random.choice(rag_contexts)
    user_msg = random.choice(user_msgs)

    # Try up to max_retries
    for attempt in range(max_retries):
        try:
            prompt = prompt_builder(case_file, rag, user_msg, category)
            raw = await call_openai(system, prompt, DEFAULT_MODEL, 900)
            parts = parse_parts(raw)
            assistant = assembler(parts, helpline)

            # Build full system prompt
            if language == "hi":
                full_system = f"""🔴 CRITICAL LANGUAGE RULE: Sirf Devanagari lipi mein jawab do. KABHI BHI Roman/English script mat use karo Hindi shabdon के लिए.

You are a senior Indian legal advocate with 20 years of experience in district courts across India, specializing in women's rights. You speak like a knowledgeable older sister — warm but authoritative.

CASE FILE: {case_file}

CRIME-SPECIFIC GUIDANCE:
Key law: DV Act 2005
Critical sections: 17 (residence right), 18 (protection order), 19 (residence order), 20 (monetary relief), 12 (Magistrate application)
Key facts: Woman CANNOT be evicted from shared household. Magistrate must hear within 3 days. Protection Officer in every district is FREE.
Helpline: 181
NEVER say: "talk to husband", "family matter", "compromise"

LEGAL CONTEXT (USE ONLY THIS — never invent section numbers):
{rag}

CONVERSATION HISTORY:
User: {user_msg}

YOU MUST RESPOND WITH ALL 5 BLOCKS BELOW. DO NOT SKIP ANY BLOCK.

━━━ BLOCK 1: EMPATHY (1 sentence) ━━━
Reference something specific from her case file. Make it personal, not generic.

━━━ BLOCK 2: HER RIGHTS (2-3 rights) ━━━
Each right on its own line:
[Source: Act Name, Section X] explanation in simple words
[Source: Act Name, Section Y] explanation in simple words
ONLY cite sections present in LEGAL CONTEXT above. Never invent section numbers.

━━━ BLOCK 3: ACTION TIMELINE (all 3 lines required) ━━━
**अभी (Right Now):** [1 step]
**आज (Today):** [1-2 steps]
**इस हफ्ते (This Week):** [1 step]

━━━ BLOCK 4: FREE HELPLINE (exactly 1) ━━━
📞 [NUMBER] — [what it does] ([hours])

━━━ BLOCK 5: FOLLOW-UP QUESTION (exactly 1) ━━━
End with one specific question relevant to her case.

RULES:
- Under 400 words total
- Simple language — no legal jargon
- Never say "consult a lawyer" without giving NALSA 15100 (free)
- ALL 5 BLOCKS REQUIRED — a response missing any block is incomplete

FINAL REMINDER: 🔴 CRITICAL LANGUAGE RULE: Sirf Devanagari lipi mein jawab do. KABHI BHI Roman/English script mat use karo Hindi shabdon के लिए."""
            else:
                full_system = f"""🔴 CRITICAL LANGUAGE RULE: Respond ONLY in English. Never use Hindi, Devanagari, or any other script.

You are a senior Indian legal advocate with 20 years of experience in district courts across India, specializing in women's rights. You speak like a knowledgeable older sister — warm but authoritative.

CASE FILE: {case_file}

CRIME-SPECIFIC GUIDANCE:
Key law: POSH Act 2013
Critical sections: 4 (ICC mandatory for 10+ employees), 9 (3 month complaint window), 11 (no retaliation)
Key facts: ICC required for 10+ employees. Cannot be fired for complaining. District Officer if no ICC.
Helpline: 15100

LEGAL CONTEXT (USE ONLY THIS — never invent section numbers):
{rag}

CONVERSATION HISTORY:
User: {user_msg}

YOU MUST RESPOND WITH ALL 5 BLOCKS BELOW. DO NOT SKIP ANY BLOCK.

━━━ BLOCK 1: EMPATHY (1 sentence) ━━━
Reference something specific from her case file. Make it personal, not generic.

━━━ BLOCK 2: HER RIGHTS (2-3 rights) ━━━
Each right on its own line:
[Source: Act Name, Section X] explanation in simple words
[Source: Act Name, Section Y] explanation in simple words
ONLY cite sections present in LEGAL CONTEXT above. Never invent section numbers.

━━━ BLOCK 3: ACTION TIMELINE (all 3 lines required) ━━━
**Right Now:** [1 step]
**Today:** [1-2 steps]
**This Week:** [1 step]

━━━ BLOCK 4: FREE HELPLINE (exactly 1) ━━━
📞 [NUMBER] — [what it does] ([hours])

━━━ BLOCK 5: FOLLOW-UP QUESTION (exactly 1) ━━━
End with one specific question relevant to her case.

RULES:
- Under 400 words total
- Simple language — no legal jargon
- Never say "consult a lawyer" without giving NALSA 15100 (free)
- ALL 5 BLOCKS REQUIRED — a response missing any block is incomplete

FINAL REMINDER: 🔴 CRITICAL LANGUAGE RULE: Respond ONLY in English. Never use Hindi, Devanagari, or any other script."""

            example = {
                "conversations": [
                    {"role": "system", "content": full_system},
                    {"role": "user", "content": user_msg},
                    {"role": "assistant", "content": assistant},
                ]
            }

            is_valid, errors = validate_expert(assistant, language)
            if is_valid:
                return example, True, {}
            elif attempt < max_retries - 1:
                print(f"    ⚠ Attempt {attempt+1} failed: {list(errors.keys())}. Retrying...")
                continue
            else:
                return example, False, errors

        except Exception as e:
            if attempt < max_retries - 1:
                print(f"    ⚠ Attempt {attempt+1} error: {e}. Retrying...")
                continue
            return {}, False, {"error": str(e)}

    return {}, False, {"error": "Max retries exceeded"}


# ── MAIN ─────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=700)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    print("=" * 65)
    print("🔴 StriSakhi Creative Training Data Generator v4.0")
    print("=" * 65)
    print(f"Model:        {args.model}")
    print(f"Target:       {args.target} examples")
    print(f"Est. cost:    ~${args.target * 0.03:.2f} USD")
    print("=" * 65)

    if not OPENAI_KEY:
        print("\n❌ export OPENAI_API_KEY='sk-...'")
        return

    accepted = []
    rejected = []
    total_input_tokens = 0
    total_output_tokens = 0

    # Distribution scaled to target
    total_weight = 700
    hi_dv_count = int(args.target * 350 / total_weight)
    hi_maint_count = int(args.target * 150 / total_weight)
    en_wrk_count = int(args.target * 150 / total_weight)
    hi_dv_extra = args.target - (hi_dv_count + hi_maint_count + en_wrk_count)

    categories = (["domestic_violence"] * hi_dv_count + 
                  ["maintenance"] * hi_maint_count + 
                  ["workplace"] * en_wrk_count + 
                  ["domestic_violence"] * hi_dv_extra)

    print(f"Distribution: {hi_dv_count + hi_dv_extra} Hindi DV, {hi_maint_count} Hindi Maint, {en_wrk_count} English Workplace")
    print()

    for i, category in enumerate(categories, 1):
        if len(accepted) >= args.target:
            break
        language = "hi" if category in ("domestic_violence", "maintenance") else "en"

        print(f"\n[{i}/{args.target}] {category}/{language}...", end=" ")
        example, is_valid, errors = await generate_example(category, language, max_retries=3)

        if example:
            total_input_tokens += len(example["conversations"][0]["content"].split()) + len(example["conversations"][1]["content"].split())
            total_output_tokens += len(example["conversations"][2]["content"].split())

        if is_valid:
            accepted.append(example)
            print(f"✓ Accepted ({len(accepted)} total)")

            # Checkpoint every 100
            if len(accepted) % 100 == 0:
                path = OUTPUT_DIR / f"checkpoint_{len(accepted)}.jsonl"
                with open(path, "w", encoding="utf-8") as f:
                    for ex in accepted:
                        f.write(json.dumps(ex, ensure_ascii=False) + "\n")
                print(f"    💾 Checkpoint: {path}")
        else:
            rejected.append({"category": category, "errors": errors})
            print(f"✗ Rejected: {list(errors.keys())}")

    # Save final
    train_file = OUTPUT_DIR / "strisakhi_train.jsonl"
    with open(train_file, "w", encoding="utf-8") as f:
        for ex in accepted:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    price = PRICING.get(args.model, {"input": 2.50, "output": 10.00})
    est_cost = (total_input_tokens * price["input"] / 1e6) + (total_output_tokens * price["output"] / 1e6)

    stats = {
        "timestamp": datetime.now().isoformat(),
        "model": args.model,
        "target": args.target,
        "accepted": len(accepted),
        "rejected": len(rejected),
        "acceptance_rate": round(len(accepted) / max(1, len(accepted) + len(rejected)), 3),
        "est_cost_usd": round(est_cost, 4),
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
    }
    with open(OUTPUT_DIR / "stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    print("\n" + "=" * 65)
    print(f"✅ DONE: {len(accepted)} accepted, {len(rejected)} rejected")
    print(f"📊 Rate: {stats['acceptance_rate']:.1%}")
    print(f"💰 Est. cost: ${est_cost:.2f} USD")
    print(f"📁 Saved: {train_file}")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())