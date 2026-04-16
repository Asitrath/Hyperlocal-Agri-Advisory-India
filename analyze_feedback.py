"""
Feedback Analysis Script
==========================
Reads the feedback.db SQLite database and generates insights:
- Queries with negative feedback
- Language-wise satisfaction breakdown
- Common failure patterns (empty responses, "not covered" refusals)
- Slow queries
- Most active users
- Weekly trend

Usage:
    python analyze_feedback.py                 # Full report to console
    python analyze_feedback.py --export        # Save to feedback_analysis.md
    python analyze_feedback.py --negative      # Only show negative feedback
    python analyze_feedback.py --last 7        # Only last 7 days
"""

import sqlite3
import json
import argparse
import os
from datetime import datetime, timedelta
from collections import Counter

DB_PATH = os.path.join(os.path.dirname(__file__), "feedback.db")


def get_connection():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: No feedback database found at {DB_PATH}")
        print("Run the bot first to collect feedback data.")
        exit(1)
    return sqlite3.connect(DB_PATH)


def analyze(since_days=None, negative_only=False):
    """Run full analysis and return structured report."""
    conn = get_connection()
    cursor = conn.cursor()

    # Build time filter
    time_filter = ""
    params = []
    if since_days:
        cutoff = (datetime.now() - timedelta(days=since_days)).isoformat()
        time_filter = "WHERE timestamp > ?"
        params.append(cutoff)

    # ── Overall stats ─────────────────────────────────────────────────────
    cursor.execute(f"""
        SELECT COUNT(*), COUNT(DISTINCT user_id),
               SUM(CASE WHEN feedback='positive' THEN 1 ELSE 0 END),
               SUM(CASE WHEN feedback='negative' THEN 1 ELSE 0 END),
               AVG(latency_sec), MAX(latency_sec)
        FROM queries {time_filter}
    """, params)
    total, users, pos, neg, avg_lat, max_lat = cursor.fetchone()

    report = {
        "period": f"Last {since_days} days" if since_days else "All time",
        "total_queries": total or 0,
        "unique_users": users or 0,
        "positive": pos or 0,
        "negative": neg or 0,
        "satisfaction_rate": f"{(pos / (pos + neg) * 100):.0f}%" if (pos or 0) + (neg or 0) > 0 else "N/A",
        "avg_latency": round(avg_lat or 0, 1),
        "max_latency": round(max_lat or 0, 1),
    }

    # ── Language breakdown ───────────────────────────────────────────────
    cursor.execute(f"""
        SELECT language, COUNT(*),
               SUM(CASE WHEN feedback='positive' THEN 1 ELSE 0 END),
               SUM(CASE WHEN feedback='negative' THEN 1 ELSE 0 END)
        FROM queries {time_filter}
        GROUP BY language
        ORDER BY COUNT(*) DESC
    """, params)
    report["languages"] = []
    for lang, count, p, n in cursor.fetchall():
        report["languages"].append({
            "language": lang,
            "total": count,
            "positive": p or 0,
            "negative": n or 0,
            "satisfaction": f"{(p / (p + n) * 100):.0f}%" if (p or 0) + (n or 0) > 0 else "N/A",
        })

    # ── Negative feedback queries ────────────────────────────────────────
    cursor.execute(f"""
        SELECT timestamp, language, original_query, english_query, response, sources
        FROM queries
        WHERE feedback='negative'
        {"AND " + time_filter.replace("WHERE ", "") if time_filter else ""}
        ORDER BY timestamp DESC
        LIMIT 30
    """, params)
    report["negative_feedback"] = []
    for ts, lang, orig, eng, resp, sources in cursor.fetchall():
        sources_list = json.loads(sources) if sources else []
        report["negative_feedback"].append({
            "time": ts[:16],
            "language": lang,
            "query": orig[:100],
            "english": eng[:100] if eng != orig else None,
            "response_preview": (resp or "")[:200],
            "sources_count": len(sources_list),
        })

    # ── Failure patterns ──────────────────────────────────────────────────
    # Queries where response contains "not covered" or "no relevant"
    cursor.execute(f"""
        SELECT COUNT(*) FROM queries
        WHERE (response LIKE '%not cover%'
               OR response LIKE '%do not have relevant%'
               OR response LIKE '%No relevant documents%')
        {"AND " + time_filter.replace("WHERE ", "") if time_filter else ""}
    """, params)
    refusals = cursor.fetchone()[0] or 0
    report["refusals"] = refusals
    report["refusal_rate"] = f"{(refusals / total * 100):.0f}%" if total else "N/A"

    # ── Feature usage ────────────────────────────────────────────────────
    cursor.execute(f"""
        SELECT
            SUM(weather_used) as weather,
            SUM(prices_used) as prices
        FROM queries {time_filter}
    """, params)
    w, p = cursor.fetchone()
    report["weather_usage"] = w or 0
    report["price_usage"] = p or 0

    # ── Slow queries ──────────────────────────────────────────────────────
    cursor.execute(f"""
        SELECT timestamp, original_query, latency_sec
        FROM queries
        WHERE latency_sec > 30
        {"AND " + time_filter.replace("WHERE ", "") if time_filter else ""}
        ORDER BY latency_sec DESC
        LIMIT 10
    """, params)
    report["slow_queries"] = [
        {"time": ts[:16], "query": q[:80], "latency": round(lat, 1)}
        for ts, q, lat in cursor.fetchall()
    ]

    # ── Most common query patterns (simple keyword analysis) ─────────────
    cursor.execute(f"""
        SELECT english_query FROM queries {time_filter}
    """, params)
    all_words = []
    stopwords = {"the", "a", "an", "is", "are", "what", "how", "can", "do", "i",
                 "my", "in", "on", "for", "to", "of", "and", "or", "me", "should",
                 "should", "have", "with", "this", "that", "you", "from"}
    for (q,) in cursor.fetchall():
        if q:
            for word in q.lower().split():
                word = "".join(c for c in word if c.isalnum())
                if len(word) > 3 and word not in stopwords:
                    all_words.append(word)
    top_keywords = Counter(all_words).most_common(15)
    report["top_keywords"] = top_keywords

    # ── Active users ──────────────────────────────────────────────────────
    cursor.execute(f"""
        SELECT username, COUNT(*) as cnt,
               SUM(CASE WHEN feedback='positive' THEN 1 ELSE 0 END) as pos,
               SUM(CASE WHEN feedback='negative' THEN 1 ELSE 0 END) as neg
        FROM queries {time_filter}
        GROUP BY user_id, username
        ORDER BY cnt DESC
        LIMIT 10
    """, params)
    report["active_users"] = [
        {"name": name or "Unknown", "queries": cnt, "positive": p or 0, "negative": n or 0}
        for name, cnt, p, n in cursor.fetchall()
    ]

    conn.close()
    return report


