#!/usr/bin/env python3
"""
StriSakhi — Kanoon Sakhi Reproducibility Test
3 Demo Use Cases — Complete Question Scripts

Run: python3 tests/test_kanoon.py
Output: tests/results/kanoon_test_TIMESTAMP.json

REPRODUCIBILITY GUIDE — What to type in UI for each demo:
  Demo 1 (Domestic Violence): See TEST_CASES[0]["conversation"]
  Demo 2 (Property Rights):   See TEST_CASES[1]["conversation"]
  Demo 3 (Maintenance):       See TEST_CASES[2]["conversation"]
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

# ─── 3 Demo Use Cases with full reproducibility guide ────────────────────────
TEST_CASES = [
    {
        "id": "demo_01_domestic_violence",
        "name": "Demo 1: Domestic Violence",
        "language": "hi",
        "description": "Husband beats wife for 3 years, joint family, financially dependent, police ignored earlier complaint",
        "what_to_expect": {
            "intake_turns": "2-4 turns",
            "crime_detected": "domestic_violence",
            "rag_moment": "Section 17 — cannot be evicted regardless of house ownership",
            "key_laws": ["DV Act 2005 Section 17", "Section 18", "Section 19", "Section 20"],
            "helpline": "181",
            "misconception_corrected": "Even if house is in husband/in-laws name, woman CANNOT be evicted",
        },
        "conversation": [
            "mere pati mujhe bahut marte hain",
            "3 saal se ho raha hai, belt se maarte hain, main unke ghar mein rehti hoon, 2 bacche bhi hain",
            "haan main puri tarah unpe dependent hoon, sasural waale bhi shamil hain",
            "pehle ek baar NCR daali thi par police ne kuch nahi kiya",
            "ghar mein rehne dena chahti hoon, nikaalna chahte hain mujhe",
        ],
        "expected": {
            "crime_type": "domestic_violence",
            "routes_to_expert": True,
            "min_turns_intake": 1,   # at least 1 intake turn
            "max_turns_intake": 5,
            "expected_sections": ["Section 17", "Section 18", "DV Act"],
            "expected_helplines": ["181"],
            "response_language": "hi",
        }
    },
    {
        "id": "demo_02_property_rights",
        "name": "Demo 2: Property Rights (RAG Power — Vineeta Sharma 2020)",
        "language": "hi",
        "description": "Daughter denied ancestral property share by brother — corrected by Vineeta Sharma SC 2020",
        "what_to_expect": {
            "intake_turns": "2-4 turns",
            "crime_detected": "property",
            "rag_moment": "Vineeta Sharma v Rakesh Sharma — SC 2020 — daughters have rights even if father died before 2005",
            "key_laws": ["Hindu Succession Act Section 6", "Vineeta Sharma 2020 SC"],
            "helpline": "15100",
            "misconception_corrected": "Brother saying 'tumhara hissa nahi' is LEGALLY WRONG",
        },
        "conversation": [
            "mere bhai keh rahe hain ki mujhe papa ki zameen mein koi hissa nahi milega",
            "hamare papa 2 saal pehle guzar gaye, zameen unke naam thi, hum sab Hindu hain",
            "bhai ne zameen apne naam karaani shuru kar di hai, koi will nahi thi",
            "zameen agricultural hai, Rajasthan mein hai",
            "documents mere paas nahi hain, kya main kuch kar sakti hoon",
        ],
        "expected": {
            "crime_type": "property",
            "routes_to_expert": True,
            "min_turns_intake": 1,
            "max_turns_intake": 5,
            "expected_sections": ["Section 6", "Hindu Succession Act", "Vineeta Sharma"],
            "expected_helplines": ["15100"],
            "response_language": "hi",
        }
    },
    {
        "id": "demo_03_maintenance",
        "name": "Demo 3: Maintenance Without Divorce (Misconception Corrected)",
        "language": "hi",
        "description": "Separated woman thinks she needs divorce to get maintenance — CrPC 125 corrects this",
        "what_to_expect": {
            "intake_turns": "2-4 turns",
            "crime_detected": "maintenance",
            "rag_moment": "CrPC Section 125 — maintenance WITHOUT divorce, interim in 60 days, no court fee",
            "key_laws": ["CrPC Section 125"],
            "helpline": "15100",
            "misconception_corrected": "Divorce NOT required. Interim maintenance within 60 days. Filing is FREE.",
        },
        "conversation": [
            "kya main bina divorce ke pati se paise maang sakti hoon",
            "main 8 mahine se alag hoon, pati ne chhod diya, wo dono bacchon ke saath hain",
            "pati government job karta hai, main khud kuch nahi kamati",
            "pati kuch bhi nahi de raha, pehle thoda deta tha",
            "usne hi chhoda mujhe, maine nahi chhoda, main chahti hoon bacche wapas milein aur guzara bhi",
        ],
        "expected": {
            "crime_type": "maintenance",
            "routes_to_expert": True,
            "min_turns_intake": 1,
            "max_turns_intake": 5,
            "expected_sections": ["CrPC Section 125", "Section 125"],
            "expected_helplines": ["15100"],
            "response_language": "hi",
        }
    },
]

# ─── SSE Parser ───────────────────────────────────────────────────────────────

async def send_message(
    client: httpx.AsyncClient,
    session_id: str,
    message: str,
    language: str,
) -> dict:
    full_response = ""
    tokens = []
    metadata_updates = []
    citations = []
    routing_events = []
    phase_changes = []
    follow_ups = []
    agent_used = "intake"
    error = None

    try:
        async with client.stream(
            "POST",
            f"{API}/api/legal/chat",
            json={
                "session_id": session_id,
                "message": message,
                "language": language,
            },
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
                    elif t == "error":
                        error = ev.get("message", "unknown")
                except Exception:
                    pass
    except Exception as e:
        error = str(e)

    return {
        "message_sent": message,
        "agent_used": agent_used,
        "full_response": full_response,
        "response_preview": full_response[:200],
        "citations": citations,
        "follow_up_questions": follow_ups,
        "metadata_updates": metadata_updates,
        "routing_events": routing_events,
        "phase_changes": phase_changes,
        "score_at_turn": (
            metadata_updates[-1].get("confidence_score", 0)
            if metadata_updates else 0
        ),
        "crime_detected": (
            metadata_updates[0].get("crime_type")
            if metadata_updates else None
        ),
        "error": error,
    }


# ─── Scorer ───────────────────────────────────────────────────────────────────

def score_result(case: dict, turns: list, expert_response: str) -> dict:
    expected = case["expected"]
    scores = {}

    # Crime detected
    detected = next(
        (t.get("crime_detected") for t in turns if t.get("crime_detected")),
        None
    )
    scores["crime_detected_correctly"] = detected == expected["crime_type"]
    scores["detected_crime"] = detected

    # Routed to expert
    scores["routed_to_expert"] = any(
        t.get("agent_used") == "expert" for t in turns
    )

    # Intake turns
    intake_turns = sum(1 for t in turns if t.get("agent_used") == "intake")
    scores["intake_turns"] = intake_turns
    scores["min_intake_turns_ok"] = intake_turns >= expected.get("min_turns_intake", 1)
    scores["max_intake_turns_ok"] = intake_turns <= expected.get("max_turns_intake", 6)

    # Max readiness score
    scores["max_readiness_score"] = max(
        (t.get("score_at_turn", 0) for t in turns), default=0
    )

    # Section accuracy — flexible matching
    SECTION_VARIANTS = {
        "DV Act": ["DV Act", "Domestic Violence Act", "Protection of Women from Domestic Violence", "घरेलू हिंसा"],
        "Section 17": ["Section 17", "धारा 17", "धारा १७", "17"],
        "Section 18": ["Section 18", "धारा 18", "धारा १८"],
        "Section 19": ["Section 19", "धारा 19"],
        "Section 20": ["Section 20", "धारा 20"],
        "Section 6": ["Section 6", "धारा 6", "धारा ६"],
        "Hindu Succession Act": ["Hindu Succession Act", "हिंदू उत्तराधिकार", "Hindu Succession"],
        "Vineeta Sharma": ["Vineeta Sharma", "Vineeta", "2020 SC", "Supreme Court 2020", "विनीता शर्मा"],
        "CrPC Section 125": ["Section 125", "CrPC 125", "CrPC Section 125", "धारा 125", "125"],
        "Section 125": ["Section 125", "125 CrPC", "धारा 125"],
    }

    exp_sections = expected.get("expected_sections", [])
    found_sections = []
    for sec in exp_sections:
        variants = SECTION_VARIANTS.get(sec, [sec])
        if any(v.lower() in expert_response.lower() for v in variants):
            found_sections.append(sec)

    scores["section_accuracy"] = (
        round(len(found_sections) / len(exp_sections), 2) if exp_sections else 1.0
    )
    scores["sections_found"] = found_sections
    scores["sections_missing"] = [s for s in exp_sections if s not in found_sections]

    # Helplines
    exp_helplines = expected.get("expected_helplines", [])
    found_helplines = [h for h in exp_helplines if h in expert_response]
    scores["helpline_accuracy"] = (
        round(len(found_helplines) / len(exp_helplines), 2) if exp_helplines else 1.0
    )

    # 5-block structure (accepts English and Hindi headers)
    block_patterns = [
        ["━━━ BLOCK 1: EMPATHY", "━━━ ब्लॉक १", "BLOCK 1"],
        ["━━━ BLOCK 2: HER RIGHTS", "━━━ ब्लॉक २", "BLOCK 2"],
        ["━━━ BLOCK 3: ACTION TIMELINE", "━━━ ब्लॉक ३", "BLOCK 3"],
        ["━━━ BLOCK 4: FREE HELPLINE", "━━━ ब्लॉक ४", "BLOCK 4"],
        ["━━━ BLOCK 5: FOLLOW-UP QUESTION", "━━━ ब्लॉक ५", "BLOCK 5"],
    ]
    found_blocks = sum(
        1 for variants in block_patterns
        if any(v in expert_response for v in variants)
    )
    scores["structure_score"] = round(found_blocks / 5, 2)
    scores["blocks_found"] = found_blocks

    # Hindi purity (excluding intentional English)
    if expected.get("response_language") == "hi":
        cleaned = re.sub(r'\[Source:[^\]]+\]', '', expert_response)
        cleaned = re.sub(r'━+[^━\n]*━+', '', cleaned)
        cleaned = re.sub(r'📞[^\n]+', '', cleaned)
        cleaned = re.sub(r'\b\d{3,}\b', '', cleaned)
        deva = len(re.findall(r'[\u0900-\u097F]', cleaned))
        roman = len(re.findall(r'[a-zA-Z]', cleaned))
        total = deva + roman
        scores["hindi_purity"] = round(deva / total, 2) if total > 0 else 1.0
    else:
        scores["hindi_purity"] = 1.0

    # Timeline present
    timeline_markers = ["अभी", "आज", "इस हफ्ते", "Right Now", "Today", "This Week"]
    scores["timeline_present"] = any(m in expert_response for m in timeline_markers)

    # Final score
    components = [
        scores["crime_detected_correctly"] * 0.10,
        scores["routed_to_expert"] * 0.10,
        scores["min_intake_turns_ok"] * 0.10,
        scores["section_accuracy"] * 0.30,
        scores["helpline_accuracy"] * 0.10,
        scores["structure_score"] * 0.20,
        scores["hindi_purity"] * 0.10,
    ]
    scores["final_score"] = round(sum(components), 3)
    scores["passed"] = (
        scores["final_score"] >= 0.70
        and scores["routed_to_expert"]
        and scores["min_intake_turns_ok"]
    )

    return scores


# ─── Run one test case ────────────────────────────────────────────────────────

async def run_test_case(case: dict) -> dict:
    print(f"\n{'='*60}")
    print(f"TEST: {case['name']}")
    print(f"Expected: {case['what_to_expect']['rag_moment']}")
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
            print(f"\n  Turn {i+1}: '{message[:65]}{'...' if len(message)>65 else ''}'")

            turn_result = await send_message(
                client, session_id, message, case["language"]
            )
            turns.append(turn_result)

            agent = turn_result["agent_used"]
            score = turn_result["score_at_turn"]
            crime = turn_result["crime_detected"] or "?"
            preview = turn_result["response_preview"][:90]

            print(f"    Agent: {agent} | Score: {score}/100 | Crime: {crime}")
            print(f"    → {preview}")

            if turn_result.get("error"):
                print(f"    ERROR: {turn_result['error']}")

            if agent == "expert":
                expert_response = turn_result["full_response"]

                # Fetch raw from DB for scoring
                try:
                    async with httpx.AsyncClient(timeout=5) as db_client:
                        r = await db_client.get(f"{API}/api/session/{session_id}")
                        msgs = r.json().get("messages", [])
                        raw_msgs = [
                            m for m in msgs
                            if m.get("role") == "assistant"
                            and m.get("agent_used") == "expert"
                        ]
                        expert_response_raw = (
                            raw_msgs[-1]["content"] if raw_msgs else expert_response
                        )
                except Exception:
                    expert_response_raw = expert_response

                print(f"    ✅ Expert responded ({len(expert_response.split())} words)")
                if turn_result.get("follow_up_questions"):
                    print(f"    Follow-ups: {turn_result['follow_up_questions'][:2]}")
                break

    # Score
    scores = score_result(case, turns, expert_response_raw)

    status = "✓ PASS" if scores["passed"] else "✗ FAIL"
    print(f"\n  RESULT: {status} | Score: {scores['final_score']:.2f}")
    print(f"  Crime: {'✓' if scores['crime_detected_correctly'] else '✗'} ({scores['detected_crime']})")
    print(f"  Intake turns: {scores['intake_turns']} ({'✓ ok' if scores['min_intake_turns_ok'] else '✗ too few'})")
    print(f"  Structure: {scores['blocks_found']}/5 blocks")
    print(f"  Sections: {scores['section_accuracy']:.0%} | Missing: {scores['sections_missing']}")
    print(f"  Hindi purity: {scores['hindi_purity']:.0%}")
    print(f"  Timeline: {'✓' if scores['timeline_present'] else '✗'}")

    return {
        "test_id": case["id"],
        "name": case["name"],
        "what_to_expect": case["what_to_expect"],
        "session_id": session_id,
        "language": case["language"],
        "conversation_turns": turns,
        "expert_response_clean": expert_response,
        "expert_response_raw": expert_response_raw,
        "expert_response_preview": expert_response_raw[:600],
        "scores": scores,
        "passed": scores["passed"],
    }


# ─── Reproducibility Guide ────────────────────────────────────────────────────

def print_reproducibility_guide():
    print("\n" + "="*60)
    print("REPRODUCIBILITY GUIDE — What to type in UI")
    print("="*60)
    for i, case in enumerate(TEST_CASES):
        print(f"\nDemo {i+1}: {case['name']}")
        print(f"Language: Select हिंदी in UI")
        print(f"Expect: {case['what_to_expect']['rag_moment']}")
        print("Messages to send:")
        for j, msg in enumerate(case["conversation"]):
            print(f"  Turn {j+1}: {msg}")
        print(f"Expected expert keywords: {case['what_to_expect']['key_laws']}")
        print(f"Expected helpline: {case['what_to_expect']['helpline']}")
        print(f"Misconception corrected: {case['what_to_expect']['misconception_corrected']}")


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    print("\nStriSakhi — Kanoon Sakhi Reproducibility Tests")
    print(f"API: {API}")

    # Health check
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{API}/api/legal/test")
            print(f"Backend: {r.json().get('status', 'ok')}")
    except Exception as e:
        print(f"Backend not reachable: {e}")
        sys.exit(1)

    # Print guide first
    print_reproducibility_guide()

    print("\n\nRunning automated tests...\n")

    results = []
    for case in TEST_CASES:
        result = await run_test_case(case)
        results.append(result)

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r["passed"])

    print(f"\n{'='*60}")
    print(f"RESULTS: {passed}/{total} passed")
    print(f"{'='*60}")

    score_keys = [
        "final_score", "section_accuracy",
        "structure_score", "hindi_purity"
    ]
    for k in score_keys:
        vals = [r["scores"].get(k, 0) for r in results]
        avg = round(sum(vals) / len(vals), 3)
        bar = "█" * int(avg * 20)
        print(f"  {k:<25} {avg:.2f} {bar}")

    summary = {
        "timestamp": datetime.now().isoformat(),
        "api": API,
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 2),
        "scores": {
            k: round(sum(r["scores"].get(k, 0) for r in results) / total, 3)
            for k in score_keys
        },
        "results": results,
    }

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out = RESULTS_DIR / f"kanoon_test_{ts}.json"
    latest = RESULTS_DIR / "kanoon_test_latest.json"

    for f in [out, latest]:
        with open(f, "w", encoding="utf-8") as fp:
            json.dump(summary, fp, ensure_ascii=False, indent=2)

    print(f"\nSaved: {out.name}")
    return summary


if __name__ == "__main__":
    asyncio.run(main())
