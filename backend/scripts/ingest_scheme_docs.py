"""
Scheme Document Ingestion Script — StriSakhi
Run ONCE to populate ChromaDB with government scheme knowledge.

Usage:
  docker exec nyay-vani-backend python scripts/ingest_scheme_docs.py

This creates a 'scheme_documents' collection separate from legal_documents.
The scheme_agent.py will need to be updated to query this collection
once it's populated (currently uses hardcoded dictionary).

Suggested PDFs to add to rag_documents/schemes/:
  - PM Awas Yojana guidelines
  - Ayushman Bharat beneficiary guide
  - MGNREGS scheme details
  - State-specific scheme booklets
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from chromadb.utils import embedding_functions
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.config import settings

SCHEME_COLLECTION = "scheme_documents"

# ─── Comprehensive scheme knowledge baseline ─────────────────────────────────
BASELINE_SCHEME_DATA = [
    {
        "content": """PM Awas Yojana — Housing for All
Two components: PMAY-Gramin (rural) and PMAY-Urban (cities)

PMAY-Gramin:
Eligibility: Homeless families or those living in 0-1 room kutcha houses. BPL / SECC list.
Benefit: Rs 1.2 lakh (plain areas) or Rs 1.3 lakh (hilly/difficult areas) for construction.
Apply: At your Gram Panchayat or online at pmayg.nic.in
Documents needed: Aadhaar, bank account, land ownership proof, caste certificate if applicable.
Priority given to: SC/ST families, minorities, disabled persons, women-headed households.

PMAY-Urban:
Eligibility: Annual income up to Rs 18 lakh (EWS/LIG/MIG categories).
Benefit: Interest subsidy on home loans (3-6.5% depending on income category).
Apply: At your local Urban Local Body office or bank.
Website: pmaymis.gov.in""",
        "metadata": {"scheme": "PM Awas Yojana", "ministry": "Housing and Urban Affairs", "issue_type": "housing"}
    },
    {
        "content": """Ayushman Bharat — Pradhan Mantri Jan Arogya Yojana (PMJAY)
Free health insurance for poor families.

Benefit: Rs 5 lakh health cover per family per year.
Covers: Hospitalisation, surgery, medicines, diagnostics at empanelled hospitals.
Eligibility: BPL families as per SECC 2011 database. Check at pmjay.gov.in or call 14555.
No premium to pay — completely free for eligible families.
How to use: Show Aadhaar at any empanelled hospital. Get Ayushman card from CSC.
Covers: Cancer, heart surgery, kidney dialysis, maternity, mental health and 1500+ procedures.

Check eligibility: SMS "PMJAY" to 56167 or visit nearest Common Service Centre (CSC).""",
        "metadata": {"scheme": "Ayushman Bharat PMJAY", "ministry": "Health and Family Welfare", "issue_type": "health"}
    },
    {
        "content": """PM Jan Dhan Yojana — Financial Inclusion
Free bank account for every Indian.

Benefits:
- Zero balance savings account
- RuPay debit card
- Rs 2 lakh accident insurance (free)
- Rs 30,000 life insurance (free, with conditions)
- Overdraft facility up to Rs 10,000 after 6 months
- Direct benefit transfer (DBT) — government money directly in your account

Eligibility: Any Indian citizen above 10 years of age.
How to apply: Visit any bank branch with Aadhaar and one passport photo.
This account is required for almost all government schemes — get it first.

Women who open account get priority for Mudra loans and other schemes.""",
        "metadata": {"scheme": "PM Jan Dhan Yojana", "ministry": "Finance", "issue_type": "financial"}
    },
    {
        "content": """Ujjwala Yojana — Free LPG Gas Connection
Free cooking gas connection for BPL women.

Benefit: Free LPG connection (stove + cylinder) to women from BPL households.
Ujjwala 2.0: Extended to migrants, poor families without ration cards.
Eligibility: Women from BPL households, SC/ST, PMAY beneficiaries, forest dwellers.
How to apply: Visit nearest LPG distributor (HP Gas, Indane, Bharat Gas) with Aadhaar + ration card.
Subsidy: Refill subsidy credited directly to bank account via DBT.

