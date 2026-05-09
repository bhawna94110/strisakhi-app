"""
Medical Document Ingestion Script — StriSakhi
Run ONCE after adding PDFs to rag_documents/medical/

Usage:
  docker exec nyay-vani-backend python scripts/ingest_medical_docs.py

Suggested PDFs to add:
  - MOHFW maternal health guidelines
  - ICMR nutrition guidelines for women
  - National Mental Health Policy summary
  - Ayushman Bharat / PMJAY scheme health benefits
  - Common symptoms guide in simple language
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from chromadb.utils import embedding_functions
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.config import settings

# ─── Baseline medical knowledge (always ingested even without PDFs) ────────────
BASELINE_MEDICAL_DATA = [
    {
        "content": """Maternal Health — Pregnancy Warning Signs
Immediately go to hospital if you experience:
- Heavy vaginal bleeding at any stage of pregnancy
- Severe headache, blurred vision, swelling of hands/face (signs of pre-eclampsia)
- High fever (above 101°F / 38.3°C)
- Baby not moving for more than 12 hours after 28 weeks
- Severe abdominal pain
- Difficulty breathing
- Fits or convulsions

Normal pregnancy discomforts (not emergency):
- Morning sickness (nausea/vomiting) in first trimester
- Mild back pain
- Frequent urination
- Mild swelling of feet in evening

Government scheme: Janani Suraksha Yojana (JSY)
Provides cash assistance to pregnant women for institutional delivery.
BPL women get Rs 1400 (rural) or Rs 1000 (urban) for delivery at government hospital.
Apply at nearest ASHA worker or Primary Health Centre (PHC).""",
        "metadata": {
            "topic": "maternal_health",
            "source": "MOHFW Maternal Health Guidelines",
            "issue_type": "pregnancy",
        }
    },
    {
        "content": """Child Health — Common Illnesses and When to Seek Help

Danger signs in children — go to hospital IMMEDIATELY:
- Child cannot drink or breastfeed
- Child vomits everything
- Child has convulsions/fits
- Child is unconscious or cannot be woken
- Rapid or difficult breathing
- Severe dehydration (sunken eyes, dry mouth, no tears)
- High fever in child under 3 months

Diarrhoea management at home:
- Give ORS (Oral Rehydration Solution) after every loose stool
- Continue breastfeeding
- Do NOT stop food
- Give zinc tablets (10-14 days) — available free at government health centres

Vaccination schedule — free at government hospitals:
- Birth: BCG, OPV, Hepatitis B
- 6 weeks: DPT, OPV, Hepatitis B, Hib
- 9 months: Measles
- 12-15 months: MMR
All vaccinations are FREE under Universal Immunisation Programme (UIP)""",
        "metadata": {
            "topic": "child_health",
            "source": "IMNCI Child Health Guidelines",
            "issue_type": "child_illness",
        }
    },
    {
        "content": """Mental Health — Depression and Anxiety in Women

Common signs of depression:
- Persistent sadness, hopelessness for more than 2 weeks
- Loss of interest in daily activities
- Sleep problems (too much or too little)
- Fatigue, loss of energy
- Difficulty concentrating
- Feelings of worthlessness or guilt
- Thoughts of death or suicide

Depression is a MEDICAL condition — it is NOT weakness. It can be treated.

Common triggers for Indian women:
- Domestic violence and abuse
- Loss of a child or family member
- Marital problems / separation
- Financial stress
- Postpartum depression (after delivery)

What to do:
1. Talk to a doctor — depression is treatable with counselling and/or medicine
2. iCall free counselling: 9152987821 (Monday-Saturday)
3. Vandrevala Foundation 24x7 helpline: 1860-2662-345
4. NIMHANS Helpline: 080-46110007

NEVER prescribe antidepressants yourself — always consult a doctor first.""",
        "metadata": {
            "topic": "mental_health",
            "source": "NIMHANS Mental Health Guidelines",
            "issue_type": "mental_health",
        }
    },
    {
        "content": """Nutrition for Women — Anaemia and Malnutrition

Anaemia (low blood/iron) is very common in Indian women.
Signs: fatigue, weakness, pale skin, dizziness, shortness of breath.

Iron-rich foods to eat daily:
- Green leafy vegetables (palak, methi, sarson)
- Lentils and pulses (dal)
- Jaggery (gud)
- Sesame seeds (til)
- Dried fruits (raisins, dates)
- Eat with Vitamin C (lemon, amla) to absorb iron better

Government scheme: POSHAN Abhiyaan
Free iron and folic acid tablets at Anganwadi and PHC.
Pregnant women: 1 tablet daily for 180 days — completely free.

Iodine deficiency:
Always use iodised salt. Prevents goitre and developmental problems in children.

Protein needs:
Women need ~45-55g protein daily.
Good sources: dal, eggs, milk, paneer, soyabean, groundnuts.""",
        "metadata": {
            "topic": "nutrition",
            "source": "ICMR Nutrition Guidelines",
            "issue_type": "nutrition",
        }
    },
    {
        "content": """Reproductive Health — Contraception and Family Planning

