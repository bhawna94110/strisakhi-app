#!/usr/bin/env python3
"""
StriSakhi — Benchmark Evaluator v3.1
=====================================
Fixed citation regex — accepts both:
  [Source: DV Act 2005, Section 17]  ← old format
  [DV Act 2005, Section 17]          ← fine-tuned model format
  [CrPC Section 125]                 ← no-year format

Section accuracy now checks full response text, not just citation strings.

Run from backend/ directory:
    python benchmark_v2/evaluate_v3.py
    python benchmark_v2/evaluate_v3.py --compare results/eval_v3_BASE.json results/eval_v3_FT.json
"""
import asyncio
import json
import re
import argparse
import sys
import httpx
from datetime import datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.agents.legal_agent import _build_system as build_expert_system
from app.agents.intake_agent import build_intake_system

LLAMA_URL = "http://localhost:8080/v1/chat/completions"
MODEL_NAME = "gemma4"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


# ═══════════════════════════════════════════════════════════════
# EXPERT SCORER — v3.1 fixes
# ═══════════════════════════════════════════════════════════════
class ExpertScorer:
    def __init__(self, language: str):
        self.language = language

    def _extract_citations(self, response: str) -> list[str]:
        """
        Extract all citation strings — accepts multiple formats:
          [Source: DV Act 2005, Section 17]
          [DV Act 2005, Section 17]
          [POSH Act 2013, Section 4]
          [CrPC Section 125]
          [IPC 354D]
        """
        # Matches content inside [...] that looks like a legal reference
        pat = r'\[(?:Source:\s*)?([^\[\]]{5,80}?)\]'
        raw = re.findall(pat, response)
        # Filter: must contain at least one of these signals
        legal_signals = ["Act", "IPC", "CrPC", "Section", "Vineeta", "POSH", "DV", "IT Act"]
        return [c.strip() for c in raw if any(s in c for s in legal_signals)]

    def score(self, response: str, rules: dict) -> dict:
        scores = {}

        # ── 1. All 5 block headers ──────────────────────────────────────────
        blocks = [
            "━━━ BLOCK 1: EMPATHY",
            "━━━ BLOCK 2: HER RIGHTS",
            "━━━ BLOCK 3: ACTION TIMELINE",
            "━━━ BLOCK 4: FREE HELPLINE",
            "━━━ BLOCK 5: FOLLOW-UP QUESTION",
        ]
        scores["all_5_blocks"] = all(b in response for b in blocks)

        # ── 2. Citations present (flexible format) ──────────────────────────
        citations = self._extract_citations(response)
        min_citations = rules.get("min_citations", 2)
        scores["citation_format_exact"] = len(citations) >= min_citations
        scores["citation_count"] = len(citations)
        scores["citations_found"] = citations  # store for debugging

        # ── 3. Timeline ─────────────────────────────────────────────────────
        if self.language == "hi":
            timeline_checks = [
                r'\*\*अभी \(Right Now\):\*\*',
                r'\*\*आज \(Today\):\*\*',
                r'\*\*इस हफ्ते \(This Week\):\*\*',
            ]
        elif self.language == "bn":
            timeline_checks = [
                r'\*\*এখনই \(Right Now\):\*\*',
                r'\*\*আজ \(Today\):\*\*',
                r'\*\*এই সপ্তাহে \(This Week\):\*\*',
            ]
        else:
            timeline_checks = [
                r'\*\*Right Now:\*\*',
                r'\*\*Today:\*\*',
                r'\*\*This Week:\*\*',
            ]
        scores["timeline_all_3"] = all(re.search(p, response) for p in timeline_checks)

        # ── 4. Helpline ──────────────────────────────────────────────────────
        helpline_pat = r'📞\s*\*?\*?\s*\b(181|100|15100|1091|1930|1098|102|104|108|112|1800-419-8588)\b'
        scores["helpline_present"] = bool(re.search(helpline_pat, response))

        # ── 5. Ends with ? ───────────────────────────────────────────────────
        scores["ends_with_question"] = response.strip().endswith("?")

        # ── 6. Word count ────────────────────────────────────────────────────
        words = len(response.split())
        max_w = rules.get("max_words", 400)
        scores["word_count_ok"] = words <= max_w
        scores["word_count"] = words

        # ── 7. Hindi purity ──────────────────────────────────────────────────
        if self.language in ("hi", "bn"):
            deva = len(re.findall(r'[\u0900-\u097F]', response))
            roman = len(re.findall(r'[a-zA-Z]', response))
            total = deva + roman
            scores["hindi_purity"] = round(deva / total, 2) if total > 0 else 1.0
        else:
            scores["hindi_purity"] = 1.0

        # ── 8. No hallucinated sections ──────────────────────────────────────
        fake = [r'Section [89]\d\d', r'Section 77', r'Section 99', r'Section 000']
        scores["no_hallucination"] = not any(re.search(p, response) for p in fake)

        # ── 9. No bare lawyer advice without NALSA ───────────────────────────
        forbidden = ["consult a lawyer", "consult an advocate", "talk to a lawyer"]
        has_forbidden = any(f in response.lower() for f in forbidden)
        has_nalsa = "15100" in response
        scores["no_bare_lawyer_advice"] = not (has_forbidden and not has_nalsa)

        # ── composite structure score ────────────────────────────────────────
        struct_components = [
            scores["all_5_blocks"],
            scores["citation_format_exact"],
            scores["timeline_all_3"],
            scores["helpline_present"],
            scores["ends_with_question"],
        ]
        scores["structure_score"] = round(sum(struct_components) / len(struct_components), 2)

        # ── section accuracy — FIXED: search full response, not just citations
        expected = rules.get("expected_sections", [])
        if expected:
            found = 0
            for sec in expected:
                # Search anywhere in the response (handles both citation formats)
                if re.search(re.escape(sec), response, re.IGNORECASE):
                    found += 1
            scores["section_accuracy"] = round(found / len(expected), 2)
            scores["sections_found"] = [s for s in expected
                                        if re.search(re.escape(s), response, re.IGNORECASE)]
            scores["sections_missing"] = [s for s in expected
                                          if not re.search(re.escape(s), response, re.IGNORECASE)]
        else:
            scores["section_accuracy"] = 1.0 if scores["citation_format_exact"] else 0.5

        return scores


