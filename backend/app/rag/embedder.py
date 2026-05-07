"""
Embedder — uses ChromaDB's built-in embedding function.
No sentence_transformers, no torch, no heavy dependencies.
ChromaDB uses all-MiniLM-L6-v2 by default — same quality, no extra install.
"""
from chromadb.utils import embedding_functions

_ef = None

def get_embedder():
    global _ef
    if _ef is None:
        print("Loading ChromaDB default embedding function...")
        _ef = embedding_functions.DefaultEmbeddingFunction()
        print("Embedder ready")
    return _ef

def embed_texts(texts: list) -> list:
    ef = get_embedder()
    return ef(texts)

def embed_query(text: str) -> list:
    ef = get_embedder()
    return ef([text])[0]
