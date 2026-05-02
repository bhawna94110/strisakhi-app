"""
Medical Expert Agent — Uses Gemma 4 E4B
Provides health guidance based on WHO/Indian health guidelines via RAG.
"""
import ollama
from app.config import settings
from app.utils.prompt_builder import build_medical_expert_prompt
from app.rag.medical_rag import get_medical_context
from typing import AsyncGenerator

client = ollama.AsyncClient(host=settings.ollama_base_url)

async def run_medical_expert_stream(
    case_file: dict,
    conversation_history: list,
    language: str = "hi"
) -> AsyncGenerator[dict, None]:
    rag_context, citations = get_medical_context(case_file)
    yield {"type": "rag_retrieved", "citations": citations, "chunk_count": len(citations)}

    prompt = build_medical_expert_prompt(
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