# ═══════════════════════════════════════════════════════════════
# INTAKE SCORER — fixed JSON extraction
# ═══════════════════════════════════════════════════════════════
class IntakeScorer:
    def score(self, response: str, rules: dict) -> dict:
        scores = {}
        raw = response.strip()

        # Robust JSON extraction — handles any wrapping
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            raw = match.group()

        try:
            data = json.loads(raw)
            scores["valid_json"] = True
        except Exception as e:
            scores["valid_json"] = False
            scores["json_error"] = str(e)
            scores["has_all_fields"] = False
            scores["no_extra_text"] = False
            scores["structure_score"] = 0.0
            return scores

        required = ["message", "extracted", "ready_for_expert", "frustrated", "readiness_score"]
        scores["has_all_fields"] = all(k in data for k in required)

        # no_extra_text: response starts with { or ` (no preamble)
        first_char = response.strip()[0]
        scores["no_extra_text"] = first_char in ("{", "`")

        msg = data.get("message", "")
        scores["one_question"] = msg.count("?") == 1

        # Extraction accuracy
        expected_extracted = rules.get("expected_extracted", {})
        extracted = data.get("extracted", {})
        if expected_extracted:
            matches = checks = 0
            for k, v in expected_extracted.items():
                if v is not None:
                    checks += 1
                    if extracted.get(k) == v:
                        matches += 1
            scores["extraction_accuracy"] = round(matches / checks, 2) if checks else 1.0
        else:
            scores["extraction_accuracy"] = 1.0

        expected_ready = rules.get("expected_ready_for_expert")
        if expected_ready is not None:
            scores["ready_correct"] = data.get("ready_for_expert") == expected_ready
        else:
            scores["ready_correct"] = True

        components = [
            scores["valid_json"],
            scores["has_all_fields"],
            scores["no_extra_text"],
            scores["one_question"],
        ]
        scores["structure_score"] = round(sum(components) / len(components), 2)
        return scores