Documents needed: Aadhaar, bank account (Jan Dhan), BPL ration card or self-declaration.""",
        "metadata": {"scheme": "Ujjwala Yojana", "ministry": "Petroleum", "issue_type": "household"}
    },
    {
        "content": """MGNREGS — Mahatma Gandhi National Rural Employment Guarantee Scheme
100 days guaranteed employment for rural households.

Benefit: 100 days of paid work per year. Wage: Rs 200-300/day (varies by state).
Eligibility: Any adult member of rural household willing to do unskilled manual work.
How to apply: Register at your Gram Panchayat. Get Job Card (free).
Work must be provided within 15 days of application — else unemployment allowance paid.
Payment: Directly to bank/post office account.

Women get 33% reservation in MGNREGS work.
Work types: Road construction, water conservation, plantation, building construction.""",
        "metadata": {"scheme": "MGNREGS", "ministry": "Rural Development", "issue_type": "employment"}
    },
    {
        "content": """Beti Bachao Beti Padhao — Girl Child Education and Welfare
Saves and educates the girl child.

Key components:
1. Sukanya Samriddhi Yojana: Savings scheme for girl child
   - Open account at post office or bank for girl under 10 years
   - Minimum deposit Rs 250/year, maximum Rs 1.5 lakh/year
   - Interest rate: ~7.6% (tax free)
   - Maturity at 21 years — good for marriage/higher education fund
   - 50% withdrawal allowed at age 18 for education

2. Scholarships for girls: National Scholarship Portal (scholarships.gov.in)
   - Pre-matric, post-matric scholarships
   - Apply online with marks and income certificate

3. Free education for girls: RTE Act — free education up to Class 8
   Government schools are free for all children up to 14 years.""",
        "metadata": {"scheme": "Beti Bachao Beti Padhao", "ministry": "Women and Child Development", "issue_type": "education"}
    },
    {
        "content": """Mudra Loan — Micro Finance for Women Entrepreneurs
Business loans without collateral for small businesses.

Three categories:
1. Shishu: Loans up to Rs 50,000 — for starting new business
2. Kishor: Loans Rs 50,001 to Rs 5 lakh — for growing business
3. Tarun: Loans Rs 5 lakh to Rs 10 lakh — for established business

Eligibility: Any Indian citizen starting or running a small business.
No collateral needed. No guarantee required.
Women entrepreneurs get priority and lower interest rates.
Apply: At any bank, MFI, NBFC, or online at mudra.org.in
Sectors covered: Street vendors, artisans, tailoring, beauty salon, dairy, poultry, etc.

Stand Up India: Loans Rs 10 lakh to Rs 1 crore for SC/ST or women entrepreneurs.
At least one SC/ST or woman borrower per bank branch.""",
        "metadata": {"scheme": "Mudra Loan", "ministry": "Finance / MSME", "issue_type": "financial"}
    },
    {
        "content": """One Stop Centre (Sakhi) — Help for Women in Distress
Integrated support for women affected by violence.

Services provided FREE:
- Emergency shelter (up to 5 days)
- Medical assistance (first aid, examination)
- Police assistance (filing FIR)
- Legal aid and counselling
- Psycho-social counselling
- Video conferencing facility

Who can use: Any woman affected by violence — domestic violence, sexual assault,
trafficking, acid attack, honour crimes, etc.
How to reach: Call Women Helpline 181 — they will connect you to nearest OSC.
Available in most districts across India.

National Mission for Empowerment of Women (NMEW):
Convergence of all government schemes for women.
Contact District Women and Child Development Officer.""",
        "metadata": {"scheme": "One Stop Centre Sakhi", "ministry": "Women and Child Development", "issue_type": "domestic_violence"}
    },
    {
        "content": """Pension Schemes for Women
Government pension for elderly, widows, and disabled women.

1. Indira Gandhi National Old Age Pension Scheme (IGNOAPS):
   For BPL persons aged 60+. Rs 200/month (60-79 years), Rs 500/month (80+ years).
   Apply at Gram Panchayat or Block Development Office.

2. Indira Gandhi National Widow Pension Scheme (IGNWPS):
   For BPL widows aged 40-79 years. Rs 300/month.
   Apply at Gram Panchayat with husband's death certificate.

3. Indira Gandhi National Disability Pension Scheme (IGNDPS):
   For BPL disabled persons aged 18-79 years with 80%+ disability. Rs 300/month.

