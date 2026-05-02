from app.rag.retriever import retrieve_documents, format_context_for_prompt, get_citations_from_docs
from app.config import settings
from typing import Tuple, List, Dict

SYMPTOM_QUERY_MAP = {
    "pregnancy": "pregnancy antenatal care complications symptoms warning signs",
    "child_fever": "child fever management danger signs IMNCI guidelines",
    "mental_health": "depression anxiety mental health women support helpline",
    "maternal": "maternal health delivery complications postpartum",
    "general": "women health symptoms treatment guidelines India",
}

def get_medical_context(case_file: dict) -> Tuple[str, List[Dict]]:
    symptom = case_file.get("primary_symptom", "general")
    patient_age = case_file.get("patient_age", "")

    # Map symptom to query
    if "pregnant" in str(symptom).lower() or "pregnancy" in str(symptom).lower():
        query_key = "pregnancy"
    elif patient_age and int(str(patient_age).split("-")[0] if "-" in str(patient_age) else patient_age or 0) < 12:
        query_key = "child_fever"
    elif any(w in str(symptom).lower() for w in ["sad", "depress", "rona", "mental", "anxiety"]):
        query_key = "mental_health"
    else:
        query_key = "general"

    base_query = SYMPTOM_QUERY_MAP.get(query_key, SYMPTOM_QUERY_MAP["general"])
    base_query += f" {symptom}"

    docs = retrieve_documents(
        query=base_query,
        collection_name=settings.medical_collection,
        n_results=3
    )

    context = format_context_for_prompt(docs)
    citations = get_citations_from_docs(docs)
    return context, citations
