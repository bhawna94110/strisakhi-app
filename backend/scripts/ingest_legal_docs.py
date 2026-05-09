"""
Legal Document Ingestion Script — StriSakhi
Run ONCE after first docker compose up to populate ChromaDB.

Usage:
  docker exec nyay-vani-backend python scripts/ingest_legal_docs.py

Place PDFs in: backend/rag_documents/legal/
Currently ingests: dv_act_2005.pdf, hindu_succession_act.pdf, posh_act_2013.pdf
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from chromadb.utils import embedding_functions
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.config import settings

# ─── Baseline legal knowledge (always ingested even without PDFs) ──────────────
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

Section 18: Protection orders
The Magistrate may, after giving the aggrieved person and the respondent an opportunity of being heard
and on being prima facie satisfied that domestic violence has taken place or is likely to take place,
pass a protection order in favour of the aggrieved person.

Section 19: Residence orders
The Magistrate may, on being satisfied that domestic violence has taken place, pass a residence order
restraining the respondent from dispossessing the aggrieved person from the shared household.

How to file: Go to nearest Magistrate court with a written application.
You DO NOT need a lawyer. The court must hear your case within 3 days.
Protection Officer in your district can help you file for FREE.""",
        "metadata": {
            "act_name": "Protection of Women from Domestic Violence Act 2005",
            "section": "Sections 12, 17, 18, 19",
            "source": "DV Act 2005",
            "issue_type": "domestic_violence",
        }
    },
    {
        "content": """Indian Penal Code (IPC) - Women's Protection Sections

Section 498A IPC: Husband or relative subjecting woman to cruelty
Punished with imprisonment up to 3 years and fine.
Cruelty means wilful conduct likely to drive woman to suicide or cause grave injury,
or harassment to coerce her to meet unlawful demands for property.

How to file: Go to nearest police station. File an FIR.
Police MUST register your FIR — they cannot refuse.
If they refuse, go to Superintendent of Police.
This is a COGNIZABLE offence — police can arrest without warrant.

Section 354 IPC: Assault to outrage modesty of woman
Section 376 IPC: Rape — minimum 7 years rigorous imprisonment
Section 406 IPC: Criminal breach of trust — for dowry articles not returned

FREE LEGAL AID: Every woman has right to free legal aid.
Call NALSA: 15100 — completely free of charge.""",
        "metadata": {
            "act_name": "Indian Penal Code",
            "section": "Sections 354, 376, 406, 498A",
            "source": "IPC Women Protection",
            "issue_type": "domestic_violence",
        }
    },
    {
        "content": """Hindu Succession Act 1956 (Amended 2005) - Women's Property Rights

Section 6 (Amended 2005): Daughters have EQUAL right to ancestral property as sons.
This right exists from BIRTH, not from marriage.
Applies even if father died BEFORE 2005 (Supreme Court ruling 2020 — Vineeta Sharma vs Rakesh Sharma).
Applies to agricultural land in most states.
Right cannot be taken away by any family agreement.

How to claim:
1. File a civil suit in District Court for partition of property
2. Apply for legal aid at District Legal Services Authority (DLSA) — FREE
3. Collect documents: birth certificate, father's death certificate, property papers

Important: Brother/family saying "you have no right to property" is LEGALLY WRONG under this Act.""",
        "metadata": {
            "act_name": "Hindu Succession Act 1956 Amendment 2005",
            "section": "Section 6, SC Judgment Vineeta Sharma 2020",
            "source": "Hindu Succession Act",
            "issue_type": "property",
        }
    },
    {
        "content": """POSH Act 2013 — Sexual Harassment at Workplace

Definition: Unwelcome physical contact, demand for sexual favours, sexually coloured remarks,
showing pornography, any unwelcome verbal or non-verbal conduct of sexual nature.

Every employer MUST constitute an Internal Complaints Committee (ICC) if 10+ employees.
Your Rights:
- File complaint within 3 months of incident
- Inquiry must complete within 60 days
- You can request transfer during inquiry
- Employer cannot terminate you for filing complaint
- If employer has less than 10 employees: file with District Officer

Minimum Wages Act 1948:
Every worker has right to minimum wages fixed by State Government.
File complaint with Labour Commissioner of your district — FREE.""",
        "metadata": {
            "act_name": "POSH Act 2013",
            "section": "Sections 2, 4, 9, 11, 13",
            "source": "POSH Act 2013",
            "issue_type": "workplace",
        }
    },
    {
        "content": """Hindu Marriage Act 1955 - Divorce and Maintenance Rights

Grounds for Divorce (Section 13) — wife may petition for divorce on grounds of:
Cruelty, Desertion (minimum 2 years), Adultery, Conversion, Mental disorder, Bigamy.

Maintenance Rights — Section 125 CrPC:
Any woman whose husband has neglected or refused to maintain her may apply to Magistrate.
Court can order husband to pay maintenance even during separation.
No court fee required. Interim maintenance can be granted within 60 days.
You can apply for maintenance even WITHOUT filing for divorce.

FREE HELP:
- District Legal Services Authority (DLSA): Free lawyer and court help
- Women Helpline: 181 (24x7)
- NALSA: 15100""",
        "metadata": {
            "act_name": "Hindu Marriage Act 1955",
            "section": "Section 13, CrPC Section 125",
            "source": "Hindu Marriage Act 1955",
            "issue_type": "divorce",
        }
    },
    {
        "content": """Free Legal Aid — Every Woman's Right in India

Legal Services Authority Act 1987:
Every woman in India has the RIGHT to free legal aid regardless of income.
Includes: free lawyer, free court fees, free documentation help.

How to get FREE legal aid:
1. District Legal Services Authority (DLSA) — in every district court complex
   Ask for "Legal Aid" or "Muft Kanoon Sahayata"
2. NALSA Helpline: 15100 — call from anywhere in India, available in Hindi
3. Women Helpline: 181 (24x7, FREE, all India)
4. One Stop Centre (Sakhi): shelter, legal help, medical help — most districts

National Commission for Women: complaints@ncw.nic.in""",
        "metadata": {
            "act_name": "Legal Services Authority Act 1987",
            "section": "Free Legal Aid Rights",
            "source": "NALSA Legal Aid",
            "issue_type": "general",
        }
    }
]


