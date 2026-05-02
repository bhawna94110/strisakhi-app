from app.rag.retriever import retrieve_documents, format_context_for_prompt, get_citations_from_docs
from app.config import settings
from typing import Tuple, List, Dict

# Issue type to search query mapping
ISSUE_QUERY_MAP = {
    "domestic_violence": "domestic violence wife rights husband house removal DV Act protection",
    "property": "daughter inheritance property rights Hindu succession equal share",
    "workplace": "workplace sexual harassment POSH Act employer employee rights",
    "divorce": "divorce Hindu marriage separation maintenance alimony rights",
    "custody": "child custody mother rights welfare best interest",
    "dowry": "dowry harassment 498A IPC cruelty husband wife",
    "land": "land rights women property ownership registration",
    "maintenance": "maintenance alimony husband wife section 125 CrPC",
    "general": "women legal rights India protection laws",
}

def get_legal_context(case_file: dict) -> Tuple[str, List[Dict]]:
    """
    Build search query from case file and retrieve relevant legal docs.
    Returns (formatted_context, citations_list)
    """
    issue_type = case_file.get("issue_type", "general")
    base_query = ISSUE_QUERY_MAP.get(issue_type, ISSUE_QUERY_MAP["general"])

    # Enrich query with case specifics
    state = case_file.get("location_state", "")
    religion = case_file.get("religion", "")
    if state:
        base_query += f" {state}"
    if religion and religion != "hindu":
        base_query += f" {religion} personal law"

    docs = retrieve_documents(
        query=base_query,
        collection_name=settings.legal_collection,
        n_results=3
    )

    context = format_context_for_prompt(docs)
    citations = get_citations_from_docs(docs)
    return context, citations
