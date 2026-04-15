import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "workmoat.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        email         TEXT UNIQUE NOT NULL,
        name          TEXT,
        password_hash TEXT,
        created_at    TEXT DEFAULT (datetime('now')),
        last_login    TEXT
    );
    -- Add password_hash column if it doesn't exist (migration)
    

    CREATE TABLE IF NOT EXISTS otp_codes (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        email       TEXT NOT NULL,
        code        TEXT NOT NULL,
        expires_at  TEXT NOT NULL,
        used        INTEGER DEFAULT 0,
        created_at  TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS reports (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id         INTEGER REFERENCES users(id),
        session_id      TEXT UNIQUE NOT NULL,
        name            TEXT,
        role            TEXT,
        overall_score   INTEGER,
        ai_susceptibility_score INTEGER,
        ai_augment_score INTEGER,
        automation_risk_level TEXT,
        automation_risk_timeline TEXT,
        full_result     TEXT,
        pdf_b64         TEXT,
        paid            INTEGER DEFAULT 0,
        created_at      TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS roadmap_progress (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER REFERENCES users(id),
        report_id   INTEGER REFERENCES reports(id),
        skill       TEXT NOT NULL,
        priority    TEXT,
        completed   INTEGER DEFAULT 0,
        notes       TEXT,
        updated_at  TEXT DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_reports_user ON reports(user_id);
    CREATE INDEX IF NOT EXISTS idx_otp_email ON otp_codes(email);
    CREATE INDEX IF NOT EXISTS idx_roadmap_user ON roadmap_progress(user_id);
    """)

    conn.commit()
    conn.close()


def save_report(session_id, result, paid=False, pdf_b64="", user_id=None):
    conn = get_db()
    try:
        import json
        conn.execute("""
            INSERT INTO reports
                (session_id, user_id, name, role, overall_score,
                 ai_susceptibility_score, ai_augment_score,
                 automation_risk_level, automation_risk_timeline,
                 full_result, pdf_b64, paid)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(session_id) DO UPDATE SET
                user_id=excluded.user_id,
                paid=excluded.paid,
                pdf_b64=excluded.pdf_b64,
                full_result=excluded.full_result
        """, (
            session_id,
            user_id,
            result.get("name", ""),
            result.get("role", ""),
            result.get("overall_score", 0),
            result.get("ai_susceptibility_score", 0),
            result.get("ai_augment_score", 0),
            (result.get("automation_risk") or {}).get("level", ""),
            (result.get("automation_risk") or {}).get("timeline", ""),
            json.dumps(result),
            pdf_b64,
            1 if paid else 0
        ))
        conn.commit()
        return conn.execute("SELECT id FROM reports WHERE session_id=?", (session_id,)).fetchone()["id"]
    finally:
        conn.close()


def get_user_reports(user_id):
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT id, session_id, name, role, overall_score,
                   ai_susceptibility_score, ai_augment_score,
                   automation_risk_level, automation_risk_timeline,
                   paid, created_at
            FROM reports WHERE user_id=? ORDER BY created_at DESC
        """, (user_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_report_pdf(session_id, user_id):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT pdf_b64, name FROM reports WHERE session_id=? AND user_id=? AND paid=1",
            (session_id, user_id)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def save_roadmap_progress(user_id, report_id, skills):
    conn = get_db()
    try:
        for skill in skills:
            existing = conn.execute(
                "SELECT id FROM roadmap_progress WHERE user_id=? AND report_id=? AND skill=?",
                (user_id, report_id, skill["skill"])
            ).fetchone()
            if not existing:
                conn.execute("""
                    INSERT INTO roadmap_progress (user_id, report_id, skill, priority, completed)
                    VALUES (?,?,?,?,0)
                """, (user_id, report_id, skill["skill"], skill.get("priority", "medium")))
        conn.commit()
    finally:
        conn.close()


def toggle_roadmap_item(user_id, item_id, completed):
    conn = get_db()
    try:
        conn.execute("""
            UPDATE roadmap_progress SET completed=?, updated_at=datetime('now')
            WHERE id=? AND user_id=?
        """, (1 if completed else 0, item_id, user_id))
        conn.commit()
    finally:
        conn.close()


def get_roadmap_progress(user_id, report_id):
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT id, skill, priority, completed, notes, updated_at
            FROM roadmap_progress WHERE user_id=? AND report_id=?
            ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END
        """, (user_id, report_id)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def migrate_db():
    """Add new columns to existing tables safely."""
    conn = get_db()
    try:
        # Add password_hash if missing
        cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        if 'password_hash' not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
            conn.commit()
            print("Migrated: added password_hash column")
    except Exception as e:
        print(f"Migration note: {e}")
    finally:
        conn.close()
