# StriSakhi — Complete Agent Design: All 3 Sakhis, All Phases

---

## PART A: SEHAT SAKHI (Medical) — Plan

### Health Crisis Numbers (NFHS-5 2019-21)
- **59.1% of women aged 15-49 are anaemic** — up from 54.1% in 2015-16
- **Maternal Mortality Rate: 103 per 1,00,000 live births**
- **Only 65% of deliveries** happen in institutions in rural areas
- **18.7% of women** have BMI under 18.5 (severely underweight)
- **Depression affects 1 in 5 Indian women** — 80% never seek help
- **34% of rural women** face intimate partner violence — major mental health driver

### Top 8 Health Issues for Sehat Sakhi

```
1. Pregnancy Complications          ← most common rural emergency
2. Child Illness & Fever            ← second most common query
3. Anaemia & Malnutrition           ← 59% of women affected
4. Mental Health / Depression       ← most underserved need
5. Reproductive Health              ← contraception, menstruation
6. Domestic Violence Health Impact  ← injuries, trauma
7. Postpartum Issues                ← depression, breastfeeding
8. Chronic Conditions               ← diabetes, thyroid, BP
```

### Universal Parameters for Sehat Sakhi

```
PARAM 1: HEALTH ISSUE TYPE (auto-detect from first message)
  Values: pregnancy | child_illness | mental_health | anaemia |
          reproductive | injury_dv | postpartum | chronic | other

PARAM 2: URGENCY
  Values: emergency | urgent_today | this_week | general_question
  Emergency signals: unconscious, heavy bleeding, fits/seizures,
                     baby not moving, chest pain, cannot breathe
  → fires emergency_response() immediately

PARAM 3: WHO IS THE PATIENT
  Values: self | child | baby | elder
  Why: Completely different advice for self vs child vs newborn

PARAM 4: PREGNANCY STATUS (if relevant)
  Values: pregnant | postpartum_recent | not_pregnant | unknown
  Why: Many medicines dangerous in pregnancy. Symptoms mean different things.

PARAM 5: AGE / LIFE STAGE
  Values: girl_child | adolescent | reproductive_age | menopausal
  Why: Anaemia advice differs for 13-year-old vs 45-year-old

PARAM 6: ACCESS TO HEALTHCARE
  Values: near_phc | distant | no_access | private_available
  Why: "Go to doctor" is useless if nearest doctor is 3 hours away.
       Need to give home management + when to urgently travel.
```

### Sehat Sakhi Intake Flow (4 turns max)

```
TURN 1: User describes health issue
  LLM: detect issue_type + urgency
  IF EMERGENCY → emergency_response() immediately
  Response: ONE empathetic question about urgency
  Example: "Yeh sunke bahut chinta hui. Yeh problem kitne samay se hai? 
            Kya unhe abhi bukhar hai?"

TURN 2: Understand patient + context
  Example (child): "Bacche ki umar kya hai? Aur kya usse ulti bhi ho rahi hai?"
  Example (pregnancy): "Aap kitne mahine ki pregnant hain?"
  Example (mental health): "Yeh feeling kitne dino se hai? 
                            Kya aap neend le pa rahi hain?"

TURN 3: Access to care
  "Kya aapke paas koi PHC ya ANM hai gaon mein? 
   Ya nearest hospital kitni door hai?"
  → This determines advice: home care vs urgent travel vs telemedicine

TURN 4 → Expert Response
```

### Sehat Sakhi Expert Response Structure

```
BLOCK 1: Empathy (1 sentence)
BLOCK 2: What this likely means (plain language, NOT diagnosis)
BLOCK 3: What to do RIGHT NOW at home
BLOCK 4: WARNING SIGNS — "If you see THIS, go to hospital immediately"
BLOCK 5: Free government resource / scheme
BLOCK 6: NEVER prescribe medicines by name

Follow-up chips after response:
"Kya main ghar par hi treat kar sakti hoon?"
"Kab hospital jaana zaroori hai?"
"Konsi government scheme milegi?"
"Yeh dobara kaise roke?"
"Bacche ke liye kya karein?"
```

