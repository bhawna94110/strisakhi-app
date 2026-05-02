import chromadb
from app.config import settings
from app.rag.embedder import embed_query
from typing import List, Dict

_client = None

def get_chroma_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    return _client

def retrieve_documents(
    query: str,
    collection_name: str,
    n_results: int = 3,
    where: dict = None
) -> List[Dict]:
    """Retrieve top N relevant document chunks for a query"""
    try:
        client = get_chroma_client()
        collection = client.get_collection(name=collection_name)
        query_embedding = embed_query(query)

        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": min(n_results, collection.count()),
            "include": ["documents", "metadatas", "distances"]
        }
        if where:
            kwargs["where"] = where

        results = collection.query(**kwargs)

        docs = []
        for i, (doc, meta, dist) in enumerate(zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        )):
            docs.append({
                "content": doc,
                "metadata": meta,
                "relevance_score": round(1 - dist, 4),
                "rank": i + 1
            })
        return docs

    except Exception as e:
        print(f"RAG retrieval error: {e}")
        return []

def format_context_for_prompt(docs: List[Dict]) -> str:
    """Format retrieved docs into prompt-ready context with citations"""
    if not docs:
        return "No specific legal documentation found for this query."

    context_parts = []
    for doc in docs:
        meta = doc.get("metadata", {})
        source = meta.get("source", "Legal Document")
        section = meta.get("section", "")
        act_name = meta.get("act_name", source)

        citation = f"{act_name}"
        if section:
            citation += f", {section}"

        context_parts.append(
            f"[Source: {citation}]\n{doc['content']}\n"
        )

    return "\n---\n".join(context_parts)

def get_citations_from_docs(docs: List[Dict]) -> List[Dict]:
    """Extract citation objects for storing with messages"""
    citations = []
    for doc in docs:
        meta = doc.get("metadata", {})
        citations.append({
            "source": meta.get("act_name", meta.get("source", "Legal Document")),
            "section": meta.get("section", ""),
            "relevance": doc.get("relevance_score", 0)
        })
    return citations
