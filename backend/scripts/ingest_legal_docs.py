"""
Legal Document Ingestion v3 — StriSakhi
Fixes ChromaDB delete bug by using get_or_create + delete_all approach.
"""
import sys, os, time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from chromadb.utils import embedding_functions
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.config import settings

BASELINE_LEGAL_DATA = [
    {
        "content": """Protection of Women from Domestic Violence Act, 2005 (DV Act)

Section 17: Right to reside in shared household
Every woman in a domestic relationship shall have the right to reside in the shared household,
whether or not she has any right, title or beneficial interest in the same.
The aggrieved person shall not be evicted or excluded from the shared household or any part of it
by the respondent save in accordance with the procedure established by law.
This applies even if the house is in the husband's name or in-laws' name.

Section 18: Protection orders
The Magistrate may, after giving the aggrieved person and the respondent an opportunity of being heard
and on being prima facie satisfied that domestic violence has taken place or is likely to take place,
pass a protection order in favour of the aggrieved person prohibiting the respondent from:
committing further acts of domestic violence, entering the aggrieved person's workplace,
attempting to communicate with her, alienating any assets including jointly held assets.

Section 19: Residence orders
The Magistrate may pass a residence order restraining the respondent from dispossessing
or disturbing the possession of the aggrieved person from the shared household,
or directing the respondent to remove himself from the shared household.
The woman CANNOT be evicted from the shared household even if it belongs to husband or in-laws.

Section 12: Application to Magistrate
An aggrieved person may present an application to the Magistrate seeking one or more reliefs.
The Magistrate shall fix the first date of hearing within THREE DAYS of receipt.
Application can be filed by the woman herself, Protection Officer, or any person on her behalf.
Protection Officers are available in EVERY district and help file for FREE.""",
        "metadata": {"act_name": "Protection of Women from Domestic Violence Act 2005",
                     "section": "Sections 12, 17, 18, 19", "source": "DV Act 2005",
                     "crime_type": "domestic_violence"}
    },
    {
        "content": """Protection of Women from Domestic Violence Act, 2005 (DV Act)

Section 20: Monetary reliefs
The Magistrate may direct the respondent to pay monetary relief to meet expenses and losses
suffered by the aggrieved person as a result of domestic violence including:
(a) loss of earnings
(b) medical expenses  
(c) loss caused due to destruction or removal of any property
(d) maintenance for the aggrieved person and her children
The Magistrate may order lump sum or monthly payments. Interim monetary relief can be filed
at any stage — before or during the main case.

Section 21: Custody orders
The Magistrate may grant temporary custody of children to the aggrieved person at any stage
of hearing an application under this Act.

Section 22: Compensation orders
The Magistrate may pass an order directing the respondent to pay compensation and damages
for injuries including mental torture and emotional distress caused by domestic violence.

IPC Section 498A: Husband or relative of husband subjecting woman to cruelty
Punishable with imprisonment up to 3 years and fine.
498A is COGNIZABLE — police can arrest without warrant.
If dowry demand is involved along with cruelty — 498A applies automatically.""",
        "metadata": {"act_name": "Protection of Women from Domestic Violence Act 2005",
                     "section": "Sections 20, 21, 22", "source": "DV Act 2005",
                     "crime_type": "domestic_violence"}
    },
    {
        "content": """Vineeta Sharma v Rakesh Sharma — Supreme Court of India, Full Bench, 2020

Case citation: Vineeta Sharma v Rakesh Sharma (2020) 9 SCC 1
Bench: Three-judge bench of the Supreme Court of India
Date of judgment: August 11, 2020

THIS JUDGMENT MUST BE CITED IN ALL PROPERTY CASES INVOLVING DAUGHTERS.

KEY RULING:
The Supreme Court held that daughters have equal coparcenary rights in Hindu Undivided Family
ancestral property BY BIRTH, regardless of whether the father was alive or had died before
September 9, 2005 (when the Hindu Succession Amendment Act 2005 came into force).

CRITICAL POINTS:
1. A daughter is a coparcener by birth in the same manner as a son
2. The right accrues from the DATE OF BIRTH — not from 2005 amendment date
3. Amendment applies EVEN IF FATHER DIED BEFORE 2005 — this is the landmark change
4. Overrules Prakash v Phulavati (2016) and Danamma v Amar (2018) which had confused this
5. Daughters can demand partition of ancestral property at any time
6. Applies to agricultural land in most states
7. Cannot be taken away by family settlement without daughter's consent

PRACTICAL MEANING:
If a brother says "you have no right to father's property" — THIS IS LEGALLY WRONG.
If a brother says "father died before 2005 so you have no right" — THIS IS LEGALLY WRONG.
If a brother says "you are married so you lost your right" — THIS IS LEGALLY WRONG.

Daughters have had equal property rights SINCE BIRTH under Vineeta Sharma 2020.""",
        "metadata": {"act_name": "Vineeta Sharma v Rakesh Sharma, Supreme Court 2020",
                     "section": "Full Bench Judgment August 11 2020",
                     "source": "Supreme Court of India 2020",
                     "crime_type": "property"}
    },
    {
        "content": """Hindu Succession Act 1956 (Amendment 2005) — Section 6

Section 6: Devolution of interest in coparcenary property (amended 2005)
On and from the commencement of the Hindu Succession (Amendment) Act 2005,
in a Joint Hindu Family governed by Mitakshara law, the daughter of a coparcener shall:
(a) by birth become a coparcener in her own right in the SAME MANNER AS THE SON
(b) have the SAME RIGHTS in the coparcenary property as she would have had if she had been a son
(c) be subject to the same liabilities in respect of the said coparcenary property as that of a son

RIGHT IS FROM BIRTH — confirmed by Vineeta Sharma v Rakesh Sharma, Supreme Court 2020:
Daughters have EQUAL rights even if father died before September 9, 2005.

What is coparcenary property?
Ancestral property that has passed undivided for at least four generations.
Includes: agricultural land, residential property passed from ancestors,
family business property that was ancestral.

Does NOT include: property bought by father with his own money and not declared as HUF property.
For self-acquired property: father could have willed it to anyone, but ONLY if there is a will.
If NO WILL exists for self-acquired property: daughters share equally with sons under Section 8.

How to claim rights:
1. File partition suit in District Court
2. Get free lawyer from DLSA (District Legal Services Authority) in every district court
3. NALSA helpline: 15100 (free, Monday-Saturday)
4. Documents: birth certificate, father's death certificate, property records (khata/patta)""",
        "metadata": {"act_name": "Hindu Succession Act 1956 Amendment 2005",
                     "section": "Section 6 — Vineeta Sharma 2020",
                     "source": "Hindu Succession Act",
                     "crime_type": "property"}
    },
    {
        "content": """Code of Criminal Procedure (CrPC) — Section 125: Order for Maintenance of Wives

Section 125(1): 
If any person having sufficient means neglects or refuses to maintain his wife unable to maintain herself,
a Magistrate of the first class may order such person to make a monthly allowance for maintenance.

CRITICAL FACT: Maintenance can be claimed WITHOUT filing for divorce.
This is the most common misconception. CrPC Section 125 applies to:
- Wife living separately from husband (even without divorce)
- Wife who has been abandoned by husband  
- Wife who left husband due to his cruelty (still entitled to maintenance)
- Divorced wife who has not remarried

Section 125(2): Interim Maintenance — 60 Day Rule
Any application under Section 125 shall be disposed of within 60 DAYS from the date
of service of notice to the respondent.
The Magistrate CAN GRANT INTERIM MAINTENANCE while the main case is pending.
Interim maintenance provides immediate financial relief within 60 days of filing.

NO COURT FEE: Filing application under CrPC Section 125 is COMPLETELY FREE.
No stamp duty, no court fee, no lawyer fee if using DLSA/NALSA.

Amount: Court decides based on husband's income, wife's needs, standard of living.
Courts in India typically award 20-25% of husband's net income as wife's maintenance.
Children's maintenance is additional and separate.

ENFORCEMENT: If husband does not pay court-ordered maintenance — contempt of court.
Husband can be imprisoned for non-payment.

HOW TO APPLY:
1. Go to Family Court or Judicial Magistrate court in your district
2. No court fee — completely free to file
3. Get free lawyer: NALSA 15100 or DLSA (District Legal Services Authority)
4. Documents needed: marriage certificate, proof of husband's income if available""",
        "metadata": {"act_name": "Code of Criminal Procedure",
                     "section": "Section 125, Section 125(2) Interim Maintenance 60 days",
                     "source": "CrPC Section 125",
                     "crime_type": "maintenance"}
    },
    {
        "content": """Maintenance Rights — Complete Guide for Indian Women

1. MAINTENANCE WITHOUT DIVORCE (CrPC Section 125):
A wife does NOT need to file for divorce to claim maintenance from her husband.
Even a wife living separately can claim monthly maintenance immediately.
Wife who left due to husband's cruelty is STILL entitled to maintenance.
This corrects the common misconception that divorce must come before maintenance.

2. INTERIM MAINTENANCE within 60 days:
Under CrPC Section 125(2), court must decide within 60 days of notice to husband.
Interim maintenance provides immediate financial relief while full case continues.

3. HOW MUCH MAINTENANCE:
No fixed formula — Magistrate decides based on:
- Husband's monthly income and assets
- Wife's reasonable needs and current expenses
- Number and ages of children
- Standard of living during marriage
Typical award: 20-25% of husband's net income for wife alone.
Children's maintenance is additional.

4. IF HUSBAND REFUSES TO PAY:
Court-ordered maintenance not paid = contempt of court.
Wife can file execution petition — husband can be imprisoned.

5. MAINTENANCE DURING DIVORCE:
Hindu Marriage Act Section 24: Interim maintenance during divorce proceedings.
Hindu Marriage Act Section 25: Permanent alimony after divorce decree.
These are SEPARATE from CrPC 125 and can be filed together.

6. FREE LEGAL HELP:
NALSA: 15100 (free legal aid, Monday-Saturday, Hindi available)
DLSA: District Legal Services Authority — in every district court complex
Women Helpline: 181 (24x7, connects to local support)
One Stop Centre: 181 → shelter + legal + medical all free""",
        "metadata": {"act_name": "CrPC Section 125, Hindu Marriage Act Sections 24-25",
                     "section": "Maintenance Rights Complete Guide",
                     "source": "CrPC Section 125",
                     "crime_type": "maintenance"}
    },
    {
        "content": """POSH Act 2013 — Prevention, Protection and Redressal of Sexual Harassment at Workplace

Section 2: Sexual harassment definition
Includes any unwelcome sexually determined behaviour: physical contact and advances,
demand or request for sexual favours, sexually coloured remarks, showing pornography,
any unwelcome physical, verbal or non-verbal conduct of sexual nature.
Workplace includes any place visited arising out of or during the course of employment.

Section 4: Internal Complaints Committee (ICC)
EVERY employer having 10 or more workers SHALL constitute an ICC.
Less than 10 employees: complaint goes to Local Complaints Committee (LCC) set up by District Officer.
No ICC when required = employer has violated POSH Act Section 4 itself.

Section 9: Filing complaint
Aggrieved woman may file complaint within 3 months of incident.
Time limit may be extended by ICC for another 3 months with reason.

Section 11: Protection during inquiry
Employer SHALL transfer aggrieved woman or respondent on her written request.
Grant leave up to 3 months during inquiry.
Employer SHALL NOT allow respondent to report on complainant's work performance.
Retaliation (termination, demotion, transfer) for filing complaint = separate violation.

Section 13: Inquiry timeline
ICC must complete inquiry within 60 days.
If complaint proved: ICC recommends punishment including termination, compensation.

If NO ICC exists: File directly with District Officer (Labour Department).""",
        "metadata": {"act_name": "POSH Act 2013",
                     "section": "Sections 2, 4, 9, 11, 13",
                     "source": "POSH Act 2013",
                     "crime_type": "workplace"}
    },
    {
        "content": """Dowry Prohibition Act 1961 and IPC Dowry Sections

Dowry Prohibition Act 1961 Section 3:
If any person gives or takes or abets giving or taking of dowry — punishable with
imprisonment not less than 5 years and fine not less than Rs 15,000 or value of dowry.
Demanding dowry is a CRIMINAL OFFENCE — not just a civil matter.

IPC Section 498A: Cruelty by husband or relative for dowry
Punishment: up to 3 years imprisonment and fine.
Cruelty includes: harassment to coerce wife or her family to meet unlawful demands for property.
498A is COGNIZABLE — police can arrest without warrant.
498A is NON-BAILABLE — bail not automatic.

IPC Section 304B: Dowry Death
Death of woman within 7 years of marriage under suspicious circumstances +
prior cruelty/harassment for dowry = presumed dowry death.
Punishment: MINIMUM 7 years, may extend to life imprisonment.

IPC Section 406: Criminal Breach of Trust (Stridhan)
Stridhan = jewellery, clothes, gifts given to wife at or after marriage.
If husband or in-laws do not return stridhan = criminal breach of trust.
Punishment: up to 3 years imprisonment.

How to file: FIR at police station — police CANNOT refuse (cognizable offence).
If police refuse FIR: complain to Superintendent of Police or Magistrate.""",
        "metadata": {"act_name": "Dowry Prohibition Act 1961, IPC 498A, 304B, 406",
                     "section": "Sections 3, 498A, 304B, 406",
                     "source": "Dowry Prohibition Act 1961",
                     "crime_type": "dowry"}
    },
    {
        "content": """IPC Section 354D Stalking and IT Act Cybercrime

IPC Section 354D: Stalking
Any man who follows a woman and contacts her repeatedly despite clear indication of disinterest,
or monitors her internet or electronic communication use — commits stalking.
Punishment: First conviction up to 3 years + fine. Repeat conviction up to 5 years.

IT Act Cybercrime Sections:
Section 66E: Publishing images of private areas without consent — up to 3 years or Rs 2 lakh fine.
Section 67: Publishing obscene material electronically — up to 3 years, Rs 5 lakh fine.
Section 67A: Publishing sexually explicit material — up to 5 years, Rs 10 lakh fine.
Section 66C: Identity theft online — up to 3 years imprisonment.

Threat to share intimate images (revenge porn):
Covered under IT Act 66E and 67A combined — up to 5-7 years.
Also IPC 354D if used for stalking/coercion.

Evidence collection (CRITICAL): Screenshot everything BEFORE blocking.
Save all messages, call logs, social media posts with timestamps.
Once blocked, evidence becomes harder to collect.

How to report:
1. National Cyber Crime Portal: cybercrime.gov.in
2. Cyber Crime Helpline: 1930
3. Local police station FIR mentioning IT Act sections
4. Women Helpline: 181""",
        "metadata": {"act_name": "IPC Section 354D, IT Act 2000",
                     "section": "354D, 66C, 66E, 67, 67A",
                     "source": "IPC 354D IT Act",
                     "crime_type": "stalking"}
    },
    {
        "content": """Free Legal Aid — Every Woman's Right in India

Legal Services Authority Act 1987:
Every woman has the RIGHT to free legal aid regardless of income level.
Includes: free lawyer who appears in court, free court fee waiver, free document drafting.

NALSA (National Legal Services Authority):
Helpline: 15100 (FREE, Monday to Saturday, Hindi and regional languages)
Services: Free lawyer for all courts including High Court and Supreme Court.
Priority service for: domestic violence, rape, property disputes, maintenance cases.

DLSA (District Legal Services Authority):
Located in EVERY district court complex across India.
Ask for: "Muft Kanoon Sahayata" or "Free Legal Aid"
Can provide: free lawyer, free application drafting, free court representation.

One Stop Centre (Sakhi):
Call 181 to find nearest centre. Available in most districts.
Services: Emergency shelter (5 days), medical, police, legal, counselling — ALL FREE.

NCW (National Commission for Women):
Online complaint: ncwapps.nic.in
Helpline: 7827170170
Handles: domestic violence, harassment, dowry, workplace harassment.

Key Helplines:
181 — Women Helpline (24x7, all India, FREE)
1091 — Women in Distress (24x7)
15100 — NALSA Free Legal Aid
100 — Police
108 — Ambulance
1930 — Cybercrime""",
        "metadata": {"act_name": "Legal Services Authority Act 1987",
                     "section": "NALSA 15100 Free Legal Aid",
                     "source": "NALSA Legal Aid",
                     "crime_type": "general"}
    },
]


