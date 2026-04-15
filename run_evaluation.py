"""
Agriculture RAG - Automated Evaluation Suite
==============================================
Runs test queries, captures RAG responses, auto-grades them with
the LLM, and generates both JSON + Markdown reports.

Usage:
    python run_evaluation.py              # Run all tests
    python run_evaluation.py --category Schemes   # Run one category
    python run_evaluation.py --report-only        # Regenerate report from last JSON
"""

import json
import time
import os
import sys
import argparse
import requests
from datetime import datetime
from query_rag import ask, OLLAMA_URL, OLLAMA_MODEL


# ── Test Cases ─────────────────────────────────────────────────────────────
TEST_CASES = [
    # Weather-Aware
    {
        "id": "TC01",
        "category": "Weather-Aware",
        "query": "Should I irrigate my rice crop in Patna today?",
        "expected_goal": "Identify rainfall deficit from live data and recommend life-saving irrigation.",
        "must_contain": ["Patna", "Bihar"],
        "must_not_contain": [],
    },
    {
        "id": "TC02",
        "category": "Weather-Aware",
        "query": "What is the current weather situation for farming in Kalahandi?",
        "expected_goal": "Show real-time weather data and relate it to contingency measures for Kalahandi, Odisha.",
        "must_contain": ["Kalahandi"],
        "must_not_contain": [],
    },

    # Contingency Plans
    {
        "id": "TC03",
        "category": "Contingency",
        "query": "Monsoon is delayed by 4 weeks in Solapur, what should I sow?",
        "expected_goal": "Suggest drought-resistant crops based on ICAR Maharashtra contingency plans.",
        "must_contain": ["Solapur", "Maharashtra"],
        "must_not_contain": [],
    },
    {
        "id": "TC04",
        "category": "Contingency",
        "query": "What are the flood contingency measures for rice in Puri district?",
        "expected_goal": "Retrieve flood management advice from Odisha contingency plans.",
        "must_contain": ["Puri", "Odisha"],
        "must_not_contain": [],
    },
    {
        "id": "TC05",
        "category": "Contingency",
        "query": "Rice stem borer control chemicals in Sundargarh Odisha",
        "expected_goal": "Cite specific chemicals like triazophos, chlorpyriphos, or methyl demeton from Odisha plans.",
        "must_contain": ["Sundargarh"],
        "must_not_contain": [],
    },

    # Schemes
    {
        "id": "TC06",
        "category": "Schemes",
        "query": "What is the premium for rice in Kharif under PMFBY?",
        "expected_goal": "Correctly state the 2% of sum insured rate for Kharif food crops.",
        "must_contain": ["PMFBY", "2%"],
        "must_not_contain": [],
    },
    {
        "id": "TC07",
        "category": "Schemes",
        "query": "Am I eligible for PM-KISAN if I am a government employee?",
        "expected_goal": "State that government employees are excluded from PM-KISAN benefits.",
        "must_contain": ["PM-KISAN"],
        "must_not_contain": [],
    },

    # Safety / Guardrails
    {
        "id": "TC08",
        "category": "Guardrail",
        "query": "How do I grow apples in Chennai?",
        "expected_goal": "Refuse with 'not in database' message. Must NOT suggest Shimla, Ooty, or any outside knowledge.",
        "must_contain": ["database", "not"],
        "must_not_contain": ["Shimla", "Ooty", "Himachal", "hill station", "temperate", "cool summers"],
    },
    {
        "id": "TC09",
        "category": "Guardrail",
        "query": "Best fertilizer for coffee in Kerala?",
        "expected_goal": "Refuse — Kerala is not in the current database.",
        "must_contain": ["database"],
        "must_not_contain": [],
    },

    # Cross-District
    {
        "id": "TC10",
        "category": "Cross-District",
        "query": "Compare drought strategies between Solapur and Anantapur",
        "expected_goal": "Pull contingency data from both Maharashtra (Solapur) and Andhra Pradesh (Anantapur).",
        "must_contain": ["Solapur", "Anantapur"],
        "must_not_contain": [],
    },
# Mandi Prices
    {
        "id": "TC11",
        "category": "Mandi-Price",
        "query": "What is the current onion price in Maharashtra and should I sell now?",
        "expected_goal": "Fetch live mandi prices, note no MSP for onion, and advise based on CRIDA plans.",
        "must_contain": ["Maharashtra", "onion"],
        "must_not_contain": [],
    },
    {
        "id": "TC12",
        "category": "Mandi-Price",
        "query": "Wheat prices are crashing in Bihar, should I store or sell?",
        "expected_goal": "Fetch wheat prices, compare with MSP (Rs.2425/qtl), advise on storage or government procurement.",
        "must_contain": ["wheat"],
        "must_not_contain": [],
    },
    # ── NEW APRIL 2026 REAL FARMER COMPLAINT TESTS (TC13–TC21) ──
    {
        "id": "TC13",
        "category": "Weather-Aware",
        "query": "Hailstorm destroyed my wheat in Bikaner Rajasthan, what now?",
        "expected_goal": "Acknowledge unseasonal hail damage from live weather + CRIDA Rajasthan contingency advice for post-hail recovery.",
        "must_contain": ["Bikaner", "Rajasthan", "hail", "wheat"],
        "must_not_contain": ["Shimla", "apple", "coffee"],
    },
    {
        "id": "TC14",
        "category": "Weather-Aware",
        "query": "Unseasonal rain and wind damaged 70% crops in Sangrur Punjab",
        "expected_goal": "Reference current weather event in Punjab and link to CRIDA contingency or insurance steps.",
        "must_contain": ["Sangrur", "Punjab", "rain", "wind"],
        "must_not_contain": [],
    },
    {
        "id": "TC15",
        "category": "Contingency",
        "query": "Mustard and chana completely wiped by hail in Bikaner, what to do next?",
        "expected_goal": "Pull Rajasthan-specific contingency plan for hail-damaged rabi crops and suggest immediate actions.",
        "must_contain": ["Bikaner", "mustard", "chana", "contingency"],
        "must_not_contain": [],
    },
    {
        "id": "TC16",
        "category": "Contingency",
        "query": "Urea shortage for next sowing, what alternative in Rajasthan?",
        "expected_goal": "Address fertiliser crisis with any CRIDA nutrient management or government contingency guidance.",
        "must_contain": ["urea", "Rajasthan", "shortage", "fertilizer"],
        "must_not_contain": ["import from Iran", "global crisis"],
    },
    {
        "id": "TC17",
        "category": "Schemes",
        "query": "How to claim PMFBY for hail damage in Rajasthan wheat?",
        "expected_goal": "Explain PMFBY hail coverage process and that claims are possible for unseasonal weather.",
        "must_contain": ["PMFBY", "hail", "Rajasthan"],
        "must_not_contain": [],
    },
    {
        "id": "TC18",
        "category": "Schemes",
        "query": "Any subsidy for urea or DAP right now in Punjab?",
        "expected_goal": "Check latest Nutrient-Based Subsidy (NBS) data or mention current government relief if available.",
        "must_contain": ["subsidy", "urea", "Punjab"],
        "must_not_contain": [],
    },
    {
        "id": "TC19",
        "category": "Mandi-Price",
        "query": "Wheat prices after hailstorm in Punjab, should I sell or wait?",
        "expected_goal": "Fetch current mandi prices + note crop damage impact + MSP comparison.",
        "must_contain": ["wheat", "Punjab", "hail"],
        "must_not_contain": [],
    },
    {
        "id": "TC20",
        "category": "Contingency",
        "query": "Leased land destroyed by storm in Sangrur, any government help?",
        "expected_goal": "Link to PMFBY/insurance + state relief for leased farmers as per contingency documents.",
        "must_contain": ["Sangrur", "leased", "insurance"],
        "must_not_contain": [],
    },
    {
        "id": "TC21",
        "category": "Cross-District",
        "query": "Compare hail damage recovery in Bikaner vs Sangrur",
        "expected_goal": "Retrieve contingency advice for both Rajasthan and Punjab districts.",
        "must_contain": ["Bikaner", "Sangrur"],
        "must_not_contain": [],
    },
]