4. Rashtriya Parivar Sahayata Yojana:
   Rs 20,000 one-time payment to BPL family on death of breadwinner (18-64 years).
   Apply within 90 days of death at District Social Welfare Office.

5. Atal Pension Yojana:
   Guaranteed pension of Rs 1,000-5,000/month after age 60.
   For workers in unorganised sector. Apply at bank.""",
        "metadata": {"scheme": "Pension Schemes", "ministry": "Rural Development / Labour", "issue_type": "pension"}
    },
    {
        "content": """PM Kaushal Vikas Yojana — Free Skill Training
Free skill training and certification for employment.

Benefit: Free training + certification + placement assistance + Rs 8,000 reward on job placement.
Courses: 300+ courses — tailoring, beauty, healthcare, IT, construction, hospitality, etc.
Duration: 3-6 months depending on course.
Eligibility: Any Indian aged 15-45 years. No minimum education required.
How to apply: Visit nearest Skill India / PMKVY centre or register at pmkvyofficial.org

Women-specific courses: Garment making, food processing, healthcare assistant,
beauty and wellness, early childhood education.

National Rural Livelihood Mission (NRLM — Deendayal Antyodaya Yojana):
Forms Self Help Groups (SHG) of rural poor women.
SHG members get: Rs 15,000 revolving fund, bank linkage, skill training.
Contact your Block Development Officer or Gram Panchayat.""",
        "metadata": {"scheme": "PM Kaushal Vikas Yojana", "ministry": "Skill Development", "issue_type": "employment"}
    }
]


def ingest_scheme_documents():
    print("=" * 60)
    print("StriSakhi — Scheme Document Ingestion")
    print("=" * 60)

    print(f"\nConnecting to ChromaDB at: {settings.chroma_persist_dir}")
    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)

    print("Loading ChromaDB default embedding function...")
    ef = embedding_functions.DefaultEmbeddingFunction()

    # Recreate collection
    try:
        client.delete_collection(SCHEME_COLLECTION)
        print(f"Deleted existing collection: {SCHEME_COLLECTION}")
    except Exception:
        pass

    collection = client.create_collection(
        name=SCHEME_COLLECTION,
        embedding_function=ef,
        metadata={"description": "Indian government schemes for women"}
    )
    print(f"Created collection: {SCHEME_COLLECTION}")

    documents = []
    metadatas = []
    ids = []

    # Baseline schemes
    print(f"\nLoading {len(BASELINE_SCHEME_DATA)} baseline scheme documents...")
    for i, item in enumerate(BASELINE_SCHEME_DATA):
        documents.append(item["content"])
        metadatas.append(item["metadata"])
        ids.append(f"baseline_{i}")

    # Load PDFs if available
    scheme_docs_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "rag_documents", "schemes"
    )

    if os.path.exists(scheme_docs_dir):
        pdf_files = [f for f in os.listdir(scheme_docs_dir) if f.endswith(('.pdf', '.txt'))]
        if pdf_files:
            print(f"\nFound {len(pdf_files)} files in rag_documents/schemes/")
            splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
            for fname in pdf_files:
                fpath = os.path.join(scheme_docs_dir, fname)
                try:
                    loader = PyPDFLoader(fpath) if fname.endswith('.pdf') else TextLoader(fpath, encoding='utf-8')
                    pages = loader.load()
                    chunks = splitter.split_documents(pages)
                    print(f"  {fname}: {len(chunks)} chunks")
                    for j, chunk in enumerate(chunks):
                        documents.append(chunk.page_content)
                        metadatas.append({
                            "scheme": fname.replace('.pdf','').replace('_',' ').title(),
                            "source": fname,
                            "issue_type": "general",
                        })
                        ids.append(f"pdf_{fname}_{j}")
                except Exception as e:
                    print(f"  WARNING: Could not load {fname}: {e}")
        else:
            print("\nNo PDFs in rag_documents/schemes/ — using baseline only")

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

    print(f"\n✅ SUCCESS: {len(documents)} scheme documents ingested")
    print(f"Collection '{SCHEME_COLLECTION}' ready")
    print("\nNOTE: Update scheme_agent.py to query 'scheme_documents' collection")
    print("instead of using the hardcoded scheme dictionary.")


if __name__ == "__main__":
    ingest_scheme_documents()
