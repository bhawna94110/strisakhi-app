#!/usr/bin/env python3
"""
StriSakhi — Kanoon Sakhi Integration Test
Tests all 3 demo use cases end-to-end.
Saves full conversation + scores to JSON.

Run from project root:
  python backend/tests/test_kanoon.py

Output:
  backend/tests/results/kanoon_test_{timestamp}.json
"""
import asyncio
import httpx
import json
import re
import sys
from datetime import datetime
from pathlib import Path

API = "http://localhost:8000"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# ─── 3 Demo Use Cases ────────────────────────────────────────────────────────

TEST_CASES = [
    {
        "id": "demo_01_domestic_violence",
        "name": "Domestic Violence — Hindi (Hinglish input)",
        "language": "hi",
        "description": "Woman beaten by husband for 3 years, children involved, in-laws also participating",
        "conversation": [
            "mere pati mujhe bahut marte hain",
            "3 saal se ho raha hai, belt se maarte hain, main unke ghar mein rehti hoon, 2 bacche bhi hain",
            "haan main puri tarah unpe dependent hoon, sasural waale bhi involved hain",
            "pehle ek baar NCR daali thi par police ne kuch nahi kiya",
            "koi aur cheez nahi batani, bas mujhe bachao aur ghar mein rehna chahti hoon",
        ],
        "expected": {
            "crime_type": "domestic_violence",
            "routes_to_expert": True,
            "min_score_at_expert": 60,
            "expected_sections": ["Section 17", "Section 18", "DV Act"],
            "expected_helplines": ["181", "15100"],
            "response_language": "hi",
            "max_intake_turns": 5,
        }
    },
    {
        "id": "demo_02_property_rights",
        "name": "Property Rights — Hindi (RAG power: Vineeta Sharma 2020)",
        "language": "hi",
        "description": "Daughter denied ancestral property share by brother after father's death",
        "conversation": [
            "mere bhai keh rahe hain ki mujhe papa ki zameen mein koi hissa nahi milega",
            "hamare papa 2 saal pehle guzar gaye, zameen unke naam thi, hum sab Hindu hain",
            "bhai ne zameen apne naam karaani shuru kar di hai, koi will nahi thi",
            "zameen agricultural hai, Rajasthan mein hai, documents hamare paas nahi hain",
            "bhai akele hain, koi aur nahi roke raha, bas unhone kaha tumhara haq nahi",
        ],
        "expected": {
            "crime_type": "property",
            "routes_to_expert": True,
            "min_score_at_expert": 60,
            "expected_sections": ["Section 6", "Hindu Succession Act", "Vineeta Sharma"],
            "expected_helplines": ["15100"],
            "response_language": "hi",
            "max_intake_turns": 5,
            "rag_power_moment": "Vineeta Sharma v Rakesh Sharma 2020 SC judgment"
        }
    },
    {
        "id": "demo_03_maintenance",
        "name": "Maintenance Without Divorce — Hindi (Common misconception corrected)",
        "language": "hi",
        "description": "Separated woman thinks she must divorce first to get maintenance",
        "conversation": [
            "kya main bina divorce ke pati se paise maang sakti hoon",
            "main 8 mahine se alag hoon, pati ne chhod diya, wo dono bacchon ke saath hain",
            "pati government job karta hai, main khud kuch nahi kamati",
            "wo kuch bhi nahi de raha, pehle thoda deta tha ab band kar diya",
            "mujhe nahi pata divorce chahiye ya nahi, bas abhi guzara chahiye",
        ],
        "expected": {
            "crime_type": "maintenance",
            "routes_to_expert": True,
            "min_score_at_expert": 60,
            "expected_sections": ["CrPC Section 125", "Section 125"],
            "expected_helplines": ["15100"],
            "response_language": "hi",
            "max_intake_turns": 5,
            "misconception_corrected": "No divorce needed for maintenance"
        }
    },
]

# ─── SSE Parser ───────────────────────────────────────────────────────────────

def parse_sse(raw: str) -> list[dict]:
    events = []
    for line in raw.split("\n"):
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except Exception:
                pass
    return events

# ─── Single turn ──────────────────────────────────────────────────────────────

