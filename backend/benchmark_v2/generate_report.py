#!/usr/bin/env python3
"""
StriSakhi — Benchmark Report Generator
Generates a beautiful HTML report from evaluate_v3 JSON results.
Perfect for showing hackathon judges Before vs After.

Usage:
    python benchmark_v2/generate_report.py benchmark_v2/results/eval_v3_latest.json
    python benchmark_v2/generate_report.py benchmark_v2/results/eval_v3_BASE.json benchmark_v2/results/eval_v3_FT.json
"""
import json
import sys
from pathlib import Path
from datetime import datetime


def generate_single_report(data: dict, output_path: Path):
    """Generate HTML report for a single run."""

    total = data["total_cases"]
    passed = data["passed"]
    pass_rate = data["pass_rate"]
    scores = data["avg_scores"]
    results = data["detailed_results"]

    # Build per-category table
    cat_rows = ""
    by_cat = {}
    for r in results:
        cat = r.get("category", "unknown")
        if cat not in by_cat:
            by_cat[cat] = {"total": 0, "passed": 0, "scores": []}
        by_cat[cat]["total"] += 1
        if r["passed"]:
            by_cat[cat]["passed"] += 1
        by_cat[cat]["scores"].append(r["scores"].get("final_score", 0))

    for cat, d in sorted(by_cat.items()):
        rate = d["passed"] / d["total"]
        avg = sum(d["scores"]) / len(d["scores"]) if d["scores"] else 0
        color = "#27ae60" if rate >= 0.65 else "#e74c3c"
        cat_rows += f"""
        <tr>
            <td>{cat}</td>
            <td>{d["passed"]}/{d["total"]}</td>
            <td style="color:{color};font-weight:bold">{rate:.0%}</td>
            <td>{avg:.2f}</td>
        </tr>"""

    # Build detailed case rows
    case_rows = ""
    for r in results:
        status = "✅ PASS" if r["passed"] else "❌ FAIL"
        color = "#27ae60" if r["passed"] else "#e74c3c"
        scores = r["scores"]
        case_rows += f"""
        <tr>
            <td>{r["test_id"]}</td>
            <td>{r["agent_type"]}</td>
            <td>{r.get("category", "-")}</td>
            <td>{r["language"]}</td>
            <td style="color:{color}">{status}</td>
            <td>{scores.get("final_score", 0):.2f}</td>
            <td>{scores.get("structure_score", 0):.2f}</td>
            <td>{scores.get("section_accuracy", 0):.2f}</td>
            <td>{scores.get("hindi_purity", 0):.2f}</td>
        </tr>"""

    # Score bars
    def bar(val):
        pct = int(val * 100)
        color = "#27ae60" if val >= 0.65 else "#f39c12" if val >= 0.4 else "#e74c3c"
        return f"""
        <div style="background:#ecf0f1;border-radius:4px;height:24px;width:100%;position:relative">
            <div style="background:{color};width:{pct}%;height:100%;border-radius:4px;transition:width 0.5s"></div>
            <span style="position:absolute;left:8px;top:2px;font-size:12px;font-weight:bold">{val:.2f}</span>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>StriSakhi Benchmark Report</title>
    <style>
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; max-width: 1100px; margin: 0 auto; padding: 30px; background: #f8f9fa; color: #2c3e50; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 30px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 2.2em; }}
        .header p {{ margin: 10px 0 0; opacity: 0.9; }}
        .score-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .score-card {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
        .score-card h3 {{ margin: 0 0 12px; font-size: 0.9em; text-transform: uppercase; color: #7f8c8d; letter-spacing: 1px; }}
        .big-number {{ font-size: 2.5em; font-weight: bold; color: #2c3e50; }}
        .pass-rate {{ font-size: 3em; color: {"#27ae60" if pass_rate >= 0.65 else "#e74c3c"}; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 30px; }}
        th {{ background: #34495e; color: white; padding: 12px; text-align: left; font-size: 0.85em; text-transform: uppercase; letter-spacing: 0.5px; }}
        td {{ padding: 12px; border-bottom: 1px solid #ecf0f1; font-size: 0.9em; }}
        tr:hover {{ background: #f8f9fa; }}
        .section {{ background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 30px; }}
        .section h2 {{ margin-top: 0; color: #34495e; border-bottom: 2px solid #ecf0f1; padding-bottom: 10px; }}
        .timestamp {{ text-align: center; color: #7f8c8d; font-size: 0.9em; margin-top: 20px; }}
        .response-box {{ background: #f8f9fa; border-left: 3px solid #667eea; padding: 12px; margin: 8px 0; font-family: monospace; font-size: 0.85em; max-height: 120px; overflow-y: auto; white-space: pre-wrap; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔴 StriSakhi Benchmark Report</h1>
        <p>Kanoon Sakhi AI Legal Assistant — Format Compliance Evaluation</p>
        <p style="font-size:0.85em;margin-top:15px">Model: {data.get("model", "gemma4-e2b-base")} | Cases: {total} | Timestamp: {data.get("timestamp", "-")}</p>
    </div>

    <div class="score-grid">
        <div class="score-card">
            <h3>Pass Rate</h3>
            <div class="big-number pass-rate">{pass_rate:.0%}</div>
            <p style="margin:5px 0 0;color:#7f8c8d">{passed}/{total} cases passed</p>
        </div>
        <div class="score-card">
            <h3>Final Score</h3>
            <div class="big-number">{scores.get("final_score", 0):.2f}</div>
            {bar(scores.get("final_score", 0))}
        </div>
        <div class="score-card">
            <h3>Structure Score</h3>
            <div class="big-number">{scores.get("structure_score", 0):.2f}</div>
            {bar(scores.get("structure_score", 0))}
        </div>
        <div class="score-card">
            <h3>Section Accuracy</h3>
            <div class="big-number">{scores.get("section_accuracy", 0):.2f}</div>
            {bar(scores.get("section_accuracy", 0))}
        </div>
        <div class="score-card">
            <h3>Hindi Purity</h3>
            <div class="big-number">{scores.get("hindi_purity", 0):.2f}</div>
            {bar(scores.get("hindi_purity", 0))}
        </div>
    </div>

    <div class="section">
        <h2>📊 Per-Category Breakdown</h2>
        <table>
            <tr><th>Category</th><th>Passed/Total</th><th>Pass Rate</th><th>Avg Score</th></tr>
            {cat_rows}
        </table>
    </div>

    <div class="section">
        <h2>🔍 Detailed Results</h2>
        <table>
            <tr>
                <th>ID</th><th>Agent</th><th>Category</th><th>Lang</th>
                <th>Status</th><th>Final</th><th>Struct</th><th>Sect</th><th>Purity</th>
            </tr>
            {case_rows}
        </table>
    </div>

    <div class="section">
        <h2>📝 Sample Responses (Failed Cases)</h2>
        <p style="color:#7f8c8d;font-size:0.9em">Showing first 3 failed responses to diagnose format issues:</p>
        """

    fail_count = 0
    for r in results:
        if not r["passed"] and fail_count < 3:
            fail_count += 1
            html += f"""
        <div style="margin-bottom:20px">
            <strong>{r["test_id"]} ({r["language"]})</strong>
            <div class="response-box">{r["actual_response"][:500]}</div>
        </div>"""

    html += """
    </div>

    <p class="timestamp">Report generated by StriSakhi Benchmark Suite v3.0</p>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Report saved: {output_path}")


def generate_comparison_report(base: dict, ft: dict, output_path: Path):
    """Generate Before vs After comparison report."""

    metrics = [
        ("Pass Rate", "pass_rate"),
        ("Final Score", "final_score"),
        ("Structure Score", "structure_score"),
        ("Section Accuracy", "section_accuracy"),
        ("Hindi Purity", "hindi_purity"),
    ]

    rows = ""
    for label, key in metrics:
        b = base["avg_scores"].get(key, 0)
        f = ft["avg_scores"].get(key, 0)
        delta = f - b
        sign = "+" if delta >= 0 else ""
        color = "#27ae60" if delta > 0 else "#e74c3c" if delta < 0 else "#7f8c8d"
        rows += f"""
        <tr>
            <td style="font-weight:bold">{label}</td>
            <td style="text-align:center;font-size:1.2em">{b:.3f}</td>
            <td style="text-align:center;font-size:1.2em">{f:.3f}</td>
            <td style="text-align:center;color:{color};font-weight:bold;font-size:1.3em">{sign}{delta:.3f}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>StriSakhi — Before vs After Fine-Tuning</title>
    <style>
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; max-width: 900px; margin: 0 auto; padding: 30px; background: #f8f9fa; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px; border-radius: 12px; text-align: center; margin-bottom: 40px; }}
        .header h1 {{ margin: 0; font-size: 2.5em; }}
        .header p {{ margin: 15px 0 0; font-size: 1.1em; opacity: 0.9; }}
        .delta-box {{ background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); margin-bottom: 30px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ background: #2c3e50; color: white; padding: 15px; text-align: center; font-size: 0.9em; text-transform: uppercase; }}
        td {{ padding: 18px; border-bottom: 2px solid #ecf0f1; text-align: center; }}
        tr:hover {{ background: #f8f9fa; }}
        .winner {{ background: #d5f5e3; }}
        .timestamp {{ text-align: center; color: #7f8c8d; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔴 StriSakhi Fine-Tuning Results</h1>
        <p>Base Model vs Fine-Tuned Model — Format Compliance Comparison</p>
        <p style="font-size:0.85em;margin-top:10px">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
    </div>

    <div class="delta-box">
        <table>
            <tr>
                <th style="text-align:left">Metric</th>
                <th>Base Model</th>
                <th>Fine-Tuned</th>
                <th>Delta</th>
            </tr>
            {rows}
        </table>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
        <div class="delta-box">
            <h3 style="margin-top:0;color:#e74c3c">Base Model</h3>
            <p><strong>Pass Rate:</strong> {base["pass_rate"]:.0%}</p>
            <p><strong>Cases:</strong> {base["passed"]}/{base["total_cases"]}</p>
            <p style="color:#7f8c8d;font-size:0.85em">{base.get("model", "gemma4-e2b-base")}</p>
        </div>
        <div class="delta-box">
            <h3 style="margin-top:0;color:#27ae60">Fine-Tuned</h3>
            <p><strong>Pass Rate:</strong> {ft["pass_rate"]:.0%}</p>
            <p><strong>Cases:</strong> {ft["passed"]}/{ft["total_cases"]}</p>
            <p style="color:#7f8c8d;font-size:0.85em">{ft.get("model", "gemma4-e2b-ft")}</p>
        </div>
    </div>

    <p class="timestamp">StriSakhi Benchmark Suite v3.0 | For Kaggle Hackathon Submission</p>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Comparison report saved: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) == 2:
        # Single report
        with open(sys.argv[1]) as f:
            data = json.load(f)
        out = Path(sys.argv[1]).with_suffix(".html")
        generate_single_report(data, out)
    elif len(sys.argv) == 3:
        # Comparison
        with open(sys.argv[1]) as f: base = json.load(f)
        with open(sys.argv[2]) as f: ft = json.load(f)
        out = Path(sys.argv[2]).parent / "comparison_report.html"
        generate_comparison_report(base, ft, out)
    else:
        print("Usage:")
        print("  python generate_report.py results/eval_v3_latest.json")
        print("  python generate_report.py results/eval_v3_BASE.json results/eval_v3_FT.json")
