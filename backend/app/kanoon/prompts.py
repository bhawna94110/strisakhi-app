"""
StriSakhi — Frozen Prompts v1.1
All prompts centralized here. Change nothing without re-running benchmark.
"""

# ─── Language instructions ────────────────────────────────────────────────────

LANG_INSTRUCTION = {
    "hi": (
        "🔴 CRITICAL: Sirf Devanagari lipi mein jawab do. "
        "KABHI BHAI Roman/English script mat use karo Hindi shabdon ke liye. "
        "Agar user Hinglish mein likhe, aap phir bhi Devanagari mein jawab do. "
        "Legal citations [Source: Act, Section] English mein reh sakte hain."
    ),
    "en": (
        "🔴 CRITICAL: Respond ONLY in English. "
        "Never use Hindi, Devanagari, or any other script."
    ),
    "bn": (
        "🔴 CRITICAL: Sudhu Bangla lipi te uttor dao. "
        "Roman ba Hindi lipi kokhono byabohar koro na. "
        "Legal citations [Source: Act, Section] English e thakbe."
    ),
}

# ─── Intake question bank — used by intake node ──────────────────────────────
# Each entry: (field_name, question_hi, question_en, why_it_matters)

INTAKE_QUESTIONS = {
    # Universal
    "urgency": (
        "urgency",
        "क्या यह अभी हो रहा है, या पहले से चल रहा है?",
        "Is this happening right now, or has it been ongoing?",
        "Changes entire strategy — immediate needs emergency response"
    ),
    "relationship_to_accused": (
        "relationship_to_accused",
        "यह कौन कर रहा है — पति, सास-ससुर, मालिक, या कोई और?",
        "Who is doing this — husband, in-laws, employer, or someone else?",
        "Determines which law applies"
    ),
    "state_india": (
        "state_india",
        "आप किस राज्य में हैं?",
        "Which state in India are you in?",
        "State-specific helplines and legal aid centres"
    ),
    "other_context": (
        "other_context",
        "कोई और बात जो आप बताना चाहती हैं जो मुझे जाननी चाहिए?",
        "Is there anything else important I should know about your situation?",
        "Free text sent verbatim to expert"
    ),

    # Domestic Violence
    "type_of_violence": (
        "type_of_violence",
        "हिंसा किस तरह की है — मारपीट, गाली-गलौज, घर से निकालने की धमकी, या पैसे न देना?",
        "What type — physical beating, verbal abuse, threat to evict, or financial control?",
        "Each maps to different DV Act sections"
    ),
    "living_situation": (
        "living_situation",
        "आप अभी उसी घर में रह रही हैं जहाँ वो हैं?",
        "Are you currently living in the same house as them?",
        "Section 17 shared household definition"
    ),
    "house_ownership": (
        "house_ownership",
        "घर किसके नाम पर है — पति के, ससुर के, किराए का, या आपके?",
        "Whose name is the house in — husband's, in-laws', rented, or yours?",
        "Affects residence order under Section 19 DV Act"
    ),
    "financial_dependence": (
        "financial_dependence",
        "क्या आप आर्थिक रूप से पति पर निर्भर हैं?",
        "Are you financially dependent on your husband?",
        "Section 20 monetary relief amount"
    ),
    "previous_complaints": (
        "previous_complaints",
        "क्या आपने पहले कभी पुलिस या कोर्ट में शिकायत की है?",
        "Have you ever filed a police complaint or court application before?",
        "Prior FIR strengthens case + shows pattern"
    ),
    "medical_evidence": (
        "medical_evidence",
        "क्या आपने कभी मारपीट के बाद अस्पताल में इलाज कराया?",
        "Have you ever received medical treatment after being beaten?",
        "Medical records = strongest evidence"
    ),
    "dowry_demand": (
        "dowry_demand",
        "क्या शादी में या बाद में दहेज की माँग भी हुई?",
        "Was dowry also demanded at or after marriage?",
        "If yes → adds IPC 498A angle automatically"
    ),
    "witnesses": (
        "witnesses",
        "क्या कोई गवाह है — पड़ोसी, परिवार, या कोई और?",
        "Are there any witnesses — neighbours, family, or others?",
        "Witness availability changes court strategy"
    ),

    # Property
    "property_type": (
        "property_type",
        "यह संपत्ति कैसी है — पुरखों की (ancestral) है, या पिताजी ने खुद कमाई?",
        "Is this ancestral property or self-acquired by your father?",
        "Ancestral = Vineeta Sharma 2020 SC applies automatically"
    ),
    "father_alive": (
        "father_alive",
        "क्या आपके पिताजी अभी जीवित हैं?",
        "Is your father still alive?",
        "Alive = partition suit. Dead = succession + probate"
    ),
    "religion": (
        "religion",
        "आप किस धर्म को मानती हैं — हिंदू, मुस्लिम, ईसाई, या अन्य?",
        "What is your religion — Hindu, Muslim, Christian, or other?",
        "Determines which personal law applies"
    ),
    "will_exists": (
        "will_exists",
        "क्या पिताजी ने कोई वसीयत (will) लिखी थी?",
        "Did your father write a will?",
        "Will changes legal challenge strategy"
    ),
    "who_blocking": (
        "who_blocking",
        "कौन आपको हिस्सा नहीं देना चाहता — भाई, चाचा, या कोई और?",
        "Who is blocking your share — brother, uncle, or someone else?",
        "Determines respondents in partition suit"
    ),
    "already_sold": (
        "already_sold",
        "क्या भाई ने संपत्ति का कोई हिस्सा बेच दिया है, या बेचने की कोशिश हो रही है?",
        "Has your brother already sold any part, or is he trying to sell?",
        "Trying to sell = urgent injunction needed"
    ),
    "property_registered": (
        "property_registered",
        "क्या संपत्ति किसी के नाम पर registered है?",
        "Is the property registered in someone's name?",
        "Registration status affects partition suit"
    ),
    "documents_available": (
        "documents_available",
        "क्या आपके पास कोई कागज़ात हैं — ज़मीन का पट्टा, मृत्यु प्रमाण पत्र?",
        "Do you have any documents — land records, death certificate?",
        "Document availability shapes legal strategy"
    ),

    # Maintenance
    "marital_status_current": (
        "marital_status_current",
        "आप अभी पति के साथ हैं, अलग रह रही हैं, या तलाक हो गया?",
        "Are you currently with husband, separated, or divorced?",
        "Determines CrPC 125 vs HMA 25"
    ),
    "husband_income": (
        "husband_income",
        "आपके पति क्या काम करते हैं और उनकी अनुमानित आमदनी कितनी है?",
        "What does your husband do and what is his approximate income?",
        "Court sets maintenance as % of husband's income"
    ),
    "your_income": (
        "your_income",
        "क्या आप खुद कुछ कमाती हैं?",
        "Do you have any income of your own?",
        "Wife's income reduces maintenance amount"
    ),
    "husband_paying_anything": (
        "husband_paying_anything",
        "क्या पति अभी कुछ भी दे रहे हैं?",
        "Is your husband currently paying you anything at all?",
        "Complete refusal = stronger Section 125 application"
    ),
    "how_long_separated": (
        "how_long_separated",
        "कितने समय से अलग हैं या पैसे नहीं मिल रहे?",
        "How long have you been separated or not receiving money?",
        "Arrears claimed from date of application"
    ),
    "reason_for_separation": (
        "reason_for_separation",
        "अलग क्यों हुईं — पति ने छोड़ा, या आप खुद आईं?",
        "Why did you separate — did husband abandon you, or did you leave?",
        "Wife left due to cruelty = still entitled to maintenance"
    ),

    # Workplace
    "company_size": (
        "company_size",
        "आपकी कंपनी में कितने कर्मचारी हैं — 10 से ज़्यादा या कम?",
        "Does your company have more than 10 employees?",
        "ICC mandatory only for 10+ employees"
    ),
    "accused_designation": (
        "accused_designation",
        "यह किसने किया — आपके सीधे बॉस ने, senior management ने, सहकर्मी ने, या client ने?",
        "Who did this — your direct boss, senior management, colleague, or client?",
        "Boss = power dynamic strengthens case"
    ),
    "incident_type": (
        "incident_type",
        "क्या हुआ — गलत तरीके से छूना, गंदी बातें, काम के बदले कुछ माँगना, या online messages?",
        "What happened — inappropriate touching, verbal comments, quid pro quo demands, or digital messages?",
        "Each type has different evidence requirements"
    ),
    "icc_exists": (
        "icc_exists",
        "क्या आपकी कंपनी में ICC (Internal Complaints Committee) है?",
        "Does your company have an Internal Complaints Committee (ICC)?",
        "No ICC = company violated POSH Act Section 4"
    ),
    "evidence_available": (
        "evidence_available",
        "क्या कोई सबूत है — WhatsApp, email, या गवाह?",
        "Is there any evidence — WhatsApp messages, emails, or witnesses?",
        "Evidence type shapes ICC complaint"
    ),
    "retaliation_happened": (
        "retaliation_happened",
        "क्या शिकायत के डर से या बाद में आपको नुकसान हुआ — transfer, demotion, या निकाला?",
        "Have you faced retaliation — transfer, demotion, or termination?",
        "Retaliation = automatic POSH Act Section 11 violation"
    ),
    "reported_to_hr": (
        "reported_to_hr",
        "क्या आपने HR को बताया? उन्होंने क्या किया?",
        "Did you report to HR? What did they do?",
        "HR inaction = employer liable under POSH Act"
    ),

    # Divorce
    "grounds": (
        "grounds",
        "तलाक क्यों चाहिए — मारपीट, पति ने छोड़ दिया, कोई और है उनकी ज़िंदगी में, या आपसी सहमति?",
        "Why divorce — cruelty, desertion, adultery, or mutual consent?",
        "Each ground = different legal process and timeline"
    ),
    "husband_consent": (
        "husband_consent",
        "क्या पति भी तलाक देने को राज़ी है?",
        "Is your husband also willing to divorce?",
        "Mutual consent = 6 months. Contested = 2-3 years"
    ),
    "maintenance_needed": (
        "maintenance_needed",
        "क्या आप तलाक के बाद गुज़ारा भत्ता चाहती हैं?",
        "Do you need maintenance/alimony after divorce?",
        "Section 25 HMA — must file simultaneously"
    ),
    "separation_duration": (
        "separation_duration",
        "आप कितने समय से अलग हैं?",
        "How long have you been separated?",
        "2 years = desertion ground. 1 year = mutual consent possible"
    ),
    "marriage_registered": (
        "marriage_registered",
        "क्या आपकी शादी officially registered है?",
        "Is your marriage officially registered?",
        "Unregistered = harder to prove but still valid"
    ),

    # Dowry
    "demand_type": (
        "demand_type",
        "क्या माँग हो रही है — पैसे, गहने, ज़मीन, या कुछ और?",
        "What is being demanded — money, jewellery, land, or something else?",
        "Specific demand maps to specific IPC section"
    ),
    "who_demanding": (
        "who_demanding",
        "माँग कौन कर रहा है — पति, सास, ससुर, या सबने मिलकर?",
        "Who is demanding — husband, mother-in-law, father-in-law, or all together?",
        "All demanding = all named as accused in FIR"
    ),
    "violence_with_demand": (
        "violence_with_demand",
        "माँग पूरी न होने पर मारपीट या धमकी भी होती है?",
        "Is there physical violence or threats when demand is not met?",
        "Violence + demand = IPC 498A + DV Act"
    ),
    "stridhan_returned": (
        "stridhan_returned",
        "क्या आपका स्त्रीधन — गहने, कपड़े, gifts — वापस मिले हैं?",
        "Have your stridhan items — jewellery, clothes, gifts — been returned?",
        "Not returned = IPC 406 (7 years)"
    ),
    "written_evidence": (
        "written_evidence",
        "क्या कोई WhatsApp, letter, या और सबूत है माँग का?",
        "Is there any WhatsApp, letter, or written evidence of the demand?",
        "Written evidence = automatic FIR basis"
    ),

    # Stalking
    "stalking_medium": (
        "stalking_medium",
        "यह कैसे हो रहा है — फोन कॉल, WhatsApp, social media, या सामने आकर?",
        "How is it happening — phone calls, WhatsApp, social media, or physical following?",
        "Online = IT Act. Physical = IPC 354D only"
    ),
    "accused_known": (
        "accused_known",
        "यह व्यक्ति कौन है — आप जानती हैं उसे, या अनजान है?",
        "Do you know who this person is?",
        "Known = immediate police action. Unknown = cyber cell"
    ),
    "content_type": (
        "content_type",
        "वो क्या भेज रहा है — धमकियाँ, अश्लील सामग्री, या बस बार-बार contact?",
        "What is he sending — threats, obscene content, or just repeated contact?",
        "Obscene = IT Act 67. Morphed photos = IT Act 66E"
    ),
    "screenshots_saved": (
        "screenshots_saved",
        "क्या आपने screenshots save की हैं?",
        "Have you saved screenshots or recordings?",
        "Digital evidence is critical for this case"
    ),
    "threats_to_share": (
        "threats_to_share",
        "क्या उसने आपकी photos या videos share करने की धमकी दी है?",
        "Has he threatened to share your photos or videos?",
        "Yes = IPC 354D + IT Act 67A up to 7 years"
    ),

    # Custody
    "children_ages": (
        "children_ages",
        "बच्चों की उम्र क्या है?",
        "What are the children's ages?",
        "Under 5 = mother gets natural custody"
    ),
    "current_custody": (
        "current_custody",
        "अभी बच्चे किसके पास हैं?",
        "Who currently has the children?",
        "Status quo custody matters in court"
    ),
    "divorce_status": (
        "divorce_status",
        "क्या तलाक हो गया है, चल रहा है, या अभी तलाक नहीं हुआ?",
        "Have you divorced, is divorce ongoing, or not yet?",
        "Determines which court and act applies"
    ),
    "father_behaviour": (
        "father_behaviour",
        "क्या पिता का बच्चों के साथ व्यवहार अच्छा रहा है?",
        "Has the father been good to the children?",
        "Father's behavior = key custody factor"
    ),
}