async def send_message(
    client: httpx.AsyncClient,
    session_id: str,
    message: str,
    language: str,
) -> dict:
    """Send one message and collect all SSE events."""
    full_response = ""
    tokens = []
    metadata_updates = []
    citations = []
    routing_events = []
    phase_changes = []
    follow_ups = []
    agent_used = "intake"
    done_event = {}
    error = None

    try:
        async with client.stream(
            "POST",
            f"{API}/api/legal/chat",
            json={"session_id": session_id, "message": message, "language": language},
            timeout=120,
        ) as resp:
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    ev = json.loads(line[6:])
                    t = ev.get("type", "")

                    if t == "token":
                        tokens.append(ev.get("token", ""))
                        agent_used = ev.get("agent", agent_used)
                    elif t == "metadata_update":
                        metadata_updates.append(ev)
                    elif t == "citations":
                        citations = ev.get("citations", [])
                    elif t == "routing":
                        routing_events.append(ev)
                    elif t == "phase_change":
                        phase_changes.append(ev)
                    elif t == "done":
                        full_response = ev.get("full_response", "".join(tokens))
                        follow_ups = ev.get("follow_up_questions", [])
                        agent_used = ev.get("agent", agent_used)
                        done_event = ev
                    elif t == "error":
                        error = ev.get("message", "unknown error")
                except Exception:
                    pass
    except Exception as e:
        error = str(e)

    return {
        "message_sent": message,
        "agent_used": agent_used,
        "full_response": full_response,
        "full_response_raw": full_response,  # same — raw saved to DB, clean streamed
        "response_preview": full_response[:200],
        "citations": citations,
        "follow_up_questions": follow_ups,
        "metadata_updates": metadata_updates,
        "routing_events": routing_events,
        "phase_changes": phase_changes,
        "score_at_turn": metadata_updates[-1].get("confidence_score", 0) if metadata_updates else 0,
        "crime_detected": metadata_updates[0].get("crime_type") if metadata_updates else None,
        "error": error,
    }

# ─── Score a test case result ─────────────────────────────────────────────────

