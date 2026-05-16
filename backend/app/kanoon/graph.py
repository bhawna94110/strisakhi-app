"""
Kanoon Sakhi — LangGraph Graph
Wires all nodes together with conditional routing.
Returns async generator of SSE events for legal.py to stream.
"""
import json
import logging
from typing import AsyncGenerator
from langgraph.graph import StateGraph, END

from app.kanoon.state import KanoonState, initial_state, state_to_metadata
from app.kanoon.nodes.translate import translate_input_node
from app.kanoon.nodes.emergency import emergency_check_node
from app.kanoon.nodes.intake import intake_node
from app.kanoon.nodes.rag import rag_node
from app.kanoon.nodes.expert import expert_node, build_expert_prompt
from app.kanoon.nodes.followup import followup_node
from app.kanoon.prompts import EMERGENCY_MESSAGES, EMERGENCY_FOLLOWUPS
from app.config import settings

LOG = logging.getLogger("strisakhi")

# ─── Conditional edges ────────────────────────────────────────────────────────

def route_after_emergency(state: KanoonState) -> str:
    """After emergency check — continue to intake or stop if critical."""
    if state.get("emergency_detected"):
        return "emergency_response"
    return "intake"


def route_after_intake(state: KanoonState) -> str:
    """After intake — continue collecting or go to expert."""
    if state.get("go_to_expert") or state.get("frustrated"):
        return "rag"
    return END  # Wait for next user message


def route_after_expert(state: KanoonState) -> str:
    """After expert response — always generate follow-ups."""
    return "followup"


# ─── Emergency response (not a node, inline in graph) ────────────────────────

async def emergency_response_node(state: KanoonState) -> dict:
    """Streams emergency message and continues conversation."""
    # Just return — actual streaming happens in run_graph()
    return {"emergency_detected": True}


# ─── Build graph ──────────────────────────────────────────────────────────────

def build_kanoon_graph() -> StateGraph:
    graph = StateGraph(KanoonState)

    graph.add_node("translate", translate_input_node)
    graph.add_node("emergency_check", emergency_check_node)
    graph.add_node("emergency_response", emergency_response_node)
    graph.add_node("intake", intake_node)
    graph.add_node("rag", rag_node)
    graph.add_node("expert", expert_node)
    graph.add_node("followup", followup_node)

    graph.set_entry_point("translate")

    graph.add_edge("translate", "emergency_check")

    graph.add_conditional_edges(
        "emergency_check",
        route_after_emergency,
        {
            "emergency_response": "emergency_response",
            "intake": "intake",
        }
    )

    graph.add_edge("emergency_response", END)

    graph.add_conditional_edges(
        "intake",
        route_after_intake,
        {
            "rag": "rag",
            END: END,
        }
    )

    graph.add_edge("rag", "expert")

    graph.add_conditional_edges(
        "expert",
        route_after_expert,
        {"followup": "followup"}
    )

    graph.add_edge("followup", END)

    return graph.compile()


# ─── Main run function — returns SSE events ───────────────────────────────────