### Emergency Keywords for Sehat Sakhi

```
Hindi: "behosh", "khoon aa raha", "dauraa", "saans nahi", "hilna band",
       "pet mein bahut dard", "aankhon ke aage andhera"
English: "unconscious", "bleeding heavily", "fitting", "not breathing",
         "baby not moving", "severe pain", "can't see"
Bengali: "behosh", "rokto poRche", "khaanchi", "nishwas nite parche na"
```

---

## PART B: YOJANA SAKHI (Scheme) — Plan

### Scheme Awareness Crisis
- India has **490+ government schemes for women** across all ministries
- **"Many women, especially in rural areas, are unaware of available schemes. Poor outreach limits the intended impact."**
- Studies show **~25% of rural population unaware** of even major schemes
- The awareness gap is the biggest barrier — not eligibility

### Top 10 Scheme Categories for Yojana Sakhi

```
1. Housing (PM Awas Yojana)         ← 1.2 crore homes built, millions still need
2. Health Insurance (Ayushman Bharat) ← Rs 5 lakh free — most don't know
3. Free LPG (Ujjwala)              ← 9 crore connections given, more pending
4. Banking (Jan Dhan)              ← 53 crore accounts — still gaps
5. Maternity (PMMVY, JSY)          ← cash benefits for pregnant women
6. Education (BBPB, Scholarships)  ← girl child education schemes
7. Employment (MGNREGS, PMKVY)     ← guaranteed work, skill training
8. Business Loans (Mudra, Stand Up) ← women entrepreneurs
9. Pension (Widow, Old Age)        ← BPL women's financial security
10. Safety (One Stop Centre, Nirbhaya Fund) ← women in distress
```

### Universal Parameters for Yojana Sakhi

```
PARAM 1: LIFE SITUATION (auto-detect from first message)
  Values: pregnant | widow | farmer | unemployed | student |
          domestic_violence | homeless | elderly | entrepreneur | general
  Why: Routes to relevant scheme category immediately

PARAM 2: BPL / INCOME LEVEL
  Values: bpl_card | no_card_but_poor | middle | unknown
  How: "Kya aapके paas ration card hai?"
  Why: Most major schemes require BPL status. Jan Dhan does not.

PARAM 3: STATE
  Values: any Indian state
  Why: Many schemes are state-specific. 
       PM Awas amounts differ by state.
       State-specific helplines differ.
  Priority parameter for Yojana Sakhi — always ask.

PARAM 4: DOCUMENTS AVAILABLE
  Values: has_aadhaar | has_ration_card | has_bank_account | has_land_papers
  How: "Kya aapke paas Aadhaar card hai?"
  Why: Determines which schemes user can apply for right now.
       No Aadhaar → Jan Dhan first, then others.

PARAM 5: MARITAL STATUS
  Values: married | widow | unmarried | separated
  Why: Widow pension, IGNWPS require marital status.
       Maternity schemes require married/pregnant status.

PARAM 6: URGENCY OF NEED
  Values: immediate_need | planning | just_curious
  Why: Homeless woman needs PMAY info today.
       Student can plan scholarship application for next cycle.
```

### Yojana Sakhi Intake Flow (4 turns max)

```
TURN 1: User describes situation
  LLM: detect life_situation + urgency
  Response: ONE warm question
  Example: "Bahut accha kiya jo poochha! 
            Kya aap mere saath apna ration card number share kar sakti hain 
            ya batayein ki ration card hai?"

TURN 2: State + documents
  "Aap kis state mein hain? Aur kya aapka Jan Dhan account hai?"
  Why: These two determine 80% of applicable schemes

TURN 3: Specific situation detail
  For pregnancy: "Yeh pahli pregnancy hai?"
  For widow: "Aapke pati kab gaye? Aur umar kya hai aapki?"
  For housing: "Kya aapke paas apni zameen hai ya kiraaye par rehti hain?"

TURN 4 → Expert Response: 3 most relevant schemes with eligibility + how to apply
```

