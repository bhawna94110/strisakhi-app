"""
Legal Expert Agent — Uses Gemma 4 E4B (fine-tuned)
Provides precise, RAG-grounded legal guidance.
Only invoked after intake agent completes.
"""
import ollama
from app.config import settings
from app.utils.prompt_builder import build_legal_expert_prompt
from app.rag.legal_rag import get_legal_context
from typing import AsyncGenerator

client = ollama.AsyncClient(host=settings.ollama_base_url)

async def run_legal_expert_stream(
    case_file: dict,
    conversation_history: list,
    language: str = "hi"
) -> AsyncGenerator[dict, None]:
    """
    Stream legal expert response with RAG citations.
    """
    # Step 1: Retrieve relevant legal context
    rag_context, citations = get_legal_context(case_file)
    yield {"type": "rag_retrieved", "citations": citations, "chunk_count": len(citations)}

    # Step 2: Build expert prompt
    prompt = build_legal_expert_prompt(
        case_file, rag_context, conversation_history, language
    )

    full_response = ""

    try:
        stream = await client.chat(
            model=settings.expert_model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            options={"temperature": 0.2, "num_predict": 512}
        )

        async for chunk in stream:
            token = chunk.message.content or ""
            full_response += token
            yield {"type": "token", "token": token, "agent": "expert"}

    except Exception as e:
        yield {"type": "error", "message": str(e)}
        return

    yield {
        "type": "done",
        "full_response": full_response,
        "citations": citations,
        "agent": "expert"
    }
