"""
Feedback Module - Query Logging & User Feedback
==================================================
Stores every query, response, and user feedback (thumbs up/down)
in a local SQLite database for evaluation and improvement.

Usage:
    from feedback import FeedbackStore

    fb = FeedbackStore()
    query_id = fb.log_query(user_id=123, query="drought in Patna",
                            translated_query="drought in Patna",
                            language="hi", response="...", sources=["Bihar—Patna"])
    fb.record_feedback(query_id, "positive")

    # Get stats
    stats = fb.get_stats()
    print(stats)
"""

import sqlite3
import os
import json
from datetime import datetime


DB_PATH = os.path.join(os.path.dirname(__file__), "feedback.db")


class FeedbackStore:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_tables()

    def _create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id INTEGER,
                username TEXT,
                language TEXT DEFAULT 'en',
                original_query TEXT,
                english_query TEXT,
                response TEXT,
                sources TEXT,
                weather_used INTEGER DEFAULT 0,
                prices_used INTEGER DEFAULT 0,
                latency_sec REAL,
                feedback TEXT DEFAULT NULL,
                feedback_time TEXT DEFAULT NULL
            )
        """)
        self.conn.commit()

    def log_query(self, user_id, query, translated_query=None, language="en",
                  response="", sources=None, weather_used=False,
                  prices_used=False, latency=None, username=None):
        """Log a query and response. Returns the query ID for feedback linking."""
        cursor = self.conn.execute("""
            INSERT INTO queries (timestamp, user_id, username, language,
                                 original_query, english_query, response,
                                 sources, weather_used, prices_used, latency_sec)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            user_id,
            username,
            language,
            query,
            translated_query or query,
            response,
            json.dumps(sources or []),
            1 if weather_used else 0,
            1 if prices_used else 0,
            latency,
        ))
        self.conn.commit()
        return cursor.lastrowid

    def record_feedback(self, query_id, feedback):
        """Record feedback ('positive' or 'negative') for a query."""
        self.conn.execute("""
            UPDATE queries SET feedback = ?, feedback_time = ?
            WHERE id = ?
        """, (feedback, datetime.now().isoformat(), query_id))
        self.conn.commit()

    def get_stats(self):
        """Get summary statistics."""
        cursor = self.conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN feedback = 'positive' THEN 1 ELSE 0 END) as positive,
                SUM(CASE WHEN feedback = 'negative' THEN 1 ELSE 0 END) as negative,
                SUM(CASE WHEN feedback IS NULL THEN 1 ELSE 0 END) as no_feedback,
                AVG(latency_sec) as avg_latency,
                COUNT(DISTINCT user_id) as unique_users
            FROM queries
        """)
        row = cursor.fetchone()
        total, pos, neg, no_fb, avg_lat, users = row

        # Language breakdown
        lang_cursor = self.conn.execute("""
            SELECT language, COUNT(*) FROM queries GROUP BY language ORDER BY COUNT(*) DESC
        """)
        languages = {r[0]: r[1] for r in lang_cursor.fetchall()}

        return {
            "total_queries": total,
            "positive": pos or 0,
            "negative": neg or 0,
            "no_feedback": no_fb or 0,
            "satisfaction_rate": f"{(pos / (pos + neg) * 100):.0f}%" if (pos or 0) + (neg or 0) > 0 else "N/A",
            "avg_latency_sec": round(avg_lat, 1) if avg_lat else 0,
            "unique_users": users or 0,
            "languages": languages,
        }

    def get_negative_feedback(self, limit=20):
        """Get recent negative feedback for review."""
        cursor = self.conn.execute("""
            SELECT id, timestamp, language, original_query, english_query, response
            FROM queries WHERE feedback = 'negative'
            ORDER BY timestamp DESC LIMIT ?
        """, (limit,))
        return [
            {
                "id": r[0], "time": r[1], "lang": r[2],
                "query": r[3], "english": r[4], "response": r[5][:200],
            }
            for r in cursor.fetchall()
        ]


# ── CLI for checking stats ─────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    fb = FeedbackStore()
    stats = fb.get_stats()

    print(f"\n{'='*50}")
    print(f"  Krishi Advisory Bot — Feedback Dashboard")
    print(f"{'='*50}")
    print(f"  Total queries:     {stats['total_queries']}")
    print(f"  Unique users:      {stats['unique_users']}")
    print(f"  Positive:          {stats['positive']}")
    print(f"  Negative:          {stats['negative']}")
    print(f"  No feedback:       {stats['no_feedback']}")
    print(f"  Satisfaction rate:  {stats['satisfaction_rate']}")
    print(f"  Avg latency:       {stats['avg_latency_sec']}s")
    print(f"\n  Languages used:")
    for lang, count in stats["languages"].items():
        print(f"    {lang}: {count} queries")

    if "--negative" in sys.argv:
        print(f"\n  Recent negative feedback:")
        for item in fb.get_negative_feedback():
            print(f"    [{item['lang']}] {item['query'][:60]}")
            print(f"    Response: {item['response'][:100]}...")
            print()

    print(f"{'='*50}\n")