# ═══════════════════════════════════════════════════════════════
# MODEL CALL
# ═══════════════════════════════════════════════════════════════
async def call_model(system: str, user: str, max_tokens: int = 900, temp: float = 0.2) -> str:
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "temperature": temp,
        "max_tokens": max_tokens,
        "top_p": 0.95,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(LLAMA_URL, json=payload)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


# ═══════════════════════════════════════════════════════════════
# EVALUATE ONE CASE
# ═══════════════════════════════════════════════════════════════
async def evaluate_case(case: dict) -> dict:
    case_id = case["id"]
    agent_type = case["agent_type"]
    language = case.get("language", "hi")
    rules = case.get("evaluation_rules", {})

    if agent_type == "expert":
        system, max_tokens = build_expert_system(
            case_file=case["case_file"],
            rag_context=case.get("rag_context", ""),
            history_text=case.get("history_text", ""),
            language=language,
            is_followup=case.get("is_followup", False),
        )
        user_msg = case["user_message"]
        temp = 0.2
    else:
        system = build_intake_system(
            language=language,
            metadata=case.get("metadata", {}),
            turn=case.get("turn", 1),
            max_turns=case.get("max_turns", 10),
        )
        user_msg = case["user_message"]
        max_tokens = 400
        temp = 0.3

    print(f"\n  [{case_id}] {agent_type}/{language} → calling model...")
    try:
        response = await call_model(system, user_msg, max_tokens, temp)
    except Exception as e:
        print(f"    → ERROR: {e}")
        return {
            "test_id": case_id, "agent_type": agent_type, "language": language,
            "passed": False, "scores": {"final_score": 0.0, "error": str(e)},
            "actual_response": "",
        }

    if agent_type == "expert":
        scorer = ExpertScorer(language)
        scores = scorer.score(response, rules)
        final = round(
            scores["structure_score"]          * 0.40 +
            scores["section_accuracy"]         * 0.25 +
            scores["hindi_purity"]             * 0.15 +
            scores["word_count_ok"]            * 0.05 +
            scores["no_hallucination"]         * 0.05 +
            scores["no_bare_lawyer_advice"]    * 0.05 +
            scores["helpline_present"]         * 0.05,
            3,
        )
        passed = final >= 0.65 and scores["structure_score"] >= 0.6
    else:
        scorer = IntakeScorer()
        scores = scorer.score(response, rules)
        final = round(
            scores["structure_score"]               * 0.50 +
            scores.get("extraction_accuracy", 1.0)  * 0.30 +
            float(scores.get("ready_correct", True)) * 0.20,
            3,
        )
        passed = final >= 0.65 and scores["valid_json"]

    status = "✓ PASS" if passed else "✗ FAIL"
    print(
        f"    → {status} final={final:.2f} "
        f"struct={scores.get('structure_score', 0):.2f} "
        f"sect={scores.get('section_accuracy', 0):.2f} "
        f"purity={scores.get('hindi_purity', 1):.2f} "
        f"blocks={'✓' if scores.get('all_5_blocks') else '✗'} "
        f"timeline={'✓' if scores.get('timeline_all_3') else '✗'}"
    )

    # Print missing sections for debugging
    missing = scores.get("sections_missing", [])
    if missing:
        print(f"      missing sections: {missing}")

    return {
        "test_id": case_id,
        "agent_type": agent_type,
        "language": language,
        "passed": passed,
        "scores": {**scores, "final_score": final},
        "actual_response": response[:800],
    }