def print_report(report):
    """Print formatted report to console."""
    print(f"\n{'='*60}")
    print(f"  Krishi Bot Feedback Analysis — {report['period']}")
    print(f"{'='*60}")

    print(f"\n📊 Overall")
    print(f"  Total queries:       {report['total_queries']}")
    print(f"  Unique users:        {report['unique_users']}")
    print(f"  👍 Positive:         {report['positive']}")
    print(f"  👎 Negative:         {report['negative']}")
    print(f"  Satisfaction:        {report['satisfaction_rate']}")
    print(f"  Avg latency:         {report['avg_latency']}s")
    print(f"  Max latency:         {report['max_latency']}s")

    print(f"\n⚠️  Failure Patterns")
    print(f"  Refusals:            {report['refusals']} ({report['refusal_rate']})")

    print(f"\n🔧 Feature Usage")
    print(f"  Weather fetched:     {report['weather_usage']} queries")
    print(f"  Prices fetched:      {report['price_usage']} queries")

    print(f"\n🌐 Languages")
    for lang in report["languages"]:
        print(f"  {lang['language']:5s} → {lang['total']:3d} queries, "
              f"satisfaction {lang['satisfaction']}")

    if report["top_keywords"]:
        print(f"\n🔑 Top Keywords")
        for word, count in report["top_keywords"][:10]:
            print(f"  {word:20s} {count}")

    if report["active_users"]:
        print(f"\n👥 Most Active Users")
        for user in report["active_users"][:5]:
            print(f"  {user['name']:20s} {user['queries']} queries "
                  f"(👍{user['positive']} 👎{user['negative']})")

    if report["slow_queries"]:
        print(f"\n🐌 Slow Queries (>30s)")
        for q in report["slow_queries"][:5]:
            print(f"  [{q['latency']}s] {q['query']}")

    if report["negative_feedback"]:
        print(f"\n👎 Recent Negative Feedback")
        print(f"  (These need investigation — check for hallucinations or poor advice)")
        for nf in report["negative_feedback"][:10]:
            print(f"\n  [{nf['time']}] [{nf['language']}]")
            print(f"    Query: {nf['query']}")
            if nf["english"]:
                print(f"    EN:    {nf['english']}")
            print(f"    Reply: {nf['response_preview'][:150]}...")
            print(f"    Sources: {nf['sources_count']} documents")

    # ── Recommendations ──────────────────────────────────────────────────
    print(f"\n💡 Recommendations")
    recs = []

    if total := report["total_queries"]:
        if report["refusals"] / total > 0.3:
            recs.append("High refusal rate (>30%) — consider expanding knowledge base "
                       "or loosening the SCORE_THRESHOLD")

        if report["negative"] > report["positive"]:
            recs.append("More negative than positive feedback — review recent negative "
                       "queries and improve system prompt")

        neg_queries = report["negative_feedback"]
        if neg_queries:
            langs = Counter(nf["language"] for nf in neg_queries)
            if langs.most_common(1)[0][1] > 3:
                top_lang = langs.most_common(1)[0][0]
                recs.append(f"Multiple negative feedbacks in {top_lang} — "
                           f"translation quality may need review")

        if report["avg_latency"] > 20:
            recs.append(f"Average latency is {report['avg_latency']}s — consider using "
                       f"a smaller Ollama model for faster responses")

    if not recs:
        recs.append("System is performing well. Keep monitoring.")

    for i, rec in enumerate(recs, 1):
        print(f"  {i}. {rec}")

    print(f"\n{'='*60}\n")


