"""
StriSakhi — RAGAS Evaluation Framework (Multi-turn)
Run on Mac (NOT in Docker)

Setup:
  pip install ragas httpx

Usage:
  python backend/tests/evaluate.py --dataset backend/tests/datasets/test_cases_manual.json
  python backend/tests/evaluate.py --compare results/eval_BASE.json results/eval_FINETUNED.json
"""

import asyncio
import json
import re
import argparse
import httpx
from datetime import datetime
from pathlib import Path

# ─── PATHS ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

LLAMA_URL = "http://localhost:8080/v1/chat/completions"
API_URL = "http://localhost:8000"


# ─── SCORING ──────────────────────────────────────────────────────────────────
def score_hindi_purity(text: str) -> float:
    deva = len(re.findall(r'[\u0900-\u097F]', text))
    roman = len(re.findall(r'[a-zA-Z]', text))
    total = deva + roman
    if total == 0:
        return 1.0
    return round(deva / total, 2)


def score_section_accuracy(response: str, expected_sections: list) -> float:
    if not expected_sections:
        return 1.0
    found = sum(1 for s in expected_sections if s.lower() in response.lower())
    return round(found / len(expected_sections), 2)


def score_helpline_presence(response: str, expected_helplines: list) -> float:
    if not expected_helplines:
        return 1.0
    found = sum(1 for h in expected_helplines if h in response)
    return round(found / len(expected_helplines), 2)


def score_structure(response: str) -> dict:
    has_empathy = any(w in response.lower() for w in [
        "samajh", "dukh", "akeli nahi", "sorry", "i understand",
        "koshto", "takleef", "understand your", "so sorry",
        "sunke", "shukriya", "himmat"
    ])
    has_citation = (
        "[source:" in response.lower() or
        "section" in response.lower() or
        "act 2005" in response.lower() or
        "act 2013" in response.lower() or
        "act 1955" in response.lower()
    )
    has_timeline = any(w in response for w in [
        "अभी", "आज", "हफ्ते", "Right Now", "Today", "This Week",
        "আজ", "এখনই", "abhi", "aaj"
    ])
    has_helpline_number = bool(re.search(
        r'\b(181|100|108|15100|1091|1930|1098|102|104)\b', response
    ))
    has_followup = response.strip().endswith("?")

    score = sum([
        has_empathy, has_citation, has_timeline,
        has_helpline_number, has_followup
    ]) / 5

    return {
        "empathy": has_empathy,
        "citation": has_citation,
        "timeline": has_timeline,
        "helpline_number": has_helpline_number,
        "followup_question": has_followup,
        "score": round(score, 2),
    }


def score_word_count(response: str, max_words: int = 350) -> float:
    words = len(response.split())
    if words <= max_words:
        return 1.0
    return max(0, round(1 - (words - max_words) / max_words, 2))


def score_no_hallucination(response: str) -> float:
    fake_patterns = [r'Section [89]\d\d', r'Section 77', r'Section 99']
    for p in fake_patterns:
        if re.search(p, response):
            return 0.0
    return 1.0


async def score_with_ragas(response: str, ground_truth: str, case: dict) -> dict:
    """Use Gemma 4 as judge for RAGAS-style metrics."""

    async def judge(prompt: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(LLAMA_URL, json={
                    "model": "gemma4",
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "temperature": 0.0,
                    "max_tokens": 80,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "score": {"type": "number"},
                                    "reason": {"type": "string"}
                                },
                                "required": ["score", "reason"]
                            }
                        }
                    }
                })
            text = r.json()["choices"][0]["message"]["content"]
            return json.loads(text)
        except Exception as e:
            return {"score": 0.5, "reason": f"judge failed: {e}"}

    user_msg = case["conversation"][-1]["content"]

    faithfulness = await judge(
        f"Does this legal advice response avoid hallucinating or inventing facts not grounded in Indian law?\n"
        f"Response: {response[:400]}\n"
        f"Score 0-1. JSON only: {{\"score\": 0.0, \"reason\": \"...\"}}"
    )
    relevancy = await judge(
        f"Is this legal advice response relevant to the user's question?\n"
        f"User question: {user_msg}\n"
        f"Response: {response[:400]}\n"
        f"Score 0-1. JSON only: {{\"score\": 0.0, \"reason\": \"...\"}}"
    )
    correctness = await judge(
        f"Does this legal advice response cover these key points?\n"
        f"Key points: {ground_truth}\n"
        f"Response: {response[:400]}\n"
        f"Score 0-1. JSON only: {{\"score\": 0.0, \"reason\": \"...\"}}"
    )

    return {
        "faithfulness": faithfulness["score"],
        "answer_relevancy": relevancy["score"],
        "answer_correctness": correctness["score"],
    }


