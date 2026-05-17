"""
Medical Document Ingestion v2 — StriSakhi Sehat Sakhi
Enhanced with real ASHA worker guidelines for rural Indian women.
Run: docker exec nyay-vani-backend python scripts/ingest_medical_docs.py
"""
import sys, os, time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from chromadb.utils import embedding_functions
from app.config import settings

MEDICAL_DATA = [
    {
        "content": """Pregnancy — Warning Signs and Safe Delivery

DANGER SIGNS — Go to hospital IMMEDIATELY:
- Heavy bleeding at any stage of pregnancy
- Severe headache + blurred vision + swollen hands/face (pre-eclampsia)
- High fever (above 101°F / 38.3°C)
- Baby not moving for more than 12 hours after 28 weeks
- Severe abdominal pain or cramping
- Fits or convulsions — call 108 immediately
- Difficulty breathing

Normal pregnancy discomforts (NOT emergency):
- Morning sickness (nausea) in first 3 months
- Mild back pain
- Frequent urination
- Mild foot swelling in evenings — rest and elevate legs

Free government help:
Janani Suraksha Yojana (JSY): Rs 1400 cash for delivery at government hospital (rural BPL women).
JSSK: Free delivery, medicines, diet, transport at all government hospitals.
ASHA worker gives free iron tablets, antenatal care guidance.
Call 104 for health advice. Call 102 for free ambulance for pregnant women.""",
        "metadata": {"topic": "pregnancy", "source": "MOHFW Maternal Health", "issue_type": "pregnancy"}
    },
    {
        "content": """Child Health — Fever, Diarrhoea, and When to Go to Hospital

DANGER SIGNS IN CHILDREN — hospital immediately:
- Child cannot drink or breastfeed at all
- Child vomits everything they eat
- Fits or convulsions in child
- Unconscious or cannot be woken
- Rapid or difficult breathing — nostrils flaring
- Severe dehydration: sunken eyes, dry cracked lips, no tears when crying
- High fever in baby under 3 months — ALWAYS go to hospital
- Blue lips or fingernails

Fever management at home (if no danger signs):
- Sponge with lukewarm water (not cold)
- Paracetamol syrup — dose by weight, ask doctor or ASHA
- Give ORS fluids, continue breastfeeding
- Keep child comfortable, watch for danger signs

Diarrhoea at home:
- Give ORS after EVERY loose stool (available free at Anganwadi/PHC)
- Continue breastfeeding — do NOT stop
- Zinc tablets 10-14 days — free at government health centres
- If blood in stool or very frequent — go to hospital

Free vaccines (all free at govt hospitals):
BCG, OPV, DPT, Measles, MMR — Universal Immunisation Programme.
Ask ASHA worker for vaccination schedule.""",
        "metadata": {"topic": "child_health", "source": "IMNCI Guidelines", "issue_type": "child_illness"}
    },
    {
        "content": """Mental Health — Depression, Anxiety, Postpartum

Depression is a MEDICAL CONDITION. It is NOT weakness. It can be treated.

Signs of depression (lasting more than 2 weeks):
- Persistent sadness, crying without reason
- Loss of interest in daily activities, family, children
- Too much or too little sleep
- No energy, exhaustion all the time
- Feeling worthless or like a burden to family
- Thoughts of death or harming yourself — seek help immediately

Common triggers for Indian women: domestic violence, loss, abandonment, financial stress, postpartum.

Postpartum depression (after delivery):
Very common — affects 1 in 5 new mothers.
Signs: persistent sadness after delivery, unable to bond with baby, extreme anxiety.
NOT a failure as a mother. Treatment available.

What to do:
1. Talk to a doctor — depression is treatable
2. iCall free counselling: 9152987821 (Mon-Sat, Hindi available)
3. Vandrevala Foundation 24x7: 1860-2662-345
4. If thoughts of self-harm: call iCall immediately or go to hospital

NEVER say: "sab theek ho jaega" without getting help.
NEVER minimize: "Everyone feels sad sometimes." Depression is real.""",
        "metadata": {"topic": "mental_health", "source": "NIMHANS Guidelines", "issue_type": "mental_health"}
    },
    {
        "content": """Anaemia — Very Common in Indian Women

Anaemia (low blood/iron) affects 59% of Indian women age 15-49 (NFHS-5).

Signs:
- Fatigue and weakness even after rest
- Pale skin, pale inside lower eyelid (pull down gently to check)
- Dizziness when standing up
- Shortness of breath during normal activity
- Palpitations (heart beating fast)
- Headaches

If severe (very pale, cannot walk without dizziness) — go to hospital.

Iron-rich foods to eat daily:
- Green leafy vegetables: palak, methi, sarson saag
- Dal, rajma, chana
- Jaggery (gud), sesame (til), dried raisins, dates
- Meat, chicken, eggs if available
- Eat WITH lemon or amla (Vitamin C) to absorb iron better
- Avoid tea/coffee with iron-rich foods — reduces absorption

Government help:
Free iron + folic acid tablets at Anganwadi and PHC.
Pregnant women: 1 tablet daily for 180 days — FREE.
POSHAN Abhiyaan — nutrition support scheme.""",
        "metadata": {"topic": "anaemia", "source": "ICMR Nutrition Guidelines", "issue_type": "anaemia"}
    },
    {
        "content": """Reproductive Health — Contraception and Menstrual Health

Free contraception at all PHC/Anganwadi/ASHA:
- Condoms: Free at any health centre
- Oral pills (Mala-N): Free monthly supply at PHC
- Antara injection: Free every 3 months at PHC
- Copper-T IUD: Free insertion at PHC
- Emergency pill: Available at chemist within 72 hours, no prescription

Irregular periods / PCOD:
- Periods missing or very irregular for 3+ months — see doctor at PHC
- Very heavy bleeding — see doctor
- Severe cramping that stops daily activities — may need treatment

Menstrual hygiene:
Free sanitary pads at many Anganwadi centres (state scheme).
If burning, itching, unusual discharge — see doctor, do not ignore.

Danger signs needing immediate doctor:
- Missing period + nausea + vomiting — pregnancy test
- Sudden severe pelvic pain — can indicate serious condition
- Foul-smelling discharge with fever — infection, needs antibiotics

Helpline: 104 (national health helpline, free, Hindi available)""",
        "metadata": {"topic": "reproductive_health", "source": "MOHFW Family Planning", "issue_type": "reproductive"}
    },
    {
        "content": """Government Health Schemes for Women

Ayushman Bharat (PMJAY):
Free health insurance up to Rs 5 lakh per family per year.
Covers: Hospitalisation, surgery, medicines, cancer, dialysis, maternity.
Check eligibility: pmjay.gov.in or call 14555 or SMS "PMJAY" to 56167.
How to use: Show Aadhaar at any empanelled hospital.
Get Ayushman card free at CSC (Common Service Centre).

Janani Shishu Suraksha Karyakaram (JSSK):
Free at ALL government hospitals:
- Normal and caesarean delivery
- Medicines and tests during pregnancy
- Diet during hospital stay
- Free blood transfusion if needed
- Free transport (call 102)

PM Matru Vandana Yojana:
Rs 5000 cash for first pregnancy.
Apply at Anganwadi. Documents: Aadhaar, MCP card, bank account.

Mental health helplines:
iCall: 9152987821 (free counselling, Mon-Sat)
NIMHANS: 080-46110007
Vandrevala: 1860-2662-345 (24x7)

General health:
104 — National Health Helpline (free, Hindi)
108 — Ambulance (free emergency)
102 — Maternity transport (free for pregnant women)""",
        "metadata": {"topic": "health_schemes", "source": "Government Health Schemes", "issue_type": "schemes"}
    },
]


