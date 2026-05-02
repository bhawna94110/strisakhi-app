"""
Medical Document Ingestion Script
Run this ONCE after ingest_legal_docs.py

Usage:
  docker exec nyay-vani-backend python scripts/ingest_medical_docs.py
"""
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from sentence_transformers import SentenceTransformer
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.config import settings

BASELINE_MEDICAL_DATA = [
    {
        "content": """WHO Antenatal Care Guidelines — India Adapted
Danger Signs During Pregnancy (Seek IMMEDIATE hospital care):
- Heavy vaginal bleeding at any time
- Severe headache + blurred vision + swelling of face/hands (Pre-eclampsia warning)
- Fits/convulsions
- Baby not moving for more than 12 hours after 28 weeks
- High fever (above 38°C/100.4°F)
- Difficulty breathing
- Severe abdominal pain
- Water breaking before 37 weeks

Normal Antenatal Visits Schedule:
- First visit: As soon as you know you are pregnant
- Weeks 1-28: Once a month
- Weeks 28-36: Every 2 weeks
- Weeks 36+: Every week

Janani Suraksha Yojana (JSY) - FREE Government Scheme:
- Free antenatal checkups at government health centres
- Free institutional delivery
- Cash incentive after delivery (Rs. 1400 in rural areas)
- Free ambulance transport via 102 helpline
- Call 102 for FREE ambulance for delivery

Signs that Labour Has Started:
Regular contractions every 5 minutes, water breaking, or continuous backache.
Go to hospital immediately when any of these occur.""",
        "metadata": {
            "act_name": "WHO Antenatal Care Guidelines India",
            "section": "Danger Signs and Normal Care",
            "source": "WHO ANC Guidelines",
            "symptom_type": "pregnancy",
            "language": "en"
        }
    },
    {
        "content": """IMNCI Guidelines — Integrated Management of Neonatal and Childhood Illness
Child Illness Assessment (0-5 years)

DANGER SIGNS requiring IMMEDIATE hospital visit:
- Not able to drink or breastfeed
- Vomits everything
- Has had convulsions/fits
- Lethargic or unconscious
- Fast breathing (more than 50 breaths/min for age 2-12 months)
- Chest indrawing (chest sucks in when breathing)
- Stridor (high pitched sound when breathing in)
- Severe malnutrition signs

Fever Management:
- Fever below 38.5°C (101.3°F): Give plenty of fluids, sponge with lukewarm water
- Fever 38.5-39°C: Give paracetamol as per weight (do not give aspirin to children)
- Fever above 39°C lasting more than 2 days: Go to hospital
- Fever with rash: Go to hospital immediately
- Fever in baby under 2 months: ALWAYS go to hospital same day

Diarrhoea and ORS (Oral Rehydration Solution):
- Give ORS after every loose stool
- How to make ORS: 1 litre clean water + 6 teaspoons sugar + half teaspoon salt
- Continue breastfeeding
- Danger: Sunken eyes, very dry mouth, unable to drink — go to hospital immediately

ICDS (Anganwadi) Services — FREE for children under 6:
Supplementary nutrition, immunisation, health check, pre-school education
Visit your nearest Anganwadi centre for free services""",
        "metadata": {
            "act_name": "IMNCI Clinical Guidelines WHO",
            "section": "Child Illness Danger Signs and Management",
            "source": "IMNCI Guidelines",
            "symptom_type": "child_illness",
            "language": "en"
        }
    },
    {
        "content": """Mental Health Support for Women — India Resources

Signs of Depression (seek help if you have 5 or more for 2+ weeks):
- Feeling sad, empty, or hopeless most of the day
- Loss of interest in activities you used to enjoy
- Significant weight loss or gain
- Sleeping too much or too little
- Feeling tired or low energy nearly every day
- Feeling worthless or excessive guilt
- Difficulty concentrating or making decisions
- Thoughts of death or suicide

This is a MEDICAL CONDITION — not weakness, not your fault.
Depression is as real as diabetes or blood pressure. It needs treatment.

Postpartum Depression (after delivery):
Feeling very sad, crying for no reason, not able to bond with baby after delivery.
This is common and TREATABLE. Talk to a doctor or ASHA worker immediately.

FREE Mental Health Support in India:
1. iCall (Tata Institute of Social Sciences): 9152987821
   - Monday to Saturday, 8am to 10pm
   - Counselling in Hindi, English, Marathi
   - FREE of charge

2. Vandrevala Foundation Helpline: 1860-2662-345
   - 24x7, FREE
   - Hindi and English

3. SNEHI: 044-24640050
   - Available weekdays

4. NIMHANS DISHA: 080-46110007
   - Free mental health support
   
Remember: Asking for help is STRENGTH, not weakness.
You deserve to feel well. Treatment works.""",
        "metadata": {
            "act_name": "NIMHANS Community Mental Health Guidelines",
            "section": "Depression Signs and Support Resources",
            "source": "NIMHANS Mental Health",
            "symptom_type": "mental_health",
            "language": "en"
        }
    },
    {
        "content": """National Health Mission — Free Health Services for Women

Pradhan Mantri Matru Vandana Yojana (PMMVY):
- Cash benefit of Rs. 5000 for first living child
- For pregnant and lactating women
- Apply at Anganwadi centre or health sub-centre

Free Government Health Services:
- All antenatal care at government hospitals: FREE
- Institutional delivery: FREE
- Postnatal care: FREE
- Family planning services: FREE
- Immunisation for children: FREE
- Iron and folic acid tablets during pregnancy: FREE
- Calcium supplements during pregnancy: FREE

Ayushman Bharat (PM-JAY) Health Insurance:
- Rs. 5 lakh per family per year for hospitalisation
- For families in Socio-Economic Caste Census 2011 list
- Works at empanelled government and private hospitals
- No premium to pay
- Check eligibility: pmjay.gov.in or call 14555

Emergency Numbers:
- Ambulance: 108 (FREE, 24x7)
- For delivery: 102 (FREE maternity ambulance)
- Health helpline: 104 (FREE medical advice, 24x7)
- Women helpline: 181

Nearest Government Health Facility:
- Sub-Centre (SC): Every 5000 population in plains
- Primary Health Centre (PHC): Every 30,000 population
- Community Health Centre (CHC): Every 1,20,000 population
- District Hospital: Every district headquarter""",
        "metadata": {
            "act_name": "National Health Mission India",
            "section": "Free Health Schemes and Services",
            "source": "NHM India",
            "symptom_type": "general",
            "language": "en"
        }
    }
]