# ─── Expert prompt (frozen v1.1) ──────────────────────────────────────────────

EXPERT_SYSTEM = """{lang_instruction}

You are a senior Indian legal advocate with 20 years of experience
in district courts across India, specializing in women's rights.
You speak like a knowledgeable older sister — warm but authoritative.

CASE FILE (all details collected from intake):
{case_file}

CRIME-SPECIFIC LEGAL GUIDANCE:
{crime_guidance}

VERIFIED LEGAL CONTEXT FROM DATABASE (USE ONLY THIS — never invent section numbers):
{rag_context}

CONVERSATION HISTORY:
{history}

YOU MUST RESPOND WITH ALL 5 BLOCKS. DO NOT SKIP ANY BLOCK.

━━━ BLOCK 1: EMPATHY (1 sentence) ━━━
Reference something SPECIFIC from her case file. Not generic.
Example: "3 साल से यह सहना और फिर भी हिम्मत करके पूछना — यह आसान नहीं है।"

━━━ BLOCK 2: HER RIGHTS (2-3 rights) ━━━
List 2-3 legal rights. Each right on its own line. ALWAYS start each line with the source citation.
Pattern: [Source: LAW_NAME, SECTION] then simple Hindi explanation.
Use sections from LEGAL CONTEXT above — do not invent.
Example pattern (use this structure, not these exact words):
[Source: Act Name, Section X] one sentence explanation of the right.
[Source: Case Name, Court Year] one sentence about what court decided.

━━━ BLOCK 3: ACTION TIMELINE (all 3 lines required) ━━━
{timeline}

━━━ BLOCK 4: FREE HELPLINE (exactly 1) ━━━
Pick the CORRECT helpline based on crime_type in case file:
- crime_type = domestic_violence → 📞 181 — महिला हेल्पलाइन (24x7, FREE)
- crime_type = property OR maintenance OR divorce → 📞 15100 — NALSA मुफ्त कानूनी सहायता (सोमवार-शनिवार)
- crime_type = workplace → 📞 15100 — NALSA मुफ्त कानूनी सहायता
- crime_type = stalking → 📞 1930 — साइबर क्राइम हेल्पलाइन
- crime_type = rape → 📞 181 — महिला हेल्पलाइन (24x7, FREE)
Write exactly: 📞 [NUMBER] — [description] ([hours])

━━━ BLOCK 5: FOLLOW-UP QUESTION (exactly 1) ━━━
One specific question relevant to her case. Write in {lang_name}.

RULES:
- Under 400 words total
- Simple language — no legal jargon
- ALL 5 BLOCKS REQUIRED
- BLOCK HEADERS stay in English exactly as written — do NOT translate
- Content inside blocks in {lang_name}
- For Hindi Devanagari: Protection Order=सुरक्षा आदेश, Section=धारा, Magistrate=मजिस्ट्रेट,
  Court=न्यायालय, FIR=प्राथमिकी, Lawyer=वकील, Maintenance=भरण-पोषण

{lang_instruction}"""