def ingest_medical_documents():
    print("=" * 60)
    print("StriSakhi — Medical Document Ingestion v2")
    print("=" * 60)

    ef = embedding_functions.DefaultEmbeddingFunction()

    # Delete safely
    try:
        _c = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        existing = [col.name for col in _c.list_collections()]
        if settings.medical_collection in existing:
            _c.delete_collection(settings.medical_collection)
            print(f"Deleted: {settings.medical_collection}")
        del _c
        time.sleep(0.5)
    except Exception as e:
        print(f"Note: {e}")

    # Fresh client
    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    collection = client.create_collection(
        name=settings.medical_collection,
        embedding_function=ef,
        metadata={"description": "Medical health guidelines for Indian women v2"}
    )
    print(f"Created: {settings.medical_collection}")

    documents = [d["content"] for d in MEDICAL_DATA]
    metadatas = [d["metadata"] for d in MEDICAL_DATA]
    ids = [f"medical_v2_{i}" for i in range(len(MEDICAL_DATA))]

    print(f"Embedding {len(documents)} documents...")
    collection.add(documents=documents, metadatas=metadatas, ids=ids)
    print(f"✅ SUCCESS: {len(documents)} medical documents ingested")

    # Verify
    print("\n--- Verifying ---")
    tests = [
        ("Pregnancy danger signs", "pregnancy bleeding fever fits hospital"),
        ("Child fever", "child fever danger signs diarrhoea ORS"),
        ("Mental health", "depression anxiety counselling postpartum"),
    ]
    for name, query in tests:
        r = collection.query(query_texts=[query], n_results=1)
        print(f"  {name}: ✓ {r['documents'][0][0][:70]}...")


if __name__ == "__main__":
    ingest_medical_documents()