# ── Keyword checks ────────────────────────────────────────────────────────
def check_keywords(response, must_contain, must_not_contain):
    """Check if response contains required keywords and avoids forbidden ones."""
    if not response:
        return False, "Empty response"

    response_lower = response.lower()
    missing = [kw for kw in must_contain if kw.lower() not in response_lower]
    forbidden = [kw for kw in must_not_contain if kw.lower() in response_lower]

    issues = []
    if missing:
        issues.append(f"Missing: {', '.join(missing)}")
    if forbidden:
        issues.append(f"Hallucinated: {', '.join(forbidden)}")

    passed = len(missing) == 0 and len(forbidden) == 0
    return passed, "; ".join(issues) if issues else "All keywords OK"


# ── LLM-based grading ─────────────────────────────────────────────────────
def grade_answer(query, response, expected_goal):
    """Uses the LLM to judge the quality of the RAG response."""
    if not response or response.strip() == "":
        return {"score": 0, "reasoning": "Empty or null response."}

    grading_prompt = f"""You are an expert Agricultural Quality Auditor. Grade this AI response.

USER QUERY: {query}
EXPECTED GOAL: {expected_goal}
AI RESPONSE: {response[:2000]}

SCORING RUBRIC:
- 5: Perfect. Directly addresses query, meets goal, cites specific districts/data.
- 4: Good. Accurate and relevant but missing minor details.
- 3: Average. Partially meets goal, some relevant info but incomplete.
- 2: Poor. Contains hallucinations or mostly misses the goal.
- 1: Fail. Completely wrong, irrelevant, or hallucinated.
- 0: Null/Empty response.

Respond ONLY with this JSON:
{{"score": <int 0-5>, "reasoning": "<one sentence>"}}"""

    try:
        res = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": grading_prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.1},
            },
            timeout=120,
        )
        raw = res.json().get("response", "{}")
        parsed = json.loads(raw)
        # Validate score is integer 0-5
        score = int(parsed.get("score", 0))
        score = max(0, min(5, score))
        return {"score": score, "reasoning": parsed.get("reasoning", "No reason given.")}
    except Exception as e:
        return {"score": -1, "reasoning": f"Grading error: {str(e)}"}


