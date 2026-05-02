"""
Legal Document Ingestion Script
Run this ONCE to embed legal documents into ChromaDB.

Usage:
  docker exec nyay-vani-backend python scripts/ingest_legal_docs.py

Or locally:
  python scripts/ingest_legal_docs.py

Place your PDF/TXT files in: backend/rag_documents/legal/
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from sentence_transformers import SentenceTransformer
from langchain_community.document_loaders import PyPDFLoader, TextLoader, DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.config import settings

# ─── Hardcoded legal knowledge ────────────────────────────────────────────────
# If you don't have PDF files yet, this provides baseline legal knowledge
# Replace with actual PDFs from indiacode.nic.in for best results

BASELINE_LEGAL_DATA = [
    {
        "content": """Protection of Women from Domestic Violence Act, 2005 (DV Act)
Section 17: Right to reside in shared household
Every woman in a domestic relationship shall have the right to reside in the shared household, 
whether or not she has any right, title or beneficial interest in the same. 
The aggrieved person shall not be evicted or excluded from the shared household or any part of it 
by the respondent save in accordance with the procedure established by law.

Section 12: Application to Magistrate
An aggrieved person or a Protection Officer or any other person on behalf of the aggrieved person 
may present an application to the Magistrate seeking one or more reliefs under this Act.
The relief sought under sub-section (1) may include a relief for issuance of an order for payment of compensation or damages.
Every application under sub-section (1) shall be in such form and contain such particulars as may be prescribed.

Section 18: Protection orders
The Magistrate may, after giving the aggrieved person and the respondent an opportunity of being heard 
and on being prima facie satisfied that domestic violence has taken place or is likely to take place, 
pass a protection order in favour of the aggrieved person.

Section 19: Residence orders
The Magistrate may, on being satisfied that domestic violence has taken place, pass a residence order—
(a) restraining the respondent from dispossessing or in any other manner disturbing the possession of the aggrieved person from the shared household;
(b) directing the respondent to remove himself from the shared household;
(c) restraining the respondent or his relatives from entering any portion of the shared household in which the aggrieved person resides.

How to file: Go to nearest Magistrate court with a written application. 
You DO NOT need a lawyer. The court must hear your case within 3 days of application.
Protection Officer in your district can help you file for FREE.""",
        "metadata": {
            "act_name": "Protection of Women from Domestic Violence Act 2005",
            "section": "Sections 12, 17, 18, 19",
            "source": "DV Act 2005",
            "issue_type": "domestic_violence",
            "language": "en"
        }
    },
    {
        "content": """Indian Penal Code (IPC) - Women's Protection Sections

Section 498A IPC: Husband or relative of husband of a woman subjecting her to cruelty
Whoever, being the husband or the relative of the husband of a woman, subjects such woman to cruelty 
shall be punished with imprisonment for a term which may extend to three years and shall also be liable to fine.
Cruelty means: any wilful conduct which is of such a nature as is likely to drive the woman to commit suicide 
or to cause grave injury or danger to life, limb or health; or harassment of the woman where such harassment 
is with a view to coercing her or any person related to her to meet any unlawful demand for any property or valuable security.

How to file: Go to nearest police station. File an FIR (First Information Report).
Police MUST register your FIR - they cannot refuse. If they refuse, go to Superintendent of Police.
This is a COGNIZABLE offence - police can arrest without warrant.

Section 354 IPC: Assault or criminal force to woman with intent to outrage her modesty
Section 376 IPC: Rape - punishable with minimum 7 years rigorous imprisonment
Section 406 IPC: Criminal breach of trust - applicable for dowry articles not returned

FREE LEGAL AID: Every woman has right to free legal aid under Legal Services Authority Act.
Call National Legal Services Authority (NALSA): 15100
This is completely free of charge.""",
        "metadata": {
            "act_name": "Indian Penal Code (IPC)",
            "section": "Sections 354, 376, 406, 498A",
            "source": "IPC Women Protection",
            "issue_type": "domestic_violence",
            "language": "en"
        }
    },
    {
        "content": """Hindu Succession Act 1956 (Amended 2005) - Women's Property Rights

Section 6 (Amended 2005): Devolution of interest in coparcenary property
By virtue of the Amendment Act 2005, the daughter of a coparcener shall by birth become a coparcener 
in her own right in the same manner as the son. She shall have the same rights in the coparcenary property 
as she would have had if she had been a son.