def ingest_medical_documents():
    print("=" * 60)
    print("Nyay Vani — Medical Document Ingestion")
    print("=" * 60)

    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)

    try:
        client.delete_collection(settings.medical_collection)
        print(f"Deleted existing collection: {settings.medical_collection}")
    except Exception:
        pass

    collection = client.create_collection(
        name=settings.medical_collection,
        metadata={"description": "Medical guidelines for women and children health India"}
    )

    print(f"\nLoading embedding model: {settings.embedding_model}")
    embedder = SentenceTransformer(settings.embedding_model)

    documents, metadatas, ids = [], [], []

    print(f"\nLoading {len(BASELINE_MEDICAL_DATA)} baseline medical documents...")
    for i, item in enumerate(BASELINE_MEDICAL_DATA):
        documents.append(item["content"])
        metadatas.append(item["metadata"])
        ids.append(f"baseline_med_{i}")

    medical_docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rag_documents", "medical")
    if os.path.exists(medical_docs_dir):
        pdf_files = [f for f in os.listdir(medical_docs_dir) if f.endswith(('.pdf', '.txt'))]
        if pdf_files:
            splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
            for fname in pdf_files:
                fpath = os.path.join(medical_docs_dir, fname)
                try:
                    loader = PyPDFLoader(fpath) if fname.endswith('.pdf') else TextLoader(fpath)
                    chunks = splitter.split_documents(loader.load())
                    for j, chunk in enumerate(chunks):
                        documents.append(chunk.page_content)
                        metadatas.append({
                            "act_name": fname.replace('.pdf','').replace('_',' ').title(),
                            "section": f"Chunk {j+1}",
                            "source": fname,
                            "symptom_type": "general",
                            "language": "en"
                        })
                        ids.append(f"pdf_med_{fname}_{j}")
                    print(f"  {fname}: {len(chunks)} chunks")
                except Exception as e:
                    print(f"  WARNING: {fname}: {e}")

    print(f"\nGenerating embeddings for {len(documents)} documents...")
    all_embeddings = []
    for i in range(0, len(documents), 32):
        batch = documents[i:i+32]
        emb = embedder.encode(batch, normalize_embeddings=True)
        all_embeddings.extend(emb.tolist())
        print(f"  Embedded {min(i+32, len(documents))}/{len(documents)}")

    collection.add(documents=documents, embeddings=all_embeddings, metadatas=metadatas, ids=ids)
    print(f"\n✅ SUCCESS: {len(documents)} medical documents ingested")
    print(f"Collection '{settings.medical_collection}' ready for RAG queries")

if __name__ == "__main__":
    ingest_medical_documents()
