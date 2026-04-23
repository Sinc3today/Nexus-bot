import sqlite3
import json
from datetime import datetime

DB_PATH = "nexus.db"

def init_db():
    """Initialize the SQLite database and create tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            platform TEXT,
            creator TEXT,
            transcript TEXT,
            summary TEXT,
            key_points TEXT,        -- JSON array of key points
            fact_checks TEXT,       -- JSON array of fact check results
            conclusion TEXT,
            sentiment TEXT,
            sentiment_confidence TEXT,
            emotional_framing TEXT,
            bias_detected TEXT,
            misinformation_score REAL,
            claims_verified INTEGER,
            claims_partly_true INTEGER,
            claims_opinion INTEGER,
            claims_total INTEGER,
            categories TEXT,        -- JSON array of category names
            primary_category TEXT,
            topics TEXT,            -- JSON array of topic tags
            processed_at TEXT,
            status TEXT DEFAULT 'completed'
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Database initialized successfully.")


def save_video(data: dict) -> int:
    """Save a processed video record to the database. Returns the new row ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO videos (
            url, platform, creator, transcript, summary,
            key_points, fact_checks, conclusion,
            sentiment, sentiment_confidence, emotional_framing, bias_detected,
            misinformation_score, claims_verified, claims_partly_true,
            claims_opinion, claims_total,
            categories, primary_category, topics, processed_at, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("url"),
        data.get("platform"),
        data.get("creator"),
        data.get("transcript"),
        data.get("summary"),
        json.dumps(data.get("key_points", [])),
        json.dumps(data.get("fact_checks", [])),
        data.get("conclusion"),
        data.get("sentiment"),
        data.get("sentiment_confidence"),
        data.get("emotional_framing"),
        data.get("bias_detected"),
        data.get("misinformation_score", 0.0),
        data.get("claims_verified", 0),
        data.get("claims_partly_true", 0),
        data.get("claims_opinion", 0),
        data.get("claims_total", 0),
        json.dumps(data.get("categories", [])),
        data.get("primary_category"),
        json.dumps(data.get("topics", [])),
        datetime.now().isoformat(),
        data.get("status", "completed")
    ))

    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id


def get_videos_by_category(category: str, limit: int = 20) -> list:
    """Retrieve videos by category for use in other projects."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM videos
        WHERE categories LIKE ?
        ORDER BY processed_at DESC
        LIMIT ?
    """, (f'%{category}%', limit))

    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()

    # Parse JSON fields back to lists
    for row in rows:
        row["key_points"] = json.loads(row["key_points"] or "[]")
        row["fact_checks"] = json.loads(row["fact_checks"] or "[]")
        row["categories"] = json.loads(row["categories"] or "[]")
        row["topics"] = json.loads(row["topics"] or "[]")

    return rows


def get_recent_videos(limit: int = 10) -> list:
    """Get the most recently processed videos."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM videos
        ORDER BY processed_at DESC
        LIMIT ?
    """, (limit,))

    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()

    for row in rows:
        row["key_points"] = json.loads(row["key_points"] or "[]")
        row["fact_checks"] = json.loads(row["fact_checks"] or "[]")
        row["categories"] = json.loads(row["categories"] or "[]")
        row["topics"] = json.loads(row["topics"] or "[]")

    return rows


def search_videos(query: str, limit: int = 20) -> list:
    """Search videos by keyword across transcript, summary, and topics."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM videos
        WHERE transcript LIKE ?
           OR summary LIKE ?
           OR topics LIKE ?
           OR key_points LIKE ?
        ORDER BY processed_at DESC
        LIMIT ?
    """, (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%', limit))

    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()

    for row in rows:
        row["key_points"] = json.loads(row["key_points"] or "[]")
        row["fact_checks"] = json.loads(row["fact_checks"] or "[]")
        row["categories"] = json.loads(row["categories"] or "[]")
        row["topics"] = json.loads(row["topics"] or "[]")

    return rows


def get_stats() -> dict:
    """Get overall database statistics."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM videos")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT primary_category, COUNT(*) FROM videos GROUP BY primary_category")
    by_category = dict(cursor.fetchall())

    cursor.execute("SELECT AVG(misinformation_score) FROM videos")
    avg_misinfo = cursor.fetchone()[0] or 0.0

    conn.close()

    return {
        "total_videos": total,
        "by_category": by_category,
        "avg_misinformation_score": round(avg_misinfo, 3)
    }


# Run this file directly to initialize the database
if __name__ == "__main__":
    init_db()
    print("Database ready at nexus.db")
    print("Stats:", get_stats())


def url_exists(url: str) -> dict | None:
    """Check if a URL has already been processed. Returns the record or None."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, url, primary_category, sentiment,
               misinformation_score, processed_at
        FROM videos WHERE url = ?
        LIMIT 1
    """, (url,))

    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None