Key Rights:
- Daughters have EQUAL right to ancestral property as sons
- This right exists from BIRTH, not from marriage
- Applies even if father died BEFORE 2005 (Supreme Court ruling 2020)
- Applies to agricultural land in most states
- Right cannot be taken away by any family agreement

Supreme Court Judgment: Vineeta Sharma vs Rakesh Sharma (2020)
The Supreme Court held that daughters have equal coparcenary rights regardless of whether the father 
was alive or not on the date of the 2005 amendment. This is a landmark judgment.

How to claim: 
1. File a civil suit in District Court for partition of property
2. Apply for legal aid at District Legal Services Authority (DLSA) - FREE
3. Collect documents: birth certificate, father's death certificate, property papers

Important: Brother/family saying "you have no right to property" is LEGALLY WRONG under this Act.""",
        "metadata": {
            "act_name": "Hindu Succession Act 1956 (Amendment 2005)",
            "section": "Section 6, SC Judgment Vineeta Sharma 2020",
            "source": "Hindu Succession Act",
            "issue_type": "property",
            "language": "en"
        }
    },
    {
        "content": """Sexual Harassment of Women at Workplace (Prevention, Prohibition and Redressal) Act, 2013 (POSH Act)

Definition of Sexual Harassment:
Unwelcome acts or behaviour (whether directly or by implication) namely—
physical contact and advances; a demand or request for sexual favours; making sexually coloured remarks;
showing pornography; any other unwelcome physical, verbal or non-verbal conduct of sexual nature.

Every employer MUST:
- Constitute an Internal Complaints Committee (ICC) if 10 or more employees
- Display information about the Act at workplace
- Provide safe working environment
- Not retaliate against complainant

Your Rights:
- File complaint within 3 months of incident (can be extended)
- Inquiry must be completed within 60 days
- You can request transfer during inquiry period
- Employer cannot terminate you for filing complaint
- If employer has less than 10 employees: file with District Officer/Local Complaints Committee

Minimum Wages Act 1948:
Every worker has right to minimum wages as fixed by State Government.
If not paid: File complaint with Labour Commissioner of your district.
This service is FREE. You can also file online at shramsuvidha.gov.in""",
        "metadata": {
            "act_name": "POSH Act 2013 and Minimum Wages Act 1948",
            "section": "POSH Act Sections 2, 4, 9, 11, 13",
            "source": "POSH Act 2013",
            "issue_type": "workplace",
            "language": "en"
        }
    },
    {
        "content": """Hindu Marriage Act 1955 - Divorce and Maintenance Rights

Grounds for Divorce (Section 13):
A wife may present a petition for divorce on grounds of:
- Cruelty: physical or mental cruelty by husband
- Desertion: husband has deserted wife for minimum 2 years
- Adultery: husband living with another woman
- Conversion: husband converts to another religion
- Mental disorder: husband of unsound mind
- Bigamy: husband has another living wife

Maintenance Rights:
Section 125 CrPC: Any woman whose husband has neglected or refused to maintain her 
may apply to Magistrate for monthly maintenance allowance.
Court can order husband to pay maintenance even during separation.
There is no fixed amount - court decides based on husband's income.

How to apply for maintenance:
1. Go to nearest Magistrate court (Family Court if available)
2. File application under Section 125 CrPC - NO COURT FEE
3. You can apply even without filing for divorce
4. Interim maintenance can be granted within 60 days

FREE HELP:
- District Legal Services Authority (DLSA): Free lawyer and court help
- Women and Child Development Ministry helpline: 181
- iCall counselling: 9152987821""",
        "metadata": {
            "act_name": "Hindu Marriage Act 1955 and CrPC Section 125",
            "section": "Section 13, 125 CrPC",
            "source": "Hindu Marriage Act 1955",
            "issue_type": "divorce",
            "language": "en"
        }
    },
    {
        "content": """Free Legal Aid - Every Woman's Right in India

Legal Services Authority Act 1987:
Every woman in India has the RIGHT to free legal aid regardless of income.
This includes: free lawyer, free court fees, free documentation help.

How to get FREE legal aid:
1. District Legal Services Authority (DLSA): Present in every district
   - Visit your district court complex
   - Ask for "Legal Aid" or "Muft Kanoon Sahayata"