### Yojana Sakhi Expert Response Structure

```
BLOCK 1: "Aapke liye yeh schemes hain:" (skip empathy — be useful fast)
BLOCK 2: TOP SCHEME (most relevant)
  - Name + what it gives
  - Eligibility in ONE sentence
  - Exactly where to apply + what documents to bring
BLOCK 3: SECOND SCHEME (related)
  Same format
BLOCK 4: THIRD SCHEME (bonus — often universal like Jan Dhan)
  Same format
BLOCK 5: "CSC (Common Service Centre) aapke nearest gaon mein 
           in sab ke liye apply karne mein madad kar sakta hai"

Follow-up chips:
"Kya main CSC mein ek hi din mein apply kar sakti hoon?"
"Aadhaar nahi hai toh kya karein?"
"Yojana ke paise kab tak aayenge?"
"Mere bacche ke liye koi yojana hai?"
"Kya main ek se zyada yojana le sakti hoon?"
```

---

## PART C: ALL THREE SAKHIS — Shared Agent Improvements

### Follow-Up Question Generation (LLM-driven)

After every expert response, the LLM generates 4-5 follow-up chips.
These are NOT hardcoded — LLM generates them based on what was just discussed.

API response adds new field:
```json
{
  "type": "done",
  "full_response": "...",
  "follow_up_questions": [
    "Protection order kaise milega?",
    "FIR kaise file karein?",
    "Muft vakeel kahan milega?",
    "Bacchon ki custody?",
    "Kya main ghar mein reh sakti hoon abhi?"
  ]
}
```

Frontend shows these as tappable chips below the response.
Tapping sends as message → expert responds → new chips generated.
Conversation never ends.

### Language-Specific Empathy Phrases (Injected into System Prompt)

```python
EMPATHY_PHRASES = {
    "hi": [
        "Yeh sunke bahut dukh hua.",
        "Main samajh sakti hoon aap kitni takleef mein hain.",
        "Aap bilkul akeli nahi hain.",
        "Aapne sahi kiya mujhse baat ki.",
        "Main poori koshish karungi aapki madad karne ki.",
    ],
    "en": [
        "I'm so sorry you're going through this.",
        "You are not alone in this.",
        "You were right to reach out.",
        "I'll do everything I can to help you.",
        "This takes courage — I'm here with you.",
    ],
    "bn": [
        "Eta shune khub koshto holo.",
        "Apni ekdom eka non.",
        "Apni thik korechen amake bolte.",
        "Ami apnar pashe achi.",
    ]
}
```

LLM picks one based on context (not random — chooses what fits the situation).

### Emergency Function Design (All Three Sakhis)

```
PHASE 1 (immediate): Frontend full-screen overlay
  Shows helplines based on Sakhi type:
  
  Kanoon Sakhi emergency:  181, 100, 1091, 15100
  Sehat Sakhi emergency:   108, 102, 104, 181
  Yojana Sakhi emergency:  181, 1800-419-8588 (trafficking), 1098 (child)

PHASE 2 (parallel): Backend still generates expert response
  Emergency expert response is SHORT (under 100 tokens):
  "Pehle 181 call karein. Main aapki madad ke liye yahan hoon."
  
PHASE 3 (after overlay dismissed): Full expert response ready
  Conversation continues as normal
  Emergency does NOT end the session
```

---

## PHASE 2: STRONGER EXPERT RESPONSES

### Action Timeline (New in Expert Response)

Every expert response gets a time-based action structure:

```
ABHI (Right Now — within 1 hour):
  Call 181 / Go to safe place / Document injuries with photos

AAJ (Today — within 24 hours):
  File FIR / Go to PHC / Visit Anganwadi / Call NALSA 15100

IS HAFTE (This Week):
  Apply for protection order / Collect documents / Contact DLSA

AAGE (Future Steps):
  Court dates / Follow-up / Scheme applications
```