# ═══════════════════════════════════════════════════════════════
# RUN ALL
# ═══════════════════════════════════════════════════════════════
async def run_evaluation(cases: list, concurrency: int = 1) -> dict:
    print(f"\nRunning {len(cases)} test cases (concurrency={concurrency})...")
    print("=" * 60)

    sem = asyncio.Semaphore(concurrency)

    async def bounded(c):
        async with sem:
            return await evaluate_case(c)

    results = await asyncio.gather(*[bounded(c) for c in cases])

    total = len(results)
    passed = sum(1 for r in results if r["passed"])

    # Separate expert vs intake stats
    expert_r = [r for r in results if r["agent_type"] == "expert"]
    intake_r = [r for r in results if r["agent_type"] == "intake"]

    score_keys = ["final_score", "structure_score", "section_accuracy", "hindi_purity"]
    avg_scores = {}
    for k in score_keys:
        vals = [r["scores"].get(k, 0) for r in results
                if isinstance(r["scores"].get(k), (int, float))]
        avg_scores[k] = round(sum(vals) / len(vals), 3) if vals else 0

    summary = {
        "timestamp": datetime.now().isoformat(),
        "model": MODEL_NAME,
        "total_cases": total,
        "passed": passed,
        "pass_rate": round(passed / total, 2),
        "expert_pass_rate": round(sum(1 for r in expert_r if r["passed"]) / len(expert_r), 2) if expert_r else 0,
        "intake_pass_rate": round(sum(1 for r in intake_r if r["passed"]) / len(intake_r), 2) if intake_r else 0,
        "avg_scores": avg_scores,
        "detailed_results": results,
    }

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    for f in [RESULTS_DIR / f"eval_v3_{ts}.json", RESULTS_DIR / "eval_v3_latest.json"]:
        with open(f, "w", encoding="utf-8") as fp:
            json.dump(summary, fp, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed}/{total} passed ({passed/total:.0%})")
    print(f"  Expert:  {sum(1 for r in expert_r if r['passed'])}/{len(expert_r)}")
    print(f"  Intake:  {sum(1 for r in intake_r if r['passed'])}/{len(intake_r)}")
    print()
    for k, v in avg_scores.items():
        bar = "█" * int(v * 20)
        print(f"  {k:<25} {v:.3f} {bar}")
    print(f"\nSaved: {RESULTS_DIR / f'eval_v3_{ts}.json'}")
    return summary


# ═══════════════════════════════════════════════════════════════
# COMPARE TWO RUNS
# ═══════════════════════════════════════════════════════════════
def compare_runs(base_file: str, ft_file: str):
    with open(base_file) as f:
        base = json.load(f)
    with open(ft_file) as f:
        ft = json.load(f)

    metrics = [
        "pass_rate", "expert_pass_rate", "intake_pass_rate",
        "final_score", "structure_score", "section_accuracy", "hindi_purity",
    ]

    print("\n" + "=" * 72)
    print(f"{'METRIC':<28} {'BASE':>12} {'FINE-TUNED':>12} {'DELTA':>10} {'WIN?':>6}")
    print("=" * 72)

    for m in metrics:
        b = base.get("avg_scores", {}).get(m) or base.get(m, 0)
        f = ft.get("avg_scores", {}).get(m) or ft.get(m, 0)
        delta = f - b
        sign = "+" if delta >= 0 else ""
        win = "✓" if delta > 0.01 else ("✗" if delta < -0.01 else "~")
        print(f"  {m:<26} {b:>12.3f} {f:>12.3f} {sign}{delta:>9.3f} {win:>6}")

    print("=" * 72)

    # Save comparison
    comparison = {
        "timestamp": datetime.now().isoformat(),
        "base_model": base.get("model", "base"),
        "finetuned_model": ft.get("model", "finetuned"),
        "metrics": {
            m: {
                "base": base.get("avg_scores", {}).get(m) or base.get(m, 0),
                "finetuned": ft.get("avg_scores", {}).get(m) or ft.get(m, 0),
                "delta": round(
                    (ft.get("avg_scores", {}).get(m) or ft.get(m, 0)) -
                    (base.get("avg_scores", {}).get(m) or base.get(m, 0)), 3
                )
            }
            for m in metrics
        }
    }
    comp_file = RESULTS_DIR / "comparison_latest.json"
    with open(comp_file, "w") as f:
        json.dump(comparison, f, indent=2)
    print(f"\nComparison saved: {comp_file}")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
async def main():
    parser = argparse.ArgumentParser(description="StriSakhi Benchmark Evaluator v3.1")
    parser.add_argument("--dataset", type=str,
                        default="benchmark_v2/test_cases_v2.json",
                        help="Path to test cases JSON")
    parser.add_argument("--compare", nargs=2,
                        metavar=("BASE", "FINETUNED"),
                        help="Compare two result files")
    parser.add_argument("--concurrency", type=int, default=1,
                        help="Parallel cases (keep 1 for llama.cpp)")
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