def ingest_legal_documents():
    print("=" * 60)
    print("StriSakhi — Legal Document Ingestion")
    print("=" * 60)

    # Initialize ChromaDB
    print(f"\nConnecting to ChromaDB at: {settings.chroma_persist_dir}")
    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)

    # Use DefaultEmbeddingFunction — no sentence_transformers, no torch needed
    print("Loading ChromaDB default embedding function...")
    ef = embedding_functions.DefaultEmbeddingFunction()
    print("Embedding function ready (downloads ~80MB model on first run)")

    # Recreate collection fresh
    try:
        client.delete_collection(settings.legal_collection)
        print(f"Deleted existing collection: {settings.legal_collection}")
    except Exception:
        pass

    collection = client.create_collection(
        name=settings.legal_collection,
        embedding_function=ef,
        metadata={"description": "Indian legal documents for women's rights"}
    )
    print(f"Created collection: {settings.legal_collection}")

    documents = []
    metadatas = []
    ids = []

    # Step 1: Baseline legal knowledge
    print(f"\nLoading {len(BASELINE_LEGAL_DATA)} baseline legal documents...")
    for i, item in enumerate(BASELINE_LEGAL_DATA):
        documents.append(item["content"])
        metadatas.append(item["metadata"])
        ids.append(f"baseline_{i}")

    # Step 2: Load PDFs if available
    legal_docs_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "rag_documents", "legal"
    )

    if os.path.exists(legal_docs_dir):
        pdf_files = [f for f in os.listdir(legal_docs_dir) if f.endswith(('.pdf', '.txt'))]
        if pdf_files:
            print(f"\nFound {len(pdf_files)} files in rag_documents/legal/")
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=800,
                chunk_overlap=100
            )
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
                        })
                        ids.append(f"pdf_{fname}_{j}")

                except Exception as e:
                    print(f"  WARNING: Could not load {fname}: {e}")
        else:
            print("\nNo PDFs found — using baseline knowledge only")

    # Step 3: Add to ChromaDB (embedding happens inside collection.add)
    print(f"\nEmbedding and storing {len(documents)} documents in ChromaDB...")
    print("(This may take 1-2 minutes on first run while model downloads)")

    # Add in batches to show progress
    batch_size = 50
    for i in range(0, len(documents), batch_size):
        batch_docs = documents[i:i+batch_size]
        batch_meta = metadatas[i:i+batch_size]
        batch_ids = ids[i:i+batch_size]
        collection.add(
            documents=batch_docs,
            metadatas=batch_meta,
            ids=batch_ids
        )
        print(f"  Stored {min(i+batch_size, len(documents))}/{len(documents)}")

    print(f"\n✅ SUCCESS: {len(documents)} documents ingested")
    print(f"Collection '{settings.legal_collection}' ready")
    print("\nVerify: docker exec nyay-vani-backend python3 -c \"")
    print("import chromadb; c = chromadb.PersistentClient(path='/app/chroma_db')")
    print(f"print(c.get_collection('{settings.legal_collection}').count())")
    print("\"")


if __name__ == "__main__":
    ingest_legal_documents()