TIMELINE_FORMAT = {
    "hi": "**अभी (Right Now):** [1 step]\n**आज (Today):** [1-2 steps]\n**इस हफ्ते (This Week):** [1 step]",
    "en": "**Right Now:** [1 step]\n**Today:** [1-2 steps]\n**This Week:** [1 step]",
    "bn": "**এখনই (Right Now):** [1 step]\n**আজ (Today):** [1-2 steps]\n**এই সপ্তাহে (This Week):** [1 step]",
}

# ─── Crime guidance blocks ────────────────────────────────────────────────────

CRIME_GUIDANCE = {
    "domestic_violence": """
Key law: DV Act 2005
Sections: 17 (residence right), 18 (protection order), 19 (residence order),
          20 (monetary relief), 12 (Magistrate application), 21 (custody)
Key facts:
- Woman CANNOT be evicted from shared household regardless of ownership
- Magistrate MUST hear application within 3 days
- Protection Officer in every district helps file for FREE
- IPC 498A if in-laws also involved (cognizable — police can arrest without warrant)
- If dowry angle confirmed: also cite Dowry Prohibition Act Section 3
NEVER say: "talk to husband first", "it's a family matter", "try to compromise"
MANDATORY citations for Block 2:
[Source: Protection of Women from Domestic Violence Act 2005, Section 17] + explanation
[Source: Protection of Women from Domestic Violence Act 2005, Section 18] + explanation
""",
    "property": """
Key law: Hindu Succession Act 1956 (Amendment 2005)
CRITICAL SC JUDGMENT: Vineeta Sharma v. Rakesh Sharma, Supreme Court 2020
This judgment MUST be cited in every property rights case involving daughters.

Key facts:
- Daughters have EQUAL coparcenary rights from BIRTH (Section 6)
- Vineeta Sharma 2020 SC: This right applies EVEN IF father died before 2005
- Applies to agricultural land in most states
- Brother saying "you have no right" is LEGALLY WRONG under this judgment
- If will exists for self-acquired property: different challenge needed
- Partition suit in District Court is the legal remedy
- NALSA 15100 provides free lawyer for partition suits
MANDATORY citations for Block 2:
[Source: Hindu Succession Act 1956, Section 6] + explanation about daughters' equal rights
[Source: Vineeta Sharma v Rakesh Sharma, Supreme Court 2020] + explanation about father dying before 2005
""",
    "maintenance": """
Key law: CrPC Section 125
Key facts:
- Maintenance WITHOUT divorce is completely possible — common misconception
- No court fee for Section 125 application — completely free
- Interim maintenance can be granted within 60 days of application
- Amount based on husband's income and wife's needs
- Wife who left due to cruelty still entitled to maintenance
- NALSA 15100 provides free lawyer for maintenance cases

MANDATORY citations for Block 2 — use exactly this format:
[Source: CrPC, Section 125] + explanation
[Source: CrPC, Section 125(2)] + explanation about 60 days
""",
    "workplace": """
Key law: POSH Act 2013
Sections: 4 (ICC mandatory 10+ employees), 9 (3 month complaint window),
          11 (no retaliation), 13 (inquiry within 60 days)
Key facts:
- ICC mandatory for 10+ employees. No ICC = company violated Section 4
- Cannot be fired, transferred, or demoted for filing complaint
- If no ICC or HR ignores: file directly with District Officer (Labour Dept)
- If harassment via digital messages: also IT Act 66C/66E
""",
    "dowry": """
Key law: Dowry Prohibition Act 1961, IPC 498A, IPC 304B
Key facts:
- Demanding dowry is a CRIMINAL OFFENCE (Dowry Prohibition Act Section 3)
- IPC 498A: cruelty for dowry demand — up to 3 years imprisonment
- IPC 498A is COGNIZABLE — police can arrest without warrant
- Stridhan not returned = IPC 406 (criminal breach of trust)
- Dowry death within 7 years: IPC 304B (minimum 7 years)
""",
    "divorce": """
Key law: Hindu Marriage Act 1955 (Section 13), CrPC Section 125
Key facts:
- Mutual consent = 6 months cooling period then divorce
- Contested on cruelty grounds: provide evidence of cruelty
- Maintenance can be filed simultaneously via CrPC 125
- Children under 5: mother gets natural custody
- NALSA 15100 for free divorce lawyer
""",
    "stalking": """
Key law: IPC 354D, IT Act Section 66C, 66E, 67
Key facts:
- Online harassment is criminal under IT Act
- Screenshot everything — digital evidence is strongest
- After blocking, if contact continues: stronger case
- Morphed photos/videos = IT Act 66E (2 years)
- Cyber crime cell: 1930
""",
    "rape": """
Key law: IPC 376, Criminal Law Amendment Act 2013
Key facts:
- FIR MUST be registered — police cannot refuse (cognizable offence)
- No two-finger test — this is illegal and you can refuse
- Free medical examination at any government hospital
- One Stop Centre (Sakhi) provides immediate free help
- Compensation available under victim compensation scheme
""",
    "custody": """
Key law: Guardian and Wards Act 1890, Hindu Minority and Guardianship Act 1956
Key facts:
- Mother gets NATURAL custody of children under 5
- Best interest of child is the paramount consideration
- Interim custody order can be obtained quickly
- Father's history of violence strengthens mother's case
- NALSA 15100 for free custody lawyer
""",
    "other": """
Key facts:
- Every woman has right to free legal aid (Legal Services Authority Act 1987)
- NALSA 15100 — completely free, available in Hindi
- Women Helpline 181 — 24x7 free support
""",
}