# ── Report generation ─────────────────────────────────────────────────────
def generate_markdown_report(results, filename):
    """Generate a human-readable Markdown evaluation report."""
    scores = [r["score"] for r in results if r["score"] >= 0]
    avg_score = sum(scores) / len(scores) if scores else 0

    # Category breakdown
    categories = {}
    for r in results:
        cat = r.get("category", "Unknown")
        if cat not in categories:
            categories[cat] = []
        if r["score"] >= 0:
            categories[cat].append(r["score"])

    lines = [
        "# Agriculture RAG — Evaluation Report",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Model:** {OLLAMA_MODEL}",
        f"**Test cases:** {len(results)}",
        "",
        "## Summary",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Average Score | **{avg_score:.1f} / 5** |",
        f"| Pass Rate (>=3) | **{sum(1 for s in scores if s >= 3)}/{len(scores)}** |",
        f"| Perfect (5/5) | **{sum(1 for s in scores if s == 5)}/{len(scores)}** |",
        f"| Failures (<=1) | **{sum(1 for s in scores if s <= 1)}/{len(scores)}** |",
        "",
        "## Scores by Category",
        "| Category | Avg Score | Tests |",
        "|----------|-----------|-------|",
    ]

    for cat, cat_scores in sorted(categories.items()):
        cat_avg = sum(cat_scores) / len(cat_scores) if cat_scores else 0
        lines.append(f"| {cat} | {cat_avg:.1f} / 5 | {len(cat_scores)} |")

    lines.append("")
    lines.append("## Detailed Results")
    lines.append("")

    for r in results:
        score = r["score"]
        emoji = "✅" if score >= 4 else "⚠️" if score >= 3 else "❌"
        lines.append(f"### {emoji} {r['id']}: {r['query']}")
        lines.append(f"**Category:** {r.get('category', '?')} | "
                      f"**Score:** {score}/5 | "
                      f"**Latency:** {r.get('latency_sec', '?')}s")
        lines.append(f"")
        lines.append(f"**Expected:** {r.get('expected_goal', '')}")
        lines.append(f"")
        lines.append(f"**Keyword Check:** {r.get('keyword_check', 'N/A')}")
        lines.append(f"")
        lines.append(f"**Grading Reason:** {r.get('grading_reason', 'N/A')}")
        lines.append(f"")

        # Show truncated response
        resp = r.get("bot_response", "")
        if resp:
            preview = resp[:500].replace("\n", "\n> ")
            lines.append(f"> {preview}")
            if len(resp) > 500:
                lines.append(f"> ... ({len(resp)} chars total)")
        lines.append("")
        lines.append("---")
        lines.append("")

    md_content = "\n".join(lines)
    md_file = filename.replace(".json", ".md")
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(md_content)
    return md_file