# ─── MULTI-TURN CONVERSATION DRIVER ───────────────────────────────────────────
async def drive_conversation(case: dict) -> dict:
    """
    Send conversation turns one by one.
    Wait for expert response OR emergency.
    Returns: {expert_response, agent_used, emergency_triggered, response_time_ms}
    """
    import time

    # Create session
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{API_URL}/api/session/new",
            json={"tab_type": "legal"}
        )
        session_id = r.json()["session_id"]

    language = case.get("language", "hi")
    turns = case["conversation"]
    expected_emergency = case.get("expected_emergency", False)

    expert_response = ""
    emergency_triggered = False
    agent_used = "intake"
    total_start = time.time()

    for i, turn in enumerate(turns):
        message = turn["content"]
        print(f"    Turn {i+1}: '{message[:50]}...' " if len(message) > 50 else f"    Turn {i+1}: '{message}'")

        turn_response = ""
        turn_agent = "intake"
        got_expert = False

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST",
                    f"{API_URL}/api/legal/chat",
                    json={
                        "session_id": session_id,
                        "message": message,
                        "language": language,
                    }
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            ev = json.loads(data_str)

                            if ev["type"] == "token":
                                turn_response += ev.get("token", "")

                            elif ev["type"] == "done":
                                turn_response = ev.get("full_response") or turn_response
                                turn_agent = ev.get("agent", "intake")

                            elif ev["type"] == "emergency":
                                emergency_triggered = True
                                print(f"    → EMERGENCY detected on turn {i+1}")

                            elif ev["type"] == "phase_change":
                                print(f"    → Phase change: intake → expert")

                            elif ev["type"] == "routing":
                                decision = ev.get("decision", "")
                                print(f"    → Routing: {decision}")
                                if decision == "expert":
                                    got_expert = True

                        except Exception:
                            pass

        except Exception as e:
            print(f"    → Error on turn {i+1}: {e}")
            continue

        # If this turn got an expert response — capture it and stop
        if turn_agent == "expert" or got_expert:
            expert_response = turn_response
            agent_used = "expert"
            print(f"    → Expert responded ({len(expert_response.split())} words)")
            break

        # If emergency triggered — capture response and stop
        if emergency_triggered:
            expert_response = turn_response
            agent_used = "emergency"
            break

        # If last turn and still in intake — use whatever we got
        if i == len(turns) - 1:
            expert_response = turn_response
            agent_used = turn_agent
            print(f"    → Used last turn response (agent: {agent_used})")

    total_ms = int((time.time() - total_start) * 1000)

    return {
        "expert_response": expert_response,
        "agent_used": agent_used,
        "emergency_triggered": emergency_triggered,
        "response_time_ms": total_ms,
        "session_id": session_id,
    }