This helps women who are in crisis mode — they need to know what to do RIGHT NOW, not a lecture on legal theory.

### Crime-Specific Expert Prompts Summary

Each of the 10 crime types gets a dedicated system prompt block injected into the expert agent. Example:

```python
CRIME_EXPERT_PROMPTS = {
    "domestic_violence": """
        Primary law: DV Act 2005
        Key sections: 17 (residence), 18 (protection), 19 (residence order), 20 (maintenance)
        Always mention: Protection Officer (free), Magistrate application (no lawyer needed)
        Action today: 181, nearest police station, Protection Officer
        Never say: "talk to husband", "family matter", "compromise"
    """,
    "property": """
        Primary law: Hindu Succession Act 1956, Vineeta Sharma SC 2020
        Key right: Equal coparcenary rights from birth
        Always mention: DLSA for free partition suit, 15100 for lawyer
        Action today: Collect birth certificate, father's documents
        Critical: 2020 SC ruling applies EVEN IF father died before 2005
    """,
    "workplace": """
        Primary law: POSH Act 2013
        Key right: ICC mandatory for 10+ employees. Cannot be fired for complaining.
        Always mention: District Officer if no ICC, 3-month complaint window
        Action today: Written complaint to HR/ICC, document all incidents
    """,
    # ... all 10 crimes
}
```

---

## PHASE 3: COMPLETE FRONTEND CHANGES

### Follow-Up Chips Component

```
After every expert response:
  ┌─────────────────────────────────┐
  │ ⚖️ Kanoon Sakhi                  │
  │                                  │
  │ [response text here]             │
  │                                  │
  │ Suggested questions:             │
  │ [FIR kaise karein?] [Vakeel?]   │
  │ [Ghar mein rehna?] [Bachche?]   │
  └─────────────────────────────────┘
  
  Chips are:
  - Tappable
  - Horizontal scroll (mobile)
  - Disappear when tapped (sent as message)
  - New chips appear after next expert response
```

### Emergency Overlay Component

```
On EMERGENCY_DETECTED:
  ┌─────────────────────────────────┐
  │  🆘 EMERGENCY HELP              │
  │  ─────────────────────          │
  │  📞 181 — Mahila Helpline       │
  │       (24 ghante, FREE)         │
  │                                 │
  │  📞 100 — Police                │
  │                                 │
  │  📞 108 — Ambulance             │
  │                                 │
  │  📞 1091 — Women in Distress    │
  │                                 │
  │  [Main surakshit hoon — aage    │
  │   baat karein]                  │
  └─────────────────────────────────┘
  
  - Shown OVER the chat, not replacing it
  - User must tap button to dismiss
  - Chat continues underneath
  - Button text changes based on language/sakhi
```

### Language Picker Enhancement

Add "Coming Soon" languages with reason:

```
Currently:
  [हिंदी ✅] [English ✅] [বাংলা ✅]

Soon:
  [தமிழ் 🔜] [తెలుగు 🔜] [मराठी 🔜]
  [ਪੰਜਾਬੀ 🔜] [ગુજરાતી 🔜]
  
Tooltip on hover: "Jaldi aa raha hai!"
```

---

## IMPLEMENTATION ORDER (Code First)

```
Step 1: intake_agent.py
  - Add 6 universal parameters per Sakhi
  - Add frustration detection
  - Add language-specific empathy phrases
  - Add per-Sakhi system prompts

Step 2: legal_agent.py + medical_agent.py + scheme_agent.py
  - Add 5-block response structure
  - Add follow-up question generation
  - Add crime/issue-specific prompt blocks
  - Add action timeline (abhi/aaj/is hafte)

Step 3: model_router.py
  - Wire intake_max_turns to config_runtime.json
  - Add frustration_detected flag

Step 4: emergency/detector.py
  - Add multilingual keywords per Sakhi
  - Add severity levels

Step 5: App.jsx (frontend)
  - Follow-up chips component
  - Emergency overlay component
  - Updated language picker

Step 6: Ingest new RAG documents (20 PDFs)
```