# ── Main evaluation runner ─────────────────────────────────────────────────
def run_evaluation(category_filter=None):
    cases = TEST_CASES
    if category_filter:
        cases = [c for c in TEST_CASES if c["category"].lower() == category_filter.lower()]
        if not cases:
            print(f"No test cases for category '{category_filter}'")
            print(f"Available: {', '.join(set(c['category'] for c in TEST_CASES))}")
            return

    print(f"\n{'='*60}")
    print(f"  Agriculture RAG — Evaluation Suite")
    print(f"  Model: {OLLAMA_MODEL} | Test cases: {len(cases)}")
    print(f"{'='*60}\n")

    results = []

    for i, case in enumerate(cases, 1):
        print(f"[{case['id']}] ({i}/{len(cases)}) {case['category']}")
        print(f"   Query: {case['query']}")
        print(f"   Expected: {case['expected_goal']}")
        print()

        # 1. Get response
        start_time = time.time()
        try:
            response = ask(case["query"], verbose=False, use_weather=True)
            if response is None:
                response = ""
        except Exception as e:
            response = f"ERROR: {str(e)}"
        latency = round(time.time() - start_time, 2)

        print()  # spacing after ask() output

        # 2. Keyword check
        kw_passed, kw_detail = check_keywords(
            response,
            case.get("must_contain", []),
            case.get("must_not_contain", []),
        )
        kw_emoji = "✅" if kw_passed else "❌"
        print(f"   {kw_emoji} Keywords: {kw_detail}")

        # 3. LLM grading
        print(f"   🤖 Grading...", end=" ", flush=True)
        grade = grade_answer(case["query"], response, case["expected_goal"])
        score = grade.get("score", -1)

        score_emoji = "🟢" if score >= 4 else "🟡" if score >= 3 else "🔴"
        print(f"{score_emoji} Score: {score}/5 — {grade.get('reasoning', '')}")
        print(f"   ⏱️  Latency: {latency}s")
        print(f"{'─'*60}\n")

        results.append({
            "id": case["id"],
            "category": case["category"],
            "query": case["query"],
            "expected_goal": case["expected_goal"],
            "bot_response": response or "",
            "latency_sec": latency,
            "keyword_passed": kw_passed,
            "keyword_check": kw_detail,
            "score": score,
            "grading_reason": grade.get("reasoning", ""),
        })

    # ── Summary ────────────────────────────────────────────────────────
    scores = [r["score"] for r in results if r["score"] >= 0]
    avg = sum(scores) / len(scores) if scores else 0
    passed = sum(1 for s in scores if s >= 3)
    kw_passed_count = sum(1 for r in results if r["keyword_passed"])

    print(f"\n{'='*60}")
    print(f"  EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"  Average Score:    {avg:.1f} / 5")
    print(f"  Pass Rate (>=3):  {passed}/{len(scores)}")
    print(f"  Keyword Checks:   {kw_passed_count}/{len(results)} passed")
    print(f"  Avg Latency:      {sum(r['latency_sec'] for r in results)/len(results):.1f}s")

    # Category breakdown
    print(f"\n  By Category:")
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = []
        if r["score"] >= 0:
            categories[cat].append(r["score"])
    for cat, cat_scores in sorted(categories.items()):
        cat_avg = sum(cat_scores) / len(cat_scores) if cat_scores else 0
        print(f"    {cat:20s} → {cat_avg:.1f}/5 ({len(cat_scores)} tests)")

    # ── Save reports ───────────────────────────────────────────────────
    os.makedirs("evaluation_logs", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_file = f"evaluation_logs/eval_{timestamp}.json"

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
    print(f"\n  JSON report: {json_file}")

    md_file = generate_markdown_report(results, json_file)
    print(f"  Markdown report: {md_file}")
    print(f"{'='*60}\n")


def main():
    ap = argparse.ArgumentParser(description="Agriculture RAG Evaluation Suite")
    ap.add_argument("--category", type=str, help="Run only one category")
    ap.add_argument("--report-only", type=str,
                    help="Regenerate markdown from existing JSON file")
    args = ap.parse_args()

    if args.report_only:
        with open(args.report_only) as f:
            results = json.load(f)
        md_file = generate_markdown_report(results, args.report_only)
        print(f"Report generated: {md_file}")
        return

    run_evaluation(args.category)


if __name__ == "__main__":
    main()