def score_result(case: dict, turns: list, expert_response: str) -> dict:
    expected = case["expected"]
    scores = {}

    # 1. Crime type detected correctly
    detected_crime = None
    for turn in turns:
        if turn.get("crime_detected"):
            detected_crime = turn["crime_detected"]
            break
    scores["crime_detected_correctly"] = detected_crime == expected["crime_type"]
    scores["detected_crime"] = detected_crime

    # 2. Routed to expert
    routed_to_expert = any(
        turn.get("agent_used") == "expert" for turn in turns
    )
    scores["routed_to_expert"] = routed_to_expert

    # 3. Max intake turns respected
    intake_turns = sum(1 for t in turns if t.get("agent_used") == "intake")
    scores["intake_turns"] = intake_turns
    scores["intake_turns_ok"] = intake_turns <= expected.get("max_intake_turns", 5)

    # 4. Score reached threshold before expert
    max_score = max((t.get("score_at_turn", 0) for t in turns), default=0)
    scores["max_readiness_score"] = max_score
    scores["score_threshold_reached"] = max_score >= expected.get("min_score_at_expert", 60)

    # 5. Expected sections in expert response
    exp_sections = expected.get("expected_sections", [])
    found_sections = []
    for sec in exp_sections:
        # Flexible matching — check variations
        variations = [sec]
        if sec == "DV Act":
            variations = ["DV Act", "Domestic Violence Act", "Protection of Women from Domestic Violence", "DV Act 2005"]
        elif sec == "Vineeta Sharma":
            variations = ["Vineeta Sharma", "Vineeta", "2020 SC", "Supreme Court 2020"]
        elif sec == "Section 17":
            variations = ["Section 17", "धारा 17", "धारा १७"]
        elif sec == "Section 18":
            variations = ["Section 18", "धारा 18", "धारा १८"]
        elif sec == "Section 6":
            variations = ["Section 6", "धारा 6", "धारा ६"]
        elif sec == "CrPC Section 125":
            variations = ["Section 125", "CrPC 125", "CrPC Section 125", "धारा 125"]

        if any(v.lower() in expert_response.lower() for v in variations):
            found_sections.append(sec)

    scores["section_accuracy"] = round(len(found_sections) / len(exp_sections), 2) if exp_sections else 1.0
    scores["sections_found"] = found_sections
    scores["sections_missing"] = [s for s in exp_sections if s not in found_sections]

    # 6. Expected helplines present
    exp_helplines = expected.get("expected_helplines", [])
    found_helplines = [h for h in exp_helplines if h in expert_response]
    scores["helpline_accuracy"] = round(len(found_helplines) / len(exp_helplines), 2) if exp_helplines else 1.0

    # 7. 5-block structure — accept both English and Hindi block headers
    block_patterns = [
        ["━━━ BLOCK 1: EMPATHY", "━━━ ब्लॉक १", "ब्लॉक १", "BLOCK 1"],
        ["━━━ BLOCK 2: HER RIGHTS", "━━━ ब्लॉक २", "ब्लॉक २", "BLOCK 2"],
        ["━━━ BLOCK 3: ACTION TIMELINE", "━━━ ब्लॉक ३", "ब्लॉक ३", "BLOCK 3"],
        ["━━━ BLOCK 4: FREE HELPLINE", "━━━ ब्लॉक ४", "ब्लॉक ४", "BLOCK 4"],
        ["━━━ BLOCK 5: FOLLOW-UP QUESTION", "━━━ ब्लॉक ५", "ब्लॉक ५", "BLOCK 5"],
    ]
    found_blocks = sum(
        1 for variants in block_patterns
        if any(v in expert_response for v in variants)
    )
    scores["structure_score"] = round(found_blocks / 5, 2)
    scores["blocks_found"] = found_blocks

    # 8. Hindi purity — exclude intentional English (citations, block headers, numbers)
    if expected.get("response_language") == "hi":
        import re
        # Remove intentional English before measuring purity:
        # [Source: ...] citations, ━━━ BLOCK headers, helpline numbers, phone emoji lines
        cleaned = re.sub(r'\[Source:[^\]]+\]', '', expert_response)
        cleaned = re.sub(r'━+[^━\n]*━+', '', cleaned)
        cleaned = re.sub(r'📞[^\n]+', '', cleaned)
        cleaned = re.sub(r'\b\d{3,}\b', '', cleaned)  # phone numbers
        deva = len(re.findall(r'[\u0900-\u097F]', cleaned))
        roman = len(re.findall(r'[a-zA-Z]', cleaned))
        total = deva + roman
        scores["hindi_purity"] = round(deva / total, 2) if total > 0 else 1.0
    else:
        scores["hindi_purity"] = 1.0

    # 9. Timeline present
    timeline_markers = ["अभी", "आज", "इस हफ्ते", "Right Now", "Today", "This Week"]
    scores["timeline_present"] = any(m in expert_response for m in timeline_markers)

    # Final score
    components = [
        scores["crime_detected_correctly"] * 0.15,
        scores["routed_to_expert"] * 0.15,
        scores["section_accuracy"] * 0.25,
        scores["helpline_accuracy"] * 0.10,
        scores["structure_score"] * 0.20,
        scores["hindi_purity"] * 0.10,
        scores["timeline_present"] * 0.05,
    ]
    scores["final_score"] = round(sum(components), 3)
    scores["passed"] = scores["final_score"] >= 0.65 and scores["routed_to_expert"]

    return scores

# ─── Run one test case ────────────────────────────────────────────────────────