# ─── EVALUATE SINGLE CASE ─────────────────────────────────────────────────────
async def evaluate_case(case: dict) -> dict:
    """Run one test case and score the result."""

    case_id = case["id"]
    category = case["category"]
    language = case["language"]
    expected_emergency = case.get("expected_emergency", False)
    should_trigger_expert = case.get("should_trigger_expert", True)

    print(f"\n  [{case_id}] {category}/{language}")

    # Drive conversation
    result = await drive_conversation(case)

    expert_response = result["expert_response"]
    agent_used = result["agent_used"]
    emergency_triggered = result["emergency_triggered"]
    response_time_ms = result["response_time_ms"]

    # Emergency cases — score differently
    if expected_emergency:
        emergency_correct = emergency_triggered
        helpline_score = score_helpline_presence(
            expert_response,
            case.get("expected_helplines", ["181"])
        )
        scores = {
            "emergency_detected": 1.0 if emergency_correct else 0.0,
            "helpline_presence": helpline_score,
            "faithfulness": 1.0,
            "answer_relevancy": 1.0 if emergency_triggered else 0.0,
            "answer_correctness": 1.0 if emergency_triggered else 0.0,
            "hindi_purity": score_hindi_purity(expert_response) if language == "hi" else 1.0,
            "section_accuracy": 1.0,
            "structure_score": helpline_score,
            "word_count_score": 1.0,
            "no_hallucination": 1.0,
            "response_time_ms": response_time_ms,
        }
        scores["final_score"] = round(
            scores["emergency_detected"] * 0.5 +
            scores["helpline_presence"] * 0.3 +
            scores["hindi_purity"] * 0.2,
            3
        )
        scores["passed"] = scores["emergency_detected"] == 1.0
        print(f"    → Emergency: {'✓ DETECTED' if emergency_triggered else '✗ MISSED'}")
        print(f"    → Score: {scores['final_score']:.0%}")
        return {
            "test_id": case_id,
            "category": category,
            "language": language,
            "agent_used": agent_used,
            "actual_response": expert_response[:300],
            "scores": scores,
            "passed": scores["passed"],
        }

    # Normal cases — need expert response
    if not expert_response or len(expert_response.strip()) < 20:
        print(f"    → Empty/short response — FAIL")
        return {
            "test_id": case_id,
            "category": category,
            "language": language,
            "agent_used": agent_used,
            "actual_response": expert_response,
            "scores": {"final_score": 0.0, "passed": False, "error": "no expert response"},
            "passed": False,
        }

    # Check agent routing
    expert_routed = agent_used in ("expert", "emergency")
    if should_trigger_expert and not expert_routed:
        print(f"    ⚠ Expected expert routing but got: {agent_used}")

    # Rule-based scores
    hindi_purity = score_hindi_purity(expert_response) if language == "hi" else 1.0
    section_acc = score_section_accuracy(
        expert_response,
        case.get("expected_sections", [])
    )
    helpline = score_helpline_presence(
        expert_response,
        case.get("expected_helplines", [])
    )
    structure = score_structure(expert_response)
    word_count = score_word_count(expert_response)
    no_halluc = score_no_hallucination(expert_response)

    # RAGAS scores (LLM judge)
    ragas = await score_with_ragas(
        expert_response,
        case.get("ground_truth", ""),
        case
    )

    # Weighted final score
    final_score = round(
        ragas["faithfulness"]       * 0.15 +
        ragas["answer_relevancy"]   * 0.15 +
        ragas["answer_correctness"] * 0.15 +
        hindi_purity                * 0.10 +
        section_acc                 * 0.15 +
        helpline                    * 0.10 +
        structure["score"]          * 0.10 +
        word_count                  * 0.05 +
        no_halluc                   * 0.05,
        3
    )
    passed = final_score >= 0.65

    scores = {
        **ragas,
        "hindi_purity": hindi_purity,
        "section_accuracy": section_acc,
        "helpline_presence": helpline,
        "structure_score": structure["score"],
        "structure_detail": structure,
        "word_count_score": word_count,
        "no_hallucination": no_halluc,
        "expert_routed": expert_routed,
        "final_score": final_score,
        "passed": passed,
        "response_time_ms": response_time_ms,
    }

    status = "✓" if passed else "✗"
    print(f"    → {status} {final_score:.0%} | sect:{section_acc:.0%} help:{helpline:.0%} "
          f"purity:{hindi_purity:.0%} struct:{structure['score']:.0%}")

    return {
        "test_id": case_id,
        "category": category,
        "language": language,
        "agent_used": agent_used,
        "actual_response": expert_response[:500],
        "scores": scores,
        "passed": passed,
    }


