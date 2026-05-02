from sentence_transformers import SentenceTransformer
from app.config import settings
import numpy as np

_model = None

def get_embedder():
    global _model
    if _model is None:
        print(f"Loading embedding model: {settings.embedding_model}")
        _model = SentenceTransformer(settings.embedding_model)
        print("Embedding model loaded")
    return _model

def embed_texts(texts: list) -> list:
    model = get_embedder()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()

def embed_query(text: str) -> list:
    model = get_embedder()
    embedding = model.encode([text], normalize_embeddings=True)
    return embedding[0].tolist()
