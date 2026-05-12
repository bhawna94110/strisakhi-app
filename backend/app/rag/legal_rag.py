"""
Legal RAG — retrieves relevant law chunks from ChromaDB
Fixed: uses crime_type (not issue_type) from case_file
"""
from app.rag.retriever import retrieve_documents, format_context_for_prompt, get_citations_from_docs
from app.config import settings
from typing import Tuple, List, Dict

CRIME_QUERY_MAP = {
    "domestic_violence": "domestic violence wife rights husband DV Act 2005 Section 17 18 19 protection order residence",
    "property":          "daughter inheritance property rights Hindu Succession Act Section 6 equal share coparcenary Vineeta Sharma 2020",
    "workplace":         "workplace sexual harassment POSH Act 2013 ICC Section 4 9 employer employee",
    "divorce":           "divorce Hindu Marriage Act Section 13 separation grounds cruelty desertion",
    "custody":           "child custody mother rights guardian ward best interest",
    "dowry":             "dowry harassment IPC 498A dowry prohibition act cruelty husband wife",
    "maintenance":       "maintenance wife husband CrPC Section 125 alimony monthly allowance without divorce",
    "stalking":          "stalking IPC 354D cybercrime IT Act harassment online",
    "rape":              "rape sexual assault IPC 376 FIR medical examination compensation",
    "acid_attack":       "acid attack IPC 326A 326B compensation NALSA scheme hospital treatment",
    "trafficking":       "trafficking forced marriage IPC 366 ITPA prohibition child marriage",
    "general":           "women legal rights India protection laws helpline",
}


def get_legal_context(case_file: dict) -> Tuple[str, List[Dict]]:
    """
    Build search query from case_file and retrieve relevant legal chunks.
    Uses crime_type (not issue_type).
    Returns (formatted_context, citations_list)
    """
    # Fix: was using issue_type — now uses crime_type
    crime_type = (
        case_file.get("crime_type") or
        case_file.get("issue_type") or  # backward compat
        "general"
    )

    base_query = CRIME_QUERY_MAP.get(crime_type, CRIME_QUERY_MAP["general"])

    # Enrich with case specifics
    state = case_file.get("state") or case_file.get("location_state", "")
    religion = case_file.get("religion", "")
    if state:
        base_query += f" {state}"
    if religion and religion not in ("hindu", ""):
        base_query += f" {religion} personal law"

    docs = retrieve_documents(
        query=base_query,
        collection_name=settings.legal_collection,
        n_results=5  # increased from 3 to get better coverage
    )

    context = format_context_for_prompt(docs)
    citations = get_citations_from_docs(docs)
    return context, citations