def export_markdown(report, filepath="feedback_analysis.md"):
    """Export report as markdown."""
    lines = [
        f"# Krishi Bot Feedback Analysis",
        f"**Period:** {report['period']}",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Summary",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total queries | {report['total_queries']} |",
        f"| Unique users | {report['unique_users']} |",
        f"| Positive feedback | {report['positive']} |",
        f"| Negative feedback | {report['negative']} |",
        f"| Satisfaction rate | {report['satisfaction_rate']} |",
        f"| Avg latency | {report['avg_latency']}s |",
        f"| Refusal rate | {report['refusal_rate']} |",
        "",
        "## Language Breakdown",
        "| Language | Queries | Satisfaction |",
        "|----------|---------|--------------|",
    ]
    for lang in report["languages"]:
        lines.append(f"| {lang['language']} | {lang['total']} | {lang['satisfaction']} |")

    if report["top_keywords"]:
        lines.extend(["", "## Top Query Keywords", ""])
        lines.append("| Keyword | Count |")
        lines.append("|---------|-------|")
        for word, count in report["top_keywords"]:
            lines.append(f"| {word} | {count} |")

    if report["negative_feedback"]:
        lines.extend(["", "## Negative Feedback (Needs Investigation)", ""])
        for nf in report["negative_feedback"][:20]:
            lines.append(f"### [{nf['time']}] [{nf['language']}] {nf['query']}")
            if nf["english"]:
                lines.append(f"**Translated:** {nf['english']}")
            lines.append(f"**Response:** {nf['response_preview']}...")
            lines.append(f"**Sources:** {nf['sources_count']}")
            lines.append("")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Report exported to: {filepath}")


def main():
    ap = argparse.ArgumentParser(description="Feedback analysis for Krishi Bot")
    ap.add_argument("--export", action="store_true", help="Export to markdown")
    ap.add_argument("--last", type=int, help="Only analyze last N days")
    ap.add_argument("--negative", action="store_true", help="Only negative feedback")
    args = ap.parse_args()

    report = analyze(since_days=args.last, negative_only=args.negative)
    print_report(report)

    if args.export:
        export_markdown(report)


if __name__ == "__main__":
    main()