2. State Legal Services Authority (SLSA): For higher courts
3. NALSA Helpline: 15100 (National Legal Services Authority)
   - Call this number from anywhere in India
   - Available in Hindi and regional languages
   - They will guide you to nearest help center

Women-specific helplines:
- Women Helpline: 181 (24x7, FREE, all India)
- Police: 100
- Domestic Violence helpline: 181
- One Stop Centre (Sakhi): Present in most districts - provides shelter, legal help, medical help

National Commission for Women: complaints@ncw.nic.in
They handle complaints of violation of women's rights.""",
        "metadata": {
            "act_name": "Legal Services Authority Act 1987",
            "section": "Free Legal Aid Rights",
            "source": "NALSA Legal Aid",
            "issue_type": "general",
            "language": "en"
        }
    }
]

def ingest_legal_documents():
    print("=" * 60)
    print("Nyay Vani — Legal Document Ingestion")
    print("=" * 60)

    # Initialize ChromaDB
    print(f"\nConnecting to ChromaDB at: {settings.chroma_persist_dir}")
    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)

    # Delete existing collection if rebuilding
    try:
        client.delete_collection(settings.legal_collection)
        print(f"Deleted existing collection: {settings.legal_collection}")
    except Exception:
        pass

    collection = client.create_collection(
        name=settings.legal_collection,
        metadata={"description": "Indian legal documents for women's rights"}
    )
    print(f"Created collection: {settings.legal_collection}")

    # Load embedding model
    print(f"\nLoading embedding model: {settings.embedding_model}")
    embedder = SentenceTransformer(settings.embedding_model)
    print("Embedding model loaded")

    documents = []
    metadatas = []
    ids = []

    # Step 1: Load baseline legal knowledge
    print(f"\nLoading {len(BASELINE_LEGAL_DATA)} baseline legal documents...")
    for i, item in enumerate(BASELINE_LEGAL_DATA):
        documents.append(item["content"])
        metadatas.append(item["metadata"])
        ids.append(f"baseline_{i}")

    # Step 2: Load PDF files if available
    legal_docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rag_documents", "legal")
    if os.path.exists(legal_docs_dir):
        pdf_files = [f for f in os.listdir(legal_docs_dir) if f.endswith(('.pdf', '.txt'))]
        if pdf_files:
            print(f"\nFound {len(pdf_files)} files in rag_documents/legal/")
            splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

            for fname in pdf_files:
                fpath = os.path.join(legal_docs_dir, fname)
                try:
                    if fname.endswith('.pdf'):
                        loader = PyPDFLoader(fpath)
                    else:
                        loader = TextLoader(fpath, encoding='utf-8')

                    pages = loader.load()
                    chunks = splitter.split_documents(pages)
                    print(f"  {fname}: {len(chunks)} chunks")

                    for j, chunk in enumerate(chunks):
                        documents.append(chunk.page_content)
                        metadatas.append({
                            "act_name": fname.replace('.pdf', '').replace('_', ' ').title(),
                            "section": f"Page chunk {j+1}",
                            "source": fname,
                            "issue_type": "general",
                            "language": "en"
                        })
                        ids.append(f"pdf_{fname}_{j}")

                except Exception as e:
                    print(f"  WARNING: Could not load {fname}: {e}")
        else:
            print("\nNo PDF files found in rag_documents/legal/")
            print("Add PDFs from indiacode.nic.in for richer legal knowledge")
            print("Using baseline knowledge only")

    # Step 3: Generate embeddings and store
    print(f"\nGenerating embeddings for {len(documents)} documents...")
    batch_size = 32
    all_embeddings = []

    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        embeddings = embedder.encode(batch, normalize_embeddings=True)
        all_embeddings.extend(embeddings.tolist())
        print(f"  Embedded {min(i+batch_size, len(documents))}/{len(documents)}")

    # Step 4: Add to ChromaDB
    print("\nStoring in ChromaDB...")
    collection.add(
        documents=documents,
        embeddings=all_embeddings,
        metadatas=metadatas,
        ids=ids
    )

    print(f"\n✅ SUCCESS: {len(documents)} legal documents ingested")
    print(f"Collection '{settings.legal_collection}' is ready for RAG queries")
    print("\nTest with: GET /api/health — chromadb should show legal_ready: true")

if __name__ == "__main__":
    ingest_legal_documents()