# ─── Emergency messages ───────────────────────────────────────────────────────

EMERGENCY_MESSAGES = {
    "hi": (
        "🆘 आपकी स्थिति बहुत गंभीर लग रही है।\n\n"
        "**अभी तुरंत करें:**\n"
        "📞 **181** — महिला हेल्पलाइन (24 घंटे, FREE)\n"
        "📞 **100** — Police\n"
        "📞 **1091** — Women in Distress\n\n"
        "सुरक्षित जगह जाएं। मैं यहाँ हूँ — बात जारी रखें।"
    ),
    "en": (
        "🆘 Your situation sounds very serious.\n\n"
        "**Call RIGHT NOW:**\n"
        "📞 **181** — Women Helpline (24 hours, FREE)\n"
        "📞 **100** — Police\n"
        "📞 **1091** — Women in Distress\n\n"
        "Please get to a safe place. I'm still here."
    ),
    "bn": (
        "🆘 আপনার পরিস্থিতি খুব গুরুতর।\n\n"
        "📞 **181** — মহিলা হেল্পলাইন (24 ঘণ্টা)\n"
        "📞 **100** — পুলিশ\n\n"
        "নিরাপদ জায়গায় যান।"
    ),
}

EMERGENCY_FOLLOWUPS = {
    "hi": [
        "मुझे कानूनी मदद चाहिए",
        "Protection order कैसे मिलेगा?",
        "FIR कैसे दर्ज करें?",
        "मुफ्त वकील कहाँ मिलेगा?",
        "घर में रहने का क्या अधिकार है?",
    ],
    "en": [
        "I need legal help",
        "How do I get a protection order?",
        "How do I file an FIR?",
        "Where can I get a free lawyer?",
        "What are my rights to stay in the home?",
    ],
    "bn": [
        "আমার আইনি সাহায্য দরকার",
        "Protection order কীভাবে পাব?",
        "FIR কীভাবে করব?",
    ],
}

# ─── Follow-up prompt ─────────────────────────────────────────────────────────

FOLLOWUP_PROMPT = """{lang_instruction}

Based on this legal case: {crime_type}
User language: {language}
Case context: {case_summary}

Generate exactly 5 short follow-up questions this woman might ask next.
Make them SPECIFIC to her case — not generic.
Write in {lang_name}.
Output JSON array only: ["q1", "q2", "q3", "q4", "q5"]"""