async def run_kanoon_graph(
    session_id: str,
    user_message: str,
    language: str,
    history: list,
    existing_metadata: dict,
    db,
    emergency_enabled: bool = True,
    max_turns: int = 10,
) -> AsyncGenerator[dict, None]:
    """
    Run the full Kanoon Sakhi pipeline.
    Yields SSE event dicts — legal.py formats them as SSE strings.
    """
    from app.kanoon.nodes.save import save_node
    from app.session.session_manager import save_message

    # Determine current phase from metadata
    current_phase = existing_metadata.get("phase", "intake")

    # Override to follow_up if already in that phase
    if current_phase == "follow_up":
        existing_metadata["phase"] = "follow_up"

    # Build initial state
    state = initial_state(
        session_id=session_id,
        language=language,
        user_message=user_message,
        history=history,
        emergency_enabled=emergency_enabled,
        max_turns=max_turns,
        existing_metadata=existing_metadata,
    )

    # Update turn count
    state["turn_count"] = len([m for m in history if m.get("role") == "user"])

    # If already in follow_up phase, set go_to_expert=True to skip intake
    if current_phase == "follow_up":
        state["go_to_expert"] = True
        state["phase"] = "follow_up"

    graph = build_kanoon_graph()

    try:
        # ── Run graph step by step for streaming ──────────────────────────────
        async for event in graph.astream_events(state, version="v2"):
            kind = event.get("event", "")
            name = event.get("name", "")
            data = event.get("data", {})

            # ── Translation complete ──────────────────────────────────────────
            if kind == "on_chain_end" and name == "translate":
                processed = data.get("output", {}).get("user_message_processed", user_message)
                yield {"type": "processing", "step": "translated", "message": processed[:50]}

            # ── Emergency detected ────────────────────────────────────────────
            elif kind == "on_chain_end" and name == "emergency_check":
                output = data.get("output", {})
                if output.get("emergency_detected"):
                    yield {"type": "emergency", "data": {
                        "message": EMERGENCY_MESSAGES.get(language, EMERGENCY_MESSAGES["en"]),
                        "helplines": _get_helplines(language),
                    }}
                    # Stream emergency text
                    em_text = EMERGENCY_MESSAGES.get(language, EMERGENCY_MESSAGES["en"])
                    for char in em_text:
                        yield {"type": "token", "token": char, "agent": "emergency"}
                    # Save emergency message to DB
                    save_message(db, session_id, "assistant", em_text,
                                 agent_used="emergency")
                    yield {
                        "type": "done",
                        "full_response": em_text,
                        "citations": [],
                        "agent": "emergency",
                        "follow_up_questions": EMERGENCY_FOLLOWUPS.get(language, EMERGENCY_FOLLOWUPS["en"]),
                    }
                    return

                yield {"type": "routing", "step": "emergency_check", "detected": False}

            # ── Intake complete ───────────────────────────────────────────────
            elif kind == "on_chain_end" and name == "intake":
                output = data.get("output", {})
                question = output.get("current_question", "")
                score = output.get("readiness_score", 0)
                crime = output.get("crime_type", state.get("crime_type", "unknown"))
                going_to_expert = output.get("go_to_expert", False)

                yield {
                    "type": "metadata_update",
                    "confidence_score": score,
                    "crime_type": crime,
                    "metadata": {k: v for k, v in output.items()
                                 if k in state and v is not None},
                }

                # If not going to expert — stream intake question
                if not going_to_expert and question:
                    yield {"type": "routing", "decision": "intake",
                           "score": score, "crime": crime}
                    for char in question:
                        yield {"type": "token", "token": char, "agent": "intake"}

                    # Save intake question to DB
                    save_message(db, session_id, "assistant", question,
                                 agent_used="intake")

                    # Save state to DB
                    merged = {**state, **output}
                    save_node(merged, db)

                    yield {
                        "type": "done",
                        "full_response": question,
                        "agent": "intake",
                        "follow_up_questions": [],
                    }
                    return  # Stop here — wait for next user message

                else:
                    # Going to expert — update state and continue graph
                    state.update(output)
                    yield {"type": "phase_change", "from": "intake", "to": "expert"}

            # ── RAG complete ──────────────────────────────────────────────────
            elif kind == "on_chain_end" and name == "rag":
                output = data.get("output", {})
                citations = output.get("citations", [])
                yield {"type": "citations", "citations": citations}

            # ── Expert streaming tokens ───────────────────────────────────────
            elif kind == "on_chain_stream" and name == "expert":
                chunk = data.get("chunk", {})
                if isinstance(chunk, dict):
                    token = chunk.get("response", "")
                    if token:
                        yield {"type": "token", "token": token, "agent": "expert"}

            # ── Expert complete ───────────────────────────────────────────────
            elif kind == "on_chain_end" and name == "expert":
                output = data.get("output", {})
                response = output.get("response", "")        # cleaned for user
                response_raw = output.get("response_raw", response)  # raw for scoring

                # Update local state
                state["response"] = response
                state["response_raw"] = response_raw
                state["phase"] = "follow_up"

                # Stream cleaned response to user
                if response:
                    for char in response:
                        yield {"type": "token", "token": char, "agent": "expert"}

                # Save raw response to DB (preserves structure for evaluation)
                merged_after_expert = {**state, **output}
                save_node(merged_after_expert, db)
                save_message(db, session_id, "assistant", response_raw,
                             citations=state.get("citations", []),
                             agent_used="expert")

            # ── Follow-ups complete ───────────────────────────────────────────
            elif kind == "on_chain_end" and name == "followup":
                output = data.get("output", {})
                follow_ups = output.get("follow_up_questions", [])
                # Use response captured from expert node
                full_response = state.get("response", "")

                yield {
                    "type": "done",
                    "full_response": full_response,
                    "citations": state.get("citations", []),
                    "agent": "expert",
                    "follow_up_questions": follow_ups,
                }

    except Exception as e:
        LOG.error(f"Graph error: {e}", exc_info=True)
        yield {"type": "error", "message": str(e)}


def _get_helplines(language: str) -> list:
    helplines = {
        "hi": [
            {"number": "181", "label": "महिला हेल्पलाइन (24 घंटे)"},
            {"number": "100", "label": "पुलिस"},
            {"number": "1091", "label": "महिला संकट"},
            {"number": "15100", "label": "मुफ्त कानूनी सहायता"},
        ],
        "en": [
            {"number": "181", "label": "Women Helpline (24 hrs)"},
            {"number": "100", "label": "Police"},
            {"number": "1091", "label": "Women in Distress"},
            {"number": "15100", "label": "Free Legal Aid"},
        ],
        "bn": [
            {"number": "181", "label": "মহিলা হেল্পলাইন"},
            {"number": "100", "label": "পুলিশ"},
        ],
    }
    return helplines.get(language, helplines["en"])