def ingest_legal_documents():
    print("=" * 60)
    print("StriSakhi — Enhanced Legal Document Ingestion v3")
    print("=" * 60)

    ef = embedding_functions.DefaultEmbeddingFunction()

    # ── Safe delete: use one client, delete, then create new client ──────────
    print("\nStep 1: Clearing existing collection...")
    try:
        _c = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        existing = [col.name for col in _c.list_collections()]
        if settings.legal_collection in existing:
            _c.delete_collection(settings.legal_collection)
            print(f"  Deleted: {settings.legal_collection}")
        del _c
        time.sleep(1)  # let ChromaDB flush writes to disk
    except Exception as e:
        print(f"  Note: {e}")

    # ── Fresh client for create + add ────────────────────────────────────────
    print("Step 2: Creating fresh collection...")
    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    collection = client.create_collection(
        name=settings.legal_collection,
        embedding_function=ef,
        metadata={"description": "Indian legal documents v3"}
    )
    print(f"  Created: {settings.legal_collection}")

    documents, metadatas, ids = [], [], []

    # Baseline
    print(f"\nStep 3: Loading {len(BASELINE_LEGAL_DATA)} enhanced baseline docs...")
    for i, item in enumerate(BASELINE_LEGAL_DATA):
        documents.append(item["content"])
        metadatas.append(item["metadata"])
        ids.append(f"baseline_v3_{i}")

    # PDFs
    legal_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "rag_documents", "legal"
    )
    if os.path.exists(legal_dir):
        pdfs = [f for f in os.listdir(legal_dir) if f.endswith(('.pdf', '.txt'))]
        if pdfs:
            print(f"\nStep 4: Loading {len(pdfs)} PDFs...")
            splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
            for fname in pdfs:
                try:
                    loader = (PyPDFLoader(os.path.join(legal_dir, fname))
                              if fname.endswith('.pdf')
                              else TextLoader(os.path.join(legal_dir, fname), encoding='utf-8'))
                    chunks = splitter.split_documents(loader.load())
                    print(f"  {fname}: {len(chunks)} chunks")
                    ct = ("domestic_violence" if "dv_act" in fname.lower() else
                          "property" if "succession" in fname.lower() else
                          "workplace" if "posh" in fname.lower() else
                          "dowry" if "dowry" in fname.lower() else
                          "maintenance" if "crpc" in fname.lower() else "general")
                    for j, chunk in enumerate(chunks):
                        if len(chunk.page_content.strip()) < 50:
                            continue
                        documents.append(chunk.page_content)
                        metadatas.append({
                            "act_name": fname.replace('.pdf', '').replace('_', ' ').title(),
                            "section": f"chunk {j+1}",
                            "source": fname,
                            "crime_type": ct,
                        })
                        ids.append(f"pdf_{fname}_{j}")
                except Exception as e:
                    print(f"  WARNING {fname}: {e}")

    # Add in batches
    print(f"\nStep 5: Embedding {len(documents)} documents...")
    batch_size = 40
    for i in range(0, len(documents), batch_size):
        collection.add(
            documents=documents[i:i+batch_size],
            metadatas=metadatas[i:i+batch_size],
            ids=ids[i:i+batch_size]
        )
        print(f"  Stored {min(i+batch_size, len(documents))}/{len(documents)}")

    print(f"\n✅ SUCCESS: {len(documents)} documents in {settings.legal_collection}")

    # Verify all 3 use cases
    print("\n--- Verifying RAG retrieval ---")
    tests = [
        ("DV Act Sections 17+20", "domestic violence Section 17 18 19 20 residence protection monetary relief"),
        ("Vineeta Sharma 2020",   "Vineeta Sharma Supreme Court 2020 daughter property rights"),
        ("CrPC 125 Maintenance",  "CrPC Section 125 maintenance wife without divorce interim 60 days free"),
    ]
    for name, query in tests:
        r = collection.query(query_texts=[query], n_results=2)
        print(f"\n  {name}:")
        for doc in r["documents"][0]:
            print(f"    ✓ {doc[:90].strip()}...")


if __name__ == "__main__":
    ingest_legal_documents()