Free contraception available at all government health centres:
- Condoms: Free at PHC, sub-centres, ASHA workers
- Oral contraceptive pills (Mala-N): Free at PHC
- Injectable contraceptive (Antara): Free at PHC — 1 injection every 3 months
- Copper-T IUD: Free insertion at PHC
- Sterilisation (tubectomy): Free with compensation under family planning scheme

Emergency contraception:
- Take within 72 hours of unprotected sex
- Available at chemist without prescription
- NOT for regular use

Signs needing immediate doctor visit:
- Missed periods for 2+ months (rule out pregnancy)
- Unusual vaginal discharge with smell or itching
- Pain during intercourse
- Heavy or irregular periods

Menstrual hygiene:
Free sanitary pads under Pradhan Mantri Surakshit Matritva Abhiyan at Anganwadi centres.""",
        "metadata": {
            "topic": "reproductive_health",
            "source": "MOHFW Reproductive Health Guidelines",
            "issue_type": "reproductive_health",
        }
    },
    {
        "content": """Government Health Schemes for Women

Ayushman Bharat — Pradhan Mantri Jan Arogya Yojana (PMJAY):
Free health insurance up to Rs 5 lakh per family per year.
Covers hospitalisation at empanelled government and private hospitals.
Eligibility: BPL families (check at pmjay.gov.in or call 14555)

Janani Shishu Suraksha Karyakaram (JSSK):
Free and cashless services for pregnant women at government hospitals:
- Free delivery (normal and caesarean)
- Free drugs and consumables
- Free diagnostics
- Free diet during hospital stay
- Free blood transfusion
- Free transport from home to hospital and back

PM Matru Vandana Yojana (PMMVY):
Rs 5000 cash benefit for first pregnancy.
Conditions: institutional delivery + breastfeeding + vaccination.
Apply at Anganwadi or Women and Child Development office.

Rashtriya Swasthya Bima Yojana (RSBY):
Smart card-based health insurance for BPL families.
Covers hospitalisation up to Rs 30,000 per year.""",
        "metadata": {
            "topic": "health_schemes",
            "source": "Government Health Schemes",
            "issue_type": "health_schemes",
        }
    }
]


def ingest_medical_documents():
    print("=" * 60)
    print("StriSakhi — Medical Document Ingestion")
    print("=" * 60)

    print(f"\nConnecting to ChromaDB at: {settings.chroma_persist_dir}")
    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)

    print("Loading ChromaDB default embedding function...")
    ef = embedding_functions.DefaultEmbeddingFunction()

    # Recreate collection
    try:
        client.delete_collection(settings.medical_collection)
        print(f"Deleted existing collection: {settings.medical_collection}")
    except Exception:
        pass

    collection = client.create_collection(
        name=settings.medical_collection,
        embedding_function=ef,
        metadata={"description": "Medical health guidelines for Indian women"}
    )
    print(f"Created collection: {settings.medical_collection}")

    documents = []
    metadatas = []
    ids = []

    # Baseline knowledge
    print(f"\nLoading {len(BASELINE_MEDICAL_DATA)} baseline medical documents...")
    for i, item in enumerate(BASELINE_MEDICAL_DATA):
        documents.append(item["content"])
        metadatas.append(item["metadata"])
        ids.append(f"baseline_{i}")

    # Load PDFs if available
    medical_docs_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "rag_documents", "medical"
    )

    if os.path.exists(medical_docs_dir):
        pdf_files = [f for f in os.listdir(medical_docs_dir) if f.endswith(('.pdf', '.txt'))]
        if pdf_files:
            print(f"\nFound {len(pdf_files)} files in rag_documents/medical/")
            splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
            for fname in pdf_files:
                fpath = os.path.join(medical_docs_dir, fname)
                try:
                    loader = PyPDFLoader(fpath) if fname.endswith('.pdf') else TextLoader(fpath, encoding='utf-8')
                    pages = loader.load()
                    chunks = splitter.split_documents(pages)
                    print(f"  {fname}: {len(chunks)} chunks")
                    for j, chunk in enumerate(chunks):
                        documents.append(chunk.page_content)
                        metadatas.append({
                            "topic": fname.replace('.pdf','').replace('_',' ').title(),
                            "source": fname,
                            "issue_type": "general",
                        })
                        ids.append(f"pdf_{fname}_{j}")
                except Exception as e:
                    print(f"  WARNING: Could not load {fname}: {e}")
        else:
            print("\nNo PDFs found in rag_documents/medical/ — using baseline only")
            print("Add PDFs later and re-run this script to enhance Sehat Sakhi")

    # Store in ChromaDB
    print(f"\nEmbedding and storing {len(documents)} documents...")
    batch_size = 50
    for i in range(0, len(documents), batch_size):
        collection.add(
            documents=documents[i:i+batch_size],
            metadatas=metadatas[i:i+batch_size],
            ids=ids[i:i+batch_size]
        )
        print(f"  Stored {min(i+batch_size, len(documents))}/{len(documents)}")

    print(f"\n✅ SUCCESS: {len(documents)} medical documents ingested")
    print(f"Collection '{settings.medical_collection}' ready")


if __name__ == "__main__":
    ingest_medical_documents()