# ─── RUN FULL EVALUATION ──────────────────────────────────────────────────────
async def run_evaluation(cases: list, concurrency: int = 1) -> dict:
    """Run all cases sequentially to avoid llama.cpp timeout."""
    print(f"\nRunning {len(cases)} test cases (concurrency={concurrency})...")
    print("=" * 60)

    all_results = []
    sem = asyncio.Semaphore(concurrency)

    async def bounded(case):
        async with sem:
            try:
                return await evaluate_case(case)
            except Exception as e:
                case_id = case.get("id", "unknown")
                print(f"\n  [{case_id}] ERROR: {e} — skipping")
                return {
                    "test_id": case_id,
                    "category": case.get("category", "unknown"),
                    "language": case.get("language", "hi"),
                    "agent_used": "error",
                    "actual_response": "",
                    "scores": {"final_score": 0.0, "passed": False, "error": str(e)},
                    "passed": False,
                }

    all_results = await asyncio.gather(*[bounded(c) for c in cases])

    # Summary
    total = len(all_results)
    passed = sum(1 for r in all_results if r["passed"])

    # Per-category
    by_cat = {}
    for r in all_results:
        cat = r["category"]
        if cat not in by_cat:
            by_cat[cat] = {"total": 0, "passed": 0, "scores": []}
        by_cat[cat]["total"] += 1
        if r["passed"]:
            by_cat[cat]["passed"] += 1
        s = r["scores"].get("final_score", 0)
        if isinstance(s, (int, float)):
            by_cat[cat]["scores"].append(s)

    cat_summary = {
        cat: {
            "pass_rate": round(d["passed"] / d["total"], 2),
            "avg_score": round(sum(d["scores"]) / len(d["scores"]), 3) if d["scores"] else 0,
            "total": d["total"],
        }
        for cat, d in by_cat.items()
    }

    # Average scores
    score_keys = [
        "faithfulness", "answer_relevancy", "answer_correctness",
        "hindi_purity", "section_accuracy", "helpline_presence",
        "structure_score", "final_score"
    ]
    avg_scores = {}
    for key in score_keys:
        vals = [
            r["scores"].get(key, 0)
            for r in all_results
            if isinstance(r["scores"].get(key), (int, float))
        ]
        avg_scores[key] = round(sum(vals) / len(vals), 3) if vals else 0

    avg_ms = int(sum(
        r["scores"].get("response_time_ms", 0) for r in all_results
    ) / total)

    summary = {
        "timestamp": datetime.now().isoformat(),
        "model": "gemma4-e2b-base",
        "total_cases": total,
        "passed": passed,
        "pass_rate": round(passed / total, 2),
        "avg_response_time_ms": avg_ms,
        "avg_scores": avg_scores,
        "by_category": cat_summary,
        "detailed_results": all_results,
    }

    # Save
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    result_file = RESULTS_DIR / f"eval_{ts}.json"
    latest_file = RESULTS_DIR / "latest.json"
    for f in [result_file, latest_file]:
        with open(f, "w", encoding="utf-8") as fp:
            json.dump(summary, fp, ensure_ascii=False, indent=2)

    # Print
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed}/{total} passed ({passed/total:.0%})")
    print(f"Avg response time: {avg_ms}ms\n")
    print("Scores:")
    for k, v in avg_scores.items():
        bar = "█" * int(v * 20)
        print(f"  {k:<25} {v:.2f} {bar}")
    print("\nBy category:")
    for cat, s in cat_summary.items():
        print(f"  {cat:<25} {s['pass_rate']:.0%} pass | {s['avg_score']:.2f} avg | {s['total']} cases")
    print(f"\nSaved: {result_file}")
    print("Admin reads: results/latest.json")

    return summary


# ─── COMPARE TWO RUNS ─────────────────────────────────────────────────────────
def compare_runs(base_file: str, finetuned_file: str):
    with open(base_file) as f:
        base = json.load(f)
    with open(finetuned_file) as f:
        ft = json.load(f)

    metrics = [
        "pass_rate", "faithfulness", "answer_relevancy", "answer_correctness",
        "hindi_purity", "section_accuracy", "helpline_presence",
        "structure_score", "final_score"
    ]

    print("\n" + "=" * 70)
    print(f"{'METRIC':<28} {'BASE':>12} {'FINE-TUNED':>12} {'DELTA':>10}")
    print("=" * 70)

    comparison = {"timestamp": datetime.now().isoformat(), "metrics": {}}

    for m in metrics:
        b = base["avg_scores"].get(m) or base.get(m, 0)
        f = ft["avg_scores"].get(m) or ft.get(m, 0)
        delta = f - b
        sign = "+" if delta >= 0 else ""
        print(f"  {m:<26} {b:>12.3f} {f:>12.3f} {sign}{delta:>9.3f}")
        comparison["metrics"][m] = {"base": b, "finetuned": f, "delta": round(delta, 3)}

    print("=" * 70)

    comp_file = RESULTS_DIR / "comparison.json"
    with open(comp_file, "w") as f:
        json.dump(comparison, f, indent=2)
    print(f"\nComparison saved: {comp_file}")


# ─── MAIN ─────────────────────────────────────────────────────────────────────
async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=str,
                        default="backend/tests/datasets/test_cases_manual.json",
                        help="Path to test cases JSON")
    parser.add_argument("--compare", nargs=2, metavar=("BASE", "FINETUNED"))
    parser.add_argument("--concurrency", type=int, default=1,
                        help="Parallel cases (default 1 — llama.cpp is single-threaded)")
    args = parser.parse_args()

    if args.compare:
        compare_runs(args.compare[0], args.compare[1])
        return

    with open(args.dataset, encoding="utf-8") as f:
        cases = json.load(f)

    print(f"Loaded {len(cases)} test cases from {args.dataset}")
    await run_evaluation(cases, concurrency=args.concurrency)


if __name__ == "__main__":
    asyncio.run(main())