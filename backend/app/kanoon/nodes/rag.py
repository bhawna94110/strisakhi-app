"""
RAG Retrieval Node — Pure Python, no LLM call
Builds English query from state → queries ChromaDB → returns 5 chunks
"""
from app.kanoon.state import KanoonState
from app.rag.legal_rag import get_legal_context


async def rag_node(state: KanoonState) -> dict:
    """
    Build case_file dict from state and retrieve legal context.
    Returns rag_context string + citations list.
    """
    # Build English case file for RAG query
    case_file = {
        "crime_type": state.get("crime_type", "general"),
        "urgency": state.get("urgency"),
        "relationship_to_accused": state.get("relationship_to_accused"),
        "state": state.get("state_india"),
        "has_children": state.get("has_children"),
        "type_of_violence": state.get("type_of_violence"),
        "property_type": state.get("property_type"),
        "religion": state.get("religion"),
        "company_size": state.get("company_size"),
        "marital_status_current": state.get("marital_status_current"),
    }

    # Remove None values
    case_file = {k: v for k, v in case_file.items() if v is not None}

    try:
        rag_context, citations = get_legal_context(case_file)
        return {
            "rag_context": rag_context,
            "citations": citations,
        }
    except Exception as e:
        return {
            "rag_context": "Legal context unavailable. Respond based on general Indian law knowledge.",
            "citations": [],
            "error": f"RAG failed: {e}",
        }