async def run_test_case(case: dict) -> dict:
    print(f"\n{'='*60}")
    print(f"TEST: {case['name']}")
    print(f"{'='*60}")

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"{API}/api/session/new",
            json={"tab_type": "legal"}
        )
        session_id = r.json()["session_id"]
    print(f"Session: {session_id[:8]}...")

    turns = []
    expert_response = ""
    expert_response_raw = ""

    async with httpx.AsyncClient() as client:
        for i, message in enumerate(case["conversation"]):
            print(f"\n  Turn {i+1}: '{message[:60]}{'...' if len(message)>60 else ''}'")

            turn_result = await send_message(
                client, session_id, message, case["language"]
            )
            turns.append(turn_result)

            agent = turn_result["agent_used"]
            score = turn_result["score_at_turn"]
            crime = turn_result["crime_detected"] or "?"
            preview = turn_result["response_preview"][:80]

            print(f"    Agent: {agent} | Score: {score} | Crime: {crime}")
            print(f"    Response: {preview}")

            if turn_result.get("error"):
                print(f"    ERROR: {turn_result['error']}")

            if agent == "expert":
                expert_response = turn_result["full_response"]  # cleaned (for display)

                # Fetch raw response from DB for accurate scoring
                try:
                    async with httpx.AsyncClient(timeout=5) as db_client:
                        r = await db_client.get(f"{API}/api/session/{session_id}")
                        sess = r.json()
                        messages = sess.get("messages", [])
                        # Last assistant message = raw expert response
                        raw_msgs = [m for m in messages if m.get("role") == "assistant" and m.get("agent_used") == "expert"]
                        if raw_msgs:
                            expert_response_raw = raw_msgs[-1].get("content", expert_response)
                        else:
                            expert_response_raw = expert_response
                except Exception:
                    expert_response_raw = expert_response

                print(f"    → Expert responded ({len(expert_response.split())} words)")
                break

            if turn_result.get("phase_changes"):
                print(f"    → Phase change: intake → expert")

    # Score against raw response (has block headers for structure check)
    score_target = expert_response_raw if expert_response_raw else expert_response
    scores = score_result(case, turns, score_target)

    status = "✓ PASS" if scores["passed"] else "✗ FAIL"
    print(f"\n  RESULT: {status}")
    print(f"  Final score: {scores['final_score']:.2f}")
    print(f"  Crime detected: {'✓' if scores['crime_detected_correctly'] else '✗'} ({scores['detected_crime']})")
    print(f"  Routed to expert: {'✓' if scores['routed_to_expert'] else '✗'} (after {scores['intake_turns']} intake turns)")
    print(f"  Structure: {scores['blocks_found']}/5 blocks")
    print(f"  Section accuracy: {scores['section_accuracy']:.0%}")
    print(f"  Hindi purity: {scores['hindi_purity']:.0%}")
    if scores.get("sections_missing"):
        print(f"  Missing sections: {scores['sections_missing']}")

    return {
        "test_id": case["id"],
        "name": case["name"],
        "session_id": session_id,
        "language": case["language"],
        "conversation_turns": turns,
        "expert_response": expert_response,
        "expert_response_preview": expert_response[:500],
        "scores": scores,
        "passed": scores["passed"],
    }

# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    print("\nStriSakhi — Kanoon Sakhi Integration Tests")
    print(f"API: {API}")
    print(f"Cases: {len(TEST_CASES)}")

    # Health check
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{API}/api/legal/test")
            print(f"Backend: {r.json()['status']}")
    except Exception as e:
        print(f"Backend not reachable: {e}")
        sys.exit(1)

    results = []
    for case in TEST_CASES:
        result = await run_test_case(case)
        results.append(result)

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r["passed"])

    print(f"\n{'='*60}")
    print(f"SUMMARY: {passed}/{total} passed")
    print(f"{'='*60}")

    avg_scores = {}
    score_keys = ["final_score", "section_accuracy", "structure_score", "hindi_purity"]
    for k in score_keys:
        vals = [r["scores"].get(k, 0) for r in results]
        avg_scores[k] = round(sum(vals) / len(vals), 3)
        bar = "█" * int(avg_scores[k] * 20)
        print(f"  {k:<25} {avg_scores[k]:.2f} {bar}")

    # Save results
    summary = {
        "timestamp": datetime.now().isoformat(),
        "api": API,
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 2),
        "avg_scores": avg_scores,
        "results": results,
    }

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_file = RESULTS_DIR / f"kanoon_test_{ts}.json"
    latest_file = RESULTS_DIR / "kanoon_test_latest.json"

    for f in [out_file, latest_file]:
        with open(f, "w", encoding="utf-8") as fp:
            json.dump(summary, fp, ensure_ascii=False, indent=2)

    print(f"\nSaved: {out_file}")
    return summary


if __name__ == "__main__":
    asyncio.run(main())
